"""Fix Karger journal using browser automation."""

import asyncio
import json
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATA_DIR = Path(__file__).parent.parent / "data"
TEXT_DIR = DATA_DIR / "processed" / "guidelines_text"
LOG_FILE = DATA_DIR / "output" / "scraping_log.json"


async def main():
    from browser_use import Agent, Browser
    from browser_use.llm.browser_use import ChatBrowserUse

    print("=" * 60)
    print("Fix Karger Journal (Psychotherapy and Psychosomatics)")
    print("=" * 60)

    llm = ChatBrowserUse(model="bu-latest")
    browser = Browser(headless=True)

    url = "https://karger.com/pps/pages/Author-Guidelines"

    agent = Agent(
        task=f"""Go to {url}

This is the author guidelines page for "Psychotherapy and Psychosomatics" journal.

Extract ALL text content from the page related to:
- Submission guidelines
- Manuscript preparation
- Article types
- Any mentions of pilot studies, feasibility studies, preliminary data

Just return the raw text content.""",
        llm=llm,
        browser=browser,
    )

    try:
        result = await agent.run(max_steps=10)

        if result and result.final_result():
            text = result.final_result()
            print(f"Success: {len(text)} chars extracted")

            # Save
            text_file = TEXT_DIR / "psychotherapy-and-psychosomatics.txt"
            text_file.write_text(text, encoding="utf-8")

            # Update log
            with open(LOG_FILE) as f:
                scrape_log = json.load(f)

            for entry in scrape_log:
                if entry["slug"] == "psychotherapy-and-psychosomatics":
                    entry["guidelines_url"] = url
                    entry["text_length"] = len(text)
                    entry["method"] = "browser-use"
                    entry["error"] = None
                    break

            with open(LOG_FILE, "w") as f:
                json.dump(scrape_log, f, indent=2)

            print("Log updated.")
        else:
            print("Failed to extract content")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
