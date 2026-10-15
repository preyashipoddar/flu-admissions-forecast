import warnings
warnings.filterwarnings('ignore')            # SARIMA convergence warnings; counted explicitly below instead

import functools
import pandas as pd, numpy as np
from scipy.stats import norm
from statsmodels.tsa.statespace.sarimax import SARIMAX

# percentiles logged for every forecast (column name -> percentile); q80/q90/q95 are the original three
QUANTILES = {'q025': 0.025, 'q05': 0.05, 'q10': 0.10, 'q25': 0.25, 'q50': 0.50,
             'q75': 0.75, 'q80': 0.80, 'q90': 0.90, 'q95': 0.95, 'q975': 0.975}

@functools.lru_cache(maxsize=1)
def load_raw():
    URL = ('https://raw.githubusercontent.com/cdcepi/FluSight-forecast-hub/'
       'main/target-data/target-hospital-admissions.csv')
    return pd.read_csv(URL, parse_dates=['date'], dtype={'location': str})

def load_data():
    raw = load_raw()
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
    mu, se = f.predicted_mean, f.se_mean
    out = pd.DataFrame({
        'model':       'SARIMA',
        'made_on':     pd.Timestamp.today().normalize(),
        'target_week': mu.index,
        'horizon':     [1, 2, 3, 4],
        'mean':        mu.clip(lower=0),
    })
    for col, p in QUANTILES.items():                      # normal ranges, same as conf_int
        out[col] = (mu + norm.ppf(p) * se).clip(lower=0).values
    out = out[out['target_week'] > out['made_on']]
    return out.reset_index(drop=True)


# ---- pooled model (notebook 05): one linear model per horizon, shared by all 53 locations ----
LAGS = 6                                    # inputs: the last 6 weekly changes + the current level
FEATURES = [f'chg{k}' for k in range(LAGS)] + ['level']
FLU_MONTHS = [11, 12, 1, 2, 3, 4]           # trained on flu-season weeks only (notebook 05, section 6)

def build_train(rate):
    """One row per (location, week, horizon): inputs, and the change h weeks later, on the 4th-root scale."""
    z = rate ** 0.25
    feat = {f'chg{k}': z.diff().shift(k) for k in range(LAGS)}
    feat['level'] = z
    tabs = []
    for h in range(1, 5):
        tb = pd.concat({n: f.stack() for n, f in feat.items()}, axis=1)
        tb['target'] = (z.shift(-h) - z).stack()
        tb['horizon'] = h
        tabs.append(tb)
    tr = pd.concat(tabs).reset_index().rename(columns={'level_1': 'location_name'})
    tr['target_date'] = tr['date'] + pd.to_timedelta(tr['horizon'], unit='W')
    return tr

def make_pooled_forecast(raw):
    """US forecast from the pooled model; 'mean' holds the median, the point forecast it was scored on."""
    rate = (raw.pivot_table(index='date', columns='location_name', values='weekly_rate')
               .sort_index().asfreq('W-SAT'))
    us = raw[raw.location == 'US'].set_index('date')['value'].sort_index().asfreq('W-SAT')
    scale = (us / rate['US']).median()                    # admissions per unit of weekly_rate (US population)
    last = rate['US'].dropna().index.max()                # newest week with US data
    tr_all = build_train(rate)
    train = tr_all[tr_all['date'].dt.month.isin(FLU_MONTHS)]
    now = tr_all[(tr_all['location_name'] == 'US') & (tr_all['date'] == last)]
    rows = []
    for h in range(1, 5):
        tr = train[train['horizon'] == h].dropna()       # rows whose outcome is already known
        X = np.c_[tr[FEATURES].values, np.ones(len(tr))]
        beta = np.linalg.lstsq(X, tr['target'].values, rcond=None)[0]
        err = tr['target'].values - X @ beta              # past errors set the range
        x_now = now[now['horizon'] == h].iloc[0]
        zhat = x_now['level'] + np.r_[x_now[FEATURES].values.astype(float), 1.0] @ beta
        q = {col: max(zhat + np.quantile(err, p), 0) ** 4 * scale for col, p in QUANTILES.items()}
        rows.append({'model': 'pooled-flu', 'made_on': pd.Timestamp.today().normalize(),
                     'target_week': last + pd.Timedelta(weeks=h), 'horizon': h, 'mean': q['q50'], **q})
    out = pd.DataFrame(rows)
    out = out[out['target_week'] > out['made_on']]
    return out.reset_index(drop=True)

import os

PRED_PATH = 'data/predictions.csv'
KEY = ['model', 'made_on', 'target_week']   # one row per model per forecast

def with_model(df):
    """Rows logged before the pooled model was added are SARIMA's."""
    if 'model' not in df.columns:
        df = df.assign(model='SARIMA')
    return df.assign(model=df['model'].fillna('SARIMA'))

def log_predictions(rows):
    if os.path.exists(PRED_PATH):
        old = with_model(pd.read_csv(PRED_PATH, parse_dates=['made_on', 'target_week']))
    else:
        old = rows.iloc[0:0]                     # an empty table with the same columns
    combined = pd.concat([old, rows])
    combined = combined.drop_duplicates(subset=KEY, keep='first')
    combined = combined[['model'] + [c for c in combined.columns if c != 'model']]
    combined.to_csv(PRED_PATH, index=False)
    print(f'predictions log: {len(combined) - len(old)} new rows, {len(combined)} total')

SCORE_PATH = 'data/scores.csv'
SETTLE_WEEKS = 2          # only score weeks at least this old (first reports run ~9% low)

def score(y):
    if not os.path.exists(PRED_PATH):
        print('scores: no predictions logged yet')
        return

    preds = with_model(pd.read_csv(PRED_PATH, parse_dates=['made_on', 'target_week']))
    if os.path.exists(SCORE_PATH):
        done = with_model(pd.read_csv(SCORE_PATH, parse_dates=['made_on', 'target_week']))
    else:
        done = pd.DataFrame(columns=KEY)

    # 1. not already scored (anti-join)
    merged = preds.merge(done[KEY], on=KEY, how='left', indicator=True)
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
        'model':       todo['model'].values,
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
ALERT_MODEL = 'pooled-flu'   # the model the dashboard shows; SARIMA is still logged and scored

def alert_status(y):
    """(number of recent scored 4-week forecasts, model MAE, naive MAE); MAEs are None until there are enough."""
    if not os.path.exists(SCORE_PATH):
        return 0, None, None
    s = pd.read_csv(SCORE_PATH, parse_dates=['made_on', 'target_week'])
    if 'model' in s.columns:
        s = s[s['model'] == ALERT_MODEL]
    recent = s[s['horizon'] == 4].sort_values('target_week').tail(ALERT_WINDOW)
    if len(recent) < ALERT_WINDOW:
        return len(recent), None, None
    naive = y.reindex(recent['target_week'] - pd.Timedelta(weeks=52)).values
    return len(recent), recent['abs_error'].mean(), np.abs(recent['actual'].values - naive).mean()

def check_alert(y):
    if not os.path.exists(SCORE_PATH):
        print('alert check: no scores yet')
        return
    n, model_mae, naive_mae = alert_status(y)
    if model_mae is None:
        print(f'alert check: only {n} scored 4-week forecasts, need {ALERT_WINDOW}')
        return
    print(f'alert check: last {ALERT_WINDOW} 4-week forecasts | model MAE {model_mae:,.0f} | naive MAE {naive_mae:,.0f}')

    if model_mae > naive_mae:
        print('ALERT: the model is no longer beating "same week last year"')
        sys.exit(1) 



if __name__ == '__main__':
    y = load_data()
    rows = pd.concat([make_forecast(y), make_pooled_forecast(load_raw())])
    log_predictions(rows)
    score(y)
    check_alert(y)
