"""Publish the dashboard's data to a Google Sheet, which Tableau Public reads.

Runs after monitor.py in the weekly workflow. Each tab is replaced in full every run:

  status       one row: when the data was updated, latest week, the drift check
  forecast     the latest pooled-model forecast, 1-4 weeks ahead, ten percentiles
  fan          ready for the fan chart: this season's actuals + the forecast's median and 50%/80% bands
  actuals      weekly US admissions, with season and week-of-season for comparing seasons
  forecast_log every forecast logged so far, both models
  scores       every scored forecast so far
  backtest     static: the real-time backtest (notebook 06), pooled model vs CDC ensemble and baseline

Needs GCP_SA_KEY (service-account JSON) and DASHBOARD_SHEET_ID in the environment.
"""
import json, os
from datetime import datetime, timezone
import numpy as np, pandas as pd
import gspread
import monitor

BACKTEST_PATH = 'data/dashboard/backtest_us.csv'

def season_columns(dates):
    """Season label ('2025-26') and weeks since the season started (first Saturday on or after 1 Aug)."""
    start_year = np.where(dates.dt.month >= 8, dates.dt.year, dates.dt.year - 1)
    aug1 = pd.to_datetime([f'{y}-08-01' for y in start_year])
    first_sat = aug1 + pd.to_timedelta((5 - aug1.dayofweek) % 7, unit='D')
    label = [f'{y}-{str(y + 1)[2:]}' for y in start_year]
    week = ((dates.values - first_sat.values) / np.timedelta64(7, 'D')).astype(int) + 1
    return label, week

def build_tables():
    y = monitor.load_data().dropna()
    latest = y.index.max()

    actuals = pd.DataFrame({'week': y.index, 'admissions': y.values})
    actuals['season'], actuals['season_week'] = season_columns(actuals['week'])
    actuals['is_latest_week'] = actuals['week'] == latest   # first reports run ~9% low; dashboard flags it

    log = monitor.with_model(pd.read_csv(monitor.PRED_PATH, parse_dates=['made_on', 'target_week']))
    pooled = log[log['model'] == monitor.ALERT_MODEL]
    newest = pooled[pooled['made_on'] == pooled['made_on'].max()]
    qcols = list(monitor.QUANTILES)
    anchor = {'target_week': latest, 'horizon': 0, **{c: y[latest] for c in qcols}}  # joins the fan to the actuals
    forecast = pd.concat([pd.DataFrame([anchor]), newest[['target_week', 'horizon'] + qcols]], ignore_index=True)
    forecast['made_on'] = newest['made_on'].max()

    # Bands as a lower edge + a width, so Tableau can draw them as stacked areas (lower edge transparent)
    season_now = actuals.loc[actuals['week'] == latest, 'season'].iloc[0]
    recent = actuals[actuals['season'] == season_now]
    fan = pd.concat([
        pd.DataFrame({'week': recent['week'], 'actual': recent['admissions']}),
        pd.DataFrame({'week': forecast['target_week'], 'forecast_median': forecast['q50'],
                      'low_80': forecast['q10'], 'band_80': forecast['q90'] - forecast['q10'],
                      'low_50': forecast['q25'], 'band_50': forecast['q75'] - forecast['q25']}),
    ], ignore_index=True)
    fan['horizon'] = ((fan['week'] - latest) / pd.Timedelta(weeks=1)).astype(int).clip(lower=0)

    if os.path.exists(monitor.SCORE_PATH):
        scores = monitor.with_model(pd.read_csv(monitor.SCORE_PATH, parse_dates=['made_on', 'target_week']))
    else:
        scores = pd.DataFrame(columns=['model', 'target_week', 'made_on', 'horizon', 'predicted', 'actual', 'abs_error'])

    n, model_mae, naive_mae = monitor.alert_status(y)
    if model_mae is None:
        state = f'Not enough scored forecasts yet ({n} of {monitor.ALERT_WINDOW})'
    elif model_mae > naive_mae:
        state = 'ALERT: not beating "same week last year"'
    else:
        state = 'On track'
    status = pd.DataFrame([{
        'updated_at_utc': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M'),
        'data_through': latest, 'latest_admissions': y[latest],
        'monitor_status': state, 'model_mae_last4': model_mae, 'naive_mae_last4': naive_mae,
    }])

    backtest = pd.read_csv(BACKTEST_PATH)
    return {'status': status, 'forecast': forecast, 'fan': fan, 'actuals': actuals,
            'forecast_log': log, 'scores': scores, 'backtest': backtest}

def to_values(df):
    """A DataFrame as a list of rows for the Sheets API: dates as YYYY-MM-DD, blanks for missing values."""
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime('%Y-%m-%d')
        elif pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round(2)
    out = out.astype(object).where(out.notna(), '')
    return [list(out.columns)] + out.values.tolist()

def publish(tables, sheet):
    existing = {ws.title: ws for ws in sheet.worksheets()}
    for name, df in tables.items():
        values = to_values(df)
        rows, cols = len(values), len(values[0])
        ws = existing.get(name) or sheet.add_worksheet(title=name, rows=rows, cols=cols)
        ws.clear()
        ws.resize(rows=rows, cols=cols)
        ws.update(values=values, range_name='A1', value_input_option='USER_ENTERED')
        print(f'sheet tab {name}: {rows - 1} rows')

if __name__ == '__main__':
    tables = build_tables()
    gc = gspread.service_account_from_dict(json.loads(os.environ['GCP_SA_KEY']))
    publish(tables, gc.open_by_key(os.environ['DASHBOARD_SHEET_ID']))
