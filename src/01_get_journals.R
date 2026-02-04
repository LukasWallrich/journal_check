# Extract top 20 psychology journals from SCImago data
# Using sjrdata package: https://github.com/ikashnitsky/sjrdata

# Install if needed: pak::pak("ikashnitsky/sjrdata")

library(sjrdata)
library(dplyr)
library(readr)
library(stringr)

# Load the SCImago Journal Rank data
data("sjr_journals")

# The dataset has multiple years per journal
# Filter for Psychology journals, get most recent year (2024), and top 20 by SJR
top_psychology <- sjr_journals |>
  filter(
    str_detect(areas, "Psychology"),
    year == max(year)  # Most recent year in the dataset
  ) |>
  arrange(desc(sjr)) |>
  head(20) |>
  select(
    title,
    issn,
    publisher,
    sjr,
    h_index,
    total_docs_3years,
    country,
    areas,
    year
  ) |>
  mutate(sjr_rank = row_number())

# Display results
cat("Most recent year in dataset:", max(sjr_journals$year), "\n\n")
print(top_psychology, n = 20, width = Inf)

# Export to CSV
output_path <- here::here("data", "input", "top_psychology_journals.csv")
write_csv(top_psychology, output_path)

cat("\nExported", nrow(top_psychology), "journals to:", output_path, "\n")
