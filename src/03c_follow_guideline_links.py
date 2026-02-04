"""Follow links in scraped content to get complete author guidelines."""

import asyncio
import json
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"
TEXT_DIR = DATA_DIR / "processed" / "guidelines_text"
LOG_FILE = DATA_DIR / "output" / "scraping_log.json"

# Patterns to identify guideline links in text
GUIDELINE_LINK_PATTERNS = [
    r'(?:complete|full|detailed|author)\s+(?:author\s+)?guidelines[^:]*:\s*(https?://[^\s\)\"\']+)',
    r'(?:submission|manuscript)\s+guidelines[^:]*:\s*(https?://[^\s\)\"\']+)',
    r'(?:please\s+)?visit[^:]*:\s*(https?://[^\s\)\"\']+guidelines[^\s\)\"\']*)',
    r'(https?://[^\s\)\"\']*(?:submission-guidelines|author-guidelines|for-authors|instructions)[^\s\)\"\']*)',
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def extract_guideline_links(text: str, base_url: str | None = None) -> list[str]:
    """Extract URLs that likely point to detailed author guidelines."""
    links = []

    for pattern in GUIDELINE_LINK_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            url = match.strip()
            # Clean up common URL artifacts
            url = url.rstrip('.,;:')
            if base_url and not url.startswith('http'):
                url = urljoin(base_url, url)
            if url not in links:
                links.append(url)

    return links


def extract_text(html: str) -> str:
    """Extract readable text from HTML."""
    soup = BeautifulSoup(html, "lxml")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


async def fetch_url(url: str, client: httpx.AsyncClient) -> str | None:
    """Fetch a URL and return its text content."""
    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code == 200:
            return extract_text(resp.text)
    except Exception as e:
        print(f"    Error fetching {url}: {e}")
    return None


async def process_journal(slug: str, guidelines_url: str | None) -> dict:
    """Check a journal's scraped text for links to follow."""
    text_file = TEXT_DIR / f"{slug}.txt"

    if not text_file.exists():
        return {"slug": slug, "status": "no_file", "links_found": [], "new_text_length": 0}

    original_text = text_file.read_text(encoding="utf-8")

    # Extract links from the text
    links = extract_guideline_links(original_text, guidelines_url)

    # Filter out links we've already scraped
    if guidelines_url:
        links = [l for l in links if urlparse(l).path != urlparse(guidelines_url).path]

    if not links:
        return {"slug": slug, "status": "no_new_links", "links_found": [], "new_text_length": len(original_text)}

    print(f"  Found {len(links)} potential guideline links:")
    for link in links[:5]:  # Show first 5
        print(f"    - {link}")

    # Fetch the linked pages
    new_texts = []
    async with httpx.AsyncClient(headers=HEADERS, timeout=30) as client:
        for link in links[:3]:  # Limit to 3 links to avoid over-fetching
            print(f"    Fetching: {link}")
            text = await fetch_url(link, client)
            if text and len(text) > 500:  # Only include substantial content
                new_texts.append(f"\n\n--- Additional Guidelines from {link} ---\n\n{text}")

    if new_texts:
        # Append new content to existing text
        combined_text = original_text + "\n".join(new_texts)
        text_file.write_text(combined_text, encoding="utf-8")
        print(f"  Added {len(new_texts)} additional pages ({len(combined_text) - len(original_text)} chars)")
        return {
            "slug": slug,
            "status": "updated",
            "links_found": links,
            "links_fetched": len(new_texts),
            "new_text_length": len(combined_text)
        }

    return {"slug": slug, "status": "links_failed", "links_found": links, "new_text_length": len(original_text)}


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Follow Guideline Links")
    print("=" * 60)

    # Load scraping log
    with open(LOG_FILE) as f:
        scrape_log = json.load(f)

    results = []

    for entry in scrape_log:
        if entry["status"] != "success":
            continue

        slug = entry["slug"]
        journal_name = entry["journal_name"]
        guidelines_url = entry.get("guidelines_url")

        print(f"\n[{journal_name}]")
        result = await process_journal(slug, guidelines_url)
        result["journal_name"] = journal_name
        results.append(result)

    # Summary
    updated = sum(1 for r in results if r["status"] == "updated")
    print("\n" + "=" * 60)
    print(f"Summary: Updated {updated}/{len(results)} journals with additional content")
    print("=" * 60)

    # Update scraping log with new text lengths
    slug_to_result = {r["slug"]: r for r in results}
    for entry in scrape_log:
        if entry["slug"] in slug_to_result:
            result = slug_to_result[entry["slug"]]
            if result["status"] == "updated":
                entry["text_length"] = result["new_text_length"]
                entry["additional_links_fetched"] = result["links_fetched"]

    with open(LOG_FILE, "w") as f:
        json.dump(scrape_log, f, indent=2)

    print("\nScraping log updated.")


if __name__ == "__main__":
    asyncio.run(main())
