"""Collect Google Play reviews (US, English) for Gemini and ChatGPT
going back DAYS days.

Writes big_reviews.csv as it goes and keeps its place in collect_state.json.
If the run stops (closed window, Ctrl+C, network trouble), start it again
and it continues where it left off.
Usernames and profile images are not saved. Dates are stored in UTC.
"""
import csv
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

try:
    from google_play_scraper import Sort
    from google_play_scraper.constants.element import ElementSpecs
    from google_play_scraper.constants.request import Formats
    from google_play_scraper.features.reviews import _fetch_review_items
except ImportError:
    sys.exit("Missing package. Run: python3 -m pip install google-play-scraper==1.2.7")

DAYS = 90
APPS = {
    "Gemini": "com.google.android.apps.bard",
    "ChatGPT": "com.openai.chatgpt",
}
PER_REQUEST = 1000
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "big_reviews.csv")
STATE = os.path.join(HERE, "collect_state.json")
COLUMNS = ["app", "review_id", "review_date", "rating", "review_text",
           "thumbs_up", "app_version", "developer_replied"]
URL = Formats.Reviews.build(lang="en", country="us")
TS = "%Y-%m-%d %H:%M:%S+00"


def fetch_page(name, package, token):
    """One request to the Play Store. Raises after repeated failures."""
    for attempt in range(6):
        try:
            items, new_token = _fetch_review_items(
                URL, package, Sort.NEWEST.value, PER_REQUEST, None, None, token)
            if isinstance(new_token, list):
                new_token = None
            parsed = [{k: spec.extract_content(i)
                       for k, spec in ElementSpecs.Review.items()} for i in items]
            return parsed, new_token
        except Exception as e:
            wait = 15 * (attempt + 1)
            print(f"  {name}: request failed ({type(e).__name__}), retrying in {wait}s")
            time.sleep(wait)
    raise RuntimeError(f"{name}: too many failed requests")


def shift(ts, days):
    """Move a TS-formatted UTC timestamp string by a number of days."""
    dt = datetime.strptime(ts[:19], "%Y-%m-%d %H:%M:%S") + timedelta(days=days)
    return dt.strftime(TS)


def save_state(state):
    tmp = STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, STATE)


def load_or_start():
    if os.path.exists(STATE) and os.path.exists(OUT):
        with open(STATE) as f:
            state = json.load(f)
        if all(a["done"] for a in state["apps"].values()):
            print("The last collection already finished. To collect fresh data,")
            print("delete big_reviews.csv and collect_state.json, then run again.")
            return state, None
        seen = set()
        with open(OUT, encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                seen.add(row["review_id"])
        print(f"Resuming: {len(seen):,} reviews already saved.")
        return state, seen
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS)
    state = {
        "cutoff": cutoff.strftime(TS),
        "apps": {n: {"token": None, "count": 0, "oldest": None, "done": False,
                     "started": False} for n in APPS},
    }
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writeheader()
    save_state(state)
    return state, set()


def to_row(name, r):
    text = (r.get("content") or "")
    text = text.replace("\x00", "").replace("\r", " ").replace("\n", " ").strip()
    return {
        "app": name,
        "review_id": r["reviewId"],
        "review_date": r["at"].astimezone(timezone.utc).strftime(TS),
        "rating": r.get("score"),
        "review_text": text,
        "thumbs_up": r.get("thumbsUpCount") or 0,
        "app_version": r.get("reviewCreatedVersion") or r.get("appVersion") or "",
        "developer_replied": bool(r.get("replyContent")),
    }


def progress(state):
    parts = []
    for n, a in state["apps"].items():
        back = a["oldest"][:10] if a["oldest"] else "-"
        flag = " (done)" if a["done"] else ""
        parts.append(f"{n}: {a['count']:,} back to {back}{flag}")
    return " | ".join(parts)


def main():
    state, seen = load_or_start()
    if seen is None:
        return
    cutoff = state["cutoff"]
    print(f"Collecting reviews newer than {cutoff[:10]} (UTC). This can take 1-2 hours.")
    print("You can close this window any time; run it again to continue.\n")
    empty_retries = {n: 0 for n in APPS}
    restarted = set()
    t0, n0 = time.time(), sum(a["count"] for a in state["apps"].values())

    def restart(name, why):
        # A saved position can expire. Start this app over from the newest
        # review; reviews already saved are skipped, nothing is lost.
        print(f"  {name}: {why}; starting this app again from the newest reviews")
        restarted.add(name)
        state["apps"][name].update(token=None, started=False, done=False)
        empty_retries[name] = 0
        save_state(state)

    with open(OUT, "a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        try:
            while True:
                active = [n for n, a in state["apps"].items() if not a["done"]]
                if not active:
                    break
                # Work on whichever app is furthest from the cutoff so both
                # cover the same dates even if the run is stopped early.
                name = max(active, key=lambda n: state["apps"][n]["oldest"] or "9999")
                a = state["apps"][name]
                if a["started"] and a["token"] is None:
                    a["done"] = True
                    continue

                try:
                    rows, new_token = fetch_page(name, APPS[name], a["token"])
                except RuntimeError:
                    if a["token"] is not None and name not in restarted:
                        restart(name, "could not continue from the saved position")
                        continue
                    raise
                a["started"] = True

                if not rows and new_token is None:
                    # Could be the real end, or Google briefly returning nothing.
                    if empty_retries[name] < 3:
                        empty_retries[name] += 1
                        print(f"  {name}: empty page, checking again in 30s")
                        time.sleep(30)
                        continue
                    far_from_cutoff = (a["oldest"] or "9999") > shift(cutoff, days=2)
                    if a["token"] is not None and far_from_cutoff and name not in restarted:
                        restart(name, "the Play Store stopped returning reviews early")
                        continue
                    a["done"] = True
                    save_state(state)
                    continue
                empty_retries[name] = 0

                keep, reached_cutoff = [], False
                for r in rows:
                    if r.get("at") is None or not r.get("reviewId"):
                        continue
                    row = to_row(name, r)
                    if a["oldest"] is None or row["review_date"] < a["oldest"]:
                        a["oldest"] = row["review_date"]
                    if row["review_date"] < cutoff:
                        reached_cutoff = True
                        continue
                    if row["review_id"] in seen:
                        continue
                    seen.add(row["review_id"])
                    keep.append(row)

                writer.writerows(keep)
                f.flush()
                a["count"] += len(keep)
                a["token"] = new_token
                if reached_cutoff or new_token is None:
                    a["done"] = True
                save_state(state)

                total = sum(x["count"] for x in state["apps"].values())
                rate = (total - n0) / max(time.time() - t0, 1)
                print(f"{progress(state)}  [{rate:,.0f}/s]")
                time.sleep(0.3)
        except KeyboardInterrupt:
            save_state(state)
            print("\nStopped. Run again to continue from here.")

    total = sum(x["count"] for x in state["apps"].values())
    print(f"\nSaved {total:,} reviews to big_reviews.csv")
    print(progress(state))


if __name__ == "__main__":
    main()
