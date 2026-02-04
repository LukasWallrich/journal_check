# Psychology Journal Pilot/Feasibility Study Guidelines Analysis

Automated analysis of author guidelines from top psychology journals to determine whether they mention pilot studies, feasibility studies, or related concepts.

## Key Finding

**Of the top 20 psychology journals by SJR, we could assess journal-specific author guidelines for 15. Of these:**
- **0/15 mention pilot studies**
- **0/15 mention feasibility studies**
- **4/15 mention registered reports** (Psychological Bulletin, Journal of Applied Psychology, Clinical Psychology Review, Leadership Quarterly)

*5 journals could not be fully assessed: 3 Annual Reviews journals (invitation-only, generic author resources), Nature Reviews Psychology (landing page only), and Psychotherapy and Psychosomatics (Cloudflare blocked).*

## Quick Start

```bash
# 1. Install R dependencies
Rscript -e 'pak::pak("ikashnitsky/sjrdata")'

# 2. Install Python dependencies
uv sync

# 3. Set up API keys in .env
cp .env.example .env
# Edit .env with your GOOGLE_API_KEY and BROWSER_USE_API_KEY

# 4. Run the pipeline
Rscript src/01_get_journals.R
uv run python src/02_discover_urls.py
uv run python src/03_scrape_guidelines.py
uv run python src/03b_browser_scrape.py  # For blocked sites
uv run python src/03c_follow_guideline_links.py  # Get linked content
uv run python src/04_analyze_guidelines.py
```

## Project Structure

```
journal_check/
├── data/
│   ├── input/
│   │   └── top_psychology_journals.csv    # From SCImago
│   ├── raw/guidelines_html/               # Backup HTML files
│   ├── processed/guidelines_text/         # Extracted text
│   └── output/
│       ├── journals_with_urls.csv         # URLs from OpenAlex
│       ├── scraping_log.json              # Scraping status
│       └── pilot_feasibility_results.csv  # Final analysis
├── src/
│   ├── 01_get_journals.R                  # Extract top 20 from SCImago
│   ├── 02_discover_urls.py                # Find URLs via OpenAlex API
│   ├── 03_scrape_guidelines.py            # HTTP-based scraping
│   ├── 03b_browser_scrape.py              # Browser automation fallback
│   ├── 03c_follow_guideline_links.py      # Follow links to detailed guidelines
│   ├── 03d_fix_elsevier.py                # Fix specific broken URLs
│   ├── 04_analyze_guidelines.py           # LLM analysis with Gemini
│   └── models.py                          # Pydantic schemas
├── .env                                   # API keys (not committed)
└── pyproject.toml
```

## Pipeline Overview

### Phase 1: Journal Identification (R)
- Uses `sjrdata` package to get SCImago Journal Rankings
- Filters for psychology journals (areas containing "Psychology")
- Exports top 20 by SJR score

### Phase 2: URL Discovery (Python)
- Queries OpenAlex API by ISSN to get journal homepage URLs
- Handles multiple ISSNs per journal (print/electronic)
- Falls back to CrossRef if OpenAlex fails

### Phase 3: Web Scraping (Python)
**Tiered approach:**
1. **HTTP scraping** (httpx) - Fast, works for ~65% of sites
2. **Browser automation** (browser-use) - For Cloudflare-protected sites
3. **Link following** - Extracts URLs from scraped content pointing to detailed guidelines
4. **Manual fixes** - Some sites need specific URL patterns (e.g., Elsevier)

### Phase 4: LLM Analysis (Python)
- Uses Google Gemini via `google.genai` SDK with Instructor for structured output
- Validates content type (actual guidelines vs landing pages)
- Searches for pilot/feasibility study mentions
- Extracts quotes and validates them against source text

## API Keys Required

| Service | Environment Variable | Purpose |
|---------|---------------------|---------|
| Google AI | `GOOGLE_API_KEY` | Gemini for LLM analysis |
| Browser Use | `BROWSER_USE_API_KEY` | Browser automation for blocked sites |

Get keys from:
- Google AI: https://aistudio.google.com/apikey
- Browser Use: https://browser-use.com

## Results Schema

The output CSV includes:

| Field | Description |
|-------|-------------|
| `is_author_guidelines` | Whether content is actual submission guidelines |
| `content_type` | journal_specific_guidelines, publisher_generic_guidelines, landing_page, error_page |
| `pilot_study_mentioned` | Boolean |
| `pilot_study_stance` | required, encouraged, accepted, discouraged, not_mentioned |
| `feasibility_study_mentioned` | Boolean |
| `registered_reports_mentioned` | Boolean |
| `confidence_score` | 0-1, how confident the LLM is |
| `quote_validation_score` | 0-1, fuzzy match of quotes against source |

## Known Limitations

1. **Annual Reviews journals** - Invitation-only, generic author resource pages
2. **Karger (Psychotherapy and Psychosomatics)** - Strong Cloudflare protection, couldn't scrape
3. **Some guidelines are PDFs** - Not all PDF content is captured
4. **Guidelines change over time** - Results reflect guidelines at time of scraping

## Extending to More Journals

To analyze more journals:

1. Modify `src/01_get_journals.R` to change `head(20)` to desired count
2. Re-run the full pipeline
3. Check `scraping_log.json` for failures
4. Add failing journals to fix scripts as needed

## Dependencies

**R:**
- sjrdata
- dplyr, readr, stringr

**Python:**
- httpx, beautifulsoup4, lxml
- browser-use, playwright
- google-genai, instructor
- pandas, pydantic, rapidfuzz
