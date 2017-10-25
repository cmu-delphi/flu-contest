"""
===============
=== Purpose ===
===============

Library for flu forecast input, output, and validation. Reads and writes 2014
(XLS (read-only), CSV), 2015 (CSV), and 2016 (CSV, JSON) forecasts. Also
includes utilities for calculating target values.

Everything in this file is specific to the CDC flu contest: file formats,
metadata, targets, regional wILI baselines, weeks and wILI bins, etc.

Notes:
 - The module `xlrd` is required only when reading Excel files (2014-2015).
 - wILI baselines can be found at http://www.cdc.gov/flu/weekly/overview.htm


=================
=== Changelog ===
=================

2016-12-05: v2
  + `equals` method for forecast comparison
2016-11-29: v2
  * fix 2016 filename regex
2016-11-18: v2
  + export and import 2016 "flusight" json format
  * fix reading 2016 csv point predictions for ILI targets
2016-10-27: v2
  + read and write 2016 flu contest submissions
  * organize baseline definitions
  * update peakweek target definition (exists even with no onset)
2016-05-19: v1
  * `parse_epiweek` supports int and float types (no longer forces int)
2016-04-11: v1
  * fixed epiweek parsing (round instead of truncate)
2015-11-18: v1
  + Export to JSON string
  * Fixed epiweek 2-to-6 conversion when reading forecast
2015-11-10: v1
  * Infer year from version when reading epiweek from spreadsheet
  * Permissive flag for handling misbehaved forecasts
2015-11-02: v1
  * Ignore encoding errors (i.e. the 0x96 bytes in the 2015 template)
  * More permissive epiweek parsing (i.e. allow floats by casting to int)
2015-10-28: v1
  * Duplicate lookaheads for truncated curves
  * In sanity check, allow peak before onset
2015-10-26: v1
  + `Targets` class for onset/peakweek/peak/lookahead calculation
  + Provisional v2015 reading
2015-10-22: v1
  + Provisional v2015 writing
2015-10-22: v1
  + Version from (1, 2) to (2014, 2015)
  + Predefined baselines for 2014 and 2015
  + Include custom version field in csv output
2015-10-20
  * Branched from forecast_reader.py
2015-10-14
  * Branched from fluv_submission_check.py
  - Removed all plotting code
  - No longer a standalone program (module only)
2015-04-04
  * Added regex to extract epiweek from filename
2014-11-09
  * Branched from experimental version
  * Modularized the check/plot function (analyze)
"""

import csv
from datetime import datetime
import json
import os.path
import re
import statistics


class Targets:

  @staticmethod
  def get_onset(wili, baseline):
    """ index of season onset (rounding to 1 decimal place) """
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
    return statistics.median_low(weeks)

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


class Forecast:

  _map = lambda a, b: dict(zip(a, b))
  _version = 2
  _permissive = False
  regions = ['nat'] + ['hhs%d' % i for i in range(1, 11)]
  region_names = ['US National'] + ['HHS Region %d' % i for i in range(1, 11)]
  region_from_name = _map(region_names, regions)
  region_to_name = _map(regions, region_names)
  targets = ['onset', 'peakweek', 'peak'] + ['x%d' % i for i in range(1, 5)]
  target_names = ['Season onset', 'Season peak week', 'Season peak percentage'] + ['%d wk ahead' % i for i in range(1, 5)]
  target_from_name = _map(target_names, targets)
  target_to_name = _map(targets, target_names)
  week_targets = targets[:2]
  ili_targets = targets[2:]
  long_targets = targets[:3]
  short_targets = targets[3:]
  precision = 8
  tolerance = [1 - 1e-5, 1 + 1e-5]
  baselines = {
    2014: _map(regions, [2.0, 1.2, 2.3, 2.0, 1.9, 1.7, 3.3, 1.7, 1.3, 2.7, 1.1]),
    2015: _map(regions, [2.1, 1.3, 2.3, 1.8, 1.6, 1.9, 3.6, 1.7, 1.4, 2.6, 1.1]),
    2016: _map(regions, [2.2, 1.4, 3.0, 2.2, 1.7, 1.9, 4.1, 1.8, 1.4, 2.5, 1.1]),
    2017: _map(regions, [2.2, 1.4, 3.1, 2.0, 1.9, 1.8, 4.2, 1.9, 1.3, 2.4, 1.4]),
  }

  def __init__(self, version, timestamp, team, epiweek):
    self.version = version
    self.timestamp = timestamp
    self.team = team
    self.epiweek = epiweek
    self.epiweek2 = epiweek % 100
    self.year_weeks = {2014: 53, 2015: 52, 2016: 52}[version]
    self.ili_bins = {2014: 11, 2015: 27, 2016: 131}[version]
    self.ili_bin_size = {2014: 1.0, 2015: 0.5, 2016: 0.1}[version]
    self.baselines = Forecast.baselines[version]
    self.season_weeks = self.year_weeks - 19
    self.i2w = {}
    self.w2i = {}
    for i in range(self.year_weeks):
      w = i + 40
      if w > self.year_weeks:
        w -= self.year_weeks
      self.i2w[i] = w
      self.w2i[w] = i
    self.data = {}
    for r in Forecast.regions:
      self.data[r] = {}
      for t in Forecast.targets:
        self.data[r][t] = {'point': -1}
        if t in Forecast.week_targets:
          self.data[r][t]['dist'] = [-1 for i in range(self.season_weeks)]
          if t == 'onset' or self.version < 2016:
            self.data[r][t]['none'] = -1
        else:
          self.data[r][t]['dist'] = [-1 for i in range(self.ili_bins)]

  def _get(self, region, target, index):
    if type(region) is int:
      region = Forecast.regions[region]
    if type(index) is int:
      return self.data[region][target]['dist'][index]
    else:
      return self.data[region][target][index]

  def _set(self, region, target, index, value):
    if type(region) is int:
      region = Forecast.regions[region]
    if type(index) is int:
      self.data[region][target]['dist'][index] = value
    else:
      self.data[region][target][index] = value

  def _check_week_values(self, dist, none, point):
    dist = list(dist)
    if len(dist) != self.season_weeks:
      raise Exception('distribution length is wrong')
    if none is None:
      none = 0
    if not Forecast.tolerance[0] <= sum(dist) + none <= Forecast.tolerance[1]:
      raise Exception('distribution (including `none`) must sum to 1')
    for x in dist + [none, point]:
      if x < 0:
        raise Exception('value is negative')
    if type(point) != int:
        raise Exception('point prediction is not an integer')

  def _check_ili_values(self, dist, point):
    dist = list(dist)
    if len(dist) != self.ili_bins:
      raise Exception('distribution length is wrong')
    if not Forecast.tolerance[0] <= sum(dist) <= Forecast.tolerance[1]:
      raise Exception('distribution must sum to 1')
    for x in dist + [point]:
      if x < 0:
        raise Exception('value is negative')

  def _get_target(self, region, target):
    if type(region) is int:
      region = Forecast.regions[region]
    return self.data[region][target]

  def _set_week_target(self, region, target, dist, none, point):
    if type(region) is int:
      region = Forecast.regions[region]
    self._check_week_values(dist, none, point)
    for (i, p) in enumerate(dist):
      self._set(region, target, i, p)
    if target == 'onset' or self.version < 2016:
      self._set(region, target, 'none', none)
    self._set(region, target, 'point', Forecast.parse_epiweek(point, 'float'))

  def _set_ili_target(self, region, target, dist, point):
    if type(region) is int:
      region = Forecast.regions[region]
    self._check_ili_values(dist, point)
    for (i, p) in enumerate(dist):
      self._set(region, target, i, p)
    self._set(region, target, 'point', point)

  def get_onset(self, region):
    return self._get_target(region, 'onset')

  def get_peakweek(self, region):
    return self._get_target(region, 'peakweek')

  def get_peak(self, region):
    return self._get_target(region, 'peak')

  def get_lookahead(self, region, week):
    return self._get_target(region, 'x%d' % week)

  def set_onset(self, region, dist, none, point):
    self._set_week_target(region, 'onset', dist, none, point)

  def set_peakweek(self, region, dist, none, point):
    self._set_week_target(region, 'peakweek', dist, none, point)

  def set_peak(self, region, dist, point):
    self._set_ili_target(region, 'peak', dist, point)

  def set_lookahead(self, region, week, dist, point):
    self._set_ili_target(region, 'x%d' % week, dist, point)

  def equals(self, fc, tol=1e-8):
    if self.epiweek != fc.epiweek:
      return False
    approx = lambda a, b: -tol < a - b < +tol
    for r in Forecast.regions:
      for t in Forecast.targets:
        v1, v2 = self.data[r][t], fc.data[r][t]
        if v1.keys() != v2.keys():
          return False
        if len(v1['dist']) != len(v2['dist']):
          return False
        for (a, b) in zip(v1['dist'], v2['dist']):
          if not approx(a, b):
            return False
        if not approx(v1['point'], v2['point']):
          return False
        if 'none' in v1 and not approx(v1['none'], v2['none']):
          return False
    return True

  def sanity_check(self, epiweek=None):
    errors = []
    try:
      # check the epiweek
      if epiweek is not None and epiweek != self.epiweek:
        errors.append(Exception('epiweek mismatch'))
      # make sure the timestamp and team name are present
      if self.timestamp is None:
        errors.append(Exception('timestamp is missing'))
      if self.team is None or len(self.team) == 0:
        errors.append(Exception('team is missing'))
      elif re.match('^[-_\\w]*$', self.team) is None:
        errors.append(Exception('team has special characters'))
      # check each region
      for region in Forecast.regions:
        onset = self.get_onset(region)
        peakweek = self.get_peakweek(region)
        peak = self.get_peak(region)
        lookaheads = [self.get_lookahead(region, i) for i in range(1, 5)]
        # nothing can be zero or negative, nothing can be missing
        for x in [onset, peakweek, peak] + lookaheads:
          for v in x['dist']:
            if type(v) is str:
              errors.append(Exception('Pr(x) is missing (string instead of a number?)'))
            if v <= 0:
              errors.append(Exception('Pr(x) is not positive'))
          if 'none' in x:
            if type(x['none']) is str:
              errors.append(Exception('Pr(none) is missing (string instead of a number?)'))
            if x['none'] <= 0:
              errors.append(Exception('Pr(none) is not positive'))
          #if type(x['point']) is str:
          #  week = Forecast.parse_epiweek(x['point'])
          #  if not (1 <= week <= 20) and not (40 <= week <= 53):
          #    errors.append(Exception('A point prediction week is out of range'))
          #else:
          if x['point'] <= 0:
            errors.append(Exception('a point prediction value is not positive'))
          # make sure distributions sum to one-ish
          s = sum(x['dist'])
          if 'none' in x:
            s += x['none']
          if not Forecast.tolerance[0] <= s <= Forecast.tolerance[1]:
            errors.append(Exception('distribution over/under flowed: r=%s s=%.6f' % (region, s)))
        # onset should come before peakweek
        #if self.w2i[onset['point']] > self.w2i[peakweek['point']]:
        #  errors.append(Exception('peakweek is before onset'))
    except Exception as ex:
      errors.append(ex)
    # did it pass?
    if len(errors) == 0:
      # looks ok
      return self
    else:
      print('Sanity check failed:')
      for e in errors:
        print(' ', e)
      raise Exception('Sanity check failed')

  @staticmethod
  def parse_epiweek(ew, dtype):
    if type(ew) is str:
      if len(ew) > 2 and ew.lower()[:2] == 'ew':
        ew = ew[2:]
      #if not 1 <= len(ew) <= 2:
      #  raise Exception('invalid epiweek [%s]' % ew)
    if dtype == 'int':
      ew = int(float(ew) + 0.5) % 100
      #if Forecast._permissive and ew == 0:
      #  ew += 52
      if not 1 <= ew <= 53:
        raise Exception('invalid epiweek [%d]' % ew)
    elif dtype == 'float':
      ew = float(ew) % 100
      if not 0 <= ew < 54:
        raise Exception('invalid epiweek [%.3f]' % ew)
    else:
      raise Exception('invalid epiweek data type [%s]' % str(dtype))
    return ew

  @staticmethod
  def _write_csv(filename, rows):
    with open(filename, 'w', newline='') as f:
      writer = csv.writer(f)
      for row in rows:
        writer.writerow(row)
    return filename

  @staticmethod
  def _read_csv(filename):
    with open(filename, errors='replace', newline='') as f:
      reader = csv.reader(f)
      return [[col for col in row] for row in reader]

  def _write_v2014(self, path, filename):
    if filename is None:
      date = self.timestamp.strftime('%Y-%m-%d')
      filename = '%s-EW%02d-%s.csv' % (date, self.epiweek2, self.team)
    if path is not None:
      filename = os.path.join(path, filename)
    timestamp = self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    rows = [['' for c in range(67)] for r in range(61)]
    rows[0][0] = 'Flu forecasts for 2014-2015 flu season'
    rows[1][0] = 'Forecast created: %s' % timestamp
    rows[2][0] = 'Forecasting team: %s' % self.team
    rows[3][0] = 'Last published wILI:'
    rows[3][1] = 'EW%02d' % self.epiweek2
    rows[4][0] = 'forecast_io.py v%d' % Forecast._version
    for i in range(self.season_weeks):
      week = self.i2w[i]
      row = 7 + i
      rows[row][0] = 'Pr(EW%02d)' % week
    rows[41][0] = 'Pr(none)'
    rows[42][0] = 'SUM <= 1 ?'
    rows[43][0] = 'Point Prediction'
    for i in range(self.ili_bins):
      row = 48 + i
      if i == self.ili_bins - 1:
        rows[row][0] = 'Pr(%d%% <= wILI )' % i
      else:
        rows[row][0] = 'Pr(%d%%<= wILI < %d%%)' % (i, i + 1)
    rows[59][0] = 'SUM <= 1 ?'
    rows[60][0] = 'Point Prediction:'
    for (i, name) in enumerate(Forecast.region_names):
      col = 2 + i * 6
      rows[5][col + 0] = name
      rows[6][col + 1] = 'Season onset'
      rows[6][col + 3] = 'Peak week'
      rows[42][col + 1] = '-'
      rows[42][col + 3] = '-'
      rows[47][col + 0] = '1wk ahead'
      rows[47][col + 1] = '2wk ahead'
      rows[47][col + 2] = '3wk ahead'
      rows[47][col + 3] = '4wk ahead'
      rows[47][col + 4] = 'Peak Height'
      rows[59][col + 0] = '-'
      rows[59][col + 1] = '-'
      rows[59][col + 2] = '-'
      rows[59][col + 3] = '-'
      rows[59][col + 4] = '-'
    f = lambda x: ('%%.%df' % Forecast.precision) % x
    for (i, region) in enumerate(Forecast.regions):
      col = 2 + i * 6
      for j in range(self.season_weeks):
        row = 7 + j
        rows[row][col + 1] = f(self._get(region, 'onset', j))
        rows[row][col + 3] = f(self._get(region, 'peakweek', j))
      rows[41][col + 1] = f(self._get(region, 'onset', 'none'))
      rows[41][col + 3] = f(self._get(region, 'peakweek', 'none'))
      rows[43][col + 1] = self._get(region, 'onset', 'point')
      rows[43][col + 3] = self._get(region, 'peakweek', 'point')
      for j in range(self.ili_bins):
        row = 48 + j
        rows[row][col + 0] = f(self._get(region, 'x1', j))
        rows[row][col + 1] = f(self._get(region, 'x2', j))
        rows[row][col + 2] = f(self._get(region, 'x3', j))
        rows[row][col + 3] = f(self._get(region, 'x4', j))
        rows[row][col + 4] = f(self._get(region, 'peak', j))
      rows[60][col + 0] = f(self._get(region, 'x1', 'point'))
      rows[60][col + 1] = f(self._get(region, 'x2', 'point'))
      rows[60][col + 2] = f(self._get(region, 'x3', 'point'))
      rows[60][col + 3] = f(self._get(region, 'x4', 'point'))
      rows[60][col + 4] = f(self._get(region, 'peak', 'point'))
    return Forecast._write_csv(filename, rows)

  def _write_v2015(self, path, filename):
    if filename is None:
      date = self.timestamp.strftime('%Y-%m-%d')
      filename = 'EW%02d-%s-%s.csv' % (self.epiweek2, self.team, date)
    if path is not None:
      filename = os.path.join(path, filename)
    timestamp = self.timestamp.strftime('%Y-%m-%d %H:%M:%S')
    rows = [['' for c in range(67)] for r in range(74)]
    rows[0][0] = 'This spreadsheet is scored automatically - do not change any of its formatting (e.g. add or delete blank rows or columns) or place forecasts in different cells.'
    rows[1][0] = 'Template version:'
    rows[1][1] = '2'
    rows[2][0] = 'Flu forecasts for season:'
    rows[2][1] = '2015-2016'
    rows[3][0] = 'Forecast created:'
    rows[3][1] = timestamp
    rows[4][0] = 'Forecasting team:'
    rows[4][1] = self.team
    rows[5][0] = 'Last published wILI:'
    rows[5][1] = 'EW%02d' % self.epiweek2
    rows[6][0] = 'forecast_io.py v%d' % Forecast._version
    for i in range(self.season_weeks):
      week = self.i2w[i]
      row = 9 + i
      rows[row][0] = 'Pr(EW%02d)' % week
    rows[42][0] = 'Pr(none)'
    rows[43][0] = 'Point Prediction'
    for i in range(self.ili_bins):
      row = 46 + i
      iliA = i * self.ili_bin_size
      iliB = (i + 1) * self.ili_bin_size
      if i == self.ili_bins - 1:
        rows[row][0] = 'Pr(%.1f%% <= wILI)' % iliA
      else:
        rows[row][0] = 'Pr(%.1f%% <= wILI < %.1f%%)' % (iliA, iliB)
    rows[73][0] = 'Point Prediction:'
    for (i, name) in enumerate(Forecast.region_names):
      col = 2 + i * 6
      rows[7][col + 0] = name
      rows[8][col + 0] = 'Season onset'
      rows[8][col + 1] = 'Peak week'
      rows[45][col + 0] = '1wk ahead'
      rows[45][col + 1] = '2wk ahead'
      rows[45][col + 2] = '3wk ahead'
      rows[45][col + 3] = '4wk ahead'
      rows[45][col + 4] = 'Peak Height'
    f = lambda x: ('%%.%df' % Forecast.precision) % x
    for (i, region) in enumerate(Forecast.regions):
      col = 2 + i * 6
      for j in range(self.season_weeks):
        row = 9 + j
        rows[row][col + 0] = f(self._get(region, 'onset', j))
        rows[row][col + 1] = f(self._get(region, 'peakweek', j))
      rows[42][col + 0] = f(self._get(region, 'onset', 'none'))
      rows[42][col + 1] = f(self._get(region, 'peakweek', 'none'))
      rows[43][col + 0] = self._get(region, 'onset', 'point')
      rows[43][col + 1] = self._get(region, 'peakweek', 'point')
      for j in range(self.ili_bins):
        row = 46 + j
        rows[row][col + 0] = f(self._get(region, 'x1', j))
        rows[row][col + 1] = f(self._get(region, 'x2', j))
        rows[row][col + 2] = f(self._get(region, 'x3', j))
        rows[row][col + 3] = f(self._get(region, 'x4', j))
        rows[row][col + 4] = f(self._get(region, 'peak', j))
      rows[73][col + 0] = f(self._get(region, 'x1', 'point'))
      rows[73][col + 1] = f(self._get(region, 'x2', 'point'))
      rows[73][col + 2] = f(self._get(region, 'x3', 'point'))
      rows[73][col + 3] = f(self._get(region, 'x4', 'point'))
      rows[73][col + 4] = f(self._get(region, 'peak', 'point'))
    return Forecast._write_csv(filename, rows)

  def _write_v2016(self, path, filename):
    if filename is None:
      date = self.timestamp.strftime('%Y-%m-%d')
      filename = 'EW%02d-%s-%s.csv' % (self.epiweek2, self.team, date)
    if path is not None:
      filename = os.path.join(path, filename)
    tryint = lambda x: int(x) if int(x) == x else x
    rows = [['' for c in range(7)] for r in range(8020)]
    rows[0][0] = 'Location'
    rows[0][1] = 'Target'
    rows[0][2] = 'Type'
    rows[0][3] = 'Unit'
    rows[0][4] = 'Bin_start_incl'
    rows[0][5] = 'Bin_end_notincl'
    rows[0][6] = 'Value'
    row = 1
    for region in Forecast.regions:
      region_name = Forecast.region_to_name[region]
      for target in Forecast.targets:
        target_name = Forecast.target_to_name[target]
        unit = 'week' if target in Forecast.week_targets else 'percent'
        for point_bin in ['Point', 'Bin']:
          point = point_bin == 'Point'
          if point:
            num_rows = 1
          elif target == 'onset':
            num_rows = self.season_weeks + 1
          elif target == 'peakweek':
            num_rows = self.season_weeks
          else:
            num_rows = self.ili_bins
          for i in range(num_rows):
            if point:
              start = end = 'NA'
              idx = 'point'
            elif target in Forecast.week_targets:
              if target == 'onset' and i == self.season_weeks:
                start = end = idx = 'none'
              else:
                start = self.i2w[i]
                end = start + 1
                idx = i
            else:
              start = i / 10
              end = 100 if start == 13 else (i + 1) / 10
              start, end = tryint(start), tryint(end)
              idx = i
            value = tryint(self._get(region, target, idx))
            rows[row][0] = region_name
            rows[row][1] = target_name
            rows[row][2] = point_bin
            rows[row][3] = unit
            rows[row][4] = start
            rows[row][5] = end
            rows[row][6] = value
            row += 1
    return Forecast._write_csv(filename, rows)

  def write(self, path=None, filename=None):
    return {
      2014: self._write_v2014,
      2015: self._write_v2015,
      2016: self._write_v2016,
    }[self.version](path, filename)

  @staticmethod
  def _read_v2014(read):
    team = read(2, 0)
    if ':' in team:
      team = team[team.index(':') + 1:]
    team = '-'.join(team.strip().split())
    ew = Forecast.parse_epiweek(read(3, 1), 'int')
    epiweek = (2014 + (1 if ew <= 20 else 0)) * 100 + ew
    fc = Forecast(2014, datetime.now(), team, epiweek)
    for (i, region) in enumerate(Forecast.regions):
      col = 2 + i * 6
      for j in range(fc.season_weeks):
        row = 7 + j
        fc._set(region, 'onset', j, float(read(row, col + 1)))
        fc._set(region, 'peakweek', j, float(read(row, col + 3)))
      fc._set(region, 'onset', 'none', float(read(41, col + 1)))
      fc._set(region, 'peakweek', 'none', float(read(41, col + 3)))
      fc._set(region, 'onset', 'point', Forecast.parse_epiweek(read(43, col + 1), 'float'))
      fc._set(region, 'peakweek', 'point', Forecast.parse_epiweek(read(43, col + 3), 'float'))
      for j in range(fc.ili_bins):
        row = 48 + j
        fc._set(region, 'x1', j, float(read(row, col + 0)))
        fc._set(region, 'x2', j, float(read(row, col + 1)))
        fc._set(region, 'x3', j, float(read(row, col + 2)))
        fc._set(region, 'x4', j, float(read(row, col + 3)))
        fc._set(region, 'peak', j, float(read(row, col + 4)))
      fc._set(region, 'x1', 'point', float(read(60, col + 0)))
      fc._set(region, 'x2', 'point', float(read(60, col + 1)))
      fc._set(region, 'x3', 'point', float(read(60, col + 2)))
      fc._set(region, 'x4', 'point', float(read(60, col + 3)))
      fc._set(region, 'peak', 'point', float(read(60, col + 4)))
    return fc

  @staticmethod
  def _read_v2015(read):
    team = '-'.join(read(4, 1).strip().split())
    ew = Forecast.parse_epiweek(read(5, 1), 'int')
    epiweek = (2015 + (1 if ew <= 20 else 0)) * 100 + ew
    fc = Forecast(2015, datetime.now(), team, epiweek)
    for (i, region) in enumerate(Forecast.regions):
      col = 2 + i * 6
      for j in range(fc.season_weeks):
        row = 9 + j
        fc._set(region, 'onset', j, float(read(row, col + 0)))
        fc._set(region, 'peakweek', j, float(read(row, col + 1)))
      fc._set(region, 'onset', 'none', float(read(42, col + 0)))
      fc._set(region, 'peakweek', 'none', float(read(42, col + 1)))
      fc._set(region, 'onset', 'point', Forecast.parse_epiweek(read(43, col + 0), 'float'))
      fc._set(region, 'peakweek', 'point', Forecast.parse_epiweek(read(43, col + 1), 'float'))
      for j in range(fc.ili_bins):
        row = 46 + j
        fc._set(region, 'x1', j, float(read(row, col + 0)))
        fc._set(region, 'x2', j, float(read(row, col + 1)))
        fc._set(region, 'x3', j, float(read(row, col + 2)))
        fc._set(region, 'x4', j, float(read(row, col + 3)))
        fc._set(region, 'peak', j, float(read(row, col + 4)))
      fc._set(region, 'x1', 'point', float(read(73, col + 0)))
      fc._set(region, 'x2', 'point', float(read(73, col + 1)))
      fc._set(region, 'x3', 'point', float(read(73, col + 2)))
      fc._set(region, 'x4', 'point', float(read(73, col + 3)))
      fc._set(region, 'peak', 'point', float(read(73, col + 4)))
    return fc

  @staticmethod
  def _read_v2016(read, ew, team):
    epiweek = (2016 + (1 if ew <= 20 else 0)) * 100 + ew
    fc = Forecast(2016, datetime.now(), team, epiweek)
    point_bin = ['Point', 'Bin']
    for row in range(1, 8020):
      region = Forecast.region_from_name[read(row, 0)]
      target = Forecast.target_from_name[read(row, 1)]
      point = read(row, 2) == 'Point'
      unit = read(row, 3)
      if point:
        idx = 'point'
        if unit == 'week':
          value = Forecast.parse_epiweek(read(row, 6), 'float')
        else:
          value = float(read(row, 6))
      else:
        idx = read(row, 4)
        value = float(read(row, 6))
        if idx != 'none':
          if unit == 'week':
            idx = fc.w2i[int(idx)]
          else:
            idx = round(float(idx) * 10)
      fc._set(region, target, idx, value)
    return fc

  @staticmethod
  def read(filename):
    extension = os.path.splitext(filename.lower())[1]
    if extension == '.csv':
      rows = Forecast._read_csv(filename)
      read = lambda row, col: rows[row][col]
    elif extension in ('.xls', '.xlsx'):
      import xlrd
      sheet = xlrd.open_workbook(filename).sheet_by_index(0)
      read = lambda row, col: sheet.cell_value(row, col)
    else:
      raise Exception('invalid extension')
    if read(0, 0) == 'Flu forecasts for 2014-2015 flu season':
      return Forecast._read_v2014(read)
    elif read(1, 1) == '2':
      return Forecast._read_v2015(read)
    elif read(0, 0) == 'Location':
      fn = os.path.basename(filename)
      m = re.compile('^EW(\\d{2})-(.*)-\\d{4}-\\d{2}-\\d{2}.csv$').match(fn)
      if m is not None:
        ew, team = int(m.group(1)), m.group(2)
      else:
        ew, team = 40, 'unknown'
      return Forecast._read_v2016(read, ew, team)
    else:
      raise Exception('version detection failed')

  def export_json(self):
    return json.dumps({
      '_version': Forecast._version,
      'name': self.team,
      'season': self.version,
      'epiweek': self.epiweek,
      'data': self.data,
      'baselines': self.baselines,
      'year_weeks': self.year_weeks,
      'season_weeks': self.season_weeks,
      'ili_bins': self.ili_bins,
      'ili_bin_size': self.ili_bin_size,
    })

  def export_flusight(self):
    if self.version != 2016:
      raise Exception('not supported for season ' + self.version)
    exp = []
    tryint = lambda x: int(x) if int(x) == x else x
    for region in Forecast.regions:
      for target in Forecast.targets:
        unit = 'week' if target in Forecast.week_targets else 'percent'
        point = self._get(region, target, 'point')
        bins = []
        if target == 'onset':
          num_rows = self.season_weeks + 1
        elif target == 'peakweek':
          num_rows = self.season_weeks
        else:
          num_rows = self.ili_bins
        for i in range(num_rows):
          if target in Forecast.week_targets:
            if target == 'onset' and i == self.season_weeks:
              start, end, idx = 0, 0, 'none'
            else:
              start = self.i2w[i]
              end = start + 1
              idx = i
          else:
            start = i / 10
            end = 100 if start == 13 else (i + 1) / 10
            start, end = tryint(start), tryint(end)
            idx = i
          value = self._get(region, target, idx)
          bins.append({
            'start': start,
            'end': end,
            'value': value,
          })
        exp.append({
          'location': Forecast.region_to_name[region],
          'target': Forecast.target_to_name[target],
          'unit': unit,
          'point': point,
          'bins': bins,
        })
    return json.dumps(exp)

  @staticmethod
  def import_flusight(version, timestamp, team, epiweek, json_data):
    if version != 2016:
      raise Exception('not supported for season ' + version)
    data = json.loads(json_data)
    fc = Forecast(version, timestamp, team, epiweek)
    for row in data:
      region = Forecast.region_from_name[row['location']]
      target = Forecast.target_from_name[row['target']]
      if target in Forecast.week_targets:
        value = Forecast.parse_epiweek(row['point'], 'float')
      else:
        value = float(row['point'])
      fc._set(region, target, 'point', value)
      for bin_row in row['bins']:
        if target == 'onset' and bin_row['start'] == 0 and bin_row['end'] == 0:
          idx = 'none'
        elif target in Forecast.week_targets:
          idx = bin_row['start']
          if idx < 40:
            idx += fc.year_weeks
          idx -= 40
        else:
          idx = round(bin_row['start'] / fc.ili_bin_size)
        value = bin_row['value']
        fc._set(region, target, idx, value)
    return fc
