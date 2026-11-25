"""First look at the season's KMI decisions: the headline numbers for the VAR video.

Run after update.py:  py analyse.py
"""
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")   # Windows terminals choke on some characters otherwise

DATA = Path(__file__).parent / "data" / "processed" / "kmi_decisions.csv"
UNANIMOUS = {"5:0", "0:5"}


def pct(part, whole):
    return f"{part / whole:.0%}" if whole else "-"


def main():
    # keep_default_na=False: by default pandas turns the text "N/A" into an empty value, and a
    # check like == "N/A" then silently matches nothing. Here N/A means "VAR couldn't review it".
    d = pd.read_csv(DATA, keep_default_na=False)

    # --- Helper columns: True/False flags that make the questions below one-liners ---
    d["onfield_correct"] = d["onfield_outcome"].str.startswith("Correct")
    d["overturned"] = d["var_overturn"] == "Y"
    d["var_correct"] = d["var_outcome"].str.startswith("Correct")
    d["split_panel"] = ~d["onfield_votes"].isin(UNANIMOUS)
    # The decision that actually stood after VAR: the referee's call, unless VAR overturned it,
    # in which case it is right only if the panel backed the overturn.
    d["final_correct"] = d["onfield_correct"].where(~d["overturned"], d["var_correct"])
    # Wrong on the pitch, not overturned, and the panel says the VAR outcome was wrong. That covers
    # two different failures, and only the commentary tells them apart:
    not_fixed = (~d["onfield_correct"]) & (~d["overturned"]) & d["var_outcome"].str.startswith("Incorrect")
    #  - VAR rightly sent the referee to the monitor, and the referee kept the wrong call (R10-012).
    #    Wording may change in future rounds, so check new cases by eye.
    d["rejected_at_monitor"] = not_fixed & d["commentary"].str.contains("after the on-field review", case=False)
    #  - VAR should have stepped in and didn't.
    d["missed_by_var"] = not_fixed & ~d["rejected_at_monitor"]
    # Wrong on the pitch, but the panel says VAR was right NOT to step in ("not clear and obvious").
    d["wrong_but_left_alone"] = (~d["onfield_correct"]) & (~d["overturned"]) & d["var_correct"]

    n = len(d)
    rounds = d["round"].nunique()
    wrong = (~d["onfield_correct"]).sum()
    print(f"KMI DECISIONS: {n} incidents from {rounds} rounds\n")

    print("1. HOW OFTEN ARE OFFICIALS RIGHT ON THE PITCH?")
    print(f"   {d['onfield_correct'].sum()} of {n} correct ({pct(d['onfield_correct'].sum(), n)}); {wrong} wrong")
    ref = d[d["official"] == "Referee"]
    print(f"   Referee calls only: {pct(ref['onfield_correct'].sum(), len(ref))} of {len(ref)} "
          f"(the Premier League's own headline figure counts these)\n")

    print("2. DOES VAR MAKE IT BETTER?")
    print(f"   Correct before VAR: {pct(d['onfield_correct'].sum(), n)}   "
          f"after VAR: {pct(d['final_correct'].sum(), n)}  (the decision that actually stood)")
    # The Premier League's own "after VAR" figure also counts wrong calls that VAR was right to
    # leave alone ("not clear and obvious") as correct. Same data, different question.
    pl_style = d["final_correct"] | d["wrong_but_left_alone"]
    print(f"   Premier League's way of counting: {pct(pl_style.sum(), n)} "
          f"(counts the 'not clear and obvious' wrong calls as correct)")
    ov = d[d["overturned"]]
    print(f"   VAR overturned {len(ov)} decisions; the panel backed {ov['var_correct'].sum()} of them")
    print(f"   Of the {wrong} wrong calls on the pitch:")
    wrong_calls = d[~d["onfield_correct"]]
    print(f"     fixed by VAR:                          {(wrong_calls['overturned'] & wrong_calls['var_correct']).sum()}")
    print(f"     VAR stepped in but still got it wrong:  {(wrong_calls['overturned'] & ~wrong_calls['var_correct']).sum()}")
    print(f"     missed by VAR (should have acted):      {d['missed_by_var'].sum()}")
    print(f"     sent to the monitor, wrong call kept:   {d['rejected_at_monitor'].sum()}")
    print(f"     left alone, 'not clear and obvious':    {d['wrong_but_left_alone'].sum()}")
    print(f"     VAR not allowed to review (2nd yellow): {(wrong_calls['var_overturn'] == 'N/A').sum()}\n")

    print("3. CAN THE PANEL AGREE?")
    split = d[d["split_panel"]]
    close = d[d["onfield_votes"].isin({"3:2", "2:3"})]
    print(f"   Split votes on the on-field call: {len(split)} of {n} ({pct(len(split), n)})")
    print(f"   Decided 3:2 either way (one vote from flipping): {len(close)}")
    for _, r in close.iterrows():
        print(f"     {r['incident_id']}  {r['home_team']} v {r['away_team']}, {r['time']}: "
              f"{r['decision_type']} ({r['onfield_votes']})")
    print()

    print("4. WHICH DECISIONS GO WRONG MOST?")
    by_type = d.groupby("decision_type").agg(incidents=("incident_id", "size"),
                                             wrong=("onfield_correct", lambda s: (~s).sum()))
    by_type["wrong_rate"] = by_type["wrong"] / by_type["incidents"]
    by_type = by_type.sort_values("wrong_rate", ascending=False)
    for t, r in by_type.iterrows():   # int(): iterrows hands back floats when a row mixes types
        print(f"   {t:36} {int(r['wrong']):>2} wrong of {int(r['incidents']):>3}  ({r['wrong_rate']:.0%})")
    print()

    print("5. WRONG ON-FIELD CALLS BY ROUND")
    for rnd, g in d.groupby("round"):
        w = (~g["onfield_correct"]).sum()
        print(f"   Round {rnd:>2}: {w:>2} wrong of {len(g):>2}  {'#' * w}")
    print()

    print("6. WRONG ON-FIELD CALLS IN EACH CLUB'S MATCHES")
    print("   (counts every error in games the club played, for or against them)")
    long = pd.concat([d.assign(club=d["home_team"]), d.assign(club=d["away_team"])])
    per_club = long.groupby("club").agg(incidents=("incident_id", "size"),
                                        wrong=("onfield_correct", lambda s: (~s).sum()))
    for club, r in per_club.sort_values(["wrong", "incidents"], ascending=False).iterrows():
        print(f"   {club:24} {r['wrong']:>2} wrong of {r['incidents']:>2} incidents")
    print()

    print("7. WHEN VAR OVERTURNS A CALL: FACT OR OPINION?")
    # The PL labels measurable overturns 'factual' (offside lines, ball out of play, handball by
    # the scorer). Everything else is VAR swapping the referee's judgement for its own. The panel's
    # vote on the VAR call shows how settled each kind really is. Unlabelled overturns count as
    # judgement calls.
    ov = d[d["overturned"]].copy()
    ov["factual"] = ov["var_outcome"].str.contains("factual", case=False)
    for label, g in [("Factual", ov[ov["factual"]]), ("Judgement calls", ov[~ov["factual"]])]:
        split_vote = ~g["var_votes"].isin(UNANIMOUS)
        close_vote = g["var_votes"].isin({"3:2", "2:3"})
        print(f"   {label:16} {len(g):>2} overturns: panel split on {split_vote.sum()} "
              f"({pct(split_vote.sum(), len(g))}), {close_vote.sum()} of them 3:2")
    for _, r in ov[~ov["factual"] & ~ov["var_votes"].isin(UNANIMOUS)].iterrows():
        print(f"     {r['incident_id']}  {r['home_team']} v {r['away_team']}: "
              f"{r['decision_type']} overturned, panel {r['var_votes']}")
    print()

    print("8. VAR'S OWN ERRORS, AND HOW OBVIOUS THEY WERE")
    # A unanimous panel (5:0 or 0:5 on the VAR call) = all five experts saw it. Those are the
    # 'how did they not see that?' moments that wreck trust.
    errs = d[d["missed_by_var"] | d["rejected_at_monitor"] | (d["overturned"] & ~d["var_correct"])].copy()
    errs["kind"] = "missed"
    errs.loc[errs["rejected_at_monitor"], "kind"] = "kept at monitor"
    errs.loc[errs["overturned"], "kind"] = "wrong overturn"
    obvious = errs["var_votes"].isin(UNANIMOUS)
    print(f"   {len(errs)} VAR errors; the panel was unanimous on {obvious.sum()}")
    for _, r in errs.iterrows():
        print(f"     {r['incident_id']}  {r['home_team']} v {r['away_team']}, {r['time']}: "
              f"{r['decision_type']}  [{r['kind']}, panel {r['var_votes']}"
              f"{', unanimous' if r['var_votes'] in UNANIMOUS else ''}]")


if __name__ == "__main__":
    main()
