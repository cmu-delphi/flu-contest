"""An implemention of the Epicast methodology applied to COVID-19."""

# standard library
import statistics

# third party
import numpy as np
import scipy.stats

# first party
from delphi.epidata.client.delphi_epidata import Epidata
import delphi.flu_contest.covid.constants as Constants
from delphi.flu_contest.covid.targets import Targets


class EpicastCore:

  @staticmethod
  def forecast(epiweek, user_predictions, location_code):
    # get actual wILI from the epidata API
    # to enable honest retrospective re-runs of this program, fetch the version
    # of wILI that was available at the time the forecast was originally made
    resp = Epidata.fluview(
        [location_code],
        Epidata.range(202010, Constants.MAX_EPIWEEK),
        issues=epiweek)
    if resp['result'] != 1:
     raise Exception(resp['message'])
    values = [(row['epiweek'], row['wili']) for row in resp['epidata']]
    wili = [w for (_, w) in sorted(values)]
    print('wili for %s: ' % location_code, wili)

    # assume independent noise across weeks, locations, etc
    # assume wili is stable after 5 weeks
    # assume stdev is like 1, 1/2, ..., 1/(2^n) with age
    backfill_stdev = [0.5 ** i for i in range(5)]

    # start with wili, inject noise, splice with user prediction, repeat
    samples = []
    for prediction in user_predictions[location_code].values():
      for _ in range(Constants.BACKFILL_MODEL_NUM_SAMPLES):

        # copy of wili
        curve = wili[:]

        # add noise for recent (unstable) wili
        start = len(curve) - 1
        num = min(len(wili), len(backfill_stdev))
        for i, j in enumerate(range(start, start - num, -1)):
          curve[j] += np.random.normal(scale=backfill_stdev[i])

        # append current user's prediction
        curve += [wili for (week, wili) in prediction]

        if len(curve) != 31:
          raise Exception('curve should be 31 weeks, but is %d' % len(curve))

        # stash this sample and maybe do it again
        samples.append(curve)

    current_week = len(wili) - 1
    baseline = Constants.BASELINES.get(location_code, None)
    is_region = baseline is not None

    target_values = {
      'peak_week': [],
      'peak_wili': [],
      '1wk_wili': [],
      '2wk_wili': [],
      '3wk_wili': [],
      '4wk_wili': [],
      '5wk_wili': [],
      '6wk_wili': [],
      'offset_week': [],
      'offset_happened': [],
    }
    for sample in samples:

      target_values['peak_week'].append(Targets.get_peak_week(sample))
      target_values['peak_wili'].append(Targets.get_peak_wili(sample))
      for n in range(1, 7):
        n_week_wili = Targets.get_n_week_wili(sample, current_week, n)
        target_values['%dwk_wili' % n].append(n_week_wili)

      if is_region:
        offset_week = Targets.get_offset_week(sample, baseline)
        if offset_week is None:
          # no offset
          target_values['offset_happened'].append(0)
        else:
          # offset happened
          target_values['offset_happened'].append(1)
          target_values['offset_week'].append(offset_week)

    forecasts = {
      'dists': {},
      'points': {},
    }
    for target in Constants.COMMON_TARGETS:
      point, t_dist = EpicastCore.get_forecast_point_and_dist(
          target, target_values)

      forecasts['points'][target] = point
      forecasts['dists'][target] = t_dist

    if is_region:
      if not target_values['offset_week']:
        # need a point prediction, but there are no values in the array
        # welp, no one thinks the pandemic will end... need to handle this case
        # idea: what about picking the last possible week?
        raise Exception('no offsets, forecast is undefined')

      point, t_dist = EpicastCore.get_forecast_point_and_dist(
          'offset_week', target_values)

      forecasts['points']['offset_week'] = point
      forecasts['dists']['offset_week'] = t_dist

      # 2-bin distribution (yes/no), with only this single bin appearing in the
      # output file (see template)
      # dont' worry, we'll make sure this isn't zero (same for other targets
      # and their distributions) later on
      values = target_values['offset_happened']
      forecasts['dists']['offset_happened'] = np.mean(values)

    print('forecast created for', location_code)
    return forecasts

  @staticmethod
  def get_forecast_point_and_dist(target, target_values):
    values = target_values[target]

    if target.endswith('week'):
      # discrete value (i.e. no fractional weeks)
      point = statistics.median_low(values)
    else:
      # continuous value (i.e. wili)
      point = statistics.median(values)

    t_dist_df = len(values)
    t_dist_loc = statistics.median(values)
    t_dist_scale = np.std(values)

    # lower bound on scale in case there is just a single value, or for the
    # otherwise rare case where all values are equal
    if target.endswith('week'):
      # stdev of one week
      t_dist_scale = max(t_dist_scale, 1)
    else:
      # stdev of 0.2 wili
      t_dist_scale = max(t_dist_scale, 0.2)

    # t-dist centered on (actual, continuous) median, with empirical stdev and
    # degrees of freedom equal to number of user values
    # df may be smaller than number of users, e.g. because some users may not
    # predict that offset will ever happen and so there are fewer offset week
    # values than users
    t_dist = scipy.stats.t(df=t_dist_df, loc=t_dist_loc, scale=t_dist_scale)

    return point, t_dist

  @staticmethod
  def materialize_bins(forecasts):
    # make an array of floats that represents the "true" distribution
    # raise the prob floor (never say never...), normalize, and sanity check

    uniform_weight = Constants.UNIFORM_WEIGHT
    if not (0 < uniform_weight < 1):
      raise Exception('UNIFORM_WEIGHT must be in [0, 1]')

    if uniform_weight == 0:
      raise Exception('strongly advised to reconsider UNIFORM_WEIGHT')

    for location in forecasts.keys():
      forecasts[location]['bins'] = {}
      for target in forecasts[location]['dists'].keys():
        t_dist = forecasts[location]['dists'][target]

        if target == 'offset_happened':
          # special case, this is a 2-bin distribution with just one of the
          # bins output in the CSV
          prob_offset = t_dist
          if not isinstance(prob_offset, float):
            raise Exception('expected float for prob of offset happening')
          if not (0 <= prob_offset <= 1):
            raise Exception('prob of offset happening is not sane')
          # not too small, not too large...
          prob_offset = min(prob_offset, 1 - uniform_weight / 2)
          prob_offset = max(prob_offset, uniform_weight / 2)
          forecasts[location]['bins'][target] = prob_offset
          continue

        # all other targets get normal bins for the distribution
        bins = []

        if target.endswith('week'):
          # week target, bins over 2020w10--2020w35
          for i in range(26):
            # bin is "centered" on index (i.e. 2020w10 is noon Weds, 2020w09.5
            # is midnight Sun AM, and so on)
            lower, upper = i - 0.5, i + 0.5
            bins.append(t_dist.cdf(upper) - t_dist.cdf(lower))
        else:
          # wili target, bins over [0, 100]
          for i in range(250):
            lower, upper = i / 10, (i + 1) / 10
            bins.append(t_dist.cdf(upper) - t_dist.cdf(lower))
          # special [25, 100] bin
          lower, upper = 25, 100
          bins.append(t_dist.cdf(upper) - t_dist.cdf(lower))

        # normalize (tails were clipped)
        bins = np.array(bins)
        bins /= np.sum(bins)

        # blend with uniform to prevent zero-probability for any event
        if target.endswith('week'):
          unif_bin_value = 1 / len(bins)
          bins = bins * (1 - uniform_weight) + unif_bin_value * uniform_weight
        else:
          # the last, giant bin spans a whopping 75 ILI. it needs more
          # influence from uniform than the other bins.
          unif_bins = np.ones(251)
          # add in enough weight to uniformly cover another 50 bins (i.e. as if
          # forecasting over [0, 30] instead of [0, 25]).
          unif_bins[-1] += 49
          unif_bins /= np.sum(unif_bins)
          bins = bins * (1 - uniform_weight) + unif_bins * uniform_weight

        # last sanity checks
        if not np.allclose(np.sum(bins), 1):
          raise Exception('uniform blending is broken')
        if min(bins) < 1e-5:
          raise Exception('prob is very small, consider blending more')

        forecasts[location]['bins'][target] = list(bins)
