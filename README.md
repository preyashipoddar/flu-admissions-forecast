# Forecasting weekly US flu hospital admissions

Four-week-ahead forecasts of weekly flu hospital admissions, with calibrated uncertainty ranges,
evaluated the way CDC evaluates its own forecasting challenge (FluSight), translated into a
staffing decision, and run as a monitored weekly job.

## Headline

Forecasting from the data **as it was first published** (the same conditions CDC's FluSight
teams face), a linear model pooled across 53 states and territories:

| 4 weeks ahead, 51 flu-season dates, real-time data | Relative WIS ↓ | MAE | 80% interval coverage | Staffing cost (3:1) |
|---|---|---|---|---|
| CDC FluSight ensemble (dozens of teams) | **0.59** | **5,888** | 78% | 619k |
| **Pooled model (this project)** | 0.63 | 6,967 | **82%** | **614k** |
| SARIMA (this project) | 0.89 | 8,105 | 59% | 805k |
| CDC FluSight baseline | 1.00 | 8,940 | 59% | 867k |

- **37% better than CDC's baseline** on CDC's weighted interval score (WIS), and **within 0.04
  of CDC's multi-team ensemble**.
- **Ties the ensemble on the staffing decision** it supports, with the most honest uncertainty
  range of the four.
- *Relative WIS* = WIS ÷ FluSight-baseline's WIS; below 1 beats the baseline. Staffing cost is in
  cost points with an assumed 3:1 understaffing-to-overstaffing ratio.

## Key findings

- **Accuracy collapses with horizon.** SARIMA beats "same week last year" by 75% at 1 week but
  only 5% at 4 weeks, the horizon a staffing plan needs.
- **One coverage number hid a seasonal failure.** SARIMA's 80% interval covered 77% of weeks
  overall, but 100% off-season and only 56% in flu season.
- **The turn of the season is not visible four weeks ahead.** Not in the national curve, state
  data or outpatient visits (ILINet), and CDC's ensemble also missed one of the three recent peaks.
- **Pooling across states is what closes the gap.** Learning from ~200 state-season curves instead
  of 4 national ones teaches the model that fast climbs rarely continue at full speed.
- **Initial CDC reports understate admissions by ~9% nationally**, a gap that grew from 3% to 12%
  over three seasons. Correcting for it helps 1-week forecasts, not 4-week ones.
- **Data-quality issues in public CDC data:** gaps and a fully duplicated release in CDC's version
  archive, and a 3–17% disagreement between two CDC sources (not blended for that reason).

## How it was done

| Notebook | What it does |
|---|---|
| `01-baseline` | Seasonal-naive baseline ("same week last year") |
| `02-sarima-holtwinters` | Rolling-origin backtest: 97 forecast dates × 4 horizons = 388 forecasts |
| `03-intervals` | Prediction intervals, coverage by season, calibration from past errors, staffing cost (newsvendor rule) |
| `04-benchmarks` | Can the season's turn be seen early? Comparison with CDC FluSight ensemble and baseline |
| `05-pooled` | WIS scoring; model pooled across 53 locations; one pre-registered experiment (flu-season training) |
| `06-as-of` | Re-run on CDC's archive of 98 data versions, forecasting each date from first-published data |

**Method in brief.** Chronological splits only; every forecast refit using data available on its
date; error reported per horizon, never blended; intervals checked for coverage; model changes
tested as pre-registered experiments with success criteria written before seeing results.

**The pooled model.** Admissions per 100,000 people, fourth-root transformed so states of any
size are comparable; one linear regression per horizon shared by all locations (inputs: last 6
weekly changes and current level), trained on flu-season weeks; uncertainty ranges from the
pooled past errors. Design follows the AR component of UMass's `flusion` FluSight model.

## Weekly monitoring job

Every Thursday, `src/monitor.py` forecasts US flu admissions for the next 1–4 weeks and logs each
forecast to `data/predictions.csv` before the outcome is known. It then scores earlier forecasts
against actual admissions in `data/scores.csv`, once a week is at least two weeks old (first
reports run ~9% low). The run fails, and emails an alert, if the average error of the last four
4-week-ahead forecasts is worse than "same week last year" on the same weeks. A fixed threshold
would fire every January and never catch a broken model in July; comparing against the naive
forecast adjusts for the season.

Running unattended since 12 October 2026 (`.github/workflows/monitor.yml`). Tests in `tests/`
cover no lookahead, no double scoring, no scoring before data settles, and the alert in both
directions. Dependencies are pinned in `requirements-monitor.txt`.

A second job (`weekly-snapshot.yml`, standard library only) archives every CDC data release to
`data/snapshots/`, building a record of revisions.

## Repository

```
notebooks/                 analysis, 01-06 in order
src/monitor.py             weekly forecast, log, score and drift alert
src/fetch.py               weekly data snapshot collector
src/check_data.py          data availability check
tests/                     tests for the monitoring job
data/predictions.csv       every forecast, logged before its outcome
data/scores.csv            each forecast scored once its week has settled
data/snapshots/            dated data vintages
```

**Data:** [CDC FluSight forecast hub](https://github.com/cdcepi/FluSight-forecast-hub) (weekly
admissions for 53 locations since Feb 2022, CDC's forecasts, and an archive of past data
versions) and [CDC Socrata `vdzy-6i9v`](https://data.cdc.gov/d/vdzy-6i9v).

## Limits

- **Two flu seasons of test data** (51–55 forecast dates). Results are comparable to the
  professionals', not proof of being better.
- **The 3:1 staffing cost ratio is assumed**, not sourced; sourced costs are next.
- **The state and ILINet checks compare peak weeks only**, over four seasons.
- Notebooks 02–05 use revised data; notebook 06 supersedes their headline FluSight figures.
- Nothing here is clinical experience or a substitute for it.
