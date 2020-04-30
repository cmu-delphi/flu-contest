"""Generates an epicast (aka crowdcast) forecast.

This is a COVID-19-specific reimplementation of the normal flu-season epicast.

The original epicast forecasting code is available in this repo at: ../epicast

The methodology is published at:
https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005248
"""

# standard library
import argparse

# first party
import delphi.flu_contest.covid.constants as Constants
from delphi.flu_contest.covid.database import Database
from delphi.flu_contest.covid.epicast_core import EpicastCore
from delphi.flu_contest.covid.forecast_writer import ForecastWriter
import delphi.utils.epiweek as epiweek_lib


def get_argument_parser():
  """Define command line arguments."""

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '--epiweek',
    type=int,
    help='week when predictions were submitted')
  return parser


def load_predictions(epiweek):
  # load epicast data from the database
  database = Database()
  database.connect()
  try:
    prediction_rows = database.get_user_predictions(epiweek)
  finally:
    # there are no changes to commit
    database.disconnect(False)

  # epicast locations (either give a list or `None` to use all locations)
  # location_codes = ['nat']
  location_codes = None

  if location_codes:
    # forecast only manually specified locations
    keep_set = set(code.lower() for code in location_codes)
    prediction_rows = [row for row in prediction_rows if row[0] in keep_set]
  else:
    # forecast all available locations
    location_codes = sorted(set(row[0] for row in prediction_rows))

  # organize predictions (time-series) by location and user
  user_predictions = {}
  for (location, user, week, wili) in prediction_rows:
    if location not in user_predictions:
      user_predictions[location] = {}
    if user not in user_predictions[location]:
      user_predictions[location][user] = []
    user_predictions[location][user].append((week, wili))

  return location_codes, user_predictions


def drop_invalid_predictions(epiweek, user_predictions):
  # sanity check user inputs (copy key sets since we modify the dict in-place)
  expected_length = epiweek_lib.delta_epiweeks(epiweek, Constants.MAX_EPIWEEK)
  num_dropped = 0
  for location in list(user_predictions.keys()):
    for user in list(user_predictions[location].keys()):
      if len(user_predictions[location][user]) != expected_length:
        num_dropped += 1
        del user_predictions[location][user]
        if not user_predictions[location]:
          del user_predictions[location]
  if num_dropped:
    print('NOTE: dropped %d time-series with invalid length' % num_dropped)


def main(args):
  if not args.epiweek:
    raise Exception('epiweek is required (use --epiweek flag)')

  # load and validate all predictions made this week
  location_codes, user_predictions = load_predictions(args.epiweek)
  drop_invalid_predictions(args.epiweek, user_predictions)

  # run the epicast core forecaster
  forecasts = {}
  for location_code in location_codes:
    forecasts[location_code] = EpicastCore.forecast(
        args.epiweek, user_predictions, location_code)

  # convert pure distributions into uniform-blended bins
  EpicastCore.materialize_bins(forecasts)

  # generate the output files
  ForecastWriter.generate_csv(forecasts, args.epiweek)


if __name__ == '__main__':
  main(get_argument_parser().parse_args())
