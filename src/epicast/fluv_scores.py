"""
===============
=== Purpose ===
===============

Scores Epicast FLUV users.


=================
=== Changelog ===
=================

2016-12-14
  + use secrets
2016-10-24
  * update valid epiweeks based on 2016 flu contest
2015-12-17
  * complete rewrite of scoring, now based on ranking
2015-12-04
  * only scoring first four weeks (still linear weight decrease)
  * added --user argument for debugging
  * more lenient scoring when missing regions or entire weeks
2015-11-13
  * reformatted header and comments
  * use database epicast2
  * updated epiweek bounds for 2015-2016 season
  * use SQL parameters instead of string formatting
  * changed from weighted to unweighted regional mean
2014-11-09
  * replacing missing values with most recent forecast instead of zero
"""

import argparse

import mysql.connector

from epiweek import *
import secrets

# Args and usage
parser = argparse.ArgumentParser()
parser.add_argument('-w', '--epiweek', action='store', type=int, help="epiweek override (yyyyww); default most recent epiweek")
parser.add_argument('-v', '--verbose', action='store_const', default=False, const=True, help="show extra output")
parser.add_argument('-t', '--test', action='store_const', default=False, const=True, help="test mode, don't update the database")
parser.add_argument('-u', '--user', action='store', default=None, type=int, help="show extra output for a specific user")
args = parser.parse_args()

# DB stuff
u, p = secrets.db.epi
cnx = mysql.connector.connect(user=u, password=p, database='epicast2')
cur = cnx.cursor()

# Get the epiweek
if args.epiweek is None:
  cur.execute('SELECT max(`epiweek`) `epiweek` FROM ec_fluv_history')
  for (epiweek,) in cur:
    pass
else:
  epiweek = args.epiweek
if epiweek < 201641 or epiweek > 201721 or not check_epiweek(epiweek):
  raise Exception('invalid epiweek %d' % (epiweek))
print('latest epiweek: %d' % (epiweek))

# Calculate the expected length of each forecast (and other important dates)
season_start, season_end = get_season(epiweek)
if season_start is None:
  raise Exception('this is the offseason')
if epiweek <= season_start:
  raise Exception('epiweek <= season_start')
expected_weeks = delta_epiweeks(season_start, epiweek) + 1
print('current season: %d-%d (currently %d weeks in)' % (season_start // 100, season_end // 100, expected_weeks))

# Get the history
history = {}
cur.execute("""
  SELECT `region_id`, `epiweek`, `wili` FROM ec_fluv_history WHERE `epiweek` BETWEEN %s AND %s ORDER BY `region_id` ASC, `epiweek` ASC
""", (season_start, epiweek))
for (r, ew, wili) in cur:
  if r not in history:
    history[r] = {}
  history[r][ew] = wili
num_weeks = len(history[1])
print('loaded history for %d weeks' % (num_weeks))
if num_weeks != expected_weeks:
  raise Exception('expected %d weeks of history, but found %d weeks instead' % (expected_weeks, num_weeks))

# Get the forecasts
forecast = {}
for r in range(1, 12):
  forecast[r] = {}
  for ew1 in range_epiweeks(season_start, season_end, inclusive=False):
    forecast[r][ew1] = {}
    for ew2 in range_epiweeks(add_epiweeks(ew1, 1), season_end, inclusive=True):
      forecast[r][ew1][ew2] = {}
cur.execute("""
  select u.id, coalesce(p.value, d.value) debug from ec_fluv_users u join ec_fluv_defaults d on d.name = '_debug' left join ec_fluv_user_preferences p on p.user_id = u.id and p.name = d.name where coalesce(p.value, d.value) = 0 order by u.id asc
""")
num_users = 0
user_ids = []
for (u, d) in cur:
  num_users += 1
  user_ids.append(u)
  for r in forecast:
    for ew1 in forecast[r]:
      for ew2 in forecast[r][ew1]:
        forecast[r][ew1][ew2][u] = 0
cur.execute("""
  select f.user_id, f.region_id, f.epiweek_now, f.epiweek, f.wili from ec_fluv_forecast f where f.epiweek_now >= %s and f.epiweek <= %s
""", (season_start, season_end))
num_predictions = 0
for (u, r, ew1, ew2, wili) in cur:
  try:
    forecast[r][ew1][ew2][u] = wili
    num_predictions += 1
  except:
    print(u, r, ew1, ew2, wili)
    raise Exception()
    pass
print('loaded %d predictions for %d users' % (num_predictions, num_users))

# rank users in each cell by absolute error
scores = {}
for r in forecast:
  scores[r] = {}
  for ew1 in forecast[r]:
    scores[r][ew1] = {}
    for ew2 in forecast[r][ew1]:
      scores[r][ew1][ew2] = {}
      ranking = []
      for u in forecast[r][ew1][ew2]:
        if ew2 in history[r]:
          error = abs(forecast[r][ew1][ew2][u] - history[r][ew2])
        else:
          error = 0
        ranking.append({ 'u': u, 'error': error, 'rank': 0, 'score': 0})
      ranking = sorted(ranking, key=lambda x: x['error'])
      last_error, last_rank = 0, 1
      for (i, row) in enumerate(ranking):
        new_error, new_rank = row['error'], i + 1
        if new_error == last_error:
          new_rank, new_error = last_rank, last_error
        else:
          last_rank, last_error = new_rank, new_error
        row['rank'] = new_rank
        row['score'] = 1 / row['rank']
      for row in ranking:
        u = row['u']
        scores[r][ew1][ew2][u] = row
if args.user is not None:
  row = scores[1][season_start][epiweek][args.user]
  print('[user %d scored %.3f (#%d) on %d forecasting %d (nat)]' % (args.user, row['score'], row['rank'], season_start, epiweek))

# helper to get scores on a column (different ew1, same ew2) of the score table
def get_weekly_score(u, ew2):
  max_score, min_score = 0, 0
  user_score = 0
  for ew1 in range_epiweeks(season_start, ew2, inclusive=False):
    weight = 1 / delta_epiweeks(ew1, ew2)
    for r in range(1, 12):
      max_score += weight
      min_score += (1 / num_users) * weight
      user_score += scores[r][ew1][ew2][u]['score'] * weight
  # normalized
  score = (user_score - min_score) / (max_score - min_score)
  # boosted
  score = 1 - ((1 - score) ** 2)
  # rescaled
  score = 500 + 500 * score
  return score

# calculate total and weekly score for each user
for u in user_ids:

  user_scores = []
  # compute weekly scores
  for ew2 in range_epiweeks(season_start, epiweek):
    issue = add_epiweeks(ew2, 1)
    # weekly score is the sum of all (ew1, epiweek) scores
    score = get_weekly_score(u, issue)
    user_scores.append(score)
    if u == args.user:
      print('[user %d scored %.3f on issue %d]' % (args.user, score, issue))

  # total score and last week's score
  total, last = sum(user_scores), user_scores[-1]
  print('user %d: total=%.3d last=%.3f' % (u, total, last))

  # Save to database
  cur.execute("""
    INSERT INTO ec_fluv_scores (`user_id`, `total`, `last`, `updated`) VALUES(%s, %s, %s, now()) ON DUPLICATE KEY UPDATE `total` = %s, `last` = %s, `updated` = now()
  """, (u, total, last, total, last))

# Cleanup
if args.test:
  print('test mode - not committing')
else:
  cnx.commit()
  print('scores updated')
cur.close()
cnx.close()
