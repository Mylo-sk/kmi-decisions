"""Download every round's KMI PDF (only once) and combine all incidents into one CSV.

Run after find_pdfs.py:  py update.py
"""
import csv
import re
import time
from collections import Counter
from pathlib import Path

import requests

from parse_round import (
    FIELDS,
    OFFICIAL,
    PROCESSED_DIR,
    RAW_DIR,
    extract_text,
    parse_round,
    write_csv,
)

BASE_DIR = Path(__file__).parent
PDF_LINKS = BASE_DIR / "pdf_links.csv"
OUTPUT = PROCESSED_DIR / "kmi_decisions.csv"
OUTPUT_FIELDS = ["incident_id"] + FIELDS + ["source_url"]

HEADERS = {"User-Agent": "Mozilla/5.0"}

# A second, much simpler way to count incidents: every incident has its lead official followed by
# "Correct" or "Incorrect". If this count and the parser's count differ, the parser missed something.
# "Incorr?ect" also accepts "Incorect", a typo that really appears in the Round 9 PDF.
SIMPLE_COUNT = re.compile(rf"(?:{OFFICIAL})\s+(?:Correct|Incorr?ect)")


def plan_files():
    """Read pdf_links.csv and decide each PDF's local filename: round_01.pdf, round_02.pdf ...

    If a round ever has more than one PDF, its files become round_05a.pdf, round_05b.pdf.
    """
    with open(PDF_LINKS, newline="", encoding="utf-8") as f:
        links = list(csv.DictReader(f))

    pdfs_per_round = Counter(int(link["round"]) for link in links)
    seen = Counter()
    plan = []
    for link in links:
        rnd = int(link["round"])
        suffix = "abcdefgh"[seen[rnd]] if pdfs_per_round[rnd] > 1 else ""
        seen[rnd] += 1
        plan.append((rnd, link["pdf_url"], RAW_DIR / f"round_{rnd:02d}{suffix}.pdf"))
    return plan


def download_if_missing(url, path):
    """Download only when the file isn't on disk yet. Returns True if it downloaded."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    path.write_bytes(response.content)
    time.sleep(1)   # be polite to the Premier League's server
    return True


def main():
    all_rows = []
    numbers_used = Counter()    # running incident count per round, for the incident IDs
    warnings = 0

    for rnd, url, path in plan_files():
        downloaded = download_if_missing(url, path)
        rows, failed = parse_round(path)
        expected = len(SIMPLE_COUNT.findall(extract_text(path)))

        status = "downloaded" if downloaded else "already on disk"
        print(f"Round {rnd:>2}: {len(rows):>3} incidents  ({path.name}, {status})")

        # Three checks. Each one catches a different way the data could silently go wrong.
        for chunk in failed:
            print(f"   WARNING: could not parse:\n   {chunk[:200]}")
            warnings += 1
        if len(rows) != expected:
            print(f"   WARNING: parsed {len(rows)} but the simple count found {expected}")
            warnings += 1
        if any(row["round"] != rnd for row in rows):
            print(f"   WARNING: the PDF's own round number doesn't match round {rnd} in sources.csv")
            warnings += 1

        for row in rows:
            numbers_used[rnd] += 1
            row["incident_id"] = f"R{rnd:02d}-{numbers_used[rnd]:03d}"   # e.g. R02-007
            row["source_url"] = url
        all_rows.extend(rows)

    write_csv(all_rows, OUTPUT, fieldnames=OUTPUT_FIELDS)
    print(f"\n{len(all_rows)} incidents from {len(numbers_used)} rounds -> "
          f"{OUTPUT.relative_to(BASE_DIR)}")
    print("No warnings." if warnings == 0 else f"{warnings} WARNING(S) above - check before using the data.")


if __name__ == "__main__":
    main()
