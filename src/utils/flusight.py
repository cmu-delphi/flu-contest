"""
===============
=== Purpose ===
===============

Submits forecasts to FluSight, which is CDC's flu contest interface at
https://predict.phiresearchlab.org.

After submission, forecasts are downloaded and compared to the original upload
to make sure the correct data has been recorded.


=================
=== Changelog ===
=================

2016-12-05
  + first version
"""

# standard library
import argparse
import datetime
import json
import urllib.parse
import re

# third party
import requests

# first party
from .forecast_io import ForecastIO


def submit(email, password, filename, date=None, insane=False):
  # helper to find the correct submission deadline
  def get_days_apart(expected, found):
    d1 = datetime.datetime.strptime(expected, '%Y-%m-%d')
    d2 = datetime.datetime.strptime(found, '%Y-%m-%d')
    return abs((d2 - d1).days)

  # basic setup
  base_url = 'https://predict.phiresearchlab.org/api/v1'
  s = requests.session()
  forecast = ForecastIO.load_csv(filename)
  if not insane:
    forecast.sanity_check()

  # get the forecast date
  if date is None:
    m = re.match('^EW\\d{2}-.*-(\\d{4}-\\d{2}-\\d{2}).csv$', filename)
    if m is None:
      raise Exception('unable to parse filename')
    date = m.group(1)
  print('expect deadline near %s' % date)

  # login and get FluSight project ID
  data = {
    'email': email,
    'password': password,
  }
  resp = s.post('%s/login' % base_url, json=data)
  if resp.status_code != 200:
    print(resp.text)
    raise Exception(resp.status_code)
  user_info = resp.json()
  project_id = None
  for project in user_info['projects']:
    if project['name'] == 'FluSight':
      project_id = project['_id']
      break
  if project_id is None:
    raise Exception('couldnt find FluSight project id')

  # get team name
  resp = s.get('%s/projects/%s/teams' % (base_url, project_id))
  if resp.status_code != 200:
    print(resp.text)
    raise Exception(resp.status_code)
  team_info = resp.json()
  if len(team_info) != 1:
    raise Exception('expected 1 team, found ' + len(team_info))
  team_name = team_info[0]
  print('team name is %s (server), %s (local)' % (team_name, forecast.team))

  # get forecast info
  target_deadline = date
  resp = s.get('%s/projects/%s/forecasts' % (base_url, project_id))
  if resp.status_code != 200:
    print(resp.text)
    raise Exception(resp.status_code)
  forecast_weeks = resp.json()
  best_deadline, best_days, best_index = None, None, None
  for (index, forecast_info) in enumerate(forecast_weeks):
    deadline = forecast_info['date'][:10]
    forecast_ids = forecast_info['_ids']
    days_apart = get_days_apart(target_deadline, deadline)
    if best_deadline is None or days_apart < best_days:
      best_deadline, best_days, best_index = deadline, days_apart, index
  if best_days is None or best_days > 2:
    raise Exception('could not find deadline like %s' % target_deadline)
  if best_days > 0:
    print('warning: could not find exact deadline of %s' % target_deadline)
  print('uploading for deadline %s' % best_deadline)
  forecast_ids = forecast_weeks[best_index]['_ids']
  num_ids = len(forecast_ids)
  if num_ids != 77:
    raise Exception('wrong number of forecast IDs: %s' % num_ids)

  # upload submission
  team_url = urllib.parse.quote(team_name)
  url = '%s/projects/%s/team-handouts/%s' % (base_url, project_id, team_url)
  with open(filename, 'rb') as f:
    file_size = len(f.read())
  current_timestamp = int(datetime.datetime.now().timestamp() * 1000)
  forecast_json = forecast.export_json_flusight()
  data = {
    'project': project_id,
    'forecasts': json.dumps(forecast_ids),
    'team': team_name,
    'meta': json.dumps({
      'name': filename,
      'size': file_size,
      'lastModified': current_timestamp,
      'type': 'text/csv',
    })
  }
  files = {
    'file': ('submission.json', forecast_json, 'application/json'),
  }
  resp = s.post(url, files=files, data=data)
  if resp.status_code != 201:
    print(resp.text)
    raise Exception(resp.status_code)
  handout_id = resp.json()['_id']
  print('submitted forecast, handout is %s' % handout_id)

  # as a sanity check, find the submission timestamp
  resp = s.get('%s/projects/%s/handouts' % (base_url, project_id))
  if resp.status_code != 200:
    print(resp.text)
    raise Exception(resp.status_code)
  handouts = resp.json()
  found = False
  for handout in handouts:
    if handout['_id'] == handout_id:
      print('server-side timestamp was %s' % (handout['date']))
      found = True
      break
  if not found:
    raise Exception('submission not found on server')

  # download the submission
  resp = s.get('%s/handouts/%s' % (base_url, handout_id))
  if resp.status_code != 200:
    print(resp.text)
    raise Exception(resp.status_code)
  server_json = resp.text
  print('downloaded json from server (%d bytes)' % len(server_json))

  # verify that the forecast matches what was submitted
  team = forecast.team
  timestamp = forecast.timestamp
  season = forecast.season
  epiweek = forecast.epiweek
  args = (server_json, team, timestamp, season, epiweek)
  f2 = ForecastIO.import_json_flusight(*args)
  if not insane:
    f2.sanity_check()
  if not f2.equals(forecast):
    raise Exception('uploaded forecast differs from downloaded forecast')
  print('uploaded forecast matches downloaded forecast')


if __name__ == '__main__':
  # args and usage
  parser = argparse.ArgumentParser()
  parser.add_argument('email', type=str, help='FluSight login email')
  parser.add_argument('password', type=str, help='FluSight login password')
  parser.add_argument('filename', type=str, help='forecast file')
  parser.add_argument('--date', '-d', default=None, type=str, help='submission deadline (otherwise guess from forecast)')
  parser.add_argument('--insane', '-i', default=False, action='store_true', help='skip forecast sanity checks')
  args = parser.parse_args()

  # submit the forecast
  submit(args.email, args.password, args.filename, args.date, args.insane)
