"""Direct Playwright scraping without LLM - simpler and faster."""

import asyncio
import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"
TEXT_DIR = DATA_DIR / "processed" / "guidelines_text"
LOG_FILE = DATA_DIR / "output" / "scraping_log.json"

# Direct URLs to author guidelines - manually researched
DIRECT_URLS = {
    # APA journals - use the submission guidelines tab
    "psychological-bulletin": "https://www.apa.org/pubs/journals/bul/?tab=4",
    "journal-of-applied-psychology": "https://www.apa.org/pubs/journals/apl/?tab=4",
    "psychological-methods": "https://www.apa.org/pubs/journals/met/?tab=4",
    # SAGE journals - specific journal pages
    "advances-in-methods-and-practices-in-psychological": "https://journals.sagepub.com/author-instructions/AMP",
    "psychological-science-in-the-public-interest": "https://journals.sagepub.com/author-instructions/PSI",
    "perspectives-on-psychological-science": "https://journals.sagepub.com/author-instructions/PPS",
    "personality-and-social-psychology-review": "https://journals.sagepub.com/author-instructions/PSR",
    # Elsevier - Guide for Authors
    "clinical-psychology-review": "https://www.elsevier.com/journals/clinical-psychology-review/0272-7358/guide-for-authors",
    "leadership-quarterly": "https://www.elsevier.com/journals/the-leadership-quarterly/1048-9843/guide-for-authors",
    # Taylor & Francis
    "qualitative-research-in-psychology": "https://www.tandfonline.com/action/authorSubmission?show=instructions&journalCode=uqrp20",
    "educational-psychologist": "https://www.tandfonline.com/action/authorSubmission?show=instructions&journalCode=hedp20",
    "health-psychology-review": "https://www.tandfonline.com/action/authorSubmission?show=instructions&journalCode=rhpr20",
    # Wiley
    "personnel-psychology": "https://onlinelibrary.wiley.com/page/journal/17446570/homepage/forauthors.html",
    "journal-of-consumer-psychology": "https://myscp.onlinelibrary.wiley.com/hub/journal/15327663/author-guidelines",
    # Karger
    "psychotherapy-and-psychosomatics": "https://karger.com/pps/pages/guidelines-for-authors",
}


def slugify(text: str) -> str:
    """Convert text to a safe filename slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")[:50]


def extract_text(html: str) -> str:
    """Extract readable text from HTML."""
    soup = BeautifulSoup(html, "lxml")

    # Remove script, style, nav, footer elements
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    # Get text
    text = soup.get_text(separator="\n", strip=True)

    # Clean up multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


async def scrape_with_playwright(url: str, slug: str) -> str | None:
    """Scrape a page using Playwright with stealth settings."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )

        page = await context.new_page()

        try:
            # Navigate with longer timeout
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # Wait for content to load
            await page.wait_for_timeout(3000)

            # Check for Cloudflare challenge
            content = await page.content()
            if "cf-chl-widget" in content or "Just a moment" in content:
                print(f"  Cloudflare challenge detected, waiting...")
                await page.wait_for_timeout(5000)
                content = await page.content()

                if "cf-chl-widget" in content:
                    print(f"  Still blocked by Cloudflare")
                    await browser.close()
                    return None

            # Extract text
            text = extract_text(content)

            await browser.close()
            return text

        except Exception as e:
            print(f"  Error: {e}")
            await browser.close()
            return None


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Direct Playwright Scraper")
    print("=" * 60)

    # Load existing log
    with open(LOG_FILE) as f:
        scrape_log = json.load(f)

    log_by_slug = {r["slug"]: r for r in scrape_log}

    # Find journals that need scraping
    to_scrape = []
    for entry in scrape_log:
        slug = entry["slug"]
        text_file = TEXT_DIR / f"{slug}.txt"

        # Check if we need to scrape
        needs_scrape = False
        if not text_file.exists():
            needs_scrape = True
        else:
            content = text_file.read_text()
            # Check for failure messages or empty content
            if len(content) < 500 or "Failed to access" in content or "could not be completed" in content:
                needs_scrape = True

        # Also re-scrape SAGE journals with generic content
        if slug in ["advances-in-methods-and-practices-in-psychological",
                    "psychological-science-in-the-public-interest",
                    "perspectives-on-psychological-science"] and slug in DIRECT_URLS:
            needs_scrape = True

        # Also re-scrape Elsevier journals
        if slug in ["clinical-psychology-review", "leadership-quarterly"] and slug in DIRECT_URLS:
            needs_scrape = True

        if needs_scrape and slug in DIRECT_URLS:
            to_scrape.append((slug, entry["journal_name"], DIRECT_URLS[slug]))

    print(f"Found {len(to_scrape)} journals to scrape")

    for slug, name, url in to_scrape:
        print(f"\n[Playwright] {name}")
        print(f"  URL: {url}")

        text = await scrape_with_playwright(url, slug)

        if text and len(text) > 500:
            print(f"  Success: {len(text)} chars")
            (TEXT_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")

            # Update log
            if slug in log_by_slug:
                log_by_slug[slug]["status"] = "success"
                log_by_slug[slug]["method"] = "playwright"
                log_by_slug[slug]["text_length"] = len(text)
                log_by_slug[slug]["guidelines_url"] = url
        else:
            print(f"  Failed or insufficient content")

        await asyncio.sleep(2)  # Be polite

    # Save updated log
    updated_log = list(log_by_slug.values())
    with open(LOG_FILE, "w") as f:
        json.dump(updated_log, f, indent=2)

    print("\n" + "=" * 60)
    print("Direct scraping complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
