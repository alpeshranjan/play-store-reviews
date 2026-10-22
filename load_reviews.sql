-- Load app_reviews.csv into the reviews table.
-- For the 90-day collection, change the file name below to big_reviews.csv.
-- Safe to run more than once: reviews already in the table are skipped.

SET client_min_messages = warning;

CREATE TABLE IF NOT EXISTS reviews (
    review_id         text PRIMARY KEY,
    app               text        NOT NULL,
    review_date       timestamptz NOT NULL,
    rating            smallint    CHECK (rating BETWEEN 1 AND 5),
    review_text       text,
    thumbs_up         integer,
    app_version       text,
    developer_replied boolean
);

CREATE INDEX IF NOT EXISTS reviews_app_date_idx ON reviews (app, review_date);

CREATE TEMP TABLE staging (LIKE reviews);

\copy staging (app, review_id, review_date, rating, review_text, thumbs_up, app_version, developer_replied) FROM 'app_reviews.csv' WITH (FORMAT csv, HEADER true)

INSERT INTO reviews
SELECT DISTINCT ON (review_id) *
FROM staging
ORDER BY review_id
ON CONFLICT (review_id) DO NOTHING;

ANALYZE reviews;
