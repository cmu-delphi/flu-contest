"""
Forecast serialization and deserialization.

Specific to the 2017-2018 flu season.
"""

# standard library
import csv
import datetime
import json
import os
import re

# first party
from forecast import Forecast
from forecast_meta import Locations, Targets, Types


class ForecastIO:

  _version = 3

  @staticmethod
  def int_or_float(x):
    # cast as int, but only if it doesn't change the value
    xf = float(x)
    xi = int(xf)
    return xi if xi == xf else xf

  @staticmethod
  def get_week_index(week):
    if not (40 <= week <= 52) and not (1 <= week <= 20):
      raise Exception('invalid week: %d' % week)
    return week - 40 if week >= 40 else week + 12

  @staticmethod
  def get_index_week(index):
    if not (0 <= index <= 32):
      raise Exception('invalid index: %d' % index)
    return index + 40 if index <= 12 else index - 12

  @staticmethod
  def __load_row(forecast, location, target, type_, start, value):
    # convert to delphi names
    location = Locations.get_delphi_name(location)
    target = Targets.get_delphi_name(target)
    type_ = Types.get_delphi_name(type_)

    # get the index, which is either a name or a number
    if type_ == 'dist':
      if start == 'none':
        # no onset
        index = 'none'
      elif Targets.is_ili(target):
        # ili bin index
        index = round(float(start) * 10)
      else:
        # week number
        index = ForecastIO.get_week_index(int(start))
    else:
      # point prediction
      index = 'point'

    # parse the value
    value = ForecastIO.int_or_float(value)

    # finally, set the value
    fc = forecast.get_or_create_forecast(location)
    fc.set_single_value(target, index, value)

  @staticmethod
  def load_csv(filename):
    timestamp = None
    pattern = re.compile('^EW(\\d{2})-(.*)-(\\d{4})-\\d{2}-\\d{2}.csv$')
    match = pattern.match(os.path.basename(filename))
    if match is not None:
      ew = int(match.group(1))
      team = match.group(2)
      year = int(match.group(3))
      if ew < 40:
        season = year - 1
        epiweek = (season + 1) * 100 + ew
      else:
        season = year
        epiweek = season * 100 + ew
    else:
      raise NotImplementedError()

    forecast = Forecast(season, timestamp, team, epiweek)

    # the default column layout
    # can be updated based on header row
    canonical_fields = [f.lower() for f in (
      'Location', 'Target', 'Type', 'Unit', 'Bin_start_incl',
      'Bin_end_notincl', 'Value'
    )]
    field_to_column = dict(zip(canonical_fields, range(len(canonical_fields))))

    # read the csv one row at a time
    with open(filename, 'r', newline='') as f:
      reader = csv.reader(f)
      for row in reader:
        # skip header row(s)
        fields = [f.lower() for f in row]
        if 'location' in fields:
          # update the field-to-column-index mapping
          field_to_column = dict(zip(fields, range(len(fields))))
          continue

        # extract values
        values = [row[field_to_column[f]] for f in canonical_fields]
        location, target, type_, unit, start, end, value = values

        # update forecast
        ForecastIO.__load_row(forecast, location, target, type_, start, value)

    # return the group of forecasts per location
    return forecast

  @staticmethod
  def __save_target(writer, location, target, data, unit, idx_func):
    # convert to display names
    location = Locations.get_display_name(location)
    target = Targets.get_display_name(target)

    # point prediction
    type_ = Types.get_display_name('point')
    value = ForecastIO.int_or_float(data['point'])
    row = [location, target, type_, unit, 'NA', 'NA', value]
    writer.writerow(row)

    # distribution
    type_ = Types.get_display_name('dist')
    for index, value in enumerate(data['dist']):
      start, end = idx_func(index)
      start, end, value = map(ForecastIO.int_or_float, (start, end, value))
      row = [location, target, type_, unit, start, end, value]
      writer.writerow(row)

    # probability of no onset (if applicable)
    if 'none' in data:
      value = ForecastIO.int_or_float(data['none'])
      row = [location, target, type_, unit, 'none', 'none', value]
      writer.writerow(row)

  @staticmethod
  def __save_week_target(writer, location, target, data):
    def idx_func(index):
      week = ForecastIO.get_index_week(index)
      return week, week + 1
    unit = 'week'
    ForecastIO.__save_target(writer, location, target, data, unit, idx_func)

  @staticmethod
  def __save_ili_target(writer, location, target, data):
    def idx_func(index):
      start, end = index / 10, (index + 1) / 10
      if index == 130:
        end = 100
      return start, end
    unit = 'percent'
    ForecastIO.__save_target(writer, location, target, data, unit, idx_func)

  @staticmethod
  def save_csv(forecast, filename=None):
    if filename is None:
      now = datetime.datetime.now()
      week = forecast.epiweek % 100
      args = (week, forecast.team, now.year, now.month, now.day)
      filename = 'EW%02d-%s-%04d-%02d-%02d.csv' % args

    # write the csv one row at a time
    with open(filename, 'w', newline='') as f:
      dialect = csv.excel()
      dialect.lineterminator = '\n'
      writer = csv.writer(f, dialect=dialect)

      # write the header row
      writer.writerow([
        'Location', 'Target', 'Type', 'Unit', 'Bin_start_incl',
        'Bin_end_notincl', 'Value'
      ])

      # write each location
      for location in forecast.get_locations():

        # location-specific helper functions
        def save_week_target(target, data):
          ForecastIO.__save_week_target(writer, location, target, data)

        def save_ili_target(target, data):
          ForecastIO.__save_ili_target(writer, location, target, data)

        # write each target
        fc = forecast.get_forecast(location)
        if fc.has_onset():
          save_week_target('onset', fc.get_onset())
        save_week_target('peakweek', fc.get_peakweek())
        save_ili_target('peak', fc.get_peak())
        for i in range(1, 5):
          save_ili_target('x%d' % i, fc.get_lookahead(i))

    return filename

  @staticmethod
  def import_json_delphi(json_str):
    obj = json.loads(json_str)
    if obj['_version'] > ForecastIO._version:
      raise Exception('unable to import version: %d' % obj['_version'])
    team, season, epiweek = obj['name'], obj['season'], obj['epiweek']
    timestamp = None
    forecast = Forecast(team, timestamp, season, epiweek)
    data = obj['data']
    for location in data.keys():
      fc = forecast.get_or_create_forecast(location)
      fc.data = data[location]
    return forecast

  @staticmethod
  def export_json_delphi(forecast):
    return json.dumps({
      '_version': ForecastIO._version,
      'name': forecast.team,
      'season': forecast.season,
      'epiweek': forecast.epiweek,
      'year_weeks': forecast.season_length + 19,
      'season_weeks': forecast.season_length,
      'ili_bins': forecast.num_ili_bins,
      'ili_bin_size': forecast.ili_bin_size,
      'data': dict(
        (location, forecast.get_forecast(location).data)
        for location in forecast.get_locations()
      ),
    })

  @staticmethod
  def import_json_flusight(json_str, team, timestamp, season, epiweek):
    raise NotImplementedError()

  @staticmethod
  def export_json_flusight(forecast):
    raise NotImplementedError()
