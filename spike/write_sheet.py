"""Spike test: can a GitHub Action write to a Google Sheet that Tableau Public refreshes?

Appends one row (UTC time, run number) to the first tab of the sheet. Delete this
folder and sheet-spike.yml once the test is answered.
"""
import json, os
from datetime import datetime, timezone
import gspread

gc = gspread.service_account_from_dict(json.loads(os.environ['GCP_SA_KEY']))
ws = gc.open_by_key(os.environ['SHEET_ID']).sheet1
if not any(ws.row_values(1)):
    ws.append_row(['written_at_utc', 'run'])
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
ws.append_row([now, os.environ.get('GITHUB_RUN_NUMBER', 'local')])
print('wrote row:', now)
