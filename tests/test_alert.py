import os, sys, tempfile
import pandas as pd
sys.path.insert(0, 'src')
import monitor

y = monitor.load_data()
weeks = pd.to_datetime(['2026-08-29', '2026-09-05', '2026-09-12', '2026-09-19'])
actual = y.reindex(weeks).values

def run_with_errors(errors, label):
    tmp = tempfile.mkdtemp()
    monitor.SCORE_PATH = os.path.join(tmp, 'scores.csv')
    pd.DataFrame({'target_week': weeks, 'made_on': weeks - pd.Timedelta(weeks=4), 'horizon': 4,
                  'predicted': actual + errors, 'actual': actual, 'abs_error': abs(errors)}
                 ).to_csv(monitor.SCORE_PATH, index=False)
    print(f'--- {label}')
    try:
        monitor.check_alert(y)
        print('    -> no alert')
    except SystemExit as e:
        print(f'    -> ALERT, exit code {e.code}')

run_with_errors(pd.Series([10, 10, 10, 10]).values, 'model nearly perfect')
run_with_errors(pd.Series([5000, 5000, 5000, 5000]).values, 'model way off')