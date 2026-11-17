"""Turn one KMI panel PDF (data/raw) into a clean CSV of incidents (data/processed)."""
import csv
import re
from pathlib import Path

from pypdf import PdfReader

BASE_DIR = Path(__file__).parent
RAW_DIR = BASE_DIR / "data" / "raw"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# A regex can't tell where "Crystal Palace Manchester City" splits into two teams; a list of names can.
# Longest first, so "Newcastle United" is tried before "Newcastle". Add clubs as new ones appear.
TEAMS = sorted([
    "AFC Bournemouth", "Arsenal", "Aston Villa", "Bournemouth", "Brentford",
    "Brighton & Hove Albion", "Brighton", "Burnley", "Chelsea", "Coventry City",
    "Crystal Palace", "Everton", "Fulham", "Hull City", "Ipswich Town",
    "Leeds United", "Leicester City", "Liverpool", "Manchester City",
    "Manchester United", "Middlesbrough", "Newcastle United", "Newcastle",
    "Nottingham Forest", "Sheffield United", "Southampton", "Sunderland",
    "Tottenham Hotspur", "West Ham United", "Wolverhampton Wanderers", "Wolves",
], key=len, reverse=True)
TEAM = "|".join(re.escape(t) for t in TEAMS)   # re.escape protects the "&" and any dots

# Times look like 67:43, stoppage time like 90:00+07:27, and the PDF once typos 84.20 for 84:20.
TIME = r"\d{2}[:.]\d{2}(?:\+\d{2}[:.]\d{2})?"
VOTES = r"\d:\d|N/A"          # N/A when VAR never reviewed the incident

# Where each incident starts: round number + home team + away team at the start of a line.
INCIDENT_START = re.compile(rf"^\d{{1,2}}\s+(?:{TEAM})\s+(?:{TEAM})", re.MULTILINE)

INCIDENT = re.compile(
    rf"^(\d{{1,2}})\s+"                      # round
    rf"({TEAM})\s+"                          # home team
    rf"({TEAM})\s+"                          # away team
    rf"(.*?)\s+"                             # on-field decision (type + descriptor)
    rf"({TIME})\s+"                          # time
    rf"(Assistant Referee|Referee)\s+"       # lead official
    rf"(.*?)\s+"                             # on-field outcome
    rf"\b({VOTES})\s+"                       # on-field votes (correct:incorrect)
    rf"([YN]|N/A)\s+"                        # VAR overturn
    rf"(.*?)\s+"                             # VAR outcome
    rf"\b({VOTES})\s+"                       # VAR votes
    rf"(.*)",                                # panel commentary: everything left
    re.DOTALL,
)

FIELDS = ["round", "home_team", "away_team", "decision_type", "decision_detail", "time",
          "official", "onfield_outcome", "onfield_votes", "var_overturn", "var_outcome",
          "var_votes", "commentary"]

FOOTER = "The decision outcomes are decided by a panel"


def clean(s):
    """Collapse line breaks and repeated spaces from the PDF into single spaces."""
    return " ".join(s.split())


def extract_text(pdf_path):
    reader = PdfReader(pdf_path)
    text = "\n".join(page.extract_text() for page in reader.pages)
    return text.split(FOOTER)[0]            # drop the footer and everything after it


def split_incidents(text):
    """Cut the text at every incident start; each slice runs up to the next start."""
    starts = [m.start() for m in INCIDENT_START.finditer(text)]
    ends = starts[1:] + [len(text)]
    return [text[s:e] for s, e in zip(starts, ends)]


def parse_incident(chunk):
    m = INCIDENT.search(chunk)
    if not m:
        return None
    (rnd, home, away, decision, time, official, on_out, on_votes,
     overturn, var_out, var_votes, commentary) = (clean(g) for g in m.groups())

    # "KMI Goal awarded. Jesus (NFO) in an onside position" -> type + detail
    decision = decision.removeprefix("KMI ").strip()
    dtype, _, detail = decision.partition(". ")

    return {
        "round": int(rnd), "home_team": home, "away_team": away,
        "decision_type": dtype.rstrip("."), "decision_detail": detail,
        "time": time.replace(".", ":"), "official": official,
        "onfield_outcome": on_out, "onfield_votes": on_votes,
        "var_overturn": overturn, "var_outcome": var_out,
        "var_votes": var_votes, "commentary": commentary,
    }


def parse_round(pdf_path):
    """Return (rows, failed_chunks) for one PDF."""
    rows, failed = [], []
    for chunk in split_incidents(extract_text(pdf_path)):
        row = parse_incident(chunk)
        if row:
            rows.append(row)
        else:
            failed.append(chunk)
    return rows, failed


def write_csv(rows, out_path):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    pdf_path = RAW_DIR / "round_02.pdf"
    rows, failed = parse_round(pdf_path)

    out_path = PROCESSED_DIR / "round_02.csv"
    write_csv(rows, out_path)
    print(f"Parsed {len(rows)} incidents -> {out_path.relative_to(BASE_DIR)}")

    # Never fail silently: a chunk that didn't parse is a lost incident.
    for chunk in failed:
        print("\nCOULD NOT PARSE:\n", chunk[:300])
