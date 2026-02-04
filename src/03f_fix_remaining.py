"""Fix remaining journals using browser automation."""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"
TEXT_DIR = DATA_DIR / "processed" / "guidelines_text"
LOG_FILE = DATA_DIR / "output" / "scraping_log.json"

# Journals that still need fixing
JOURNALS_TO_FIX = [
    {
        "slug": "journal-of-consumer-psychology",
        "journal_name": "Journal of Consumer Psychology",
        "url": "https://myscp.onlinelibrary.wiley.com/hub/journal/15327663/forauthors.html",
    },
]


async def scrape_journal(journal: dict) -> bool:
    """Scrape a journal using browser automation."""
    from browser_use import Agent, Browser
    from browser_use.llm.browser_use import ChatBrowserUse

    slug = journal["slug"]
    journal_name = journal["journal_name"]
    url = journal["url"]

    print(f"\n[{journal_name}]")
    print(f"  URL: {url}")

    llm = ChatBrowserUse(model="bu-latest")
    browser = Browser(headless=True)

    agent = Agent(
        task=f"""Go to {url}

This is the author guidelines page for "{journal_name}".

If there's a cookie consent dialog, accept it or dismiss it.

Extract ALL text content from the page related to:
- Submission guidelines and requirements
- Manuscript preparation
- Article types
- Review process
- Any mentions of pilot studies, feasibility studies, preliminary data

Just return the raw text content of the guidelines.""",
        llm=llm,
        browser=browser,
    )

    try:
        result = await agent.run(max_steps=15)

        if result and result.final_result():
            text = result.final_result()

            # Check if it's actually content (not an error message)
            if len(text) > 500 and "failed" not in text.lower()[:100]:
                print(f"  Success: {len(text)} chars extracted")

                # Save
                text_file = TEXT_DIR / f"{slug}.txt"
                text_file.write_text(text, encoding="utf-8")

                # Update log
                with open(LOG_FILE) as f:
                    scrape_log = json.load(f)

                for entry in scrape_log:
                    if entry["slug"] == slug:
                        entry["guidelines_url"] = url
                        entry["text_length"] = len(text)
                        entry["method"] = "browser-use"
                        entry["error"] = None
                        break

                with open(LOG_FILE, "w") as f:
                    json.dump(scrape_log, f, indent=2)

                return True

        print("  Failed to extract meaningful content")
        return False

    except Exception as e:
        print(f"  Error: {e}")
        return False


async def main():
    """Main entry point."""
    print("=" * 60)
    print("Fix Remaining Journals")
    print("=" * 60)

    success_count = 0
    for journal in JOURNALS_TO_FIX:
        if await scrape_journal(journal):
            success_count += 1

    print("\n" + "=" * 60)
    print(f"Fixed {success_count}/{len(JOURNALS_TO_FIX)} journals")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
