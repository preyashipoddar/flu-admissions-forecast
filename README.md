# Forecasting weekly US respiratory hospital admissions

Forecasting weekly hospital admissions for confirmed influenza four weeks ahead, with calibrated
prediction intervals, evaluated the way CDC evaluates its own public forecasting challenge — and
translated into the staffing decision the forecast actually exists to support.

**Status: in progress (October 2026).** Baseline, two models, prediction intervals, calibration and
a staffing-cost comparison are done and backtested. The weekly data collection is live. Next:
calibrating by epidemic phase, and a monitoring job. Findings below are current as of the date
shown and will be updated as they change.

---

## Results in brief

- **SARIMA beats "same week last year" by 75% one week out, but only 5% four weeks out.** Four
  weeks is the horizon a staffing plan needs. Holt-Winters is *worse* than the baseline at three
  and four weeks.
- **SARIMA's own 80% interval looks honest overall (77% coverage) but isn't.** It covers 100% of
  off-season weeks and only 56% of flu-season weeks. In flu season reality beat the 90th
  percentile 23% of the time, against the 10% promised.
- **Calibrating the interval from the model's own past errors** (no look-ahead) made shortfall
  rates roughly honest and cut off-season overstaffing cost by about 94%.
- **In flu season, the calibrated percentiles still cost more than the plain forecast** at a 3:1
  understaffing cost. The model under-forecasts the rise and over-forecasts the fall, so one
  uncertainty margin for the whole season misplaces it. With about two winters of history, that
  is a lead to confirm, not a final answer.

---

## The baseline — the number everything is measured against

Before fitting anything, the dumbest reasonable forecast was scored: **predict each week using the
same week one year earlier** (seasonal naive).

| | |
|---|---|
| Method | seasonal naive (52-week lag) |
| **MAE, backtest weeks** | **6,323 admissions** |
| Backtest | 97 weekly forecast dates, 2024-07-27 → 2026-05-30, 1–4 weeks ahead |

Every model below is compared on exactly these weeks. Over the full history (179 weeks,
2023-02-04 → 2026-07-04) the same baseline scores 4,780, but that is a different, easier set of
weeks, so **4,780 is not comparable to the model results** and isn't used as the yardstick.

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
an off-peak week. The 2024-25 season also double-peaked: 39,662 on 4 Jan, back down to 31,876 on
11 Jan, then a true peak of 55,718 on 8 Feb.

Series range: **223** admissions (Sep 2024) to **55,718** (Feb 2025) — a factor of 250. Percentage
error is therefore reported only in season; MAE is the headline metric.

---

## Models — point forecasts

`notebooks/02-sarima-holtwinters.ipynb`. Rolling-origin backtest: both models refitted from scratch
at each of the 97 forecast dates, scored 1–4 weeks ahead (388 forecasts each). Data as published
in September 2026.

| MAE (admissions) | 1 wk | 2 wk | 3 wk | 4 wk | overall |
|---|---|---|---|---|---|
| Seasonal naive | 6,321 | 6,323 | 6,325 | 6,324 | 6,323 |
| Holt-Winters (additive trend + 52-wk season) | 1,661 | 3,877 | **6,398** | **8,783** | 5,180 |
| SARIMA (1,1,1)(1,0,0,52) | **1,597** | **3,544** | **4,988** | **5,992** | **4,030** |
| SARIMA vs naive | −75% | −44% | −21% | −5% | −36% |

- **The advantage decays fast.** SARIMA's edge comes from recent momentum, which has a short
  memory. By four weeks it leans on the same seasonal information as the baseline.
- **Holt-Winters is worse than doing nothing at three and four weeks.** The likely mechanism: its
  linear trend, fitted mid-climb, is projected straight through the turn of the season, and its
  single fixed seasonal shape can't match seasons that peak 10 weeks apart. It also threw
  convergence warnings on about a quarter of the fits.
- **A single blended number hides this.** Overall, both models beat the baseline. At the horizon a
  staffing plan needs, one of them doesn't.

## Prediction intervals, calibration and the staffing decision

`notebooks/03-intervals.ipynb`. Same 97 forecast dates, SARIMA, current data. Flu season =
target weeks in November–April.

**Is the 80% interval honest?**

| | Off-season | Flu season | Target |
|---|---|---|---|
| Inside the 80% interval | 100% | 56% | 80% |
| Reality above the 90th percentile | 0% | 23% | 10% |

The interval has roughly constant width all year, while real errors are a few hundred admissions
in summer and tens of thousands in January. It is too wide off-season (it even goes negative) and
too narrow in flu season. The overall 77% hid both.

**What was tried:**

| Approach | Result |
|---|---|
| Model log(admissions) | Intervals improve (off-season 89%, flu season 62%), but 4-week MAE rises 30% to 7,780, worse than the baseline: percentage growth compounds, so forecasts made mid-climb overshoot massively at the turn. **Rejected.** |
| Calibrate from past errors, all seasons pooled | Flu-season weeks above the 90th percentile: 12.5%, vs 17.9% for the raw interval on the same weeks. Off-season still too wide. |
| Calibrate from past errors, same season only | Off-season fixed (89% coverage). Flu season can't be judged: too few past winters to learn from. |

Calibration multiplies the forecast by quantiles of past `actual ÷ forecast` ratios, using only
forecasts whose outcome was already known on the forecast date.

**Staffing decision.** Capacity is set 4 weeks ahead. Understaffing costs 3 per admission of
shortfall, overstaffing 1 per admission of slack (an assumption, and in cost points, not dollars).
By the newsvendor rule that points to the 75th percentile, *if* the percentiles are honest.

- **Off-season:** same-season calibration cuts overstaffing cost by about 94% against the raw 90th
  percentile.
- **Flu season:** the calibrated 75th and 90th percentiles are short about as often as they
  promise (24% and 14% of weeks), yet both cost more than staffing to the plain forecast. The
  margins are proportional to the forecast, so the biggest margins land after the peak, on
  forecasts that are already too high.
- On the weeks every strategy could be scored (51, mostly one flu season), "same week last year"
  came out cheapest. That was luck: it copied a larger, later season, so it overstaffed. Over both
  winters the plain forecast beats it (1.10M vs 1.23M cost points).

---

## Data

| Source | Role | Coverage |
|---|---|---|
| [FluSight forecast hub](https://github.com/cdcepi/FluSight-forecast-hub) `target-data/target-hospital-admissions.csv` | Modelling history | 2022-02-05 onward, 53 locations; the 2026-27 season started publishing in late September 2026 |
| [CDC Socrata `vdzy-6i9v`](https://data.cdc.gov/d/vdzy-6i9v) | Live weekly extension | Rolling ~20-week window, refreshed Wednesdays |

**The two sources disagree**, systematically: on overlapping weeks FluSight runs higher than the
CDC Socrata series — 3–17% on the earlier overlap, narrowing to 2–5% on the newest weeks
(September 2026). The cause is not yet established — candidate explanations are a different
jurisdiction set in the national aggregate, a different confirmed/suspected inclusion rule, or
revision timing. **The series are not blended until that is resolved**; modelling uses FluSight,
which is the benchmark-consistent one.

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

The archive has already caught this: between the 2026-09-24 and 2026-10-01 snapshots, FluSight's
value for the week of 4 July 2026 moved from 695 to 734, and 27 June from 729 to 751.

Keeping every weekly pull builds that vintage archive automatically, as a side effect of a job
that already has to run. It cannot be reconstructed after the fact, which is why the collector was
built before the models were. It also matters for the results above: the backtest has only about
two flu seasons, and every new winter the archive captures makes the flu-season findings testable.

`src/fetch.py` uses **only the Python standard library**, and the workflow installs nothing. A job
meant to run unattended for months should not depend on anything that can change underneath it.

---

## Evaluation approach

Scored the way CDC scores FluSight, so the results are comparable to real submissions:

- **Chronological splits only.** Train on the past, test on the future. *(done)*
- **Rolling-origin backtesting** — refit at successive cutoffs, average across them, rather than
  reporting one lucky window. *(done: 97 cutoffs)*
- **Error per horizon** (1, 2, 3, 4 weeks) — never one blended figure. *(done)*
- **Coverage check** — what fraction of weeks fell inside the 80% interval, split by season.
  *(done)*
- **Weighted interval score (WIS)** alongside MAE. WIS grades the *interval*, not the point
  estimate. *(not yet)*
- **Benchmarks**: `FluSight-baseline` (CDC's official baseline) and `FluSight-ensemble`, both
  published in the hub alongside 94 other models. *(not yet)*

## Why the interval is the point

Hospitals staff to an upper quantile, not to the mean, because the two failure directions do not
cost the same: overstaffing costs a shift of wages, understaffing costs agency premiums, overtime,
and diverted patients. A point forecast cannot support that decision however accurate it is —
and, as the results above show, an interval only supports it if it is honest in the situations
where the decision is made.

---

## Layout

```
src/fetch.py                           weekly snapshot collector (stdlib only)
src/check_data.py                      data availability check
notebooks/01-baseline.ipynb            seasonal naive baseline
notebooks/02-sarima-holtwinters.ipynb  rolling-origin backtest of both models
notebooks/03-intervals.ipynb           intervals, calibration, staffing decision
data/snapshots/                        dated vintages, committed weekly
data/vintages.md                       one row per run
```

## Honest limits

- **Four seasonal cycles is thin** for estimating a 52-week period, and **about two flu seasons**
  is thin for judging intervals and staffing in flu season. This is an argument for pooling across
  the 53 locations rather than modelling the national series alone.
- **The backtest uses data as currently published**, not as known on each forecast date. The
  vintage archive started in September 2026, so it can't yet support a fully as-of backtest.
- **The 3:1 cost ratio is an assumption**, not a sourced figure.
- The source disagreement above is **open, not solved**.
- Nothing here is clinical experience or a substitute for it.
