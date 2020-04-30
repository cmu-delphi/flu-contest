"""Writes COVID-19 forecast CSV files."""

# first party
import delphi.flu_contest.covid.constants as Constants


class ForecastWriter:

  @staticmethod
  def maybe_capitalize_word(word):
    if word in ['of', 'the']:
      return word
    return word[:1].upper() + word[1:]

  @staticmethod
  def get_location_name(location_code):
    words = Constants.LOCATION_NAMES[location_code].split()
    cap_words = [ForecastWriter.maybe_capitalize_word(word) for word in words]
    return ' '.join(cap_words)

  @staticmethod
  def write_common_targets(f, forecasts, location):
    location_name = ForecastWriter.get_location_name(location)
    for target in Constants.COMMON_TARGETS:
      target_name = Constants.TARGET_NAMES[target]

      # point prediction
      value = forecasts[location]['points'][target]
      if target.endswith('week'):
        # format as epiweek
        wk = 10 + value
        if wk < 10 or wk > 35 or round(wk) != wk:
          raise Exception('invalid week')
        value_str = '2020-ew%02d' % wk
      else:
        # wili
        value_str = '%f' % value
      f.write('%s,%s,point,NA,%s\n' % (location_name, target_name, value_str))

      bins = forecasts[location]['bins'][target]

      # distribution over weeks
      if target.endswith('week'):
        # distribution spans 2020w10--2020w35
        for i, week in enumerate(range(10, 36)):
          week_name = '2020-ew%02d' % week
          value_str = '%f' % bins[i]
          args = (location_name, target_name, week_name, value_str)
          f.write('%s,%s,bin,%s,%s\n' % args)
      else:
        # distribution over wili
        # distribution spans [0, 100]
        for i, prob in enumerate(bins):
          bin_name = '%.1f' % (i / 10)
          value_str = '%f' % bins[i]
          args = (location_name, target_name, bin_name, value_str)
          f.write('%s,%s,bin,%s,%s\n' % args)

  @staticmethod
  def write_regional_targets(f, forecasts, location):
    location_name = ForecastWriter.get_location_name(location)

    target = 'offset_week'
    target_name = Constants.TARGET_NAMES[target]

    # // copy-pasta

    # point prediction
    value = forecasts[location]['points'][target]
    wk = 10 + value
    if wk < 10 or wk > 35 or round(wk) != wk:
      raise Exception('invalid week')
    value_str = '2020-ew%02d' % wk
    f.write('%s,%s,point,NA,%s\n' % (location_name, target_name, value_str))

    bins = forecasts[location]['bins'][target]
    if target.endswith('week'):
      # distribution spans 2020w10--2020w35
      for i, week in enumerate(range(10, 36)):
        week_name = '2020-ew%02d' % week
        value_str = '%f' % bins[i]
        args = (location_name, target_name, week_name, value_str)
        f.write('%s,%s,bin,%s,%s\n' % args)

    # copy-pasta //

    target = 'offset_happened'
    target_name = Constants.TARGET_NAMES[target]

    # no point prediction, and single bin (of two total)
    value_str = '%f' % forecasts[location]['bins'][target]
    f.write('%s,%s,bin,true,%s\n' % (location_name, target_name, value_str))

  @staticmethod
  def generate_csv(forecasts, epiweek):
    # write the files (rename later if you want)
    filename = 'covid-epicast-%d-regional.csv' % epiweek
    with open(filename, 'w') as f:
      f.write('location,target,type,bin,value\n')

      for location in sorted(forecasts.keys()):
        if location in Constants.BASELINES:
          # this is a region
          ForecastWriter.write_common_targets(f, forecasts, location)
          ForecastWriter.write_regional_targets(f, forecasts, location)
    print('wrote', filename)

    filename = 'covid-epicast-%d-state.csv' % epiweek
    with open(filename, 'w') as f:
      f.write('location,target,type,bin,value\n')

      for location in sorted(forecasts.keys()):
        if location not in Constants.BASELINES:
          # this is a state (or territory, etc0)
          ForecastWriter.write_common_targets(f, forecasts, location)
    print('wrote', filename)
