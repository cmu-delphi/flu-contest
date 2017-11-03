"""
===============
=== Purpose ===
===============

Extracts forecast from CDC contest submission, exports to JSON string, and
stores in the database.


=======================
=== Data Dictionary ===
=======================

`forecasts` is where forecast data and metadata is stored. The forecast data is
stored as a JSON string and is not intended to be queried directly.
+---------+-------------+------+-----+---------+----------------+
| Field   | Type        | Null | Key | Default | Extra          |
+---------+-------------+------+-----+---------+----------------+
| id      | int(11)     | NO   | PRI | NULL    | auto_increment |
| system  | varchar(64) | NO   | MUL | NULL    |                |
| epiweek | int(11)     | NO   | MUL | NULL    |                |
| json    | mediumtext  | NO   |     | NULL    |                |
+---------+-------------+------+-----+---------+----------------+
id: unique identifier for each record
system: name of the forecasting team/system
epiweek: the most recent ILINet issue when the forecast was created
json: a JSON string containing the full forecast (including all regions)


=================
=== Changelog ===
=================

2016-12-08
  + use secrets
2016-11-07
  * field `json` is now mediumtext for forecasts > 65kb
2015-12-14
  * minor changes for better programmatic access
2015-11-18
  * original version
"""

# built-in
import argparse
# external
import mysql.connector
# local
import epiweek as flu
from forecast_io import Forecast
import secrets


def load_submission(file, system=None, epiweek=None, insane=False, test=False, verbose=False):
  # logging
  log = print if verbose else lambda x: x

  # try to load broken submissions
  Forecast._permissive = True

  # load the forecast
  log('loading %s...' % file)
  fc = Forecast.read(file)
  log(' forecast file parsed')

  # set the system (team) name
  if system is None:
    systems = [
      ('ec', 'delphi-epicast'),
      ('eb', 'delphi-eb'),
      ('sp', 'delphi-spline'),
      ('st', 'delphi-stat'),
      ('af', 'delphi-archefilter'),
    ]
    num_found = 0
    for (name, label) in systems:
      if label in fc.team.lower():
        num_found += 1
        system = name
    if num_found != 1:
      raise Exception('unrecognized system/team name')
  log(' system: %s' % system)

  # override epiweek
  if epiweek is not None and flu.check_epiweek(epiweek):
    fc.epiweek = epiweek
    fc.epiweek2 = flu.split_epiweek(epiweek)[1]
  epiweek = fc.epiweek
  log(' epiweek: %d' % epiweek)

  # sanity check
  if insane:
    log(' sanity check skipped')
  elif fc.sanity_check():
    log(' sanity check passed')
  else:
    raise Exception('sanity check failed')

  # export JSON string
  fc_json = fc.export_json_delphi()
  log(' forecast exported (%.1f KB)' % (len(fc_json) / 1024))

  # store forecast
  u, p = secrets.db.epi
  cnx = mysql.connector.connect(user=u, password=p, database='epidata')
  log(' connected to database')
  sql = """
    INSERT INTO
      `forecasts` (`system`, `epiweek`, `json`)
    VALUES
      (%s, %s, %s)
    ON DUPLICATE KEY UPDATE
      `json` = %s
  """
  values = (system, epiweek, fc_json, fc_json)
  if test:
    log(' test mode, no commit')
  else:
    cur = cnx.cursor()
    cur.execute(sql, values)
    cur.close()
    cnx.commit()
    log(' forecast committed')

  # cleanup
  cnx.close()
  log('forecast loaded')


def main():
  # args and usage
  parser = argparse.ArgumentParser()
  parser.add_argument('file', help='the submission file (*.xlsx or *.csv)')
  parser.add_argument('-s', '--system', help='system override (ex: af, eb, ec, sp, st)')
  parser.add_argument('-w', '--epiweek', type=int, help='epiweek override')
  parser.add_argument('-i', '--insane', action='store_true', help='skip sanity check and ignore errors')
  parser.add_argument('-t', '--test', action='store_true', help='test only - do not commit')
  parser.add_argument('-v', '--verbose', action='store_true', help='show more output')
  args = parser.parse_args()

  # load the submission
  load_submission(args.file, args.system, args.epiweek, args.insane, args.test, args.verbose)


if __name__ == '__main__':
  main()
