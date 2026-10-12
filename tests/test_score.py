import os, sys, tempfile
import pandas as pd
sys.path.insert(0, 'src')
import monitor                                     # your job, imported as a module

# point the job at a throwaway folder, so the real logs are never touched
tmp = tempfile.mkdtemp()
monitor.PRED_PATH = os.path.join(tmp, 'predictions.csv')
monitor.SCORE_PATH = os.path.join(tmp, 'scores.csv')

# four hand-made predictions, each testing one rule
fake = pd.DataFrame({
    'made_on':     pd.to_datetime(['2026-08-20', '2026-08-20', '2026-09-10', '2026-09-01']),
    'target_week': pd.to_datetime(['2026-08-29', '2026-09-05', '2026-09-05', '2026-09-26']),
    'horizon':     [2, 3, 0, 4],
    'mean':        [1000.0, 1200.0, 1500.0, 2000.0],
    'q80': 0.0, 'q90': 0.0, 'q95': 0.0,
})
fake.to_csv(monitor.PRED_PATH, index=False)

y = monitor.load_data()
print('--- first run');  monitor.score(y)
print('--- second run'); monitor.score(y)
print(pd.read_csv(monitor.SCORE_PATH))