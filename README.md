# Gemini vs ChatGPT: Google Play reviews

Compares what Android users said about Google Gemini and ChatGPT in the Google Play Store, using the 10,000 newest US English reviews of each app.

Python collects the reviews, PostgreSQL stores them, and R (dplyr) cleans and summarizes them.

## Results

| | ChatGPT | Gemini |
| --- | ---: | ---: |
| Reviews | 10,000 | 10,000 |
| Average rating | 4.51 | 4.02 |
| 1–2 star share | 8.6% | 21.0% |
| 1-star reviews | 679 | 1,864 |
| Reviews with a developer reply | 1 | 409 |
| Time span covered | 37.9 hours | 61.1 hours |

- Gemini's share of negative reviews is about 2.5 times ChatGPT's.
- Gemini's team replies to reviews and ChatGPT's almost never does.
- ChatGPT reached 10,000 reviews in less time, so it gets more reviews per hour.

## Pipeline

| File | What it does |
| --- | --- |
| `collect_reviews.py` | Pulls the newest 10,000 reviews per app with `google-play-scraper`, deduplicates on `review_id`, and writes `app_reviews.csv`. |
| `collect_reviews_big.py` | Collects 90 days of reviews instead. Saves its place in `collect_state.json`, so an interrupted run resumes without losing or duplicating rows. Retries with backoff and restarts an app if Google drops the continuation token. |
| `load_reviews.sql` | Creates the `reviews` table with a primary key and a rating check, loads the CSV through a staging table, and skips rows already loaded. |
| `analyze_reviews.R` | Fixes column types, adds review length and a positive/neutral/negative label, summarizes by app and by day, and lists the most-upvoted negative reviews per app. |

## Run it

```bash
pip install google-play-scraper==1.2.7
python3 collect_reviews.py          # writes app_reviews.csv

createdb play_reviews
psql -d play_reviews -f load_reviews.sql   # optional: load into PostgreSQL

Rscript analyze_reviews.R
```

## Data

- Collected September 28–30, 2026, US store, English only.
- Usernames and profile images are not collected. Fields: app, review ID, timestamp, rating, text, thumbs-up count, app version, whether the developer replied.
- The CSV is not in this repository. Run the collector to rebuild it.

## Limits

- Newest reviews are not a random sample of users. A bad release or an outage can tilt a two-day window.
- The two apps cover different time spans because each sample stops at 10,000 reviews.
- The positive/neutral/negative label comes from the star rating, not the review text.
