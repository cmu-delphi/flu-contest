"""
===============
=== Purpose ===
===============

*** WARNING: This will trigger scoring and emails! ***

Performs database updates for Epicast-FLUV:
  `history` update: import wILI from Epidata API
  `round` update: increments the deadline by a week



=================
=== Changelog ===
=================

2017-09-11
  * don't update during the offseason
2016-12-14
  + use secrets
2015-12-04
  * Enabled scoring
2015-11-13
  * Reformatted header and comments
  * Enabled sending out notification emails
2015-09-28
  * Using database `epicast2` instead of `epicast`
  * Using Epidata API for history update
  * Using new field names for `ec_fluv_round`
  * Temporarily disabled scoring and notifications
2014-01-05
  * Enabled sending out notification emails
2014-01-03
  * Temporarily disabled sending out notification emails
2014-12-30
  * Added and commented out a killswitch
2014-11-??
  * Original version
"""

import argparse

import mysql.connector

from delphi_epidata import Epidata
from epiweek import *
import secrets

# # Temporary hack to disable epicast updates (killswitch)
# import sys
# print('FLUV Updates are temporarily disabled!')
# sys.exit(0)

# Args and usage
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='store_const', const=True, default=False, help="show debugging output")
parser.add_argument('-t', '--test', action='store_const', const=True, default=False, help="do dry run only, don't update the database")
parser.add_argument('action', action='store', choices=['history', 'round'], help="the action to perform")
args = parser.parse_args()

# Utils
def get_rows(cnx):
  select = cnx.cursor()
  select.execute('SELECT count(1) num FROM ec_fluv_history')
  for (num,) in select:
    rows = num
  select.close()
  return rows

def execute_sql(cursor, sql, readonly=False):
  if args.verbose:
    print(sql)
  if readonly or not args.test:
    cursor.execute(sql)

def check(res):
  if res['result'] != 1:
    raise Exception('API failure (%d|%s)' % (res['result'], res['message']))
  return res['epidata']


def main():
  # DB stuff
  u, p = secrets.db.epi
  cnx = mysql.connector.connect(user=u, password=p, database='epicast2')
  cur = cnx.cursor()

  # Do work
  if args.action == 'history':
    print('Updating ec_fluv_history')
    epiweek_new = check(Epidata.fluview(['nat'], Epidata.range(201501, 203001)))[-1]['epiweek']
    rows1 = get_rows(cnx)
    print('rows before: %d' % (rows1))
    execute_sql(cur, 'SELECT coalesce(max(`epiweek`), 0) FROM ec_fluv_history', True)
    for (epiweek_old, ) in cur:
      pass
    print('Old epiweek: %d | New epiweek: %d' % (epiweek_old, epiweek_new))
    if epiweek_old == epiweek_new:
      print('No new data - nothing to do')
    elif epiweek_old < epiweek_new:
      print('New data available!')
      # Check to see if we are in the offseason
      execute_sql(cur, 'SELECT `first_round_epiweek`, `last_round_epiweek` FROM ec_fluv_season', True)
      for (ew1, ew2) in cur:
        if not (ew1 <= epiweek_new <= ew2):
          print('new data is outside of current season [%d-%d]' % (ew1, ew2))
          return
      # Generate the new data table and do the swap
      execute_sql(cur, 'UPDATE ec_fluv_round SET `data_epiweek` = %d' % epiweek_new)
      execute_sql(cur, 'TRUNCATE TABLE ec_fluv_history_stage')
      for (region_id, region_label) in zip([i for i in range(1, 12)], ['nat'] + ['hhs%d' % r for r in range(1, 11)]):
        print(' Updating %s...' % region_label)
        if args.test: continue
        for row in check(Epidata.fluview(region_label, Epidata.range(199740, 203001))):
          cur.execute('INSERT INTO ec_fluv_history_stage (`region_id`, `epiweek`, `wili`) VALUES (%s, %s, %s)', (region_id, row['epiweek'], row['wili']))
      execute_sql(cur, 'ALTER TABLE ec_fluv_history RENAME TO ec_fluv_history_temp')
      execute_sql(cur, 'ALTER TABLE ec_fluv_history_stage RENAME TO ec_fluv_history')
      execute_sql(cur, 'ALTER TABLE ec_fluv_history_temp RENAME TO ec_fluv_history_stage')
      execute_sql(cur, 'TRUNCATE TABLE ec_fluv_history_stage')
      # Queue an email to myself
      execute_sql(cur, "INSERT INTO automation.email_queue (`from`, `to`, `subject`, `body`) VALUES ('%s', '%s', '[DELPHI] New FluView Data', 'Another week of FluView data is now available - Happy forecasting!')" % (secrets.flucontest.email_epicast, secrets.flucontest.email_maintainer))
      execute_sql(cur, 'CALL automation.RunStep(2)')
      # Queue the score updater
      execute_sql(cur, 'CALL automation.RunStep(8)')
      # Queue the notification emails
      execute_sql(cur, 'CALL automation.RunStep(9)')
    else:
      raise Exception('The new data is older than the old data?!')
    rows2 = get_rows(cnx)
    print('rows after: %d (added %d)' % (rows2, rows2 - rows1))
  elif args.action == 'round':
    print('Updating ec_fluv_round')
    execute_sql(cur, 'SELECT `round_epiweek`, `deadline` FROM ec_fluv_round', True)
    for (epiweek, deadline) in cur:
      pass
    print('Last round was %d, due %s' % (epiweek, deadline))
    epiweek = add_epiweeks(epiweek, 1)
    print('Next round is %d' % (epiweek))
    execute_sql(cur, 'UPDATE ec_fluv_round SET `round_epiweek` = %d, `deadline` = date_add(`deadline`, INTERVAL 1 WEEK)' % (epiweek))

  # Cleanup
  cnx.commit()
  cur.close()
  cnx.close()


if __name__ == '__main__':
  main()
