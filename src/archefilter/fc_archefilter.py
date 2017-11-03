"""
===============
=== Purpose ===
===============

Assimilates digital surveillance signals and a flu model to produce nowcasts
(and, secondarily, forecasts) of flu.


=================
=== Changelog ===
=================

2016-12-08
  + use secrets
2015-12-30
  + enforce minimum number of bins when sampling
  * quick hack for 2015w50: min_shift from -10 to 0
2015-12-17
  * penalizing HHS6 curve height by 15%
2015-12-14
  + AF_Utils.signal* (replace `data_io` version)
  * replace `data_io` with Epidata API call to `signals`
  * prefixed output with [AF]
  - don't penalize tall curves
  - AF_Utils.check (duplicate of AF_Utils._get)
2015-12-07
  + penalize ridiculously tall curves (i.e. hhs6 on 2015w45)
2015-11-09
  * near total rewrite of process model and filtering
2015-10-26
  + first version
"""

# built-in
# external
from filterpy.kalman import MerweScaledSigmaPoints as SigmaPoints
from filterpy.kalman import UnscentedKalmanFilter as UKF
import numpy as np
import scipy.stats as stats
# local
from archetype import Archetype
from delphi_epidata import Epidata
import epiweek as flu
from fc_abstract import Forecaster
from neldermead import NelderMead
import secrets


class FluProcess:
  """ the model, based on the Archetype idea """

  def __init__(self, archetype):
    self.archetype = archetype
    self.target_mean = {}
    self.target_var = {}
    self.target_std = {}

  def score(self, region, curve):
    # half of summed squared normalized error (from multivariate normal PDF)
    if region == 'hhs6':
      curve = curve * 1.15
    z_scores = self.weights * (curve - self.target_mean[region]) / self.target_std[region]
    return np.dot(z_scores, z_scores) / 2

  def scan_grid(self, region, min_shift, max_shift, n_shift, min_scale, max_scale, n_scale):
    # calculate parameter bins
    shifts = np.linspace(min_shift, max_shift, n_shift)
    scales = np.linspace(min_scale, max_scale, n_scale)
    d_shift, d_scale = shifts[1] - shifts[0], scales[1] - scales[0]
    bins = [[(t, s) for s in scales] for t in shifts]
    samples = []
    # get score of curve in center of each bin
    grid = np.zeros((n_shift, n_scale))
    for (t, shift) in enumerate(shifts):
      for (s, scale) in enumerate(scales):
        grid[t][s] = self.score(region, self.archetype[region].instance(scale, shift, False))
    # convert scores to PMF
    grid = np.exp(-grid)
    grid /= np.sum(grid)
    # find best bin index
    best = np.unravel_index(np.argmax(grid), grid.shape)
    return grid, bins, best, d_shift, d_scale

  def get_best_fit(self, region, output=None):
    # coarse sweep over global parameter space
    grid, bins, best, d_shift, d_scale = self.scan_grid(region, 0, +10, 32, 1 / 3, 3, 32)
    guess = bins[best[0]][best[1]]
    # initialize derivate-free optimizer to find best parameters
    def objective(params):
      return self.score(region, self.archetype[region].instance(params[1], params[0], False))
    solver = NelderMead(objective, limit_iterations=100, silent=True)
    simplex = solver.get_simplex(len(guess), guess, min(d_shift, d_scale))
    # do the optimization
    shift, scale = solver.run(simplex)._location
    if output is not None:
      output[0] = shift
      output[1] = scale
    # return the best-fit curve
    return self.archetype[region].instance(scale, shift, False)

  def get_sample_fits(self, region, num_samples, add_holiday):
    ## find the best part of parameter space
    #loc = [0, 0]
    #self.get_best_fit(region, loc)
    # fine sweep over local parameter space
    #nw, ns = 2, 1.1
    #t1, t2 = loc[0] - nw, loc[0] + nw
    #s1, s2 = loc[1] / ns, loc[1] * ns
    t1, t2 = 0, +10
    s1, s2 = 1 / 3, 3
    grid, bins, best, d_shift, d_scale = self.scan_grid(region, t1, t2, 128, s1, s2, 128)
    # sort by decreasing bin likelihood
    data = []
    for (t, row) in enumerate(bins):
      for (s, (shift, scale)) in enumerate(row):
        data.append((grid[t][s], shift, scale))
    data = np.array(sorted(data, key=lambda d: -d[0]))
    # limit to the bins containing 99% of the probability
    limit = max(1, np.searchsorted(np.cumsum(data[:, 0]), 0.99))
    probs, shifts, scales = data[:limit, 0], data[:limit, 1], data[:limit, 2]
    cprob = np.cumsum(probs / sum(probs))
    # get sample curves
    curves = []
    for i in range(num_samples):
      # randomly select a weighted bin
      index = np.searchsorted(cprob, np.random.random())
      # randomly select a point within the bin
      try:
        shift = shifts[index] + np.random.uniform(-d_shift, +d_shift) / 2
        scale = scales[index] + np.random.uniform(-d_scale, +d_scale) / 2
      except ex:
        print('shift/scale index out of bounds!')
        print(len(shifts), shift, d_shift)
        print(len(scales), scale, d_scale)
        raise ex
      # build the archetype curve with the selected parameters
      curves.append(self.archetype[region].instance(scale, shift, add_holiday))
    return curves, grid

  def inform(self, region, mean, var):
    # combine observations and archetype
    self.week = len(mean)
    m1 = mean
    v1 = var
    m2 = self.archetype[region].unaligned_unsmoothed_mean[self.week:]
    v2 = self.archetype[region].unaligned_unsmoothed_var[self.week:]
    self.target_mean[region] = np.hstack((m1, m2))
    #self.target_var = np.ones(len(self.target_mean)) #np.hstack((v1, v2))
    self.target_var[region] = np.hstack((v1, v2))
    self.target_std[region] = self.target_var[region] ** 0.5
    # build weight vector
    self.weights = np.ones(len(self.target_mean[region])) * 0.2
    self.weights[max(0, self.week - 5):self.week] = 1

  def forecast(self, state):
    output = []
    for (x, region) in zip(state, AF_Utils.regions):
      self.target_mean[region][self.week - 1] = x
      # TODO: variance here?
      self.target_var[region][self.week - 1] = 1e-3
      curve = self.get_best_fit(region)
      output.append(curve[self.week])
    return np.array(output)

  def measure(self, state):
    # twitter (11)
    # wiki (1)
    # uili (11)
    twitter = []
    wiki = []
    uili = []
    for (x, region) in zip(state, AF_Utils.regions):
      ili_nh = x
      ili_h = self.archetype[region].add_holiday_week(ili_nh, self.week)
      twitter.append(ili_nh)
      uili.append(ili_h)
    nat_nh = [AF_Utils.get_national(twitter)]
    nat_h = [AF_Utils.get_national(uili)]
    twitter = nat_nh + twitter
    wiki = nat_nh
    uili = nat_h + uili
    return np.array(twitter + wiki + uili)


class AF_Utils:
  """ helper for loading (and generating) data """

  regions = ['hhs%d' % i for i in range(1, 11)]

  @staticmethod
  def _get(res):
    if res['result'] != 1:
      raise Exception('API result=%d (%s)' % (res['result'], res['message']))
    return res['epidata']

  @staticmethod
  def get_season(season, location):
    #end = (season + 1) * 100 + 29
    #epiweeks = Epidata.range(flu.add_epiweeks(end, -51), end)
    begin = season * 100 + 30
    epiweeks = Epidata.range(begin, flu.add_epiweeks(begin, 51))
    rows = AF_Utils._get(Epidata.ilinet(location, epiweeks))
    return [row['wili'] for row in rows]

  @staticmethod
  def initialize_filter(x, P, Q, R, process):
    # Update system state
    fx = lambda x, dt: process.forecast(x)
    # Expected measurement, given system state
    hx = lambda x: process.measure(x)
    # Get the sigma points for the unscented transformation
    # https://github.com/rlabbe/filterpy/blob/master/filterpy/kalman/sigma_points.py
    alpha, beta, kappa = 1e-3, 2, 0
    points = SigmaPoints(n=len(x), alpha=alpha, beta=beta, kappa=kappa)
    # Instantiate an Unscented Kalman Filter
    ukf = UKF(dim_x=len(x), dim_z=len(R[0]), dt=1, hx=hx, fx=fx, points=points)
    ukf.x, ukf.P, ukf.Q, ukf.R = x, P, Q, R
    # Return filter
    return ukf

  @staticmethod
  def get_unstable_wILI(region, ew1, ew2):
    weeks = Epidata.range(ew1, ew2)
    epidata = AF_Utils._get(Epidata.fluview(region, weeks, issues=ew2))
    data = [row['wili'] for row in epidata]
    if len(data) != flu.delta_epiweeks(ew1, ew2) + 1:
      raise Exception('missing data')
    return data

  @staticmethod
  def get_national(regional):
    weights = [0.045286439944771467, 0.10177386656841922, 0.095681349146225586, 0.19610707945020625, 0.16310640558744591, 0.12488754783066998, 0.043916824425230531, 0.034124204104827027, 0.15298339758467921, 0.041244820532846248]
    return np.dot(weights, regional)

  @staticmethod
  def _signal(name, region, epiweek):
    rows = AF_Utils._get(Epidata.signals(secrets.api.signals, name, region, epiweek))
    if len(rows) != 1:
      raise Exception('expected one signal row')
    return rows[0]['value']

  @staticmethod
  def signal_twitter(region, epiweek):
    return AF_Utils._signal('twitter', region, epiweek)

  @staticmethod
  def signal_wiki(epiweek):
    return AF_Utils._signal('wiki', 'nat', epiweek)

  @staticmethod
  def signal_uili(region, epiweek):
    return AF_Utils._signal('uili', region, epiweek)


class Archefilter(Forecaster):

  # TODO: calculate backfill at runtime
  BF = {
    'nat': [0.133, 0.104, 0.071, 0.064, 0.057, 0.048, 0.041, 0.031, 0.028, 0.023],
    'hhs1': [0.173, 0.098, 0.083, 0.074, 0.066, 0.052, 0.044, 0.041, 0.036, 0.030],
    'hhs2': [0.384, 0.247, 0.179, 0.143, 0.117, 0.086, 0.064, 0.053, 0.049, 0.044],
    'hhs3': [0.268, 0.142, 0.106, 0.083, 0.072, 0.067, 0.062, 0.056, 0.052, 0.044],
    'hhs4': [0.160, 0.076, 0.051, 0.044, 0.039, 0.031, 0.030, 0.029, 0.024, 0.023],
    'hhs5': [0.159, 0.087, 0.071, 0.066, 0.061, 0.056, 0.051, 0.044, 0.037, 0.036],
    'hhs6': [0.239, 0.217, 0.096, 0.086, 0.065, 0.054, 0.053, 0.045, 0.041, 0.036],
    'hhs7': [0.255, 0.190, 0.124, 0.098, 0.072, 0.050, 0.037, 0.024, 0.023, 0.021],
    'hhs8': [0.160, 0.140, 0.130, 0.122, 0.121, 0.114, 0.110, 0.103, 0.098, 0.093],
    'hhs9': [0.679, 0.573, 0.446, 0.409, 0.378, 0.320, 0.267, 0.195, 0.170, 0.132],
    'hhs10': [0.371, 0.299, 0.250, 0.227, 0.210, 0.201, 0.188, 0.189, 0.186, 0.184],
  }

  def __init__(self, test_season, locations, num_samples):
    super().__init__('fc-archefilter', test_season, locations)
    self.archetypes = {}
    self.num_samples = num_samples

  def run(self, epiweek):
    process = FluProcess(self.archetypes)
    # timing
    ew0 = flu.join_epiweek(self.test_season, 30)
    ew1 = flu.add_epiweeks(ew0, 52)
    num_weeks = flu.delta_epiweeks(ew0, epiweek) + 1
    # setup each region
    _x, _P = [], []
    _Q = [0.5 ** 2] * 10
    _R = [0.7 ** 2] * 11 + [0.5 ** 2] + [0.5 ** 2] * 11
    for region in AF_Utils.regions:
      # get unstable ili up until now
      wili = AF_Utils.get_unstable_wILI(region, ew0, epiweek)
      if len(wili) != num_weeks:
        raise Exception('missing data')
      # remove holiday effect
      wili = np.array(wili) * self.archetypes[region].holiday[:len(wili)]
      # TODO: use an actual backfill model
      bf_var = Archefilter.BF[region][::-1]
      while len(bf_var) < len(wili):
        bf_var = [bf_var[0]] + bf_var
      while len(bf_var) > len(wili):
        bf_var = bf_var[1:]
      bf_var = np.array(bf_var)
      # setup the flu process
      process.inform(region, wili, bf_var)
      # UKF data
      _x.append(wili[-1])
      _P.append(bf_var[-1])
    # set up the UKF
    x = np.array(_x)
    P = np.diag(_P)
    Q = np.diag(_Q)
    R = np.diag(_R)
    ukf = AF_Utils.initialize_filter(x, P, Q, R, process)
    # make it happen
    print(' [AF] state:', ukf.x)
    # predict next week's wILI
    ukf.predict()
    print(' [AF] state:', ukf.x)
    # measure digitial surveillance signals
    ew = flu.add_epiweeks(epiweek, 1)
    twitter, wiki, uili = [], [], []
    for region in ['nat'] + AF_Utils.regions:
      twitter.append(AF_Utils.signal_twitter(region, ew))
      if region == 'nat':
        wiki.append(AF_Utils.signal_wiki(ew))
      uili.append(AF_Utils.signal_uili(region, ew))
    measurement = np.array(twitter + wiki + uili)
    print(' [AF] measurement:', measurement)
    ukf.update(measurement)
    print(' [AF] state:', ukf.x)
    # update the process with the latest estimate
    for (i, region) in enumerate(AF_Utils.regions + ['nat']):
      # get unstable ili up until now
      wili = AF_Utils.get_unstable_wILI(region, ew0, epiweek)
      if len(wili) != num_weeks:
        raise Exception('missing data')
      # remove holiday effect
      wili = np.array(wili) * self.archetypes[region].holiday[:len(wili)]
      # TODO: use an actual backfill model
      bf_var = Archefilter.BF[region][::-1]
      while len(bf_var) < len(wili):
        bf_var = [bf_var[0]] + bf_var
      while len(bf_var) > len(wili):
        bf_var = bf_var[1:]
      bf_var = np.array(bf_var)
      # add in the filter state
      if region == 'nat':
        national = AF_Utils.get_national(ukf.x)
        # TODO: what is national variance?
        x = np.mean(np.diag(ukf.P))
        est_mean = np.hstack((wili, np.array([national])))
        est_var = np.hstack((bf_var, np.array([x])))
      else:
        est_mean = np.hstack((wili, np.array([ukf.x[i]])))
        est_var = np.hstack((bf_var, np.array([ukf.P[i][i]])))
      process.inform(region, est_mean, est_var)
    self.process = process

  def _train(self, region):
    # get the data and build the archetype
    train_seasons = [season for season in range(2004, self.test_season) if season not in (2008, 2009)]
    curves = [AF_Utils.get_season(season, region) for season in train_seasons]
    self.archetypes[region] = Archetype(curves, baseline=0)

  def _forecast(self, region, epiweek):
    if region == 'nat':
      self.run(epiweek)
    # use the process for each region to get sample curves
    curves, grid = self.process.get_sample_fits(region, self.num_samples, True)
    #if region == 'nat':
    #  import pylab as plt
    #  for c in curves[:25]:
    #    plt.plot(c, color='#888888', linewidth=1)
    #  ew0 = flu.join_epiweek(self.test_season, 30)
    #  wili = AF_Utils.get_unstable_wILI(region, ew0, epiweek)
    #  plt.plot(wili, color='#000000', linewidth=2)
    #  plt.show()
    #raise Exception()
    return [curve[10:43] for curve in curves]
