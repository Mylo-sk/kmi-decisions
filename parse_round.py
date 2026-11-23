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

# The PDFs sometimes use a short name; map each to one official name so every club is counted once.
TEAM_ALIASES = {
    "AFC Bournemouth": "Bournemouth",
    "Brighton": "Brighton & Hove Albion",
    "Newcastle": "Newcastle United",
    "Wolves": "Wolverhampton Wanderers",
}

# Times look like 67:43 and stoppage time like 90:00+07:27. The PDFs also write "45:00 + 3:02"
# (spaces, one-digit minute) and once typo 84.20 for 84:20; normalise_time() tidies all of these.
TIME = r"\d{1,2}[:.]\d{2}(?:\s*\+\s*\d{1,2}[:.]\d{2})?"
VOTES = r"\d:\d|N/A"          # N/A when VAR never reviewed the incident

# Who made the on-field call. Longest first, so "Assistant Referee" is tried before "Referee".
OFFICIALS = ["Assistant Referee", "Fourth Official", "Referee"]
OFFICIAL = "|".join(OFFICIALS)

# Where each incident starts: round number + home team + away team at the start of a line.
INCIDENT_START = re.compile(rf"^\d{{1,2}}\s+(?:{TEAM})\s+(?:{TEAM})", re.MULTILINE)

INCIDENT = re.compile(
    rf"^(\d{{1,2}})\s+"                      # round
    rf"({TEAM})\s+"                          # home team
    rf"({TEAM})\s+"                          # away team
    rf"(.*?)\s+"                             # on-field decision (type + descriptor)
    rf"({TIME})\s+"                          # time
    rf"({OFFICIAL})\s+"                      # lead official
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
HEADER_END = "Panel commentary"   # last words of the column headers


def clean(s):
    """Collapse line breaks and repeated spaces from the PDF into single spaces."""
    return " ".join(s.split())


def normalise_time(raw):
    """'45:00 + 3:02' -> '45:00+03:02', '84.20' -> '84:20': one consistent format."""
    parts = re.sub(r"\s+", "", raw).replace(".", ":").split("+")
    padded = []
    for part in parts:
        minutes, seconds = part.split(":")
        padded.append(f"{int(minutes):02d}:{seconds}")
    return "+".join(padded)


def extract_text(pdf_path):
    reader = PdfReader(pdf_path)
    text = "\n".join(page.extract_text() for page in reader.pages)
    text = text.split(FOOTER)[0]            # drop the footer and everything after it
    # Round 10's PDF puts the first incident on the same line as the headers, where the
    # start-of-line search can't see it. Replacing whatever follows the headers (spaces, or a
    # line break plus a space) with a clean line break fixes that.
    return re.sub(rf"{HEADER_END}\s*", HEADER_END + "\n", text)


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
    # The PDFs spell the same type several ways ("Penalty Awarded", "Sending off, dismissal...").
    # One spelling per type, so grouping by type later counts them together.
    dtype = dtype.replace(",", "").capitalize().replace("Dogso", "DOGSO")

    return {
        "round": int(rnd),
        "home_team": TEAM_ALIASES.get(home, home),   # .get(x, x): the alias if there is one, else x
        "away_team": TEAM_ALIASES.get(away, away),
        "decision_type": dtype.rstrip("."), "decision_detail": detail,
        "time": normalise_time(time), "official": official,
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


def write_csv(rows, out_path, fieldnames=FIELDS):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    # A quick check on one round, without touching the dataset:  py parse_round.py 10
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    rnd = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    rows, failed = parse_round(RAW_DIR / f"round_{rnd:02d}.pdf")
    print(f"Round {rnd}: parsed {len(rows)} incidents")
    for row in rows:
        print(f"  {row['time']:>12}  {row['home_team']} v {row['away_team']}: "
              f"{row['decision_type']} -> {row['onfield_outcome']} ({row['onfield_votes']})")

    # Never fail silently: a chunk that didn't parse is a lost incident.
    for chunk in failed:
        print("\nCOULD NOT PARSE:\n", chunk[:300])
