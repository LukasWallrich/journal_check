"""Scrape author guidelines from journal websites."""

import asyncio
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import pandas as pd
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_FILE = DATA_DIR / "output" / "journals_with_urls.csv"
HTML_DIR = DATA_DIR / "raw" / "guidelines_html"
TEXT_DIR = DATA_DIR / "processed" / "guidelines_text"
LOG_FILE = DATA_DIR / "output" / "scraping_log.json"

# Common paths to author guidelines
GUIDELINES_PATHS = [
    "/for-authors",
    "/authors",
    "/author-guidelines",
    "/submission-guidelines",
    "/instructions-for-authors",
    "/instructions-authors",
    "/submit",
    "/about/submissions",
    "/about/author-guidelines",
]

# Keywords indicating guidelines pages
GUIDELINES_KEYWORDS = [
    "author guidelines",
    "submission guidelines",
    "instructions for authors",
    "guide for authors",
    "author instructions",
    "how to submit",
    "manuscript preparation",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
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
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Get text
    text = soup.get_text(separator="\n", strip=True)

    # Clean up multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


def find_guidelines_link(html: str, base_url: str) -> str | None:
    """Find link to author guidelines page from homepage."""
    soup = BeautifulSoup(html, "lxml")

    for link in soup.find_all("a", href=True):
        href = link.get("href", "")
        text = link.get_text().lower()

        # Check link text for keywords
        for keyword in GUIDELINES_KEYWORDS:
            if keyword in text:
                return urljoin(base_url, href)

        # Check href path
        for path in GUIDELINES_PATHS:
            if path in href.lower():
                return urljoin(base_url, href)

    return None


async def scrape_with_browser(url: str, journal_name: str) -> tuple[str, str] | None:
    """Use browser-use for sites that block simple HTTP requests."""
    try:
        from browser_use import Agent
        from langchain_google_genai import ChatGoogleGenerativeAI

        llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

        agent = Agent(
            task=f"""Navigate to {url} and find the author guidelines or submission guidelines page for the journal "{journal_name}".
            Once you find the guidelines page, extract all the text content.
            Look for links like "For Authors", "Author Guidelines", "Submission Guidelines", "Instructions for Authors".
            """,
            llm=llm,
        )

        result = await agent.run()

        # Get the final page content
        if result and hasattr(result, "final_result"):
            return result.final_result, "browser-use"

    except ImportError:
        print("  browser-use not available, skipping browser fallback")
    except Exception as e:
        print(f"  Browser scraping error: {e}")

    return None


def scrape_journal_http(
    homepage_url: str, journal_name: str
) -> tuple[str, str, str] | None:
    """
    Tier 1: Try to scrape guidelines using simple HTTP requests.
    Returns (html, text, guidelines_url) or None if blocked.
    """
    client = httpx.Client(headers=HEADERS, follow_redirects=True, timeout=30)

    try:
        # First, try the homepage
        resp = client.get(homepage_url)

        if resp.status_code == 403:
            print(f"  Blocked (403) - will try browser fallback")
            return None

        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}")
            return None

        # Look for guidelines link
        guidelines_url = find_guidelines_link(resp.text, homepage_url)

        if guidelines_url:
            print(f"  Found guidelines link: {guidelines_url}")
            resp = client.get(guidelines_url)
            if resp.status_code == 200:
                html = resp.text
                text = extract_text(html)
                return html, text, guidelines_url

        # Try common paths directly
        parsed = urlparse(homepage_url)
        base = f"{parsed.scheme}://{parsed.netloc}"

        for path in GUIDELINES_PATHS:
            try_url = base + path
            try:
                resp = client.get(try_url)
                if resp.status_code == 200:
                    # Check if it looks like guidelines
                    text_lower = resp.text.lower()
                    if any(kw in text_lower for kw in GUIDELINES_KEYWORDS):
                        print(f"  Found via path: {try_url}")
                        html = resp.text
                        text = extract_text(html)
                        return html, text, try_url
            except httpx.HTTPError:
                continue

        # Fallback: use homepage content
        print(f"  Using homepage content (no dedicated guidelines page found)")
        html = resp.text
        text = extract_text(html)
        return html, text, homepage_url

    except httpx.HTTPError as e:
        print(f"  HTTP error: {e}")
        return None
    finally:
        client.close()


def scrape_journals(df: pd.DataFrame) -> list[dict]:
    """Scrape guidelines for all journals."""
    results = []

    HTML_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)

    for idx, row in df.iterrows():
        journal_name = row["title"]
        homepage_url = row.get("homepage_url")
        slug = slugify(journal_name)

        print(f"\n[{idx+1}/{len(df)}] {journal_name}")

        result = {
            "journal_name": journal_name,
            "slug": slug,
            "homepage_url": homepage_url,
            "guidelines_url": None,
            "status": "pending",
            "method": None,
            "text_length": 0,
            "error": None,
        }

        if not homepage_url:
            result["status"] = "no_url"
            result["error"] = "No homepage URL available"
            print("  Skipped: No URL")
            results.append(result)
            continue

        # Tier 1: Try HTTP
        http_result = scrape_journal_http(homepage_url, journal_name)

        if http_result:
            html, text, guidelines_url = http_result
            result["guidelines_url"] = guidelines_url
            result["status"] = "success"
            result["method"] = "http"
            result["text_length"] = len(text)

            # Save files
            (HTML_DIR / f"{slug}.html").write_text(html, encoding="utf-8")
            (TEXT_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")

            print(f"  Success: {len(text)} chars extracted")
        else:
            # Tier 2: Browser fallback would go here
            # For now, mark as needing browser
            result["status"] = "needs_browser"
            result["error"] = "HTTP scraping failed, needs browser automation"
            print("  Needs browser automation")

        results.append(result)

        # Be polite
        time.sleep(2)

    return results


def main():
    """Main entry point."""
    print("=" * 60)
    print("Journal Guidelines Scraper")
    print("=" * 60)

    if not INPUT_FILE.exists():
        print(f"Error: Input file not found: {INPUT_FILE}")
        print("Run 02_discover_urls.py first.")
        return

    df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df)} journals from {INPUT_FILE}")

    results = scrape_journals(df)

    # Summary
    success = sum(1 for r in results if r["status"] == "success")
    needs_browser = sum(1 for r in results if r["status"] == "needs_browser")
    no_url = sum(1 for r in results if r["status"] == "no_url")

    print("\n" + "=" * 60)
    print(f"Summary:")
    print(f"  Success: {success}/{len(df)}")
    print(f"  Needs browser: {needs_browser}/{len(df)}")
    print(f"  No URL: {no_url}/{len(df)}")
    print("=" * 60)

    # Save log
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nScraping log saved to: {LOG_FILE}")


if __name__ == "__main__":
    main()
