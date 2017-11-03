"""
A class representing a flu forecast for some location.

Specific to the 2017-2018 flu season.
"""

# first party
from forecast_meta import Locations


class ForecastLocation:

  @staticmethod
  def approx_one(x):
    return abs(1 - x) < 1e-5

  @staticmethod
  def new_target(size):
    return {
      'dist': [None] * size,
      'point': None
    }

  def __init__(self, location, season_length, num_ili_bins):
    self.season_length = season_length
    self.num_ili_bins = num_ili_bins
    self.location = location
    self.season_length = self.season_length
    self.data = {}
    self.data['peakweek'] = ForecastLocation.new_target(self.season_length)
    self.data['peak'] = ForecastLocation.new_target(self.num_ili_bins)
    for i in range(1, 5):
      self.data['x%d' % i] = ForecastLocation.new_target(self.num_ili_bins)
    if Locations.is_region(location):
      self.data['onset'] = ForecastLocation.new_target(self.season_length)
      self.data['onset']['none'] = None

  def _check_week_values(self, dist, none, point):
    dist = list(dist)
    if len(dist) != self.season_length:
      raise Exception('distribution length is wrong')
    if none is None:
      none = 0
    if not ForecastLocation.approx_one(sum(dist) + none):
      raise Exception('distribution (including `none`) must sum to 1')
    if min(dist + [none, point]) < 0:
      raise Exception('value is negative')
    point %= 100
    if point < 1 or point >= 53:
      raise Exception('weekly point prediction not in [1, 53)')

  def _check_ili_values(self, dist, point):
    dist = list(dist)
    if len(dist) != self.num_ili_bins:
      raise Exception('distribution length is wrong')
    if not ForecastLocation.approx_one(sum(dist)):
      raise Exception('distribution must sum to 1')
    if min(dist + [point]) < 0:
      raise Exception('value is negative')

  def _set_week_target(self, target, dist, none, point):
    self._check_week_values(dist, none, point)
    for (i, p) in enumerate(dist):
      self.set_single_value(target, i, p)
    if target == 'onset':
      self.set_single_value(target, 'none', none)
    self.set_single_value(target, 'point', point % 100)

  def _set_ili_target(self, target, dist, point):
    self._check_ili_values(dist, point)
    for (i, p) in enumerate(dist):
      self.set_single_value(target, i, p)
    self.set_single_value(target, 'point', point)

  def has_onset(self):
    return 'onset' in self.data

  def get_onset(self):
    if not self.has_onset():
      raise Exception('onset is not a target for %s' % self.location)
    return self.data['onset']

  def get_peakweek(self):
    return self.data['peakweek']

  def get_peak(self):
    return self.data['peak']

  def get_lookahead(self, week):
    return self.data['x%d' % week]

  def set_single_value(self, target, index, value):
    if type(index) is int:
      self.data[target]['dist'][index] = value
    else:
      self.data[target][index] = value

  def set_onset(self, dist, none, point):
    if not self.has_onset():
      raise Exception('onset is not a target for %s' % self.location)
    self._set_week_target('onset', dist, none, point)

  def set_peakweek(self, dist, none, point):
    self._set_week_target('peakweek', dist, none, point)

  def set_peak(self, dist, point):
    self._set_ili_target('peak', dist, point)

  def set_lookahead(self, week, dist, point):
    self._set_ili_target('x%d' % week, dist, point)

  def sanity_check(self):
    distributions = [self.data['x%d' % i]['dist'] for i in range(1, 5)]
    distributions.append(self.data['peakweek']['dist'])
    distributions.append(self.data['peak']['dist'])
    if self.has_onset():
      distributions.append(
        self.data['onset']['dist'] + [self.data['onset']['none']]
      )
    for dist in distributions:
      if not ForecastLocation.approx_one(sum(dist)):
        raise Exception('distribution must sum to 1')
      if min(dist) <= 0 or max(dist) >= 1:
        raise Exception('value not in (0, 1)')
