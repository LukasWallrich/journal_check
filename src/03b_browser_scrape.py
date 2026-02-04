"""Browser-based scraping for journals that need it."""

import asyncio
import json
import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"
HTML_DIR = DATA_DIR / "raw" / "guidelines_html"
TEXT_DIR = DATA_DIR / "processed" / "guidelines_text"
LOG_FILE = DATA_DIR / "output" / "scraping_log.json"

# Journals that need browser scraping (from log)
JOURNALS_NEEDING_BROWSER = [
    # Blocked sites
    {
        "name": "Qualitative Research in Psychology",
        "slug": "qualitative-research-in-psychology",
        "url": "https://www.tandfonline.com/action/authorSubmission?journalCode=uqrp20&page=instructions",
    },
    {
        "name": "Educational Psychologist",
        "slug": "educational-psychologist",
        "url": "https://www.tandfonline.com/action/authorSubmission?journalCode=hedp20&page=instructions",
    },
    {
        "name": "Personality and Social Psychology Review",
        "slug": "personality-and-social-psychology-review",
        "url": "https://journals.sagepub.com/author-instructions/PSR",
    },
    {
        "name": "Personnel Psychology",
        "slug": "personnel-psychology",
        "url": "https://onlinelibrary.wiley.com/page/journal/17446570/homepage/forauthors.html",
    },
    {
        "name": "Psychotherapy and Psychosomatics",
        "slug": "psychotherapy-and-psychosomatics",
        "url": "https://karger.com/pps/pages/guidelines-for-authors",
    },
    {
        "name": "Health Psychology Review",
        "slug": "health-psychology-review",
        "url": "https://www.tandfonline.com/action/authorSubmission?journalCode=rhpr20&page=instructions",
    },
    {
        "name": "Journal of Consumer Psychology",
        "slug": "journal-of-consumer-psychology",
        "url": "https://onlinelibrary.wiley.com/page/journal/15327663/homepage/forauthors.html",
    },
    # APA journals with 0 chars (need JS rendering)
    {
        "name": "Psychological Bulletin",
        "slug": "psychological-bulletin",
        "url": "https://www.apa.org/pubs/journals/bul/?tab=4",
    },
    {
        "name": "Journal of Applied Psychology",
        "slug": "journal-of-applied-psychology",
        "url": "https://www.apa.org/pubs/journals/apl/?tab=4",
    },
    {
        "name": "Psychological Methods",
        "slug": "psychological-methods",
        "url": "https://www.apa.org/pubs/journals/met/?tab=4",
    },
]


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")[:50]


async def scrape_with_browser(url: str, journal_name: str) -> tuple[str, str] | None:
    """Use browser-use to scrape a journal's guidelines."""
    from browser_use import Agent, Browser
    from browser_use.llm.browser_use import ChatBrowserUse

    # Uses BROWSER_USE_API_KEY env var automatically
    llm = ChatBrowserUse(model="bu-latest")

    # Use cloud browser for better stealth against Cloudflare
    browser = Browser(headless=True, use_cloud=True)

    agent = Agent(
        task=f"""Go to this URL: {url}

This should be the author guidelines page for "{journal_name}".

Your task:
1. Wait for the page to fully load
2. If there are any cookie consent dialogs, accept or dismiss them
3. Look for the main content area with submission guidelines/author instructions
4. Extract ALL the text content from the guidelines section

Return the extracted text content. Include everything related to:
- Manuscript preparation
- Submission guidelines
- Article types
- Review process
- Any mentions of pilot studies, feasibility studies, preliminary data, or registered reports

Just return the raw text content, no commentary needed.""",
        llm=llm,
        browser=browser,
    )

    try:
        result = await agent.run(max_steps=15)

        if result and result.final_result():
            return result.final_result(), url
    except Exception as e:
        print(f"  Error: {e}")

    return None


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Browser-based Guidelines Scraper")
    print("=" * 60)

    # Load existing log
    with open(LOG_FILE) as f:
        scrape_log = json.load(f)

    # Create lookup by slug
    log_by_slug = {r["slug"]: r for r in scrape_log}

    for journal in JOURNALS_NEEDING_BROWSER:
        name = journal["name"]
        slug = journal["slug"]
        url = journal["url"]

        print(f"\n[Browser] {name}")
        print(f"  URL: {url}")

        result = await scrape_with_browser(url, name)

        if result:
            text, guidelines_url = result
            print(f"  Success: {len(text)} chars extracted")

            # Save files
            (TEXT_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")

            # Update log entry
            if slug in log_by_slug:
                log_by_slug[slug]["status"] = "success"
                log_by_slug[slug]["method"] = "browser"
                log_by_slug[slug]["text_length"] = len(text)
                log_by_slug[slug]["guidelines_url"] = guidelines_url
                log_by_slug[slug]["error"] = None
        else:
            print("  Failed to extract content")

    # Save updated log
    updated_log = list(log_by_slug.values())
    with open(LOG_FILE, "w") as f:
        json.dump(updated_log, f, indent=2)

    print("\n" + "=" * 60)
    print("Browser scraping complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
