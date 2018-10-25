"""
===============
=== Purpose ===
===============

Plots CDC flu contest forecasts.


=================
=== Changelog ===
=================

2016-11-07
  * handle floating point week point predictions
2016-10-27
  * updated for 2016 flu contest
2016-01-06
  + Modularized for programmatic access (class Plotter)
  + Optional label (i.e. epiweek) in figure title
2015-11-10
  * Hardcoded to compare our three 2015 systems
2015-11-09
  + First version (inspired by fluv_submission_check.py)
"""

# standard library
import argparse

# third party
import pylab as plt

# first party
from delphi.flu_contest.utils.forecast_io import ForecastIO
from delphi.epidata.client.delphi_epidata import Epidata
import delphi.utils.epiweek as flu


class Plotter:

  @staticmethod
  def get_unstable_wILI(region, ew0, ew1):
    res = Epidata.fluview(region, Epidata.range(ew0, ew1), issues=ew1)
    if res['result'] != 1:
      raise Exception('Epidata API: [%d] %s' % (res['result'], res['message']))
    return [row['wili'] for row in res['epidata']]

  @staticmethod
  def weekly_subplot(forecasts, region, axes, main_plot, onset):
    y_ticks = [i / 5 for i in range(6)]
    axes.set_autoscale_on(False)
    axes.set_xbound(0, 33)
    axes.set_ybound(0, 1)
    axes.set_xticks([])
    axes.set_yticks(y_ticks)
    offset = -(len(forecasts) // 2) / 5
    for (forecast, label, color) in forecasts:
      fc = forecast.get_forecast(region)
      if onset:
        if not fc.has_onset():
          continue
        data = fc.get_onset()
      else:
        data = fc.get_peakweek()
      point = ForecastIO.get_week_index(int(data['point'])) + data['point'] - int(data['point'])
      point += offset
      offset += 1 / 5
      axes.axvline(point, color=color)
      main_plot.axvline(point, color=color)
      plt.plot(data['dist'], color=color, linewidth=2)
    return axes

  @staticmethod
  def wili_subplot(forecasts, region, axes, main_plot, bin_size):
    x_ticks = [i / 5 for i in range(6)]
    axes.set_autoscale_on(False)
    axes.set_xbound(0, 1)
    axes.set_ybound(0, 12)
    axes.set_xticks(x_ticks)
    axes.set_yticks([])
    for (forecast, label, color) in forecasts:
      fc = forecast.get_forecast(region)
      data = fc.get_peak()
      point = data['point']
      axes.axhline(point, color=color)
      main_plot.axhline(point, color=color)
      plt.plot([x for x in data['dist']], [(i + 1) * bin_size for i in range(len(data['dist']))], color=color, linewidth=2)
    return axes

  @staticmethod
  def plot(forecasts, prefix, fig_label=''):
    # timing
    epiweek = forecasts[0][0].epiweek
    ew0, ew1 = flu.get_season(epiweek)
    num_weeks = flu.delta_epiweeks(ew0, ew1) + 1
    year = flu.split_epiweek(ew0)[0]

    # plot settings
    x_ticks = [i for i in range(0, num_weeks, 3)]
    x_tick_labels = ['%02d' % ForecastIO.get_index_week(i) for i in x_ticks]
    y_ticks = [i for i in range(0, 14, 2)]
    regions = ['nat'] + ['hhs%s' % i for i in range(1, 11)]

    # TODO: avoid hardcoding these values everywhere
    baseline_values_2018 = [
      2.2, 1.8, 3.1, 2.0, 2.2, 1.8, 4.0, 1.6, 2.2, 2.3, 1.1
    ]
    baselines = dict((r, v) for (r, v) in zip(regions, baseline_values_2018))
    bin_size = forecasts[0][0].ili_bin_size

    # get the somewhat sorted list of all unique locations
    locations = []
    for info in forecasts:
      fc = info[0]
      for loc in fc.get_locations():
        if loc not in locations:
          locations.append(loc)

    # plot each region
    for region in locations:

      # only consider forecasts that include this location
      region_forecasts = []
      for info in forecasts:
        if info[0].has_forecast(region):
          region_forecasts.append(info)

      # center subplot
      plt.figure(figsize=(12, 12))
      ax2 = plt.subplot(3, 2, 3)
      if region in baselines:
        plt.axhline(baselines[region], color='#888888')
      weeks = [i for i in range(flu.delta_epiweeks(ew0, epiweek) + 1)]
      values = Plotter.get_unstable_wILI(region, ew0, epiweek)
      plt.plot(weeks, values, color='#000000', linewidth=2)
      weeks = [flu.delta_epiweeks(ew0, epiweek) + i for i in range(1, 5)]
      for (forecast, label, color) in region_forecasts:
        fc = forecast.get_forecast(region)
        values = [fc.get_lookahead(i)['point'] for i in range(1, 5)]
        plt.plot(weeks, values, color=color, linewidth=2)
      ax2.set_xbound(0, 33)
      ax2.set_ybound(0, 12)
      ax2.set_xticks(x_ticks)
      ax2.set_yticks(y_ticks)
      ax2.set_xticklabels(x_tick_labels)
      ax2.get_xaxis().set_tick_params(labelbottom='on', labeltop='on')
      ax2.get_yaxis().set_tick_params(labelleft='on', labelright='on')

      # top subplot: peakweek
      top = Plotter.weekly_subplot(region_forecasts, region, plt.subplot(3, 2, 1), ax2, False)

      # bottom subplot: onset
      bottom = Plotter.weekly_subplot(region_forecasts, region, plt.subplot(3, 2, 5), ax2, True)

      # right subplot: peakheight
      right = Plotter.wili_subplot(region_forecasts, region, plt.subplot(3, 2, 4), ax2, bin_size)

      # top-right subplot: legend
      leg = plt.subplot(3, 2, 2)
      for (forecast, label, color) in forecasts:
        plt.plot([0], [0], color=color, label=label)
      plt.legend(loc='lower left')

      # other stuff
      top.set_ylabel('Pr(Peak Week)')
      top.get_yaxis().set_label_position('right')
      bottom.set_ylabel('Pr(Onset Week)')
      bottom.get_yaxis().set_label_position('right')
      right.set_xlabel('Pr(Peak Height)')
      right.get_xaxis().set_label_position('top')
      ax2.set_ylabel('%s %s' % (fig_label, region.upper()))
      ax2.get_yaxis().set_label_position('left')

      # show the finished figure
      if prefix is None:
        plt.show()
        break
      else:
        filename = '%s_%s.png' % (prefix, region)
        plt.savefig(filename, bbox_inches='tight')
        print('saved %s' % filename)


def get_argument_parser():
  """Set up command line arguments and usage."""
  parser = argparse.ArgumentParser()
  parser.add_argument('-o', '--output', action='store', help='save figures with this prefix')
  parser.add_argument('file', action='store', help='the forecast file')
  parser.add_argument('file2', action='store', help='the forecast file')
  return parser


def main():
  """Run this script from the command line."""

  # args and usage
  args = get_argument_parser().parse_args()

  # load the forecast
  systems = []
  systems.append((ForecastIO.load_csv(args.file), 'ec', '#e00000'))
  systems.append((ForecastIO.load_csv(args.file2), 'st', '#0000e0'))

  # plot the forecast
  Plotter.plot(systems, args.output)


if __name__ == '__main__':
  main()
