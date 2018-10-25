"""
===============
=== Purpose ===
===============

Creates submissions for Epicast hospitalization.

"""

# first party
from ..epicast.fc_epicast_hosp import Epicast
from ..forecasters.fc_baseline import Baseline
from ..forecasters.fc_hybrid import Hybrid
from ..utils.forecast_io_hosp import ForecastIO
from delphi.utils.epidate import EpiDate
from ..utils.forecast_type import ForecastType


SEASON = 2018


class Submissions:

  def __init__(self, locations, num_backfill_samples=10000):
    self.past = Baseline(SEASON, locations, num_backfill_samples, ForecastType.HOSP)

  def run_epicast(self, epiweek, min_week_prob, min_wili_prob):
    future = Epicast(SEASON, self.past.locations, ForecastType.HOSP, verbose=True)

    forecaster = Hybrid('delphi-epicast', self.past, future, ForecastType.HOSP)
    forecaster.min_week_prob = min_week_prob
    forecaster.min_wili_prob = min_wili_prob
    forecaster.smooth_weeks_bw = 0
    forecaster.smooth_wili_bw = 0
    forecaster.forecast_weeks = None
    forecaster.forecast_wili = None

    def update_epicast_df():
      forecaster.forecast_weeks = Epicast.get_week_forecast(future._num_users)
      forecaster.forecast_wili = Epicast.get_wili_forecast(future._num_users)
      #print('Updated Epicast df for %d users.' % future._num_users)
    forecaster._callback = update_epicast_df

    print('Generating epicast for', epiweek)
    forecaster.open()
    forecast = forecaster.forecast(epiweek) # is this the forecast function in fc_abstract.py?
    filename = ForecastIO.save_csv(forecast)
    forecaster.close()
    print(filename)
    return filename


if __name__ == '__main__':
  epiweek = EpiDate.today().add_weeks(-1).get_ew()
  print("epiweek: ", epiweek)
  print('WARNING: For testing only!')
  print(' - Using very small number of samples')
  print(' - Not uploading submissions to database')
  print(' - Not emailing submissions to CDC')
  print(' - Assuming last published wILI on %d' % epiweek)
  print(' - Limited locations')

  ec_age_groups = ['rate_overall', 'rate_age_0', 'rate_age_1', 'rate_age_2', 'rate_age_3', 'rate_age_4']
  sub = Submissions(ec_age_groups, 1000)
  ec = None
  ec = sub.run_epicast(epiweek, 0.001, 0.001)

  print('Finished! Files are:')
  print(' -', ec)
