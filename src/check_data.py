#!/usr/bin/env python3
"""Availability check for the capstone forecasting project's data sources.

Run this before starting weekend 1, and any time something looks broken:

    ~/miniconda3/bin/python src/check_data.py

Uses only the standard library, so it runs on any Python 3 with no installs.
Exit code 0 = both sources usable. Non-zero = something moved; read the output.
"""

import csv
import io
import json
import sys
import urllib.request
from collections import defaultdict

FLUSIGHT = (
    "https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/"
    "main/target-data/target-hospital-admissions.csv"
)
SODA = (
    "https://data.cdc.gov/resource/vdzy-6i9v.json"
    "?jurisdiction=USA"
    "&$select=weekendingdate,totalconfflunewadm,totalconfflunewadmhosprep"
    "&$order=weekendingdate%20DESC&$limit=400"
)

TIMEOUT = 60
problems = []


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "capstone-check/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def check_flusight():
    print("1. FluSight hub target series (the modelling history)")
    try:
        raw = get(FLUSIGHT).decode("utf-8")
    except Exception as e:
        problems.append(f"FluSight target CSV unreachable: {e}")
        print(f"   FAIL — {e}\n")
        return {}

    rows = list(csv.DictReader(io.StringIO(raw)))
    if not rows:
        problems.append("FluSight CSV downloaded but is empty")
        print("   FAIL — empty file\n")
        return {}

    dates = sorted(r["date"] for r in rows)
    locs = {r["location_name"] for r in rows}
    us = {r["date"]: float(r["value"]) for r in rows if r["location"] == "US"}

    print(f"   rows            {len(rows):,}")
    print(f"   columns         {list(rows[0])}")
    print(f"   date range      {dates[0]} -> {dates[-1]}")
    print(f"   locations       {len(locs)}")
    print(f"   US weekly obs   {len(us)}  ({len(us) / 52:.1f} seasonal cycles)")
    if us:
        peak = max(us, key=us.get)
        print(f"   US range        {min(us.values()):,.0f} to {max(us.values()):,.0f}"
              f"  (peak week {peak})")

    if len(us) < 150:
        problems.append(
            f"Only {len(us)} national weeks — the plan assumes ~231. Seasonal models need history."
        )
        print(f"   WARN — expected ~231 national weeks, found {len(us)}")
    else:
        print("   OK — enough history to fit and backtest")
    print()
    return us


def check_soda():
    print("2. CDC Socrata vdzy-6i9v (the live weekly extension)")
    try:
        rows = json.loads(get(SODA).decode("utf-8"))
    except Exception as e:
        problems.append(f"CDC SODA endpoint unreachable: {e}")
        print(f"   FAIL — {e}\n")
        return {}

    if isinstance(rows, dict) and rows.get("error"):
        problems.append(f"CDC SODA returned an error: {rows.get('message')}")
        print(f"   FAIL — {rows.get('message')}\n")
        return {}

    series = {r["weekendingdate"][:10]: float(r["totalconfflunewadm"])
              for r in rows if r.get("totalconfflunewadm") is not None}
    hosp = {r["weekendingdate"][:10]: r.get("totalconfflunewadmhosprep")
            for r in rows}
    weeks = sorted(series)

    print(f"   weeks returned  {len(weeks)}")
    if weeks:
        print(f"   date range      {weeks[0]} -> {weeks[-1]}")
        print(f"   latest value    {series[weeks[-1]]:,.0f} flu admissions"
              f"  ({hosp.get(weeks[-1])} hospitals reporting)")
        print("   NOTE — this source holds a rolling window only. History comes from FluSight.")
    else:
        problems.append("CDC SODA returned no usable rows")
        print("   FAIL — no rows")
    print()
    return series


def check_overlap(fs, sd):
    print("3. Do the two sources agree? (they did not on 2026-09-05 — expected)")
    common = sorted(set(fs) & set(sd))
    if not common:
        print("   No overlapping weeks right now — normal in the off-season.\n")
        return
    print(f"   {'week':<12}{'FluSight':>10}{'CDC SODA':>10}{'ratio':>8}")
    ratios = []
    for w in common[:8]:
        a, b = fs[w], sd[w]
        r = a / b if b else float("nan")
        ratios.append(r)
        print(f"   {w:<12}{a:>10,.0f}{b:>10,.0f}{r:>8.2f}")
    if ratios:
        avg = sum(ratios) / len(ratios)
        print(f"   mean ratio      {avg:.3f}")
        print("   Reconciling this is weekend-1 work. Do not blend the two series until you"
              " know why they differ.")
    print()


def check_benchmark():
    print("4. FluSight model-output (the benchmark to score against)")
    try:
        data = json.loads(
            get("https://api.github.com/repos/cdcepi/FluSight-forecast-hub/contents/model-output")
            .decode("utf-8")
        )
    except Exception as e:
        print(f"   SKIP — GitHub API unavailable ({e}). Not fatal; the repo can be cloned.\n")
        return
    if not isinstance(data, list):
        print("   SKIP — unexpected response from GitHub API\n")
        return
    names = [d["name"] for d in data]
    want = ["FluSight-baseline", "FluSight-ensemble"]
    print(f"   models submitting  {len(names)}")
    for w in want:
        mark = "OK  " if w in names else "MISSING"
        print(f"   {mark} {w}")
        if w not in names:
            problems.append(f"{w} not found in model-output — the benchmark comparison changes")
    print()


def main():
    print("=" * 72)
    print("Capstone data availability check")
    print("=" * 72 + "\n")
    fs = check_flusight()
    sd = check_soda()
    if fs and sd:
        check_overlap(fs, sd)
    check_benchmark()

    print("=" * 72)
    if problems:
        print("PROBLEMS FOUND:")
        for p in problems:
            print(f"  - {p}")
        print("\nSomething moved. Re-check the catalogue before changing the plan:")
        print("  https://data.cdc.gov/browse?q=hospital%20respiratory")
        return 1
    print("All sources available. Good to start weekend 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
