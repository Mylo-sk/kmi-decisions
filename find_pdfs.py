"""Turn sources.csv (one Premier League article or PDF link per round) into pdf_links.csv.

Each week: find the new round's "Key Match Incidents Panel outcomes" article on
premierleague.com, add one line to sources.csv, and rerun this script.
"""
import csv
import re
import time
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
SOURCES = BASE_DIR / "sources.csv"
OUTPUT = BASE_DIR / "pdf_links.csv"

HEADERS = {"User-Agent": "Mozilla/5.0"}

# Only KMI decision PDFs: articles also link other documents, like the referee handbook.
KMI_PDF = re.compile(r'https://resources\.premierleague\.pulselive\.com/[^"\'\s<>]+?KMI[^"\'\s<>]*?\.pdf')


def pdf_links_for(url):
    """A direct PDF link is returned as is; an article page is searched for KMI PDF links."""
    if url.lower().endswith(".pdf"):
        return [url]
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    # dict.fromkeys removes duplicates but keeps the order they appear in (a set would shuffle them).
    return list(dict.fromkeys(KMI_PDF.findall(response.text)))


def main():
    with open(SOURCES, newline="", encoding="utf-8") as f:
        sources = list(csv.DictReader(f))

    rows = []
    for src in sources:
        links = pdf_links_for(src["url"])
        if not links:
            print(f"Round {src['round']}: NO KMI PDF FOUND at {src['url']}")
        for link in links:
            rows.append({"round": int(src["round"]), "pdf_url": link})
            print(f"Round {src['round']}: {link.rsplit('/', 1)[-1]}")
        if not src["url"].lower().endswith(".pdf"):
            time.sleep(1)   # be polite: one page per second

    with open(OUTPUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["round", "pdf_url"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n{len(rows)} PDF links -> {OUTPUT.name}")


if __name__ == "__main__":
    main()
