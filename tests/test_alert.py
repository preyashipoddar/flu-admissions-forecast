import os, sys, tempfile
import numpy as np, pandas as pd
sys.path.insert(0, 'src')
import monitor

# A made-up admissions series covering more than a year, so "same week last year" exists for
# every target week below. Same answer on any day, no internet.
weeks_all = pd.date_range('2025-08-02', '2026-10-10', freq='W-SAT')
y = pd.Series(1000.0 + 50 * np.arange(len(weeks_all)), index=weeks_all)
weeks = pd.to_datetime(['2026-08-29', '2026-09-05', '2026-09-12', '2026-09-19'])
actual = y.reindex(weeks).values
naive_mae = np.abs(actual - y.reindex(weeks - pd.Timedelta(weeks=52)).values).mean()   # 2,600 here

def write_scores(rows):
    tmp = tempfile.mkdtemp()
    monitor.SCORE_PATH = os.path.join(tmp, 'scores.csv')
    pd.DataFrame(rows).to_csv(monitor.SCORE_PATH, index=False)

def rows_for(target_weeks, errors, made_weeks_before=4):
    target_weeks = pd.DatetimeIndex(target_weeks)
    act = y.reindex(target_weeks).values
    return {'model': monitor.ALERT_MODEL, 'target_week': target_weeks,
            'made_on': target_weeks - pd.Timedelta(weeks=made_weeks_before), 'horizon': 4,
            'predicted': act + errors, 'actual': act, 'abs_error': np.abs(errors)}

def alerts():
    try:
        monitor.check_alert(y)
        return False
    except SystemExit as e:
        assert e.code == 1
        return True

print('--- model nearly perfect')
write_scores(rows_for(weeks, np.full(4, 10.0)))
assert not alerts(), 'alert fired for a near-perfect model'

print('--- model far worse than "same week last year"')
write_scores(rows_for(weeks, np.full(4, 5000.0)))
assert alerts(), 'alert did not fire for a bad model'

print('--- a week logged twice (manual re-run) counts once')
dup = pd.concat([pd.DataFrame(rows_for(weeks[:3], np.full(3, 10.0))),
                 pd.DataFrame(rows_for(weeks[2:3], np.full(1, 10.0), made_weeks_before=3))])
write_scores(dup)
n, model_mae, _ = monitor.alert_status(y)
assert (n, model_mae) == (3, None), f'expected 3 distinct weeks and no verdict, got {n}, {model_mae}'

print('--- for a week logged twice, the latest forecast is the one judged')
old_bad = pd.DataFrame(rows_for(weeks[3:], np.full(1, 50000.0), made_weeks_before=5))
latest_good = pd.DataFrame(rows_for(weeks, np.full(4, 10.0)))
write_scores(pd.concat([old_bad, latest_good]))
n, model_mae, _ = monitor.alert_status(y)
assert n == 4 and model_mae == 10.0, f'expected the latest forecasts only, got MAE {model_mae}'
assert not alerts()

print(f'PASS: alert fires only when worse than "same week last year" (naive MAE {naive_mae:,.0f}); '
      'each target week counted once, latest forecast judged')
