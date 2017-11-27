from delphi_epidata import Epidata
import mysql.connector
import secrets
import epiweek as epi_utils

# Connect to epicast2 database
u, p = secrets.db.epi
cnx = mysql.connector.connect(user=u, password=p, database='epicast2')
cur = cnx.cursor(buffered=True)


# Get ground truth
history = {}
regions = ["nat","hhs1","hhs2","hhs3","hhs4","hhs5","hhs6","hhs7","hhs8","hhs9","hhs10","ga","pa","dc","tx","or"]
# for 2017-18 season, 201744 is the first ground truth data we get after the competition starts (i.e., users forecasted for it in 201743)
#############################################################
season_start, season_end = 201744, 201820

for r in range(1, len(regions)+1):
  history[r] = {}
  rows = Epidata.check(Epidata.fluview(regions[r-1], Epidata.range(season_start, season_end)))
  truth = [(row['epiweek'], row['wili']) for row in rows]
  availableWeeks = [row[0] for row in truth]
  for row in truth:
    (epiweek, wili) = row
    history[r][epiweek] = wili
    print(regions[r-1], epiweek, wili)

epiweek = availableWeeks[-1]
print("epiweek", epiweek)
if (epiweek == 201801): forecast_made = 201752
else: forecast_made = epiweek-1

# debug print
print("availableWeeks", availableWeeks)
expected_weeks = epi_utils.delta_epiweeks(season_start, epiweek) + 1
num_weeks = len(history[1])
print('loaded history for %d weeks' % (num_weeks))
# #######################################################
if num_weeks != expected_weeks:
  raise Exception('expected %d weeks of history, but found %d weeks instead' % (expected_weeks, num_weeks))


# Get all user_id
cur.execute("select id from ec_fluv_users") # maybe need to investigate more about _debug???
num_users = 0
user_ids = []
for user_id in cur:
  num_users += 1
  user_ids.append(user_id[0])


# Get the forecasts
forecast = {}
for r in range(1, len(regions)+1): 
  # r is region_id
  forecast[r] = {}
  ################################# might need to check this season_end and inclusive_false at the end of the season, season_start-1?
  for ew1 in epi_utils.range_epiweeks(season_start-1, season_end, inclusive=False):
    forecast[r][ew1] = {}
    for ew2 in epi_utils.range_epiweeks(epi_utils.add_epiweeks(ew1, 1), season_end, inclusive=True):
      forecast[r][ew1][ew2] = {}
      for user_id in user_ids:
        forecast[r][ew1][ew2][user_id] = -200


cur.execute("""
  select f.user_id, f.region_id, f.epiweek_now, f.epiweek, f.wili from ec_fluv_forecast f 
  JOIN ec_fluv_submissions s ON f.user_id = s.user_id AND f.region_id = s.region_id AND
  f.epiweek_now = s.epiweek_now where f.epiweek_now >= 201743 and f.epiweek <= 201820""")

num_predictions = 0
for (u, r, ew1, ew2, wili) in cur:
  # we asked users to forecast 14 regions in week 201743 and 16 regions from 201744
  if ((ew1 == 201743 and r <= len(regions)-2) or (ew1 > 201743 and r <= 16)):  
  # if ((ew1 == 201743 and r <= len(regions)) or (ew1 > 201743 and r <= 14)):  
    try:
      forecast[r][ew1][ew2][u] = wili
      num_predictions += 1
    except:
      # print(u, r, ew1, ew2, wili)
      raise Exception()
      pass
print('loaded %d predictions for %d users' % (num_predictions, num_users))


# rank users in each cell by absolute error
scores = {}
print("user_ids in the order of best accuracy to worst accuracy")
print("i: week during which users submitted input")
print("j: week for which we have ground truth")
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
          # print("u",u,"r",r,"ew1",ew1,"ew2",ew2,"forecast",forecast[r][ew1][ew2][u],"r",r,"truth",history[r][ew2],"error", error)
        else:
          error = 0
        ranking.append({ 'u': u, 'error': error, 'rank': 0, 'score': 0})
      ranking = sorted(ranking, key=lambda x: x['error'])

      # debug print
      if (ew2 == 201745):
        print(regions[r-1],"i:", ew1, "j:",ew2, [y['u'] for y in ranking])


      last_error, last_rank = 0, 1
      for (i, row) in enumerate(ranking):
        new_error, new_rank = row['error'], i + 1
        if new_error == last_error:
          new_rank, new_error = last_rank, last_error
        else:
          last_rank, last_error = new_rank, new_error
        row['rank'] = new_rank
        # if (ew2 == 201744):
          # print("for week 201744,","r",r,"u",row['u'], "rank", row['rank'])
        row['score'] = 1 / row['rank']
      for row in ranking:
        u = row['u']
        scores[r][ew1][ew2][u] = row

# helper to get scores on a column (different ew1, same ew2) of the score table
# weekly score is the sum of all (ew1, epiweek) scores
def get_weekly_score(u, ew2):
  max_score, min_score = 0, 0
  user_score = 0
  for ew1 in epi_utils.range_epiweeks(201743, ew2, inclusive=False):
    weight = 1 / epi_utils.delta_epiweeks(ew1, ew2)
    for r in range(1, len(regions)+1):
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

# def get_weekly_score(u, ew2):
#   max_score, min_score = 0, 0
#   user_score = 0
#   # for ew1 in epi_utils.range_epiweeks(201743, ew2, inclusive=False):
#   ew1 = 201743
#   ew2 = 201744
#   weight = 1 / epi_utils.delta_epiweeks(ew1, ew2)
#   delta = (1 / num_users) * weight
#   # print("weight", weight)
#   # print("delta", delta)

#   for r in range(1, len(regions)+1):

#     max_score += weight
#     min_score += delta
#     user_score += scores[r][ew1][ew2][u]['score'] * weight
#     # print("r", r, "u", u, "row_score", scores[r][ew1][ew2][u]['score'])
#   # print("r", r, "u", u, "user_score", user_score)
    
#   # normalized
#   score = (user_score - min_score) / (max_score - min_score)
#   # print("u", u, "normalized score", score)
#   # boosted
#   score = 1 - ((1 - score) ** 2)
#   # print("u", u, "boosted score", score)
#   # rescaled
#   score = 500 + 500 * score
#   # print("u", u, "rescaled score", score)
#   return score



# calculate total and weekly score for each user
for u in user_ids:

  user_scores = []
  # compute weekly scores
  for ew2 in epi_utils.range_epiweeks(season_start, availableWeeks[-1], inclusive=True):
    score = get_weekly_score(u, ew2)
    user_scores.append(score)
    

  # total score and last week's score
  total, last = sum(user_scores), user_scores[-1]
  print('user %d: total=%.3d last=%.3f' % (u, total, last))


# for u in user_ids:
#   user_scores = []
#   score = get_weekly_score(u, 201744)
#   user_scores.append(score)
#   # total score and last week's score
#   total, last = sum(user_scores), user_scores[-1]
#   print('user %d: total=%.3d last=%.3f' % (u, total, last))


  # Save to database
  cur.execute("""
    INSERT INTO ec_fluv_scores (`user_id`, `total`, `last`, `updated`) VALUES(%s, %s, %s, now()) ON DUPLICATE KEY UPDATE `total` = %s, `last` = %s, `updated` = now()
  """, (u, total, last, total, last))

cnx.commit()
cur.close()
cnx.close()
