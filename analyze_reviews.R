# Clean and summarize Google Play reviews for Gemini and ChatGPT.
# Input: app_reviews.csv from collect_reviews.py, in the working directory.

library(dplyr)

# Empty cells become NA. app_version stays text so "1.10" is not read as 1.1.
reviews <- read.csv("app_reviews.csv",
                    encoding = "UTF-8",
                    na.strings = c("", "NA"),
                    colClasses = c(app_version = "character"),
                    stringsAsFactors = FALSE)

str(reviews)
colSums(is.na(reviews))
stopifnot(!any(duplicated(reviews$review_id)))

# Timestamps were written in US Eastern time by the collector.
reviews_clean <- reviews %>%
  select(app, review_date, rating, review_text, thumbs_up,
         app_version, developer_replied) %>%
  mutate(
    review_date       = as.POSIXct(review_date, format = "%Y-%m-%d %H:%M:%S",
                                   tz = "America/New_York"),
    review_day        = as.Date(review_date),
    developer_replied = toupper(developer_replied) == "TRUE",
    review_length     = nchar(review_text),
    sentiment         = case_when(
      rating >= 4 ~ "positive",
      rating == 3 ~ "neutral",
      TRUE        ~ "negative"
    )
  )

# One row per app.
app_summary <- reviews_clean %>%
  group_by(app) %>%
  summarize(
    total_reviews = n(),
    avg_rating    = round(mean(rating, na.rm = TRUE), 2),
    pct_negative  = round(mean(rating <= 2, na.rm = TRUE) * 100, 1),
    one_star      = sum(rating == 1, na.rm = TRUE),
    dev_replies   = sum(developer_replied, na.rm = TRUE),
    hours_covered = round(as.numeric(difftime(max(review_date), min(review_date),
                                              units = "hours")), 1),
    avg_length    = round(mean(review_length, na.rm = TRUE), 1)
  )
print(app_summary)

# Reviews and average rating per app per day.
daily_summary <- reviews_clean %>%
  group_by(app, review_day) %>%
  summarize(reviews    = n(),
            avg_rating = round(mean(rating, na.rm = TRUE), 2),
            .groups    = "drop")
print(daily_summary)

# The most-upvoted negative reviews for each app.
top_complaints <- reviews_clean %>%
  filter(sentiment == "negative") %>%
  group_by(app) %>%
  slice_max(thumbs_up, n = 10, with_ties = FALSE) %>%
  select(app, rating, thumbs_up, review_text)
print(top_complaints, n = 20)
