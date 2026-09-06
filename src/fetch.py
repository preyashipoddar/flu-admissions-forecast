#!/usr/bin/env python3
"""Weekly snapshot of the two US respiratory-admissions data sources.

Run by .github/workflows/weekly-snapshot.yml every Thursday, and runnable by hand:

    python src/fetch.py

WHY THIS USES ONLY THE STANDARD LIBRARY
---------------------------------------
This script is the one piece that has to keep working unattended for months. Every
third-party dependency is a way for it to break while nobody is watching, so it has
none. pandas belongs in the notebooks, not here.

WHY IT SAVES A DATED SNAPSHOT INSTEAD OF OVERWRITING
----------------------------------------------------
Public health series are revised after publication: the number published for a given
week is not the number that series shows a month later. Grading a forecast against
revised data is cheating, because the model never saw the numbers it is graded on.
Honest evaluation uses the data as it was known at the time -- "vintages".

Keeping every weekly pull builds that vintage archive automatically, as a side effect
of the job already running. It cannot be reconstructed later, which is why this job
started before the modelling did.
"""

import csv
import gzip
import io
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SNAP = os.path.join(ROOT, "data", "snapshots")
LOG = os.path.join(ROOT, "data", "vintages.md")

FLUSIGHT = ("https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/"
            "main/target-data/target-hospital-admissions.csv")
SODA = ("https://data.cdc.gov/resource/vdzy-6i9v.json"
        "?$select=weekendingdate,jurisdiction,totalconfflunewadm,"
        "totalconfc19newadm,totalconfrsvnewadm,totalconfflunewadmhosprep"
        "&$order=weekendingdate%20DESC&$limit=5000")

TIMEOUT = 120


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "flu-admissions-forecast/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def fetch_flusight(stamp):
    """Full FluSight target series, stored gzipped -- this is the modelling history."""
    raw = get(FLUSIGHT)
    path = os.path.join(SNAP, f"flusight_target_{stamp}.csv.gz")
    # mtime=0 so the output is byte-deterministic. gzip normally writes the
    # compression time into its header, which makes identical data produce a
    # different file on every run -- so git would report a change every week
    # whether or not the data moved. With this, a diff means the data actually
    # changed, which is exactly the signal the revision analysis needs.
    with open(path, "wb") as fh:
        with gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
            gz.write(raw)

    rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
    us = sorted((r for r in rows if r["location"] == "US"), key=lambda r: r["date"])
    latest = us[-1] if us else {}
    return {
        "file": os.path.basename(path),
        "bytes": len(raw),
        "rows": len(rows),
        "us_weeks": len(us),
        "latest_week": latest.get("date"),
        "latest_us_value": latest.get("value"),
    }


def fetch_soda(stamp):
    """CDC Socrata rolling window -- the live weekly extension."""
    rows = json.loads(get(SODA).decode("utf-8"))
    if isinstance(rows, dict) and rows.get("error"):
        raise RuntimeError(f"CDC SODA error: {rows.get('message')}")

    path = os.path.join(SNAP, f"cdc_soda_{stamp}.csv")
    cols = ["weekendingdate", "jurisdiction", "totalconfflunewadm",
            "totalconfc19newadm", "totalconfrsvnewadm", "totalconfflunewadmhosprep"]
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    usa = [r for r in rows if r.get("jurisdiction") == "USA"]
    usa.sort(key=lambda r: r["weekendingdate"])
    latest = usa[-1] if usa else {}
    return {
        "file": os.path.basename(path),
        "rows": len(rows),
        "latest_week": (latest.get("weekendingdate") or "")[:10],
        "latest_us_flu": latest.get("totalconfflunewadm"),
        "hospitals_reporting": latest.get("totalconfflunewadmhosprep"),
    }


HEADER = (
    "# Vintage log\n\n"
    "One row per weekly run. Each row is the data **as published that week** --\n"
    "later revisions do not change earlier rows. That is the point.\n\n"
    "| Run date | FluSight latest week | US flu adm | CDC SODA latest week "
    "| US flu adm | Hospitals reporting |\n"
    "|---|---|---|---|---|---|\n"
)


def append_log(stamp, fs, sd):
    """One row per run date, newest last. Makes `git log` on this repo legible.

    Rewrites rather than appends so that re-running on the same day (the manual
    "Run workflow" button, or a retry after a failure) replaces that day's row
    instead of duplicating it.
    """
    row = (f"| {stamp} | {fs.get('latest_week')} | {fs.get('latest_us_value')} "
           f"| {sd.get('latest_week')} | {sd.get('latest_us_flu')} "
           f"| {sd.get('hospitals_reporting')} |\n")

    rows = {}
    if os.path.exists(LOG):
        for line in open(LOG):
            if line.startswith("| ") and not line.startswith("| Run date"):
                rows[line.split("|")[1].strip()] = line

    rows[stamp] = row
    with open(LOG, "w") as f:
        f.write(HEADER)
        for key in sorted(rows):
            f.write(rows[key])


def main():
    os.makedirs(SNAP, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    print(f"snapshot {stamp}")

    failures = []
    try:
        fs = fetch_flusight(stamp)
        print(f"  FluSight: {fs['rows']:,} rows, {fs['us_weeks']} US weeks, "
              f"latest {fs['latest_week']} = {fs['latest_us_value']}")
    except Exception as e:
        fs = {}
        failures.append(f"FluSight: {e}")
        print(f"  FluSight FAILED: {e}")

    try:
        sd = fetch_soda(stamp)
        print(f"  CDC SODA: {sd['rows']:,} rows, latest {sd['latest_week']} = "
              f"{sd['latest_us_flu']} ({sd['hospitals_reporting']} hospitals reporting)")
    except Exception as e:
        sd = {}
        failures.append(f"CDC SODA: {e}")
        print(f"  CDC SODA FAILED: {e}")

    if not fs and not sd:
        print("both sources failed -- nothing written")
        return 1

    append_log(stamp, fs, sd)

    if failures:
        # One source down is worth flagging loudly but is not a reason to lose the other.
        print("\nPARTIAL: " + "; ".join(failures))
        return 2
    print("ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
