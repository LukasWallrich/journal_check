"""Analyze guidelines using Gemini with structured output."""

import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(Path(__file__).parent.parent / ".env")

from google import genai
import instructor
import pandas as pd
from rapidfuzz import fuzz

from models import GuidelinesAnalysis

DATA_DIR = Path(__file__).parent.parent / "data"
TEXT_DIR = DATA_DIR / "processed" / "guidelines_text"
LOG_FILE = DATA_DIR / "output" / "scraping_log.json"
OUTPUT_FILE = DATA_DIR / "output" / "pilot_feasibility_results.csv"

ANALYSIS_PROMPT = """Analyze the following text that was scraped from what should be author guidelines for a psychology journal.

Journal: {journal_name}

Scraped text:
---
{text}
---

## FIRST: Validate the content

Before analyzing for pilot studies, determine if this is actually author submission guidelines:

1. Set `is_author_guidelines` to True ONLY if the text contains actual submission/author guidelines for this specific journal (manuscript formatting, submission process, article types, etc.)

2. Set `content_type` to one of:
   - "journal_specific_guidelines" - Detailed guidelines specific to this journal
   - "publisher_generic_guidelines" - Generic guidelines from the publisher (e.g., SAGE, Elsevier) not specific to this journal
   - "landing_page" - A navigation/landing page with links but no actual guidelines content
   - "error_page" - A 404 or other error page
   - "unrelated_content" - Content not related to author guidelines

3. Add `guidelines_specificity_notes` explaining your assessment (e.g., "This is a generic Annual Reviews author resource center page, not specific to this psychology journal")

## THEN: Search for pilot/feasibility study mentions

Search for these terms and concepts:
- Pilot study / pilot studies
- Feasibility study / feasibility studies
- Preliminary study / preliminary data / exploratory study
- Registered reports (a submission format where study design is reviewed before data collection)

For each concept found, determine the journal's stance:
- "required" - The journal requires this
- "encouraged" - The journal actively encourages or welcomes this
- "accepted" - The journal accepts this as a valid submission type
- "discouraged" - The journal discourages or advises against this
- "not_mentioned" - No mention found

Extract up to 3 direct quotes (exact text from the guidelines) for pilot studies and feasibility studies if mentioned.

Set confidence_score based on:
- 1.0: Clear, explicit statements about the topics in journal-specific guidelines
- 0.7-0.9: Indirect mentions or implications
- 0.5-0.7: Ambiguous or unclear references, OR generic publisher guidelines
- <0.5: Landing page, error page, or very limited relevant content

Provide analysis_notes if there are any ambiguities or important context."""


def validate_quotes(quotes: list[str], source_text: str) -> float:
    """Return average similarity score for quotes (0-1)."""
    if not quotes:
        return 1.0  # No quotes to validate

    scores = []
    for quote in quotes:
        # Use partial_ratio for substring matching
        score = fuzz.partial_ratio(quote.lower(), source_text.lower()) / 100
        scores.append(score)

    return sum(scores) / len(scores)


def analyze_journal(
    journal_name: str, text: str, client: instructor.Instructor
) -> tuple[GuidelinesAnalysis, float]:
    """Analyze a single journal's guidelines."""
    prompt = ANALYSIS_PROMPT.format(journal_name=journal_name, text=text[:50000])

    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        response_model=GuidelinesAnalysis,
    )

    # Validate quotes
    all_quotes = response.pilot_study_quotes + response.feasibility_study_quotes
    quote_validation = validate_quotes(all_quotes, text)

    return response, quote_validation


def main():
    """Main entry point."""
    print("=" * 60)
    print("Guidelines Analysis with Gemini")
    print("=" * 60)

    # Load scraping log
    if not LOG_FILE.exists():
        print(f"Error: Scraping log not found: {LOG_FILE}")
        print("Run 03_scrape_guidelines.py first.")
        return

    with open(LOG_FILE) as f:
        scrape_results = json.load(f)

    # Filter to successful scrapes
    to_analyze = [r for r in scrape_results if r["status"] == "success"]
    print(f"Found {len(to_analyze)} journals to analyze")

    if not to_analyze:
        print("No journals to analyze. Check scraping results.")
        return

    # Initialize Gemini client with instructor using new google-genai API
    genai_client = genai.Client()
    client = instructor.from_genai(
        client=genai_client,
        model="gemini-2.0-flash",
    )

    results = []

    for idx, scrape_info in enumerate(to_analyze):
        journal_name = scrape_info["journal_name"]
        slug = scrape_info["slug"]
        text_file = TEXT_DIR / f"{slug}.txt"

        print(f"\n[{idx+1}/{len(to_analyze)}] {journal_name}")

        if not text_file.exists():
            print(f"  Warning: Text file not found: {text_file}")
            continue

        text = text_file.read_text(encoding="utf-8")

        if len(text) < 500:
            print(f"  Warning: Very short text ({len(text)} chars)")

        try:
            analysis, quote_validation = analyze_journal(journal_name, text, client)

            result = {
                "journal_name": journal_name,
                "guidelines_url": scrape_info.get("guidelines_url"),
                "text_length": len(text),
                **analysis.model_dump(),
                "quote_validation_score": quote_validation,
            }

            # Flag low confidence or poor quote validation
            flags = []
            if analysis.confidence_score < 0.7:
                flags.append("low_confidence")
            if quote_validation < 0.8:
                flags.append("quote_validation_warning")
            result["review_flags"] = ";".join(flags) if flags else None

            results.append(result)

            # Summary output
            print(f"  Pilot: {analysis.pilot_study_stance or 'not_mentioned'}")
            print(f"  Feasibility: {analysis.feasibility_study_stance or 'not_mentioned'}")
            print(f"  Confidence: {analysis.confidence_score:.2f}")
            print(f"  Quote validation: {quote_validation:.2f}")

        except Exception as e:
            print(f"  Error: {e}")
            results.append(
                {
                    "journal_name": journal_name,
                    "error": str(e),
                }
            )

    # Save results
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_FILE, index=False)

    print("\n" + "=" * 60)
    print(f"Analysis complete. Results saved to: {OUTPUT_FILE}")
    print("=" * 60)

    # Summary statistics
    if "pilot_study_mentioned" in df.columns:
        pilot_mentioned = df["pilot_study_mentioned"].sum()
        feasibility_mentioned = df["feasibility_study_mentioned"].sum()
        registered_reports = df["registered_reports_mentioned"].sum()

        print(f"\nSummary:")
        print(f"  Pilot studies mentioned: {pilot_mentioned}/{len(df)}")
        print(f"  Feasibility studies mentioned: {feasibility_mentioned}/{len(df)}")
        print(f"  Registered reports mentioned: {registered_reports}/{len(df)}")

        flagged = df["review_flags"].notna().sum()
        print(f"  Flagged for review: {flagged}/{len(df)}")


if __name__ == "__main__":
    main()
