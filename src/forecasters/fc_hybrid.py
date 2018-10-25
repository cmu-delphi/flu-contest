"""
===============
=== Purpose ===
===============

Join curves produced by two forecasters; one for the past, and one for the
future (including the current week).


=================
=== Changelog ===
=================

2015-11-09
  + Temporary callback hack (e.g. to set Epicast df)
2015-10-26
  + First version
"""

# first party
from .fc_abstract import Forecaster
import delphi.utils.epiweek as flu
from ..utils.forecast_type import ForecastType


class Hybrid(Forecaster):

  def __init__(self, name, past, future, forecast_type):
    if past.test_season != future.test_season:
      raise Exception('`past` and `future` trained on different seasons')
    super().__init__(name, past.test_season, past.locations, forecast_type)
    self.past = past
    self.future = future
    self._callback = None
    self.forecast_type = forecast_type

  def _init(self):
    self.past.open()
    self.future.open()

  def _fini(self):
    self.past.close()
    self.future.close()

  def _forecast(self, region, epiweek):
    epiweek = 201841;
    print('inside hybrid._forecast, region, epiweek:', region, epiweek)
    P = self.past._forecast(region, epiweek)
    F = self.future._forecast(region, epiweek)
    i = flu.delta_epiweeks(flu.join_epiweek(self.test_season, 40), epiweek)
    curves = []
    for j in range(max(len(P), len(F))):
      p, f = P[j % len(P)], F[j % len(F)]
      curves.append(list(p[:i]) + list(f[i:]))
    if self._callback is not None:
      self._callback()
    return curves
