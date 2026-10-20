import os, sys, tempfile
import numpy as np, pandas as pd
sys.path.insert(0, 'src')
import monitor                                     # your job, imported as a module

# point the job at a throwaway folder, so the real logs are never touched
tmp = tempfile.mkdtemp()
monitor.PRED_PATH = os.path.join(tmp, 'predictions.csv')
monitor.SCORE_PATH = os.path.join(tmp, 'scores.csv')

# A made-up admissions series instead of CDC's, so the test gives the same answer on any day
# and needs no internet. Latest week with data: 10 Oct. With SETTLE_WEEKS = 2, weeks up to
# 26 Sep count as settled. The week of 12 Sep is left blank: an actual that never arrived.
weeks = pd.date_range('2026-08-01', '2026-10-10', freq='W-SAT')
y = pd.Series(np.arange(1000.0, 1000.0 + 100 * len(weeks), 100), index=weeks)
y['2026-09-12'] = np.nan
latest = y.dropna().index.max()
assert monitor.SETTLE_WEEKS == 2 and latest == pd.Timestamp('2026-10-10')

# five hand-made predictions, one per rule
fake = pd.DataFrame({
    'model':       'SARIMA',
    'made_on':     pd.to_datetime(['2026-08-20', '2026-09-10', '2026-08-30', '2026-09-20', '2026-09-01']),
    'target_week': pd.to_datetime(['2026-08-29', '2026-09-05', '2026-09-12', '2026-10-03', '2026-09-26']),
    'horizon':     [2, 0, 2, 2, 4],
    'mean':        [1000.0, 1500.0, 1200.0, 1800.0, 2000.0],
    'q80': 0.0, 'q90': 0.0, 'q95': 0.0,
})
# 29 Aug: valid, scored
# 5 Sep:  made after its target week (lookahead), refused
# 12 Sep: actual missing, refused
# 3 Oct:  only 1 week old, not settled yet, refused
# 26 Sep: exactly SETTLE_WEEKS old, the boundary, scored
fake.to_csv(monitor.PRED_PATH, index=False)

print('--- first run');  monitor.score(y)
scored = pd.read_csv(monitor.SCORE_PATH, parse_dates=['target_week'])
print(scored)
assert sorted(scored['target_week'].dt.strftime('%Y-%m-%d')) == ['2026-08-29', '2026-09-26'], 'wrong rows scored'
assert scored['actual'].notna().all(), 'a score row has no actual'
assert (scored['abs_error'] == (scored['actual'] - scored['predicted']).abs()).all(), 'abs_error is wrong'

print('--- second run'); monitor.score(y)
again = pd.read_csv(monitor.SCORE_PATH, parse_dates=['target_week'])
assert len(again) == len(scored), 'a forecast was scored twice'

print('PASS: lookahead, unsettled and missing-actual rows refused; settled rows scored once')
