# Forecasting weekly US respiratory hospital admissions

Forecasting weekly hospital admissions for confirmed influenza four weeks ahead, with calibrated
prediction intervals, evaluated the way CDC evaluates its own public forecasting challenge — and
translated into the staffing decision the forecast actually exists to support.

**Status: in progress (October 2026).** Baseline, two models, prediction intervals, calibration, a
staffing-cost comparison, a benchmark against CDC's FluSight forecasts scored with CDC's weighted
interval score, a model pooled across all 53 locations, and a real-time re-run of the comparison
on data as it was first published are done. The weekly data collection is live. Next: a
monitoring job. Findings below are current as of the date shown and will be updated as they
change.

**Headline.** Forecasting from the data as it was first published (the same conditions CDC's
FluSight teams face), a single linear model pooled across 53 locations scores **37% better than
CDC's FluSight baseline** on CDC's weighted interval score, comes **within 0.04 of CDC's
multi-team ensemble** (relative WIS 0.63 vs 0.59), and **ties it on the staffing decision** it
supports, with a more honest uncertainty range.

---

## Results in brief

- **SARIMA beats "same week last year" by 75% one week out, but only 5% four weeks out.** Four
  weeks is the horizon a staffing plan needs. Holt-Winters is *worse* than the baseline at three
  and four weeks.
- **SARIMA's own 80% interval looks honest overall (77% coverage) but isn't.** It covers 100% of
  off-season weeks and only 56% of flu-season weeks. In flu season reality beat the 90th
  percentile 23% of the time, against the 10% promised.
- **Calibrating the interval from the model's own past errors** (no look-ahead) made flu-season
  shortfall rates roughly honest and cut off-season overstaffing cost by about 94%.
- **In flu season, the calibrated percentiles still cost more than the plain forecast** at a 3:1
  understaffing cost. The model under-forecasts the climb and overshoots when forecasting from
  the top of the curve, so one uncertainty margin for the whole season misplaces it. With about
  two winters of history, that is a lead to confirm, not a final answer.
- **The turn of the season is not visible four weeks ahead** in the national curve, in
  state-level data, or in outpatient flu-like illness, and CDC's professional ensemble missed it
  at one of the three recent peaks.
- **Against CDC's FluSight ensemble**, SARIMA's 4-week error is about 27% higher, roughly level
  with CDC's own baseline (relative WIS 0.99). Staffing from the ensemble's range would have cost
  about 19% less, mostly because its range is trustworthy enough to staff above.
- **Pooling across all 53 locations nearly closes the gap.** A single linear regression shared
  across states reaches a 4-week relative WIS of **0.67**, against **0.64** for the FluSight
  ensemble, with a more honest 80% range (84% coverage vs 77%). It still trails the ensemble for
  staffing: its forecasts run low in flu season, and at a 3:1 cost shortfalls dominate.
- **Trained on flu-season weeks only** (one change, declared with success criteria before
  testing), the pooled model improves at every horizon and closes most of the remaining gap.
- **On real-time data** (each forecast made from the first-published version, as the FluSight
  teams had to), the pooled flu-season model reaches a 4-week relative WIS of **0.63** against
  **0.59** for the ensemble and **1.00** for CDC's baseline, and **ties the ensemble on staffing
  cost** (614k vs 619k cost points). Initial reports understate admissions by about 9%
  nationally, and increasingly so.

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
| Calibrate from past errors, all seasons pooled | Flu-season weeks above the 90th percentile: 13.7%, vs 17.9% for the raw interval on the same weeks. Off-season still too wide. |
| Calibrate from past errors, same season only | Off-season coverage 79%, near target, but lopsided: reality beats the 90th percentile 17% of the time. Flu season can't be judged: too few past winters to learn from. |

Calibration multiplies the forecast by quantiles of past `actual ÷ forecast` ratios, using only
forecasts whose outcome was already known on the forecast date. Before calibrating, the forecast
is floored at the lowest week seen so far: after steep post-peak falls, 21 of 388 SARIMA
forecasts went below zero, which made those ratios explode.

**Staffing decision.** Capacity is set 4 weeks ahead. Understaffing costs 3 per admission of
shortfall, overstaffing 1 per admission of slack (an assumption, and in cost points, not dollars).
By the newsvendor rule that points to the 75th percentile, *if* the percentiles are honest.

- **Off-season:** same-season calibration cuts overstaffing cost by about 94% against the raw 90th
  percentile.
- **Flu season:** the calibrated 75th and 90th percentiles are short about as often as they
  promise (24% and 14% of weeks), yet both cost more than staffing to the plain forecast. The
  margins are proportional to the forecast, so the biggest margins land on forecasts made at the
  top of the curve, which are already too high.
- On the weeks every strategy could be scored (51, mostly one flu season), "same week last year"
  came out cheapest. That was luck: it copied a larger, later season, so it overstaffed. Over both
  winters the plain forecast beats it (1.08M vs 1.23M cost points).

## Benchmarks: can anyone see the turn?

`notebooks/04-benchmarks.ipynb`. Almost all of the 4-week error, and of the staffing cost, sits at
the turn of the season. Four ways to see it coming were tested:

| Possible warning | Result |
|---|---|
| The national curve slowing before a peak | No. The largest overshoots were forecasts made 1–2 weeks before a peak, while weekly growth was still *accelerating*. These peaks arrived at full speed. |
| States peaking before the nation | No. In complete seasons nearly every state peaked in the same week as the nation, or one week off. No state was early every season. |
| Outpatient flu-like illness (ILINet) | No. It peaked 0–1 weeks before admissions; seeing a turn 4 weeks ahead would need 3–4. |
| CDC's FluSight ensemble | Partly. It nailed the February 2025 peak (within 6%), but overshot the January 2026 peak by 138% and undershot in December 2024. |

**Comparison with FluSight** on the 55 flu-season forecast dates both cover (Nov 2024 – May 2026).
FluSight-ensemble is the median, percentile by percentile, of all submitted forecasts;
FluSight-baseline carries the latest week forward flat.

| 4 weeks ahead | MAE | Above own 90th percentile | Staffing cost (3:1) |
|---|---|---|---|
| FluSight-ensemble | **7,104** | 20% | **807k** (staffing to its 90th percentile) |
| SARIMA (this project) | 9,765 | 20% | 998k (staffing to its mean) |
| FluSight-baseline | 10,024 | 24% | 1,153k |

- **Everyone underestimates upside risk.** Reality beat the 90th percentile about 20% of the time
  for both the ensemble and SARIMA, against 10% promised. The ensemble's misses are almost all on
  the high side.
- **The newsvendor rule holds once miscalibration is accounted for.** The ensemble's "90th
  percentile" was short 24% of weeks, so it behaved like an honest 75th, and it was the cheapest
  plan, as the rule predicts for a 3:1 cost ratio.
- **Averaging SARIMA with a flat forecast improved 4-week error by only 3%.** Both see the same
  national series, so they miss in the same weeks. The ensemble's advantage comes from members
  that see *different* data.
- **Caveat:** FluSight teams forecast in real time from data later revised (often upward); this
  backtest uses the final data. The real-time re-run below measures the effect directly.

## Pooling across states

`notebooks/05-pooled.ipynb`. SARIMA learns from one curve, about four seasons. The FluSight file
has 53: every state, DC, Puerto Rico and the nation. The pooled model learns from all of them.

- **Same scale for every location:** admissions per 100,000 people, then a fourth root, which
  compresses large values more gently than a log.
- **One linear regression per horizon, shared by all locations:** inputs are the last 6 weekly
  changes and the current level; the target is the change *h* weeks ahead. The nation is
  forecast with the shared coefficients and its own recent changes.
- **Range from past errors:** the regression's errors across all locations, about 7,000 at each
  forecast date, give the 23 percentiles.
- **One design, run once.** These choices follow the published AR component of UMass's
  `flusion` model, were fixed before evaluation, and were not tuned on these dates.

Scored with CDC's **weighted interval score (WIS)**, which penalises every percentile of the
forecast, not just the middle; *relative* WIS divides by FluSight-baseline's, so below 1 beats it.
These figures use today's revised data; the real-time re-run is in the next section.

| 4 weeks ahead, 55 flu-season dates | MAE | Relative WIS | 80% range inside / above q90 | Best staffing cost (3:1) |
|---|---|---|---|---|
| FluSight-ensemble | **7,104** | **0.64** | 77% / 20% | 807k |
| Pooled, flu-season training (this project) | 7,799 | **0.64** | 82% / 14% | **777k** |
| Pooled (this project) | 7,859 | 0.67 | **84% / 14%** | 932k |
| SARIMA | 9,764 | 0.99 | 61% / 20% | 998k |
| FluSight-baseline | 10,023 | 1.00 | 60% / 24% | 1,153k |

- **By horizon,** SARIMA is best of our models at 1 week (relative WIS 0.77 vs 0.97 for pooled),
  the pooled model at 2–4 weeks (0.81, 0.72, 0.67).
- **At the turns,** the pooled model beat the ensemble at both 2025–26 peaks and more than halved
  SARIMA's worst overshoot. It doesn't predict turns; it learned from about 200 season-curves that
  fast climbs rarely continue at full speed for four weeks.
- **The flip side is a low bias in flu season:** its median was short 73% of weeks (an honest
  median is short 50%). WIS prices errors symmetrically and rates the model highly; the 3:1
  staffing cost punishes those shortfalls, so the ensemble stays ~15% cheaper.

**Declared experiment: flu-season-only training.** One change, with success criteria written
down before running: train on examples whose forecast date falls in November–April. All three
criteria passed:

| Criterion (4 weeks) | Pooled | Flu-season training | Bar |
|---|---|---|---|
| Median short | 73% | 69% | closer to 50% (passed only narrowly) |
| Best staffing cost | 932k | 777k | below 932k |
| Relative WIS | 0.67 | 0.64 | no worse than 0.67 |

Relative WIS improved at every horizon (0.79 / 0.74 / 0.68 / 0.64), and the range stayed honest
(82% inside, 14% above q90). The low bias mostly remains: the gain comes from better-placed upper
percentiles, not from a better middle line (4-week MAE 7,799, barely changed). Summer and flu
season behave differently, and training on both had blended the two.

## The real-time test: data as it was first published

`notebooks/06-as-of.ipynb`. Every comparison above uses today's data, but public-health data is
revised after publication, and FluSight teams forecast from the *first-published* numbers.
CDC's hub keeps every past version of its data (98 versions since September 2023), so the
backtest was re-run using, for each forecast date, **only the version that existed that day**.

**How much early reports are revised.** The newest week is first reported about **9% low**
nationally (states about 5%), filling in over the next one to two weeks. The gap is always in the
same direction and has grown: about 3% in 2023–24, 11% in 2024–25, 12% in 2025–26.

**The fair comparison** — 4 weeks ahead, the same 51 flu-season dates for every model (the other
4 FluSight dates fall on gaps in CDC's archive):

| 4 weeks ahead, real-time data | MAE | Relative WIS | 80% range inside / above q90 | Best staffing cost (3:1) |
|---|---|---|---|---|
| FluSight-ensemble | **5,888** | **0.59** | 78% / 18% | 619k |
| Pooled, flu-season training (this project) | 6,967 | 0.63 | **82% / 16%** | **614k** |
| SARIMA (this project) | 8,105 | 0.89 | 59% / 22% | 805k |
| FluSight-baseline | 8,940 | 1.00 | 59% / 20% | 867k |

- **The pooled model holds up under real-time conditions:** 37% better than CDC's baseline,
  within 0.04 of the professional ensemble, tied with it on the staffing decision, and with the
  most honest range.
- **Real-time data costs it a little:** relative WIS 0.60 → 0.63 against revised data on the same
  dates, the honest price of starting from under-reported numbers.
- **SARIMA scores better on real-time data at 4 weeks** (1.04 → 0.89), but worse at 1 week. An
  under-reported latest week shrinks the most recent jump, which happens to dampen SARIMA's
  overshoots: an error in the data partly cancelling an error in the model.
- **Correcting for late reporting** (scaling up the newest weeks by their typical revision,
  learned only from past versions) sharpens 1-week forecasts (0.95 → 0.90) but leaves 4 weeks
  unchanged: the 4-week gap is set by the turns of the season, not by reporting delays.
- **Data quality, found along the way:** CDC's version archive has gaps (no version for four
  forecast weeks, e.g. Thanksgiving 2025) and one version that repeats every row.

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
  estimate. *(done: relative WIS against FluSight-baseline, all 23 percentiles)*
- **Benchmarks**: `FluSight-baseline` (CDC's official baseline) and `FluSight-ensemble`, both
  published in the hub alongside 94 other models. *(done: accuracy, interval coverage and
  staffing cost on 55 flu-season dates)*

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
notebooks/04-benchmarks.ipynb          turn-of-season checks, FluSight comparison
notebooks/05-pooled.ipynb              WIS scoring, model pooled across 53 locations
notebooks/06-as-of.ipynb               real-time re-run on first-published data
data/snapshots/                        dated vintages, committed weekly
data/vintages.md                       one row per run
```

## Honest limits

- **Four seasonal cycles is thin** for estimating a 52-week period, and **about two flu seasons**
  is thin for judging intervals and staffing in flu season. Pooling across the 53 locations
  addresses the first; the second still limits every flu-season comparison here (55 dates).
- **Notebooks 02–05 use data as currently published.** Notebook 06 re-runs the FluSight
  comparison on first-published data and supersedes their headline figures; the earlier
  notebooks' year-round results (e.g. summer coverage) have not been re-run that way.
- **The 3:1 cost ratio is an assumption**, not a sourced figure.
- **The state and ILINet checks compare peak weeks only**, over four seasons, one of them
  double-peaked. They show no usable early warning in this data, not that none exists.
- The source disagreement above is **open, not solved**.
- Nothing here is clinical experience or a substitute for it.
