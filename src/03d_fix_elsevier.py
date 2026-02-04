"""Fix Elsevier journals that didn't scrape correctly."""

import asyncio
import json
import re
from pathlib import Path

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"
TEXT_DIR = DATA_DIR / "processed" / "guidelines_text"
LOG_FILE = DATA_DIR / "output" / "scraping_log.json"

# Journals needing URL fixes
JOURNAL_FIXES = [
    {
        "slug": "clinical-psychology-review",
        "journal_name": "Clinical Psychology Review",
        "url": "https://www.elsevier.com/journals/clinical-psychology-review/0272-7358/guide-for-authors",
    },
    {
        "slug": "leadership-quarterly",
        "journal_name": "Leadership Quarterly",
        "url": "https://www.elsevier.com/journals/the-leadership-quarterly/1048-9843/guide-for-authors",
    },
    {
        "slug": "journal-of-consumer-psychology",
        "journal_name": "Journal of Consumer Psychology",
        "url": "https://myscp.onlinelibrary.wiley.com/hub/journal/15327663/forauthors.html",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def extract_text(html: str) -> str:
    """Extract readable text from HTML."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


async def fetch_elsevier_guidelines(url: str) -> str | None:
    """Fetch Elsevier guide for authors page."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=30, follow_redirects=True) as client:
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                return extract_text(resp.text)
            print(f"  HTTP {resp.status_code}")
        except Exception as e:
            print(f"  Error: {e}")
    return None


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Fix Elsevier Journal Guidelines")
    print("=" * 60)

    # Load scraping log
    with open(LOG_FILE) as f:
        scrape_log = json.load(f)

    log_by_slug = {r["slug"]: r for r in scrape_log}

    for fix in JOURNAL_FIXES:
        slug = fix["slug"]
        journal_name = fix["journal_name"]
        url = fix["url"]

        print(f"\n[{journal_name}]")
        print(f"  URL: {url}")

        text = await fetch_elsevier_guidelines(url)

        if text and len(text) > 500:
            # Save the text
            text_file = TEXT_DIR / f"{slug}.txt"
            text_file.write_text(text, encoding="utf-8")

            # Update log
            if slug in log_by_slug:
                log_by_slug[slug]["guidelines_url"] = url
                log_by_slug[slug]["text_length"] = len(text)
                log_by_slug[slug]["method"] = "http-fixed"

            print(f"  Success: {len(text)} chars extracted")
        else:
            print(f"  Failed to extract content")

    # Save updated log
    with open(LOG_FILE, "w") as f:
        json.dump(list(log_by_slug.values()), f, indent=2)

    print("\n" + "=" * 60)
    print("Done. Log updated.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
