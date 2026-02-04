"""Discover journal homepage URLs using OpenAlex API."""

import json
import time
from pathlib import Path

import httpx
import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"
INPUT_FILE = DATA_DIR / "input" / "top_psychology_journals.csv"
OUTPUT_FILE = DATA_DIR / "output" / "journals_with_urls.csv"

OPENALEX_BASE = "https://api.openalex.org/sources"
CROSSREF_BASE = "https://api.crossref.org/journals"

# Polite headers for API requests
HEADERS = {
    "User-Agent": "JournalCheck/1.0 (mailto:research@example.com)",
    "Accept": "application/json",
}


def get_issn_variants(issn: str) -> list[str]:
    """Generate all ISSN variants from a possibly comma-separated string."""
    variants = []

    # Split on comma if multiple ISSNs
    for issn_part in issn.split(","):
        issn_clean = issn_part.strip().replace(" ", "")
        if not issn_clean:
            continue

        # Add the clean version
        variants.append(issn_clean)

        # Add with hyphen if 8 digits without hyphen
        if "-" not in issn_clean and len(issn_clean) == 8:
            variants.append(f"{issn_clean[:4]}-{issn_clean[4:]}")
        # Add without hyphen if has hyphen
        elif "-" in issn_clean:
            variants.append(issn_clean.replace("-", ""))

    return list(set(variants))  # Remove duplicates


def query_openalex(issn: str) -> dict | None:
    """Query OpenAlex API for journal info by ISSN."""
    issn_variants = get_issn_variants(issn)

    for issn_try in issn_variants:
        url = f"{OPENALEX_BASE}/issn:{issn_try}"
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp.json()
        except httpx.HTTPError as e:
            print(f"  OpenAlex error for {issn_try}: {e}")

    return None


def query_crossref(issn: str) -> dict | None:
    """Fallback: Query CrossRef API for journal info."""
    issn_variants = get_issn_variants(issn)

    for issn_try in issn_variants:
        # CrossRef prefers hyphenated format
        if "-" not in issn_try and len(issn_try) == 8:
            issn_try = f"{issn_try[:4]}-{issn_try[4:]}"

        url = f"{CROSSREF_BASE}/{issn_try}"
        try:
            resp = httpx.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return resp.json().get("message", {})
        except httpx.HTTPError as e:
            print(f"  CrossRef error for {issn_try}: {e}")

    return None


def discover_urls(df: pd.DataFrame) -> pd.DataFrame:
    """Add homepage_url column to journal dataframe."""
    results = []

    for idx, row in df.iterrows():
        journal_name = row["title"]
        issn = row["issn"]

        print(f"\n[{idx+1}/{len(df)}] {journal_name} (ISSN: {issn})")

        homepage_url = None
        source = None

        # Try OpenAlex first
        oa_data = query_openalex(issn)
        if oa_data:
            homepage_url = oa_data.get("homepage_url")
            if homepage_url:
                source = "openalex"
                print(f"  Found via OpenAlex: {homepage_url}")

        # Fallback to CrossRef
        if not homepage_url:
            cr_data = query_crossref(issn)
            if cr_data:
                # CrossRef uses "URL" field
                homepage_url = cr_data.get("URL")
                if homepage_url:
                    source = "crossref"
                    print(f"  Found via CrossRef: {homepage_url}")

        if not homepage_url:
            print("  No URL found - will need manual lookup or Google search")

        results.append(
            {
                **row.to_dict(),
                "homepage_url": homepage_url,
                "url_source": source,
            }
        )

        # Be polite to APIs
        time.sleep(0.5)

    return pd.DataFrame(results)


def main():
    """Main entry point."""
    print("=" * 60)
    print("Journal URL Discovery")
    print("=" * 60)

    if not INPUT_FILE.exists():
        print(f"Error: Input file not found: {INPUT_FILE}")
        print("Run 01_get_journals.R first to create the journal list.")
        return

    df = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df)} journals from {INPUT_FILE}")

    df_with_urls = discover_urls(df)

    # Summary
    found = df_with_urls["homepage_url"].notna().sum()
    print("\n" + "=" * 60)
    print(f"Summary: Found URLs for {found}/{len(df)} journals")
    print("=" * 60)

    # Save results
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    df_with_urls.to_csv(OUTPUT_FILE, index=False)
    print(f"\nSaved to: {OUTPUT_FILE}")

    # List journals needing manual lookup
    missing = df_with_urls[df_with_urls["homepage_url"].isna()]
    if not missing.empty:
        print("\nJournals needing manual URL lookup:")
        for _, row in missing.iterrows():
            print(f"  - {row['title']} (ISSN: {row['issn']})")


if __name__ == "__main__":
    main()
