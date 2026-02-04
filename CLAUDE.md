# Project: Journal Guidelines Analysis

## Overview
Analyze psychology journal author guidelines for mentions of pilot studies, feasibility studies, and related concepts. Pipeline: R (journal list) → Python (scraping) → Python (LLM analysis).

## Current Results (Top 20 Psychology Journals)
- 15/20 journals had assessable journal-specific guidelines
- 0/15 mention pilot studies
- 0/15 mention feasibility studies
- 4/15 mention registered reports
- 5 could not be assessed (invitation-only journals, landing pages, or blocked sites)

## Key Files
- `src/04_analyze_guidelines.py` - Main analysis script with Gemini
- `src/models.py` - Pydantic schemas for structured LLM output
- `data/output/pilot_feasibility_results.csv` - Final results
- `data/output/scraping_log.json` - Scraping status for each journal

## Lessons Learned

### Web Scraping
1. **Always use tiered scraping**: HTTP first, browser automation as fallback
2. **Publisher sites vary wildly**:
   - Elsevier: Use `elsevier.com/journals/{name}/{issn}/guide-for-authors` pattern
   - Wiley: Often blocks HTTP, needs browser-use
   - Taylor & Francis: Blocks HTTP, use `tandfonline.com/action/authorSubmission?journalCode={code}`
   - SAGE: `journals.sagepub.com/author-instructions/{code}`
   - Karger: Heavy Cloudflare, may need manual intervention
3. **Follow links in scraped content**: Landing pages often link to detailed guidelines
4. **ISSNs can be tricky**: Some journals have multiple (print/electronic), try all variants

### Content Validation
1. **Always validate scraped content is actually guidelines** - many pages are:
   - Landing pages with links but no content
   - Generic publisher-wide guidelines (not journal-specific)
   - Cookie consent dialogs
   - Error pages (404, Cloudflare challenges)
2. **Annual Reviews journals are invitation-only** - no traditional submission guidelines

### LLM Analysis
1. **Use `google.genai`, NOT `google.generativeai`** (deprecated)
2. **Instructor works with genai**: `instructor.from_genai(client, model="gemini-2.0-flash")`
3. **Validate LLM quotes**: Use rapidfuzz to check if quotes actually appear in source
4. **Include content validation in prompt**: Ask LLM to classify content type before analyzing

### Browser Automation (browser-use)
1. **Use ChatBrowserUse with bu-latest model**: `from browser_use.llm.browser_use import ChatBrowserUse`
2. **Cloudflare challenges often fail** - browser-use can't solve all CAPTCHAs
3. **Don't call browser.close()** - browser-use handles cleanup internally
4. **Set headless=True**: `Browser(headless=True)`

## Common Issues & Fixes

### "0 chars extracted" for a journal
- Check if URL redirected to wrong page
- Try the publisher's standard guidelines URL pattern
- Use browser automation if HTTP blocked

### Low confidence scores
- Usually means content is a landing page or generic guidelines
- Check `content_type` field in results
- May need to find journal-specific guidelines URL

### Cloudflare blocking
- First try browser-use with `use_cloud=True`
- If still failing, mark for manual review
- Some sites (Karger) have very aggressive protection

## Scaling Up

To add more journals:
1. Change `head(20)` in `01_get_journals.R`
2. Run full pipeline
3. Check `scraping_log.json` for failures
4. Common failure patterns:
   - HTTP 403 → Add to browser scraping list
   - 0 chars → Wrong URL, find correct guidelines page
   - Error page → Site blocking, try alternative URL

## Environment Variables
```
GOOGLE_API_KEY=...      # For Gemini analysis
BROWSER_USE_API_KEY=... # For browser automation
```

## Quick Commands
```bash
# Re-run just the analysis (after fixing scraped content)
uv run python src/04_analyze_guidelines.py

# Check scraping status
cat data/output/scraping_log.json | jq '.[] | select(.status != "success")'

# View results summary
uv run python -c "import pandas as pd; df=pd.read_csv('data/output/pilot_feasibility_results.csv'); print(df[['journal_name','content_type','pilot_study_mentioned','confidence_score']])"
```
