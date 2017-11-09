"""
===============
=== Purpose ===
===============

A slightly improved version of the "pinned baseline" forecast, combining a
backfill model (weekly variance) of the past with an empirical model (weekly
mean and variance) of the future. Point predictions and distributions are built
for each target by randomly sampling trajectories from the combined models.


=================
=== Changelog ===
=================

2015-10-28
  * Avoid needlessly retraining
2015-10-26
  + First version
"""

# third party
import numpy as np

# first party
from .fc_abstract import Forecaster
from delphi.epidata.client.delphi_epidata import Epidata
import delphi.utils.epiweek as flu


class Baseline(Forecaster):

  def __init__(self, test_season, locations, num_samples, backfill_weeks=10, do_sampling=True):
    method = '%d%d' % (backfill_weeks is not None, do_sampling)
    super().__init__('fc-baseline-%s' % method, test_season, locations)
    self.num_samples = num_samples
    self.backfill_weeks = backfill_weeks
    self.do_sampling = do_sampling
    self.bf_var = {}
    self.emp_mean = {}
    self.emp_var = {}
    self.emp_curves = {}

  def _train(self, region):
    if region in self.bf_var:
      # already trained
      return
    if len(region) == 2:
      # TODO: this is a hack for state ILI
      # assume backfill of region 4
      print('FIXME: setting backfill for %s as hhs4' % region)
      self.bf_var[region] = self.bf_var['hhs4']
      self.emp_mean[region] = self.emp_mean['hhs4']
      self.emp_var[region] = self.emp_var['hhs4']
      self.emp_curves[region] = self.emp_curves['hhs4']
      return
    stable = self._get_stable(region)
    start_weeks = [flu.get_season(ew)[0] for ew in stable.keys()]
    curves = []
    seasons = set([flu.split_epiweek(ew)[0] for ew in start_weeks if ew is not None])
    for s in seasons:
      ew1 = flu.join_epiweek(s + 0, 40)
      ew2 = flu.add_epiweeks(ew1, 37)
      curve = [stable[ew] for ew in flu.range_epiweeks(ew1, ew2)]
      curves.append(curve)
    self.emp_mean[region] = np.mean(curves, axis=0)
    self.emp_var[region] = np.var(curves, axis=0, ddof=1)
    self.emp_curves[region] = curves
    if self.backfill_weeks is None:
      self.bf_var[region] = [0]
    else:
      self.bf_var[region] = []
      for lag in range(self.backfill_weeks):
        unstable = self._get_unstable(region, lag)
        changes = [stable[ew] - unstable[ew] for ew in stable.keys() & unstable.keys()]
        if len(changes) < 2:
          raise Exception('not enough data')
        self.bf_var[region].append(np.var(changes, ddof=1))
    print(' %5s: %s' % (region, ' '.join(['%.3f' % (b ** 0.5) for b in self.bf_var[region]])))

  def _forecast(self, region, epiweek):
    ew1 = flu.join_epiweek(self.test_season + 0, 40)
    ew2 = flu.join_epiweek(self.test_season + 1, 24)
    num_weeks = flu.delta_epiweeks(ew1, ew2)
    observed = self._get_current(region, epiweek)
    mean, var = self.emp_mean[region].copy(), self.emp_var[region].copy()
    for ew in flu.range_epiweeks(ew1, flu.add_epiweeks(epiweek, 1)):
      i = flu.delta_epiweeks(ew1, ew)
      lag = flu.delta_epiweeks(ew1, epiweek) - i
      lag = min(lag, len(self.bf_var[region]) - 1)
      mean[i] = observed[i]
      var[i] = self.bf_var[region][lag]
    curves = Forecaster.Utils.sample_normal_var(mean, var, self.num_samples)
    if not self.do_sampling:
      offset = flu.delta_epiweeks(ew1, epiweek) + 1
      for (i, curve) in enumerate(curves):
        index = i % len(self.emp_curves[region])
        curve[offset:] = self.emp_curves[region][index][offset:]
    return curves

  def _get_unstable(self, region, lag):
    ranges = []
    for s in range(2010, self.test_season):
      ew1 = flu.join_epiweek(s + 0, 40)
      ew2 = flu.join_epiweek(s + 1, 20)
      ranges.append(Epidata.range(ew1, ew2))
    epidata = Forecaster.Utils.decode(Epidata.fluview(region, ranges, lag=lag))
    return dict([(row['epiweek'], row['wili']) for row in epidata])

  def _get_stable(self, region):
    ranges = []
    for s in range(2003, self.test_season):
      if s == 2009:
        continue
      ew1 = flu.join_epiweek(s, 40)
      ew2 = flu.add_epiweeks(ew1, 37)
      ranges.append(Epidata.range(ew1, ew2))
    epidata = Forecaster.Utils.decode(Epidata.fluview(region, ranges))
    return dict([(row['epiweek'], row['wili']) for row in epidata])

  def _get_current(self, region, epiweek):
    ew1 = flu.join_epiweek(self.test_season + 0, 40)
    ew2 = flu.join_epiweek(self.test_season + 1, 20)
    weeks = Epidata.range(ew1, ew2)
    epidata = Forecaster.Utils.decode(Epidata.fluview(region, weeks, issues=epiweek))
    data = [row['wili'] for row in epidata]
    if len(data) != flu.delta_epiweeks(ew1, epiweek) + 1:
      raise Exception('missing data')
    return data
