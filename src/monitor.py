import warnings
warnings.filterwarnings('ignore')            # SARIMA convergence warnings; counted explicitly below instead

import pandas as pd, numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX

def load_data():
    URL = ('https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/'
       'main/target-data/target-hospital-admissions.csv')
    raw = pd.read_csv(URL, parse_dates=['date'])

    # one column of weekly US admissions, oldest -> newest, labelled by each week's Saturday
    y = raw[raw.location == 'US'].set_index('date')['value'].sort_index().asfreq('W-SAT')
    return y

def fit_sarima(series):
    with warnings.catch_warnings():          # statsmodels re-enables its own warnings; silence per fit
        warnings.simplefilter('ignore')
        return SARIMAX(series, order=(1,1,1), seasonal_order=(1,0,0,52),
                   enforce_stationarity=False, enforce_invertibility=False).fit(disp=False)


def make_forecast(y):
    f = fit_sarima(y).get_forecast(4)
    upper = lambda a: f.conf_int(alpha=a).iloc[:, 1].clip(lower=0)   # upper edge for a given alpha
    out = pd.DataFrame({
        'made_on':     pd.Timestamp.today().normalize(),
        'target_week': f.predicted_mean.index,
        'horizon':     [1, 2, 3, 4],
        'mean':        f.predicted_mean.clip(lower=0),
        'q80':         upper(0.4),
        'q90':         upper(0.2),
        'q95':         upper(0.1),
    })
    out = out[out['target_week'] > out['made_on']]
    return out.reset_index(drop=True)

import os

PRED_PATH = 'data/predictions.csv'

def log_predictions(rows):
    if os.path.exists(PRED_PATH):
        old = pd.read_csv(PRED_PATH, parse_dates=['made_on', 'target_week'])
    else:
        old = rows.iloc[0:0]                     # an empty table with the same columns
    combined = pd.concat([old, rows])
    combined = combined.drop_duplicates(subset=['made_on', 'target_week'], keep='first')
    combined.to_csv(PRED_PATH, index=False)
    print(f'predictions log: {len(combined) - len(old)} new rows, {len(combined)} total')

SCORE_PATH = 'data/scores.csv'
SETTLE_WEEKS = 2          # only score weeks at least this old (first reports run ~9% low)

def score(y):
    if not os.path.exists(PRED_PATH):
        print('scores: no predictions logged yet')
        return

    preds = pd.read_csv(PRED_PATH, parse_dates=['made_on', 'target_week'])
    if os.path.exists(SCORE_PATH):
        done = pd.read_csv(SCORE_PATH, parse_dates=['made_on', 'target_week'])
    else:
        done = pd.DataFrame(columns=['made_on', 'target_week'])

    # 1. not already scored (anti-join)
    merged = preds.merge(done[['made_on', 'target_week']], on=['made_on', 'target_week'],
                         how='left', indicator=True)
    todo = merged[merged['_merge'] == 'left_only'].drop(columns='_merge')

    # 2. settled real data exists, and no lookahead
    latest = y.dropna().index.max()                          # newest week with data
    settled_until = latest - pd.Timedelta(weeks=SETTLE_WEEKS)
    todo = todo[(todo['target_week'] <= settled_until) & (todo['made_on'] < todo['target_week'])]

    if todo.empty:
        print(f'scores: nothing to score yet (data settled up to {settled_until.date()})')
        return

    # 3. build the score rows
    actual = y.reindex(todo['target_week']).values           # real values for those weeks
    new = pd.DataFrame({
        'target_week': todo['target_week'].values,
        'made_on':     todo['made_on'].values,
        'horizon':     todo['horizon'].values,
        'predicted':   todo['mean'].values,
        'actual':      actual,
        'abs_error':   np.abs(actual - todo['mean'].values),
    })
    new = new.dropna(subset=['actual'])                      # never invent a score

    combined = pd.concat([done, new]) if len(done) else new
    combined.to_csv(SCORE_PATH, index=False)
    print(f'scores: {len(new)} new, {len(combined)} total')  

import sys

ALERT_WINDOW = 4          # number of recent 4-week-ahead forecasts to judge 

def check_alert(y):
    if not os.path.exists(SCORE_PATH):
        print('alert check: no scores yet')
        return
    s = pd.read_csv(SCORE_PATH, parse_dates=['made_on', 'target_week'])
    recent = s[s['horizon'] == 4].sort_values('target_week').tail(ALERT_WINDOW)
    if len(recent) < ALERT_WINDOW:
        print(f'alert check: only {len(recent)} scored 4-week forecasts, need {ALERT_WINDOW}')
        return

    naive = y.reindex(recent['target_week'] - pd.Timedelta(weeks=52)).values
    model_mae = recent['abs_error'].mean()
    naive_mae = np.abs(recent['actual'].values - naive).mean()
    print(f'alert check: last {ALERT_WINDOW} 4-week forecasts | model MAE {model_mae:,.0f} | naive MAE {naive_mae:,.0f}')

    if model_mae > naive_mae:
        print('ALERT: the model is no longer beating "same week last year"')
        sys.exit(1) 



if __name__ == '__main__':
    y = load_data()
    rows = make_forecast(y)
    log_predictions(rows)
    score(y)
    check_alert(y)
