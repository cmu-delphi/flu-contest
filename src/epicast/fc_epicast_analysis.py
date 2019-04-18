from statistics import median_low
import mysql.connector
import numpy as np
import scipy.stats
from ..forecasters.fc_abstract import Forecaster
from delphi.epidata.client.delphi_epidata import Epidata
import delphi.operations.secrets as secrets
import delphi.utils.epiweek as flu
from ..utils.forecast_type import ForecastType


class Epicast(Forecaster):

  def __init__(self, test_season, locations, forecast_type, verbose=False, users=None):
    super().__init__('epicast', test_season, locations, forecast_type, smooth_weeks_bw=0, smooth_wili_bw=0)
    self.verbose = verbose
    self.users = users

  @staticmethod
  def fit_distribution(values, num_bins, bin_size, first_value, unbounded, num_users):
    values = [v for v in values if v is not None]
    if len(values) == 0:
      values = [0]
    mu = np.median(values)
    if len(values) == 1:
      sigma = 0
    else:
      sigma = np.std(values, ddof=1)
    sigma = max(sigma, 1e-3)
    df = max(1, num_users - 1)
    cdf = scipy.stats.t(df, mu, sigma).cdf
    dist = []
    for i in range(num_bins):
      a = first_value + i * bin_size
      if unbounded and i == num_bins - 1:
        b = float('inf')
      else:
        b = a + bin_size
      dist.append(cdf(b) - cdf(a))
    dist = np.array(dist)
    mass = sum(dist)
    if mass > 0:
      dist /= mass
    return dist

  @staticmethod
  def get_week_forecast(num_users):
    def _forecast(first_epiweek, num_bins, indices, uniform_weight, smooth_bw, allow_none):
      if smooth_bw > 0:
        print(' [EC] warning: epicast doesnt smooth week bins, but smooth_bw = %.3f' % smooth_bw)
      num_none = indices.count(None)
      if num_none > 0 and not allow_none:
        raise Exception('target does not allow None, but None given')
      dist = Epicast.fit_distribution(indices, num_bins, 1, -0.5, False, num_users)
      dist *= len(indices) - num_none
      extra = [num_none] if allow_none else []
      dist = Forecaster.Utils.normalize(list(dist) + extra)
      dist = Forecaster.Utils.blend(dist, uniform_weight)
      if allow_none:
        dist, none = dist[:-1], dist[-1]
      else:
        none = None
      possibilities = [i for i in indices if i is not None]
      if len(possibilities) == 0:
        possibilities = [0]
      point = flu.add_epiweeks(first_epiweek, int(np.median(possibilities)))
      return (dist, none, point)
    return _forecast

  @staticmethod
  def get_wili_forecast(num_users):
    def _forecast(bin_size, num_bins, wili, uniform_weight, smooth_bw):
      if smooth_bw > 0:
        print(' [EC] warning: epicast doesnt smooth wILI bins, but smooth_bw = %.3f' % smooth_bw)
      dist = Epicast.fit_distribution(wili, num_bins, bin_size, 0, True, num_users)
      dist = Forecaster.Utils.normalize(dist)
      dist = Forecaster.Utils.blend(dist, uniform_weight)
      point = np.median(wili)
      return (dist, point)
    return _forecast


  def extractUsers(self, region, epiweek_now):
      self.cur = self.cnx.cursor()

      # 1. load forecast, with dimensions [location, user, ew2 (+1, 2, 3, 4)]
      epiweek_now = 201910

      # Get all user_id
      self.cur.execute("select distinct(user_id) from ec_fluv_forecast_mturk where epiweek_now = %d" % epiweek_now)
      num_users = 0
      user_ids = []
      for user_id in self.cur:
          user_id = user_id[0]
          if user_id not in [45, 312, 539, 670, 145, 410, 411, 1, 2, 3, 4, 5, 6, 7, 8]:
              num_users += 1
              user_ids.append(user_id)

      # Get forecasts
      forecast = {}
      region_ids = [i for i in range(1, 24)] + [i for i in range(25, 30)] + [i for i in range(31, 62)]
      region_user_map = {}
      for r in region_ids:
          forecast[r] = {}
          region_user_map[r] = {}
          for ew2 in range(epiweek_now + 1, epiweek_now + 5):
              forecast[r][ew2] = {}

      self.cur.execute("""
          select f.user_id, f.region_id, f.epiweek_now, f.epiweek, f.wili from ec_fluv_forecast_mturk f 
          JOIN ec_fluv_submissions_mturk s ON f.user_id = s.user_id AND f.region_id = s.region_id AND
          f.epiweek_now = s.epiweek_now where f.epiweek_now = %d and f.epiweek <= 201920""" % epiweek_now)

      num_predictions = 0
      for (u, r, ew1, ew2, wili) in self.cur:
          if ew1 == epiweek_now:
              try:
                  forecast[r][ew2][u] = wili
                  region_user_map[r][u] = 1
                  num_predictions += 1
              except:
                  pass

      # 2. for each location and epiweek, compute the median
      medians = {}
      for r in region_ids:
          medians[r] = {}
          for ew2 in range(epiweek_now + 1, epiweek_now + 5):
              # print('forecast for this region and ew2: ', list(forecast[r][ew2].keys()))
              medians[r][ew2] = np.median(list(forecast[r][ew2].values()))

      # 3. for each location, for each user, get the sum of distance of the 4 weeks' forecasts
      errors = {}
      for r in region_ids:
          errors[r] = {}
          for user_id in region_user_map[r]:
              errors[r][user_id] = 0
              for ew2 in range(epiweek_now + 1, epiweek_now + 5):
                  errors[r][user_id] += abs(medians[r][ew2] - forecast[r][ew2][user_id])

      # 4. for each region, rank the users and take the upper half
      topWorkers = {}
      for r in region_ids:
          ranks = []
          topWorkers[r] = []
          for user_id in region_user_map[r]:
              error = errors[r][user_id]
              ranks.append({'user_id': user_id, 'error': error})
          sorted_users = sorted(ranks, key=lambda x: x['error'])
          numTopHalf = len(sorted_users) // 2
          tmp = sorted_users[:numTopHalf]
          for worker in tmp:
              topWorkers[r].append(worker['user_id'])

      # get region id from region (which is fluview_name)
      self.cur.execute("select id from ec_fluv_regions where fluview_name = %d" % region)
      print(self.cur)
      region = self.cur[0]

      return topWorkers[region]


  def fetch_submissions(self, region, epiweek_now):
    final_week = flu.join_epiweek(self.test_season + 1, 20)
    self.cur = self.cnx.cursor()
    self.cur.execute("""
    SELECT
      u.`id` `user_id`, f.`epiweek`, f.`wili`
    FROM (
      SELECT
        u.*
      FROM
        `ec_fluv_users_mturk_2019` u
      JOIN
        `ec_fluv_defaults` d
      ON
        TRUE
      LEFT JOIN
        `ec_fluv_user_preferences` p
      ON
        p.`user_id` = u.`id` AND p.`name` = d.`name`
      WHERE
        d.`name` = '_debug' AND coalesce(p.`value`, d.`value`) = '0'
      ) u
    JOIN
      `ec_fluv_submissions_mturk` s
    ON
      s.`user_id` = u.`id`
    JOIN
      `ec_fluv_forecast_mturk` f
    ON
      f.`user_id` = u.`id` AND f.`region_id` = s.`region_id` AND f.`epiweek_now` = s.`epiweek_now`
    JOIN
      `ec_fluv_regions` r
    ON
      r.`id` = s.`region_id`
    WHERE
      r.`fluview_name` = %s AND s.`epiweek_now` = %s AND f.`epiweek` <= %s AND f.`wili` > 0
    ORDER BY
      u.`id` ASC, f.`epiweek` ASC
    """, (region, epiweek_now, final_week))
    submissions = {}

    topUsers = self.extractUsers(region, epiweek_now)
    print(topUsers)
    for (user, epiweek, wili) in self.cur:
      if self.users is not None and user not in self.users:
        continue
      if user not in submissions and user in topUsers:
        submissions[user] = []
      submissions[user].append(wili)
    self.cur.close()
    curves = []
    expected_weeks = flu.delta_epiweeks(epiweek_now, final_week)
    for user in submissions:
      if len(submissions[user]) != expected_weeks:
        print(' [EC] warning: missing data in user submission [%d|%s|%d]' % (user, region, epiweek_now))
      else:
        curves.append(submissions[user])

    print(region, curves)
    return curves

  def _init(self):
    if self.test_season == 2014:
      db = 'epicast'
    elif self.test_season >= 2015:
      db = 'epicast2'
    else:
      raise Exception('invalid epicast season [%d]' % self.test_season)
    u, p = secrets.db.epi
    self.cnx = mysql.connector.connect(user=u, password=p, database=db)

  def _fini(self):
    self.cnx.commit()
    self.cnx.close()

  def _train(self, region):
    pass

  def _forecast(self, region, epiweek):
    # season setup and sanity check
    ew1 = flu.join_epiweek(self.test_season, 40)
    ew2 = flu.join_epiweek(self.test_season + 1, 20)
    if not ew1 <= epiweek <= ew2:
      raise Exception('`epiweek` outside of `test_season`')
    # get past values (left half) from the Epidata API
    epidata = Forecaster.Utils.decode(Epidata.fluview(region, Epidata.range(ew1, epiweek), issues=epiweek))
    pinned = [row['wili'] for row in epidata]
    if len(pinned) != flu.delta_epiweeks(ew1, epiweek) + 1:
      raise Exception('missing ILINet data')
    # get the user submissions (right half) from the database
    epiweek = 201842
    submissions = self.fetch_submissions(region, epiweek)
    self._num_users = len(submissions)
    print(' [EC] %d users found for %s on %d' % (len(submissions), region, epiweek))
    # concatenate observed data and user submissions
    return [pinned + sub for sub in submissions]
