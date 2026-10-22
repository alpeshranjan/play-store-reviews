"""Collect recent US English Google Play reviews for Gemini and ChatGPT.

Usage:
    pip3 install google-play-scraper==1.2.7
    python3 collect_reviews.py

Output: app_reviews.csv in the same folder as this script.
Usernames and profile images are not saved.
"""
import csv
import os
import sys
import time

try:
    from google_play_scraper import Sort, reviews
except ImportError:
    sys.exit("Missing package. Run: pip3 install google-play-scraper")

APPS = {
    "Gemini": "com.google.android.apps.bard",
    "ChatGPT": "com.openai.chatgpt",
}


BATCH = 200
MAX_PER_APP = 10_000
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_reviews.csv")
COLUMNS = ["app", "review_id", "review_date", "rating", "review_text",
           "thumbs_up", "app_version", "developer_replied"]


def fetch(app_name, package):
    rows, seen, token = [], set(), None
    while len(rows) < MAX_PER_APP:
        for attempt in range(3):
            try:
                batch, token = reviews(
                    package, lang="en", country="us", sort=Sort.NEWEST,
                    count=min(BATCH, MAX_PER_APP - len(rows)),
                    continuation_token=token,
                )
                break
            except Exception as e:
                print(f"  {app_name}: error ({e}), retrying...")
                time.sleep(3 * (attempt + 1))
        else:
            print(f"  {app_name}: giving up after repeated errors")
            break
        if not batch:
            break
        for r in batch:
            if r["reviewId"] in seen:
                continue
            seen.add(r["reviewId"])
            text = (r.get("content") or "").replace("\r", " ").replace("\n", " ").strip()
            rows.append({
                "app": app_name,
                "review_id": r["reviewId"],
                "review_date": r["at"].strftime("%Y-%m-%d %H:%M:%S") if r.get("at") else "",
                "rating": r.get("score"),
                "review_text": text,
                "thumbs_up": r.get("thumbsUpCount", 0),
                "app_version": r.get("reviewCreatedVersion") or r.get("appVersion") or "",
                "developer_replied": bool(r.get("replyContent")),
            })
        print(f"  {app_name}: {len(rows)} reviews")
        if token is None or getattr(token, "token", None) is None:
            break
        time.sleep(0.5)
    return rows[:MAX_PER_APP]


def main():
    all_rows = []
    for name, pkg in APPS.items():
        print(f"Collecting {name} ({pkg})...")
        all_rows.extend(fetch(name, pkg))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(all_rows)
    print(f"\nSaved {len(all_rows)} reviews to {OUT}")
    for name in APPS:
        print(f"  {name}: {sum(r['app'] == name for r in all_rows)}")


if __name__ == "__main__":
    main()
