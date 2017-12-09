"""
===============
=== Purpose ===
===============

Generates CDC flu contest forecasts from Epicast [FLUV] user predictions.


=================
=== Changelog ===
=================

2016-12-08
  + use secrets
2016-10-27
  * updated for 2016 flu contest and updated peakweek definition
2015-12-14
  * prefixed output with [EC]
  + support presence of bin smoothing parameter
2015-11-09
  + temporary hack to set df based on number of users
2015-11-04
  * replaced normal with student's-t distribution (df=3)
2015-10-28
  + support backcasts for 2014-2015 season
  + optional verbose output and specific user IDs
  * fixed standard deviation when n=1
  * fixed CDF when sigma=0
2015-10-26
  + first version, based partly on last year's fluv_submission.py
"""

# standard library
from statistics import median_low

# third party
import mysql.connector
import numpy as np
import scipy.stats

# first party
from ..forecasters.fc_abstract import Forecaster
from delphi.delphi_epidata.client.delphi_epidata import Epidata
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


  def fetch_submissions(self, ageGroup, epiweek_now):
    final_week = flu.join_epiweek(self.test_season + 1, 17)
    self.cur = self.cnx.cursor()
    self.cur.execute("""
    SELECT
      u.`id` `user_id`, f.`epiweek`, f.`value`
    FROM (
      SELECT
        u.*
      FROM
        `ec_fluv_users` u
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
      `ec_fluv_submissions_hosp` s
    ON
      s.`user_id` = u.`id`
    JOIN
      `ec_fluv_forecast_hosp` f
    ON
      f.`user_id` = u.`id` AND f.`group_id` = s.`group_id` AND f.`epiweek_now` = s.`epiweek_now`
    JOIN
      `ec_fluv_age_groups` r
    ON
      r.`id` = s.`group_id`
    WHERE
      r.`flusurv_name` = %s AND s.`epiweek_now` = %s AND f.`epiweek` <= %s AND f.`value` > 0
    ORDER BY
      u.`id` ASC, f.`epiweek` ASC
    """, (ageGroup, epiweek_now, final_week))


    submissions = {}
    for (user, epiweek, wili) in self.cur:
      # print (user, epiweek, wili)
      if self.users is not None and user not in self.users:
        continue
      if user not in submissions:
        submissions[user] = []
      submissions[user].append(wili)
    self.cur.close()
    curves = []
    expected_weeks = flu.delta_epiweeks(epiweek_now, final_week)
    for user in submissions:
      # print ("user: ", user)
      if len(submissions[user]) != expected_weeks:
        print(' [EC] warning: missing data in user sumission [%d|%s|%d]' % (user, ageGroup, epiweek_now))
      else:
        curves.append(submissions[user])
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

  def _train(self, ageGroup):
    pass

  def _forecast(self, ageGroup, epiweek):
    # season setup and sanity check
    ew1 = flu.join_epiweek(self.test_season, 40)
    ew2 = flu.join_epiweek(self.test_season + 1, 17)
    print("test season:", self.test_season, "ew1:", ew1, "epiweek:", epiweek)
    if not ew1 <= epiweek <= ew2:
      raise Exception('`epiweek` outside of `test_season`')

    # get past values (left half) from the Epidata API
    response = Epidata.flusurv('network_all', Epidata.range(ew1, epiweek), issues=epiweek)
    epidata = Forecaster.Utils.decode(response)

    pinned = [row[ageGroup] for row in epidata]

    if len(pinned) != flu.delta_epiweeks(ew1, epiweek) + 1:
      raise Exception('missing ILINet data')
    # get the user submissions (right half) from the database
    print ("ageGroup", ageGroup, "epiweek", epiweek)
    submissions = self.fetch_submissions(ageGroup, epiweek)
    self._num_users = len(submissions)
    if self.verbose:
      print(' [EC] %d users found for %s on %d' % (len(submissions), ageGroup, epiweek))
    # concatenate observed data and user submissions
    return [pinned + sub for sub in submissions]


# test_epicast = Epicast(2017, ['rate_age_0'], ForecastType.HOSP, verbose=True)
# test_epicast._init()
# test_epicast.fetch_submissions('rate_age_0', 201747)
# # test_epicast._forecast('rate_age_0', 201748)
#
# response = Epidata.flusurv('network_all', Epidata.range(201740, 201747), 201747)
# print(repr(response))
# epidata = Forecaster.Utils.decode(response)
# print("epidata: ", epidata)
