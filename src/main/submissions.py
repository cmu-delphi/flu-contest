"""
===============
=== Purpose ===
===============

Creates submissions for Epicast. This program also used to create Archefilter
submissions.


=================
=== Changelog ===
=================

2016-11-29
  - not using default probability floor of 0.001 (must be provided)
2016-10-27
  - removed archefilter
  * updated for 2016 flu contest
2015-12-14
  * original version (combines make_epicast_submission.py and driver.py)
"""

# first party
from ..epicast.fc_epicast import Epicast
from ..forecasters.fc_baseline import Baseline
from ..forecasters.fc_hybrid import Hybrid
from ..utils.forecast_io import ForecastIO
from delphi.utils.epidate import EpiDate
from ..utils.forecast_type import ForecastType


SEASON = 2018


class Submissions:

  def __init__(self, locations, num_backfill_samples=10000):
    self.past = Baseline(SEASON, locations, num_backfill_samples, ForecastType.WILI)

  def run_epicast(self, epiweek, min_week_prob, min_wili_prob):
    future = Epicast(SEASON, self.past.locations, ForecastType.WILI, verbose=True)

    forecaster = Hybrid('delphi-epicast', self.past, future, ForecastType.WILI)
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
    forecast = forecaster.forecast(epiweek)
    filename = ForecastIO.save_csv(forecast)
    forecaster.close()
    print(filename)
    return filename

  def run_archefilter(self, epiweek, min_week_prob, min_wili_prob, num_samples=10000):
    future = Archefilter(SEASON, self.past.locations, num_samples)
    forecaster = Hybrid('delphi-archefilter', self.past, future, ForecastType.WILI)
    forecaster.min_week_prob = min_week_prob
    forecaster.min_wili_prob = min_wili_prob
    forecaster.smooth_weeks_bw = 1
    forecaster.smooth_wili_bw = 1

    print('Generating archefilter for', epiweek)
    forecaster.open()
    forecast = forecaster.forecast(epiweek)
    filename = ForecastIO.save_csv(forecast)
    forecaster.close()
    print(filename)
    return filename


if __name__ == '__main__':
  epiweek = EpiDate.today().add_weeks(-1).get_ew()
  print('WARNING: For testing only!')
  print(' - Using very small number of samples')
  print(' - Not uploading submissions to database')
  print(' - Not emailing submissions to CDC')
  print(' - Assuming last published wILI on %d' % epiweek)
  print(' - Limited locations')

  regions = ['nat', 'hhs1','hhs2','hhs3','hhs4','hhs5','hhs6','hhs7','hhs8','hhs9','hhs10', 'pa', 'ga', 'tx', 'or', 'dc']
  sub = Submissions(regions, 10000)
  ec, af = None, None
  ec = sub.run_epicast(epiweek, 0.001, 0.001)
  #af = sub.run_archefilter(epiweek, 0.002, 0.002, num_samples=1000)

  print('Finished! Files are:')
  print(' -', ec)
  print(' -', af)
