# Forecasting weekly US respiratory hospital admissions

Forecasting weekly hospital admissions for confirmed influenza four weeks ahead, with calibrated
prediction intervals, evaluated the way CDC evaluates its own public forecasting challenge — and
translated into the staffing decision the forecast actually exists to support.

**Status: in progress.** The baseline is measured and the weekly data collection is live. Models
are next. Findings below are current as of the date shown and will be updated as they change.

---

## The baseline — the number everything is measured against

Before fitting anything, the dumbest reasonable forecast was scored: **predict each week using the
same week one year earlier** (seasonal naive).

| | |
|---|---|
| Method | seasonal naive (52-week lag) |
| **MAE** | **4,780 admissions** |
| Weeks scored | 179 |
| Period | 2023-02-04 → 2026-07-04 |

Seasonal naive is genuinely hard to beat on seasonal data, and most portfolio forecasting projects
skip it. Without it, an error figure means nothing: no model here gets reported except as a margin
against this number.

## Why that baseline fails — and what a model has to fix

Across four seasons the epidemic peak varies in **two independent ways**:

| Season | Peak admissions | Peak week |
|---|---|---|
| 2022-23 | 26,835 | 3 Dec |
| 2023-24 | 21,720 | 30 Dec |
| 2024-25 | **55,718** | 8 Feb |
| 2025-26 | 42,626 | 3 Jan |

**Amplitude varies 2.6x. Timing varies by 10 weeks.** A 52-week lag assumes both are fixed, so it
is wrong on height *and* phase — and a phase error on a curve this steep aligns a peak week against
an off-peak week, which is where the 4,780 comes from. The 2024-25 season also double-peaked:
39,662 on 4 Jan, back down to 31,876 on 11 Jan, then a true peak of 55,718 on 8 Feb.

Series range: **223** admissions (Sep 2024) to **55,718** (Feb 2025) — a factor of 250. Percentage
error is therefore reported only in season; MAE and WIS are the headline metrics.

---

## Data

| Source | Role | Coverage |
|---|---|---|
| [FluSight forecast hub](https://github.com/cdcepi/FluSight-forecast-hub) `target-data/target-hospital-admissions.csv` | Modelling history | 2022-02-05 → 2026-07-04, 53 locations, 231 national weeks |
| [CDC Socrata `vdzy-6i9v`](https://data.cdc.gov/d/vdzy-6i9v) | Live weekly extension | Rolling ~20-week window, refreshed Wednesdays |

**The two sources disagree**, systematically: on overlapping weeks FluSight runs 3–17% higher than
the CDC Socrata series, converging to about 7%. The cause is not yet established — candidate
explanations are a different jurisdiction set in the national aggregate, a different
confirmed/suspected inclusion rule, or revision timing. **The series are not blended until that is
resolved**; modelling uses FluSight, which is the benchmark-consistent one.

The CDC series also carries `totalconfflunewadmhosprep`, the number of hospitals reporting each
week. That is a coverage denominator and a real confound: admissions can rise because more
hospitals reported, not because more people were admitted.

### Availability check

```bash
python src/check_data.py
```

Standard library only. Verifies both sources, prints coverage, and exits non-zero if anything moved.

---

## The vintage archive

`.github/workflows/weekly-snapshot.yml` runs every Thursday, pulls both sources, and commits a
dated snapshot to `data/snapshots/`. `data/vintages.md` logs one row per run.

This is not a backup. Public health series are **revised after publication** — the value published
for a given week is not the value that series shows a month later. Evaluating a forecast against
revised data is cheating, because the model never saw the numbers it is being graded on. Honest
evaluation uses the data **as it was known at the time**.

Keeping every weekly pull builds that vintage archive automatically, as a side effect of a job
that already has to run. It cannot be reconstructed after the fact, which is why the collector was
built before the models were.

`src/fetch.py` uses **only the Python standard library**, and the workflow installs nothing. A job
meant to run unattended for months should not depend on anything that can change underneath it.

---

## Evaluation plan

Scored the way CDC scores FluSight, so the results are comparable to real submissions:

- **Chronological splits only.** Train on the past, test on the future.
- **Rolling-origin backtesting** — refit at successive cutoffs, average across them, rather than
  reporting one lucky window.
- **Error per horizon** (1, 2, 3, 4 weeks) — never one blended figure. Error grows with distance.
- **Weighted interval score (WIS)** alongside MAE. WIS grades the *interval*, not the point
  estimate, which is the thing an operational user actually needs.
- **Coverage check** — of the weeks in the backtest, what fraction fell inside the 80% interval?
  A miscalibrated interval is reported as miscalibrated.
- **Benchmarks**: `FluSight-baseline` (CDC's official baseline) and `FluSight-ensemble`, both
  published in the hub alongside 94 other models.

## Why the interval is the point

Hospitals staff to an upper quantile, not to the mean, because the two failure directions do not
cost the same: overstaffing costs a shift of wages, understaffing costs agency premiums, overtime,
and diverted patients. A point forecast cannot support that decision however accurate it is.

The planned output is therefore not an error metric but a comparison, over the backtest period, of
staffing to the baseline, to the mean forecast, and to the upper interval — reported in shifts and
in dollars, with the cost ratio sourced rather than assumed.

---

## Layout

```
src/fetch.py         weekly snapshot collector (stdlib only)
src/check_data.py    data availability check
notebooks/           analysis, in order
data/snapshots/      dated vintages, committed weekly
data/vintages.md     one row per run
```

## Honest limits

- **Four seasonal cycles is thin** for estimating a 52-week period. This is an argument for pooling
  across the 53 locations rather than modelling the national series alone.
- The source disagreement above is **open, not solved**.
- Nothing here is clinical experience or a substitute for it.
