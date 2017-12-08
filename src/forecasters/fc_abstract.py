"""
===============
=== Purpose ===
===============

The abstract base class of all forecasting systems.


=================
=== Changelog ===
=================

2016-10-27
  * support change in peakweek definition
2015-12-14
  + kernel smoothing is optional
2015-11-09
  + kernel smoothing distributions before uniform blending (bw=1)
2015-10-26
  + first version
"""

# standard library
import abc
from datetime import datetime
import math
from statistics import median_low

# third party
import numpy as np
import numpy.random as random
import scipy.stats as stats

# first party
from ..utils.forecast import Forecast
from ..utils.forecast_meta import Locations
import delphi.utils.epiweek as flu
from ..utils.forecast_type import ForecastType


class Targets:

  regions = ['nat'] + ['hhs%d' % i for i in range(1, 11)]
  baselines = {
    2014: dict(zip(
      regions, [2.0, 1.2, 2.3, 2.0, 1.9, 1.7, 3.3, 1.7, 1.3, 2.7, 1.1]
    )),
    2015: dict(zip(
      regions, [2.1, 1.3, 2.3, 1.8, 1.6, 1.9, 3.6, 1.7, 1.4, 2.6, 1.1]
    )),
    2016: dict(zip(
      regions, [2.2, 1.4, 3.0, 2.2, 1.7, 1.9, 4.1, 1.8, 1.4, 2.5, 1.1]
    )),
    2017: dict(zip(
      regions, [2.2, 1.4, 3.1, 2.0, 1.9, 1.8, 4.2, 1.9, 1.3, 2.4, 1.4]
    )),
  }

  @staticmethod
  def get_onset(wili, baseline):
    """ index of season onset (rounding to 1 decimal place) """
    if baseline is None:
      return None
    weeks_above = 0
    for i in range(len(wili)):
      w = round(wili[i], 1)
      if w >= baseline:
        weeks_above += 1
        if weeks_above >= 3:
          return (i - 2)
      else:
        weeks_above = 0
    return None

  @staticmethod
  def get_peakweek(wili, baseline, rule_season=None):
    """ median-low index of peak wILI (rounding to 1 decimal place) """
    if rule_season is not None:
      if rule_season < 2016:
        if Targets.get_onset(wili, baseline) is None:
          return None
    peak = round(Targets.get_peak(wili), 1)
    weeks = [i for (i, w) in enumerate(wili) if round(w, 1) == peak]
    return median_low(weeks)

  @staticmethod
  def get_peak(wili):
    """ maximum wILI value """
    return max(wili)

  @staticmethod
  def get_lookahead(wili, current_index, ahead):
    """ short-term wILI value """
    index = min(current_index + ahead, len(wili) - 1)
    return wili[index]

  @staticmethod
  def get_all_targets(wili, baseline, current_index, rule_season=None):
    """ dictionary of all targets """
    targets = {
      'onset': Targets.get_onset(wili, baseline),
      'peakweek': Targets.get_peakweek(wili, baseline, rule_season),
      'peak': Targets.get_peak(wili),
      'x1': Targets.get_lookahead(wili, current_index, 1),
      'x2': Targets.get_lookahead(wili, current_index, 2),
      'x3': Targets.get_lookahead(wili, current_index, 3),
      'x4': Targets.get_lookahead(wili, current_index, 4),
    }
    return targets


class Forecaster(abc.ABC):

  class Utils:

    @staticmethod
    def decode(response):
      if response['result'] != 1:
        raise Exception('failed to fetch data [%d|%s]' % (response['result'], response['message']))
      return response['epidata']

    @staticmethod
    def normalize(dist):
      return np.array(dist) / sum(dist)

    @staticmethod
    def blend(dist, weight):
      uniform = np.ones(len(dist)) / len(dist)
      return uniform * weight + np.array(dist) * (1 - weight)

    @staticmethod
    def smooth(curve, bandwidth):
      cdf = stats.norm(0, bandwidth).cdf
      prob = lambda i: cdf(i + 0.5) - cdf(i - 0.5)
      num = 1
      while prob(num) > 1e-5:
        num += 2
      window = num * 2 + 1
      kernel = np.array([prob(i - window // 2) for i in range(window)])
      temp = np.convolve(curve, kernel, 'full')
      i = window // 2
      j = -(i + 1)
      temp[i] = np.sum(temp[:i + 1])
      temp[j] = np.sum(temp[j:])
      smoothed = temp[i:j + 1]
      return smoothed

    @staticmethod
    def get_week_forecast(first_epiweek, num_bins, indices, uniform_weight, smooth_bw, allow_none):
      dist = [indices.count(i) for i in range(num_bins)]
      none = indices.count(None)
      if none > 0 and not allow_none:
        raise Exception('target does not allow None, but None was provided')
      extra = [none] if allow_none else []
      temp = Forecaster.Utils.normalize(np.array(dist + extra))
      if smooth_bw > 0:
        # TODO: don't smooth across dist and norm
        temp = Forecaster.Utils.smooth(temp, smooth_bw)
      temp = Forecaster.Utils.blend(temp, uniform_weight)
      if allow_none:
        dist, none = temp[:-1], temp[-1]
      else:
        dist, none = temp, None
      possibilities = [i for i in indices if i is not None]
      if len(possibilities) == 0:
        possibilities = [0]
      point = flu.add_epiweeks(first_epiweek, int(median_low(possibilities)))
      return (dist, none, point)

    @staticmethod
    def get_wili_forecast(bin_size, num_bins, wili, uniform_weight, smooth_bw):
      limit = lambda i: i * bin_size if i < num_bins else float('inf')
      dist = []
      for i in range(num_bins):
        a, b = limit(i), limit(i + 1)
        dist.append(sum(a <= w < b for w in wili))
      dist = Forecaster.Utils.normalize(np.array(dist))
      if smooth_bw > 0:
        dist = Forecaster.Utils.smooth(dist, smooth_bw)
      dist = Forecaster.Utils.blend(dist, uniform_weight)
      point = np.median(wili)
      return (dist, point)

    @staticmethod
    def sample_normal_std(mean, std, num):
      return Forecaster.Utils.sample_normal_var(mean, std ** 2, num)

    @staticmethod
    def sample_normal_var(mean, var, num):
      return Forecaster.Utils.sample_normal_cov(mean, np.diag(var), num)

    @staticmethod
    def sample_normal_cov(mean, cov, num):
      curves = random.multivariate_normal(mean, cov, num)
      zeros = np.zeros(curves.shape)
      return np.fmax(curves, zeros)

  def __init__(self, name, test_season, locations, forecast_type, min_week_prob=0.002,
    min_wili_prob=0.002, forecast_weeks=Utils.get_week_forecast,
    forecast_wili=Utils.get_wili_forecast, smooth_weeks_bw=1, smooth_wili_bw=1):
    """
    `name`: human-friendly system name
    `test_season`: the season that will be forecasted
      This season should be left out of the training set.
    `locations`: the list of locations that should be forecasted
    `min_week_prob`: the minimum probability allowed in any week bin, which
      determines how heavily the final distribution is blended with a uniform
      distribution
      We do this because, for example, a pandemic could happen on
      any calendar week, so it would be crazy to put a probability of zero on
      any week. The goal here is to minimize surprise while not ruling any
      event out completely. The default value of this parameter was selected by
      assuming pandemics happen once every ~10 years and are equally likely to
      peak on any week.
    `min_wili_prob`: the minimum probability allowed in any wILI bin
      It has the same purpose as the `min_week_prob` parameter, but the defaut
      was chosen somewhat more arbitrarily.
    `forecast_weeks`: function to generate weekly [dist/none/point] predictions
      given target values
      The default function returns [empirical/empirical/median].
    `forecast_wili`: function to generate wILI [dist/point] predictions given
      target values
      The default function returns [empirical/median].
    `smooth_weeks_bw`: Gaussian kernel bandwidth for smoothing weekly bins
      This is applied before uniform blening. If 0, no smoothing is applied.
      The default bandwidth is 1 bin.
    `smooth_wili_bw`: Gaussian kernel bandwidth for smoothing wILI bins
      This is applied before uniform blening. If 0, no smoothing is applied.
      The default bandwidth is 1 bin.
    """
    self.name = name
    self.test_season = test_season
    self.locations = locations
    self.min_week_prob = min_week_prob
    self.min_wili_prob = min_wili_prob
    self.forecast_weeks = forecast_weeks
    self.forecast_wili = forecast_wili
    self.smooth_weeks_bw = smooth_weeks_bw
    self.smooth_wili_bw = smooth_wili_bw
    self.forecast_type = forecast_type

  # def forecast(self, epiweek, forecast_type):
  def forecast(self, epiweek):
    """
    `epiweek`: the most recent epiweek for which ILINet data is available
    """

    # sanity checks
    flu.check_epiweek(epiweek)
    season = flu.split_epiweek(flu.get_season(epiweek)[0])[0]
    week = flu.split_epiweek(epiweek)[1]
    first_epiweek = flu.join_epiweek(season, 40)
    offset = flu.delta_epiweeks(first_epiweek, epiweek)
    if season != self.test_season:
      raise Exception('unable to forecast season %d' % season)
    if 20 < week < 40:
      raise Exception('unable to forecast week %02d' % week)

    # initialize forecast
    forecast = Forecast(self.test_season, datetime.now(), self.name, epiweek, self.forecast_type)

    # aliases for readability
    num_week_bins = forecast.season_length
    num_wili_bins = forecast.num_ili_bins
    wili_bin_size = forecast.ili_bin_size

    # if (forecast_type == ForecastType.HOSP):
    #     num_wili_bins = 601

    # uniform blending weights
    week_weight = self.min_week_prob * (num_week_bins + 1)  # include `none` "bin"
    wili_weight = self.min_wili_prob * num_wili_bins
    if week_weight > 1:
      raise Exception('`min_week_prob` is impossibly high')
    if wili_weight > 1:
      raise Exception('`min_wili_prob` is impossibly high')

    # forecast each region
    for region in self.locations:

      # draw sample curves
      curves = self._forecast(region, epiweek)

      # regional info
      if Locations.is_region(region):
        baseline = Targets.baselines[self.test_season][region]
      else:
        baseline = None

      # get all targets
      targets = [Targets.get_all_targets(c, baseline, offset, rule_season=self.test_season) for c in curves]
      onsets = [t['onset'] for t in targets]
      peakweeks = [t['peakweek'] for t in targets]
      peaks = [t['peak'] for t in targets]
      x1s = [t['x1'] for t in targets]
      x2s = [t['x2'] for t in targets]
      x3s = [t['x3'] for t in targets]
      x4s = [t['x4'] for t in targets]

      # forecast each target
      allow_no_pw = self.test_season < 2016
      if Locations.is_region(region):
        # skip onset for states and hospitalization, and do it only for regions
        onset = self.forecast_weeks(first_epiweek, num_week_bins, onsets, week_weight, self.smooth_weeks_bw, True)

      peakweek = self.forecast_weeks(first_epiweek, num_week_bins, peakweeks, week_weight, self.smooth_weeks_bw, allow_no_pw)
      peak = self.forecast_wili(wili_bin_size, num_wili_bins, peaks, wili_weight, self.smooth_wili_bw)
      x1 = self.forecast_wili(wili_bin_size, num_wili_bins, x1s, wili_weight, self.smooth_wili_bw)
      x2 = self.forecast_wili(wili_bin_size, num_wili_bins, x2s, wili_weight, self.smooth_wili_bw)
      x3 = self.forecast_wili(wili_bin_size, num_wili_bins, x3s, wili_weight, self.smooth_wili_bw)
      x4 = self.forecast_wili(wili_bin_size, num_wili_bins, x4s, wili_weight, self.smooth_wili_bw)

      # fill in the forecast data
      fc = forecast.get_or_create_forecast(region)
      if Locations.is_region(region):
        fc.set_onset(*onset)
      fc.set_peakweek(*peakweek)
      fc.set_peak(*peak)
      fc.set_lookahead(1, *x1)
      fc.set_lookahead(2, *x2)
      fc.set_lookahead(3, *x3)
      fc.set_lookahead(4, *x4)

    # sanity check completed forecast
    forecast.sanity_check()
    return forecast

  def open(self):
    self._init()
    for region in self.locations:
      self._train(region)

  def close(self):
    self._fini()

  def debug(self, region, epiweek):
    # draw sample curves
    curves = self._forecast(epiweek, region)
    import pylab as plt
    for curve in curves[:25]:
      plt.plot(curve)
    plt.plot(np.mean(curves, axis=0), linewidth=3)
    plt.show()

  def _init(self):
    pass

  def _fini(self):
    pass

  def _train(self, region):
    pass

  @abc.abstractmethod
  def _forecast(self, region, epiweek):
    raise NotImplementedError()
