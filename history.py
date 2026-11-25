"""VAR season by season: check data/history/var_seasons.csv and compare this season against it.

var_seasons.csv stores every figure someone published as its own row ("long" format): the
season, which metric, the value, how much of the season it covers, the source, and the exact
words it came from. Sources disagree and report over different windows, so nothing is
averaged or overwritten when a figure goes in. Choosing which figure to trust happens in this
script, where the rules are written down and anyone can check them.

Run:  py history.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")   # Windows terminals choke on some characters otherwise

HERE = Path(__file__).parent
HISTORY = HERE / "data" / "history" / "var_seasons.csv"
KMI = HERE / "data" / "processed" / "kmi_decisions.csv"
FULL_SEASON = 38
THIS_SEASON = "2026-27"

# Every metric the CSV may use: (unit, plain-English meaning). The checker rejects anything not
# listed here, so a typo like "var_error" can't quietly become a new metric.
METRICS = {
    "kmi_onfield_correct_pct":    ("pct", "Key decisions the on-field officials got right (the PL's headline)"),
    "kmi_after_var_correct_pct":  ("pct", "Key decisions correct after VAR, the PL's way (counts 'not clear and obvious' wrong calls as correct)"),
    "kmi_stood_correct_pct":      ("pct", "Decisions that actually stood that were right (needs per-incident data: 2026-27 onwards)"),
    "incidents_checked":          ("count", "Incidents VAR checked"),
    "var_interventions":          ("count", "Times VAR intervened: overturns plus ones the referee rejected at the monitor"),
    "var_overturns":              ("count", "Decisions changed after VAR"),
    "var_rejected_overturns":     ("count", "Referee went to the monitor and kept the original decision"),
    "var_interventions_correct":  ("count", "Interventions the KMI panel backed"),
    "var_errors":                 ("count", "VAR errors judged by the KMI panel = missed + incorrect + wrongly rejected"),
    "var_errors_missed":          ("count", "VAR should have stepped in and didn't"),
    "var_errors_incorrect":       ("count", "VAR stepped in and shouldn't have"),
    "var_errors_wrongly_rejected": ("count", "Not defined by ESPN; presumably a correct VAR recommendation the referee turned down"),
    "onfield_errors_referee":     ("count", "Wrong key decisions by the referee"),
    "onfield_errors_ar":          ("count", "Wrong key decisions by assistant referees"),
    "onfield_errors_not_for_var": ("count", "Wrong on-field calls below the VAR bar ('not clear and obvious')"),
    "refereeing_errors_total":    ("count", "Total refereeing errors as the press reported them (scope not defined)"),
    "avg_var_delay_sec":          ("seconds", "Average delay VAR adds per match"),
    "penalties_awarded":          ("count", "All penalties awarded, VAR or not"),
    "var_goals_awarded":          ("count", "VAR overturns leading to a goal"),
    "var_goals_disallowed":       ("count", "VAR overturns ruling a goal out"),
    "var_penalties_awarded":      ("count", "Penalties given after VAR"),
    "var_penalties_cancelled":    ("count", "Penalties cancelled after VAR"),
    "var_red_cards":              ("count", "Red cards given after VAR"),
    "var_red_cards_cancelled":    ("count", "Red cards cancelled after VAR"),
}

# How far a row can be trusted, best first. Only the first three feed the comparison tables;
# 'unverified' and 'ambiguous' rows stay in the file as leads to chase, not as evidence.
STATUS_RANK = {"verified": 0, "derived": 1, "secondary": 2, "unverified": 3, "ambiguous": 4}
USABLE = ["verified", "derived", "secondary"]
FLAG = {"verified": "", "derived": "~", "secondary": "*"}   # marks shown next to values in tables

COLUMNS = ["season", "metric", "value", "unit", "through_round", "status", "source", "source_kind",
           "published", "source_url", "quote", "note", "accessed"]


def load():
    # dtype=str + keep_default_na=False: read everything as plain text first, so the checker sees
    # exactly what's in the file (pandas would otherwise turn blanks into NaN and "38" into 38.0).
    h = pd.read_csv(HISTORY, dtype=str, keep_default_na=False)
    problems = check(h)
    if problems:
        print(f"{len(problems)} problem(s) in {HISTORY.name}; fix these first:")
        for p in problems:
            print("  -", p)
        sys.exit(1)
    h["value"] = h["value"].astype(float)
    # Int64 (capital I) is pandas' whole-number type that allows blanks; plain int can't hold one.
    h["through_round"] = pd.to_numeric(h["through_round"]).astype("Int64")
    return h


def check(h):
    """Every rule a row must pass. Returns a list of problems (empty = all good)."""
    if list(h.columns) != COLUMNS:
        return [f"columns should be {COLUMNS}, found {list(h.columns)}"]
    problems = []
    for i, r in h.iterrows():
        where = f"line {i + 2} ({r['season']} {r['metric']})"   # +2: the header is line 1
        m = re.fullmatch(r"(\d{4})-(\d{2})", r["season"])
        if not m or (int(m[1]) + 1) % 100 != int(m[2]):
            problems.append(f"{where}: season should look like 2023-24")
        if r["metric"] not in METRICS:
            problems.append(f"{where}: unknown metric (add it to METRICS if it's new)")
        elif r["unit"] != METRICS[r["metric"]][0]:
            problems.append(f"{where}: unit should be {METRICS[r['metric']][0]}")
        try:
            v = float(r["value"])
            if r["unit"] == "pct" and not 0 <= v <= 100:
                problems.append(f"{where}: a percentage must be 0-100")
        except ValueError:
            problems.append(f"{where}: value '{r['value']}' is not a number")
        if r["through_round"] and not (r["through_round"].isdigit() and 1 <= int(r["through_round"]) <= FULL_SEASON):
            problems.append(f"{where}: through_round must be 1-38, or blank if unknown")
        if not r["through_round"] and not r["note"]:
            problems.append(f"{where}: window unknown, so the note must say what it covers")
        if r["status"] not in STATUS_RANK:
            problems.append(f"{where}: status must be one of {list(STATUS_RANK)}")
        if r["source_kind"] not in ("official", "press"):
            problems.append(f"{where}: source_kind must be official or press")
        if not r["source_url"].startswith("http"):
            problems.append(f"{where}: missing source_url")
        if r["status"] != "unverified" and not r["quote"]:
            problems.append(f"{where}: needs the quote the value came from")
    return problems


def pick(h):
    """One figure per season + metric + window. Official beats press; then verified > derived > secondary."""
    u = h[h["status"].isin(USABLE)].copy()
    u["kind_rank"] = (u["source_kind"] != "official").astype(int)
    u["status_rank"] = u["status"].map(STATUS_RANK)
    u = u.sort_values(["kind_rank", "status_rank"], kind="stable")   # stable: ties keep file order
    return u.drop_duplicates(["season", "metric", "through_round"])


def fmt(v):
    return f"{v:.0f}" if v == int(v) else f"{v:.1f}"


def window(r, full="full season", unknown="window unknown", part="to round {}"):
    # Check for blank first: pandas' missing value (pd.NA) can't answer "== 38" with True/False.
    if pd.isna(r):
        return unknown
    return full if r == FULL_SEASON else part.format(r)


def conflicts(h):
    """Same season, metric and window, but sources give different numbers."""
    u = h[h["status"].isin(USABLE)]
    groups = u.groupby(["season", "metric", "through_round"], dropna=False)
    return [(key, g) for key, g in groups if g["value"].nunique() > 1]


def this_season():
    """The same metrics for the current season, computed from the per-incident KMI data."""
    d = pd.read_csv(KMI, keep_default_na=False)
    onfield_ok = d["onfield_outcome"].str.startswith("Correct")
    overturned = d["var_overturn"] == "Y"
    var_ok = d["var_outcome"].str.startswith("Correct")
    stood_ok = onfield_ok.where(~overturned, var_ok)          # the decision that actually stood
    left_alone = ~onfield_ok & ~overturned & var_ok           # wrong, but "not clear and obvious"
    missed = ~onfield_ok & ~overturned & d["var_outcome"].str.startswith("Incorrect")
    incorrect = overturned & ~var_ok
    # The PL's on-field headline counts Referee + Fourth Official calls (this reproduced its
    # published totals exactly after rounds 9 and 10); assistant referees' offside calls are left out.
    pl_calls = d["official"].isin(["Referee", "Fourth Official"])
    values = {
        "kmi_onfield_correct_pct": 100 * onfield_ok[pl_calls].mean(),
        "kmi_after_var_correct_pct": 100 * (stood_ok | left_alone).mean(),
        "kmi_stood_correct_pct": 100 * stood_ok.mean(),
        "var_overturns": overturned.sum(),
        "var_interventions_correct": (overturned & var_ok).sum(),
        "var_errors": (missed | incorrect).sum(),
        "var_errors_missed": missed.sum(),
        "var_errors_incorrect": incorrect.sum(),
        "onfield_errors_referee": (~onfield_ok & (d["official"] == "Referee")).sum(),
        "onfield_errors_ar": (~onfield_ok & (d["official"] == "Assistant Referee")).sum(),
        "onfield_errors_not_for_var": left_alone.sum(),
    }
    return int(d["round"].max()), {k: float(v) for k, v in values.items()}


def main():
    h = load()
    best = pick(h)
    seasons = sorted(h["season"].unique())
    status_counts = h["status"].value_counts().reindex(STATUS_RANK).fillna(0).astype(int)
    print(f"{HISTORY.name}: {len(h)} figures, {h['metric'].nunique()} metrics, "
          f"{len(seasons)} seasons ({seasons[0]} to {seasons[-1]})")
    print("   " + ", ".join(f"{n} {s}" for s, n in status_counts.items()))
    print("   ~ = derived by us from the source, * = second-hand (source cites someone we couldn't read)\n")

    # --- 1. Counts over a whole season. Only full-season figures, so every column is like-for-like.
    full = best[(best["through_round"] == FULL_SEASON) & (best["unit"] != "pct")]
    table = full.assign(cell=full["value"].map(fmt) + full["status"].map(FLAG)) \
                .pivot(index="metric", columns="season", values="cell")
    table = table.reindex([m for m in METRICS if m in table.index]).fillna("")
    print("1. FULL-SEASON COUNTS")
    print(table.to_string(), "\n")

    # --- 2. Percentages: a rate doesn't depend on how many rounds were played, so the most
    #        complete window available is shown, labelled (R23 = up to round 23).
    pcts = best[best["unit"] == "pct"].sort_values("through_round", na_position="first")
    pcts = pcts.drop_duplicates(["season", "metric"], keep="last")
    tag = pcts["through_round"].map(lambda r: window(r, full="", unknown=" (part)", part=" (R{})"))
    pcts = pcts.assign(cell=pcts["value"].map(fmt) + "%" + pcts["status"].map(FLAG) + tag)
    rnd, now = this_season()
    rates = pcts.pivot(index="metric", columns="season", values="cell")
    for m in ["kmi_onfield_correct_pct", "kmi_after_var_correct_pct", "kmi_stood_correct_pct"]:
        if m not in rates.index:
            rates.loc[m] = pd.NA
        rates.loc[m, f"{THIS_SEASON} (R{rnd})"] = f"{now[m]:.0f}%"
    print("2. ACCURACY RATES (on-field vs after VAR)")
    print(rates.reindex([m for m in METRICS if m in rates.index]).fillna("").to_string(), "\n")

    # --- 3. VAR's own errors at the same point of the season. Different windows only become
    #        comparable as a rate, so everything is converted to errors per 10 rounds.
    print("3. VAR ERRORS AT THE SAME STAGE OF THE SEASON")
    print("   (last column assumes errors are spread evenly through a season: a fair rough guide, not exact)")
    rows = []
    stage = best[best["metric"].isin(["var_errors", "var_errors_missed", "var_errors_incorrect"])
                 & best["through_round"].notna()]
    for (season, r), g in stage.groupby(["season", "through_round"]):
        v = dict(zip(g["metric"], g["value"]))
        if "var_errors" in v:
            rows.append((season, int(r), v.get("var_errors_missed"), v.get("var_errors_incorrect"), v["var_errors"]))
    rows.append((THIS_SEASON, rnd, now["var_errors_missed"], now["var_errors_incorrect"], now["var_errors"]))
    print(f"   {'season':9} {'window':>8} {'missed':>8} {'incorrect':>10} {'total':>7}  per 10 rounds")
    for season, r, mi, inc, tot in sorted(rows, key=lambda x: (x[1], x[0])):
        label = window(r, full="full", part="R{}")
        show = lambda x: "-" if x is None or pd.isna(x) else fmt(x)
        print(f"   {season:9} {label:>8} {show(mi):>8} {show(inc):>10} {fmt(tot):>7}  {10 * tot / r:5.1f}")
    pace = now["var_errors"] / rnd * FULL_SEASON
    print(f"   {THIS_SEASON} at this pace: about {pace:.0f} VAR errors over a full season "
          f"(a straight-line guess, not a forecast)\n")

    # --- 4. Where sources disagree. Shown, not hidden: each one is a decision for the video.
    clashes = conflicts(h)
    print(f"4. SOURCES THAT DISAGREE ({len(clashes)})")
    for (season, metric, r), g in clashes:
        label = window(r)
        vals = "; ".join(f"{fmt(v)} ({s})" for v, s in zip(g["value"], g["source"]))
        print(f"   {season} {metric} [{label}]: {vals}")
    parked = h[~h["status"].isin(USABLE)]
    print(f"   Not used until checked ({len(parked)}):")
    for _, r in parked.iterrows():
        print(f"   - {r['season']} {r['metric']} = {fmt(r['value'])} [{window(r['through_round'])}] "
              f"({r['status']}, {r['source']}): {r['note']}")
    print()

    # --- 5. What's still missing for each season (full-season figures only).
    print("5. GAPS TO FILL (key metrics with no usable full-season figure)")
    key = ["kmi_after_var_correct_pct", "var_overturns", "var_errors", "var_errors_missed", "var_errors_incorrect"]
    have = set(zip(best.loc[best["through_round"] == FULL_SEASON, "season"],
                   best.loc[best["through_round"] == FULL_SEASON, "metric"]))
    for season in seasons:
        if season == "2018-19":
            continue   # pre-VAR: only the on-field baseline exists, by definition
        missing = [m for m in key if (season, m) not in have]
        if missing:
            print(f"   {season}: {', '.join(missing)}")


if __name__ == "__main__":
    main()
