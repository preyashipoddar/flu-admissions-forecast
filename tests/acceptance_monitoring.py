#!/usr/bin/env python3
"""Acceptance test for the weekend-4 monitoring job.

    ~/miniconda3/bin/python profile-building/capstone/weekend4_acceptance.py ~/projects/flu-admissions-forecast

Checks the FILES your job produces against the contract in weekend4-spec.md. It never reads your
source, so it cannot tell you how to write it -- only whether it does what it promised.

Standard library only. Exit 0 = all pass.
"""

import csv
import os
import sys
from datetime import datetime

PRED_COLS = {"made_on", "target_week", "horizon", "mean", "q80", "q90", "q95"}
SCORE_COLS = {"target_week", "made_on", "horizon", "predicted", "actual", "abs_error"}

passed, failed, warned = [], [], []


def ok(msg):
    passed.append(msg)
    print(f"  PASS  {msg}")


def bad(msg):
    failed.append(msg)
    print(f"  FAIL  {msg}")


def warn(msg):
    warned.append(msg)
    print(f"  WARN  {msg}")


def load(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def d(s):
    return datetime.strptime(s.strip()[:10], "%Y-%m-%d").date()


def check_predictions(path):
    print("\n[1] data/predictions.csv")
    if not os.path.exists(path):
        bad("file does not exist -- the job has not run, or writes somewhere else")
        return []
    rows = load(path)
    if not rows:
        bad("file is empty")
        return []
    ok(f"exists, {len(rows)} rows")

    missing = PRED_COLS - set(rows[0])
    if missing:
        bad(f"missing columns: {sorted(missing)}")
    else:
        ok(f"has all required columns")

    # uniqueness on (made_on, target_week)
    seen, dupes = set(), []
    for r in rows:
        k = (r.get("model", "").strip(), r.get("made_on", "").strip(), r.get("target_week", "").strip())
        if k in seen:
            dupes.append(k)
        seen.add(k)
    if dupes:
        bad(f"{len(dupes)} duplicate (model, made_on, target_week) rows, e.g. {dupes[0]} "
            "-- re-running the job must not append again")
    else:
        ok("(model, made_on, target_week) is unique -- job is idempotent")

    # horizons
    hs = {r.get("horizon", "").strip() for r in rows}
    if hs and not hs <= {"1", "2", "3", "4"}:
        warn(f"horizons present: {sorted(hs)} (spec says 1-4)")
    else:
        ok("horizons are 1-4")

    # forecast ordering: mean <= q80 <= q90 <= q95
    badorder = 0
    for r in rows:
        try:
            m, a, b, c = (float(r["mean"]), float(r["q80"]), float(r["q90"]), float(r["q95"]))
            if not (m <= a <= b <= c):
                badorder += 1
        except (KeyError, ValueError):
            pass
    if badorder:
        bad(f"{badorder} rows where mean <= q80 <= q90 <= q95 does not hold -- "
            "quantiles cannot cross")
    else:
        ok("quantiles are correctly ordered in every row")

    # a forecast must be about the future
    future_bad = 0
    for r in rows:
        try:
            if d(r["target_week"]) <= d(r["made_on"]):
                future_bad += 1
        except (KeyError, ValueError):
            pass
    if future_bad:
        bad(f"{future_bad} rows predict a week that was already over when the forecast was made")
    else:
        ok("every prediction is about a week later than the day it was made")
    return rows


def check_scores(path, preds):
    print("\n[2] data/scores.csv")
    if not os.path.exists(path):
        warn("file does not exist -- expected until flu season restarts and there is "
             "something to score. Re-run this test once it appears.")
        return []
    rows = load(path)
    if not rows:
        warn("file is empty -- fine off-season, but the job must not crash on it")
        return []
    ok(f"exists, {len(rows)} rows")

    missing = SCORE_COLS - set(rows[0])
    if missing:
        bad(f"missing columns: {sorted(missing)}")
    else:
        ok("has all required columns")

    seen, dupes = set(), []
    for r in rows:
        k = (r.get("model", "").strip(), r.get("made_on", "").strip(), r.get("target_week", "").strip())
        if k in seen:
            dupes.append(k)
        seen.add(k)
    if dupes:
        bad(f"{len(dupes)} predictions scored more than once, e.g. {dupes[0]}")
    else:
        ok("no prediction is scored twice")

    # THE IMPORTANT ONE
    leaks = [r for r in rows if _leak(r)]
    if leaks:
        bad(f"{len(leaks)} rows where made_on >= target_week -- the forecast was made after the "
            "outcome was knowable. This is the one rule in the spec that must not break.")
    else:
        ok("no lookahead: every score is of a forecast made before its target week")

    # scores must trace back to a logged prediction
    if preds:
        key = lambda r: (r.get("model", "").strip() or "SARIMA", r.get("made_on", "").strip(),
                         r.get("target_week", "").strip())
        known = {key(r) for r in preds}
        orphans = [r for r in rows if key(r) not in known]
        if orphans:
            bad(f"{len(orphans)} scored rows have no matching row in predictions.csv -- "
                "a score must trace back to a forecast that was logged in advance")
        else:
            ok("every score traces back to a logged prediction")

    # arithmetic
    wrong = 0
    for r in rows:
        try:
            if abs(abs(float(r["actual"]) - float(r["predicted"])) - float(r["abs_error"])) > 0.51:
                wrong += 1
        except (KeyError, ValueError):
            pass
    if wrong:
        bad(f"{wrong} rows where abs_error != |actual - predicted|")
    else:
        ok("abs_error matches |actual - predicted|")
    return rows


def _leak(r):
    try:
        return d(r["made_on"]) >= d(r["target_week"])
    except (KeyError, ValueError):
        return False


def check_workflow(repo):
    print("\n[3] scheduling")
    wf = os.path.join(repo, ".github", "workflows")
    if not os.path.isdir(wf):
        bad("no .github/workflows directory")
        return
    files = [f for f in os.listdir(wf) if f.endswith((".yml", ".yaml"))]
    text = "\n".join(open(os.path.join(wf, f)).read() for f in files)
    ok(f"{len(files)} workflow file(s): {', '.join(files)}")
    if "schedule" in text and "cron" in text:
        ok("something is on a schedule")
    else:
        bad("no cron schedule found -- a job you have to run by hand is not monitoring")
    if "exit 1" in text or "::error" in text:
        ok("a failure path exists (this is the alert)")
    else:
        warn("no 'exit 1' or '::error' found -- how does the job tell you it drifted?")


def main():
    repo = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/projects/flu-admissions-forecast")
    repo = os.path.expanduser(repo)
    print("=" * 72)
    print(f"Weekend 4 acceptance test\nrepo: {repo}")
    print("=" * 72)
    if not os.path.isdir(repo):
        print(f"\nNo such directory: {repo}")
        return 2

    preds = check_predictions(os.path.join(repo, "data", "predictions.csv"))
    check_scores(os.path.join(repo, "data", "scores.csv"), preds)
    check_workflow(repo)

    print("\n" + "=" * 72)
    print(f"{len(passed)} passed, {len(failed)} failed, {len(warned)} warnings")
    if failed:
        print("\nFailures:")
        for f in failed:
            print(f"  - {f}")
        return 1
    print("\nAll checks passed. Now the real test: explain every line of it without looking.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
