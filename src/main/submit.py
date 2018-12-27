"""
***************
*** WARNING ***
***************

This program will potentially:
 - Email CDC and the Delphi team!
 - Update the Epicast round counter!
 - Upload forecast data to FluSight!


===============
=== Purpose ===
===============

Handles everything for our Epicast and Archefilter submissions to CDC's
Flu Contest. This entails:
  1. Generation (see submissions.py)
  2. Sanity checking (see forecast_io.py and submissions.py)
  3. Storing in our database (see submission_loader.py)
  4. Generating plots (see plot_forecast.py)
  5. Emailing to CDC and Delphi (see emailer.py)
  6. Uploading to FluSight (see flusight.py)
  7. Incrementing the round counter (Epicast only)

If running as a script (i.e. not calling from another program), the default
behavior is to:
  1. Generate forecasts for both systems
  2. Sanity check forecasts
  3. Don't touch the database
  4. Don't generate plots
  5. Don't email anyone
  6. Don't upload to FluSight
  7. Don't modify Epicast's round
Storing, emailing, and uploading must be confirmed at run-time by setting their
respective command-line flags.


=================
=== Changelog ===
=================

2016-12-12
  * update metadata tag
2016-12-07
  + embed metadata tag in forecasts
  * use secrets for epicast round update
2016-12-05
  + upload to FluSight via flusight.py
  * use secrets for upload
  * deprecated `ecround`
2016-11-29
  * update probability floors for 2016 flu contest bin sizes
2016-10-27
  * updated email wording
  * use current working directory instead of hardcoded string
2016-01-06
  + generate plots
2015-12-15
  + test mode
  - path prefix for forecast files
2015-12-14
  * original version (loosely based on last year's fluv_submission.py)
"""

# standard library
import argparse
import mimetypes
import os
import time

# third party
import mysql.connector

# first party
from .submissions import Submissions
from .submissions_hosp import Submissions_Hosp
from ..utils import flusight
from ..utils.forecast import Forecast
from ..utils.forecast_io import ForecastIO
from ..utils import forecast_tagger
from ..utils.plot_forecast import Plotter
from ..utils.submission_loader import load_submission
from delphi.epidata.client.delphi_epidata import Epidata
import delphi.operations.emailer as emailer
import delphi.operations.secrets as secrets
from delphi.utils.epidate import EpiDate
import delphi.utils.epiweek as flu


regions = ['nat'] + ['hhs%d' % i for i in range(1, 11)]
af_locations = regions
ec_locations = regions + ['dc', 'ga', 'ca']


def get_expected_issue():
  # two weeks before the current week
  return EpiDate.today().add_weeks(-2).get_ew()


def get_most_recent_issue():
  # search for FluView issues within the last 10 weeks
  ew2 = EpiDate.today().get_ew()
  ew1 = flu.add_epiweeks(ew2, -9)
  res = Epidata.fluview('nat', Epidata.range(ew1, ew2))
  if res['result'] != 1:
    raise Exception('API result=%d (%s)' % (res['result'], res['message']))
  return max([row['issue'] for row in res['epidata']])


def submit(plotdir, run_ec, run_af, insane, epiweek, do_store, do_email, do_upload, update_round, test_mode):
  if not run_ec and not run_af:
    raise Exception('either EC or AF is required')
  if not do_store and do_email:
    raise Exception('`do_email` requires `do_store`')
  if not do_store and do_upload:
    raise Exception('`do_upload` requires `do_store`')
  if not run_ec and update_round:
    raise Exception('`update_round` requires `run_ec`')

  # 1a: generate forecast(s)
  ec, af = None, None
  if test_mode:
    num_samples = 100
  else:
    num_samples = 10000
  print('generating forecasts with %d samples' % num_samples)
  ili_bin_width, week_bin_width = 0.1, 1.0
  ili_floor, week_floor = 0.001 * (ili_bin_width / 0.5), 0.001 * (week_bin_width / 1.0)
  print('with ILI-bin-width of %f, probability floor is %f' % (ili_bin_width, ili_floor))
  print('with week-bin-width of %f, probability floor is %f' % (week_bin_width, week_floor))
  if run_ec:
    sub = Submissions(ec_locations, num_samples)
    ec = sub.run_epicast(epiweek, ili_floor, week_floor)
    print('EC = %s' % ec)
  if run_af:
    sub = Submissions(af_locations, num_samples)
    af = sub.run_archefilter(epiweek, ili_floor, week_floor, num_samples=num_samples)
    print('AF = %s' % af)

  # 1b: split into regional and state forecasts
  def split(filename):
    fc_reg, fc_sta = Forecast.split(ForecastIO.load_csv(filename))
    fc_reg.team += '-regional'
    fc_sta.team += '-state'
    return ForecastIO.save_csv(fc_reg), ForecastIO.save_csv(fc_sta)
  if run_ec:
    ec_reg, ec_sta = split(ec)
  if run_af:
    af_reg, af_sta = split(af)

  # TODO: make forecast_tagger work with new forecast class
  # # 1c: embed metadata
  # def embed_metadata(name, tag):
  #   fc1 = ForecastIO.load_csv(name)
  #   fc2 = ForecastIO.load_csv(name)
  #   forecast_tagger.write_tag_str(fc2, tag)
  #   if not fc1.equals(fc2):
  #     raise Exception('metadata tag meaningfully changed forecast')
  #   ForecastIO.save_csv(fc2, filename=name)
  # tag = 'delphi submit.py %d' % round(time.time())
  # if run_ec:
  #   embed_metadata(ec, tag)
  # if run_af:
  #   embed_metadata(af, tag)

  # 2: sanity check
  if not insane:
    if run_ec:
      ForecastIO.load_csv(ec).sanity_check()
      ForecastIO.load_csv(ec_reg).sanity_check()
      ForecastIO.load_csv(ec_sta).sanity_check()
      print('EC passed sanity check')
    if run_af:
      ForecastIO.load_csv(af).sanity_check()
      ForecastIO.load_csv(af_reg).sanity_check()
      ForecastIO.load_csv(af_sta).sanity_check()
      print('AF passed sanity check')

  # 3: store to database
  if do_store:
    # store only the combined forecast, not the regional/state splits
    if run_ec:
      load_submission(ec, insane=insane, test=test_mode, verbose=True)
    if run_af:
      load_submission(af, insane=insane, test=test_mode, verbose=True)

  # 4: generate plots
  if plotdir is not None:
    print('generating plots...')
    # load the forecasts (combined only)
    systems = []
    if run_ec:
      systems.append((ForecastIO.load_csv(ec), 'ec', '#960018'))
    if run_af:
      systems.append((ForecastIO.load_csv(af), 'af', '#c04000'))
    # plot the forecast
    week = 'EW%02d' % flu.split_epiweek(epiweek)[1]
    Plotter.plot(systems, os.path.join(plotdir, 'fc'), week)

  # 5: email CDC and Delphi
  if do_email:
    # setup
    mimetypes.init()
    date = str(EpiDate.today())
    yr, ew = flu.split_epiweek(epiweek)

    # wording
    systems, names, attachments = [], [], []
    path = os.getcwd()
    if run_ec:
      systems.append('EW%02d-delphi-epicast-%s' % (ew, date))
      names.append('Epicast (delphi-epicast)')
      ec_reg_path = os.path.join(path, ec_reg)
      ec_sta_path = os.path.join(path, ec_sta)
      attachments.append([(ec_reg_path, mimetypes.types_map['.csv'])])
      attachments.append([(ec_sta_path, mimetypes.types_map['.csv'])])
    if run_af:
      systems.append('EW%02d-delphi-archefilter-%s' % (ew, date))
      names.append('Archefilter (delphi-archefilter)')
      af_reg_path = os.path.join(path, af_reg)
      af_sta_path = os.path.join(path, af_sta)
      attachments.append([(af_reg_path, mimetypes.types_map['.csv'])])
      attachments.append([(af_sta_path, mimetypes.types_map['.csv'])])
    system_string = ' + '.join(systems)
    name_string = ' and '.join(names)
    plural = 's' if len(systems) > 1 else ''

    # email fields
    to = secrets.flucontest.email_cdc
    cc = [secrets.flucontest.email_delphi, secrets.flucontest.email_maintainer]
    subject = '[Flu Contest Submission] %s' % (' + '.join(systems))
    body = '''Dear CDC,

Thank you for hosting the collaborative comparison of forecasts for the current flu season. Please find attached the %04dw%02d (%s) forecast%s for the %s forecasting framework%s.

Best wishes,
The Delphi Group at Carnegie Mellon University
https://delphi.midas.cs.cmu.edu/
''' % (yr, ew, date, plural, name_string, plural)
    html = '''
<html><body>
<script type="application/ld+json">{
  "@context": "http://schema.org",
  "@type": "EmailMessage",
  "potentialAction": {
    "@type": "ViewAction",
    "target": "https://delphi.midas.cs.cmu.edu/~automation/public/forecast_plots/",
    "url": "https://delphi.midas.cs.cmu.edu/~automation/public/forecast_plots/",
    "name": "Preview"
  },
  "description": "View the most recent Epicast forecasts."
}</script>
%s
</body></html>
''' % body.replace("\n", "<br>")

    # send the email
    if test_mode:
      # just testing, don't email anyone else
      to = secrets.flucontest.email_maintainer
      cc = None
    emailer.queue_email(to=to, subject=subject, text=body, html=html, cc=cc, attachments=attachments)
    emailer.call_emailer()
    print('queued submission email')

  # 6: upload to FluSight
  if do_upload:
    if test_mode:
      print('testing - skipping upload')
    else:
      email, password = secrets.flucontest.flusight
      # TODO: this needs to be implemented for 2017
      raise NotImplementedError()
      #if run_ec:
      #  flusight.submit(email, password, ec_reg)
      #  flusight.submit(email, password, ec_sta)
      #if run_af:
      #  flusight.submit(email, password, af_reg)
      #  flusight.submit(email, password, af_sta)
      print('uploaded forecast(s) to FluSight')

  # 7: update epicast round
  if update_round:
    # connect
    u, p = secrets.db.epi
    cnx = mysql.connector.connect(user=u, password=p, database='automation')
    cur = cnx.cursor()
    # queue the round update
    if test_mode:
      print('testing - skipping Epicast round update')
    else:
      cur.execute('CALL RunStep(12)')
      print('queued Epicast round update')
    # disconnect
    cur.close()
    cnx.commit()
    cnx.close()

  print('done!')


if __name__ == '__main__':
  # args and usage
  parser = argparse.ArgumentParser()
  parser.add_argument('--plotdir', default=None, type=str, action='store', help='generate and store plots in this directory')
  parser.add_argument('--onlyec', default=False, action='store_true', help='Epicast only')
  parser.add_argument('--onlyaf', default=False, action='store_true', help='Archefilter only')
  parser.add_argument('--insane', default=False, action='store_true', help='skip sanity check and ignore errors')
  parser.add_argument('--epiweek', default=None, type=int, help='epiweek override')
  parser.add_argument('--store', default=False, action='store_true', help='(over)write forecast to database')
  parser.add_argument('--email', default=False, action='store_true', help='send forecast(s) to CDC and Delphi (requires --store)')
  parser.add_argument('--upload', default=False, action='store_true', help='upload forecast(s) to CDC FluSight (requires --store)')
  parser.add_argument('--ecround', default=False, action='store_true', help='deprecated (see fluv_updater.py). update the epicast round counter (requires no --onlyaf)')
  parser.add_argument('--test', default=False, action='store_true', help='very small sample size, store without commit, only email myself, skip EC round update')
  args = parser.parse_args()

  # epiweeks and timing
  week1 = get_expected_issue()
  week2 = get_most_recent_issue()
  if week1 != week2:
    print('warning: based on the date, epiweek should be %d, but according to the API it is %d' % (week1, week2))

  # check args
  if args.onlyec and args.onlyaf:
    raise Exception('at least one of Epicast and Archefilter is required')
  if args.onlyec:
    print('only generating submission for Epicast')
  if args.onlyaf:
    print('only generating submission for Archefilter')
  if args.insane:
    print('warning: skipping sanity checks')
  if args.epiweek is None:
    epiweek = week2
    print('no epiweek specified, assuming %d' % epiweek)
  else:
    epiweek = args.epiweek
    print('should be epiweek %d, but using %d instead' % (week2, epiweek))
  if args.email and not args.store:
    raise Exception('--store is required to use --email')
  if args.upload and not args.store:
    raise Exception('--store is required to use --upload')
  if args.plotdir is not None:
    print('will generate plots at [%s]' % args.plotdir)
  else:
    print('will NOT generate plots')
  if args.store:
    print('will store to database')
  else:
    print('will NOT store to database')
  if args.email:
    print('will email to CDC+Delphi')
  else:
    print('will NOT email to CDC+Delphi')
  if args.upload:
    print('will upload to CDC FluSight')
  else:
    print('will NOT upload to CDC FluSight')
  if args.ecround and args.onlyaf:
    raise Exception('must generate Epicast submission to update Epicast round')
  if args.ecround:
    print('will update Epicast round')
    # Epicast's round is set by fluv_updater.py in automation flow #4 step #12
    raise Exception('deprecated')
  else:
    print('will NOT update Epicast round')
  if args.test:
    print('*** running in test mode ***')

  # one last check for epiweek
  flu.check_epiweek(epiweek)

  # one last chance to back out...
  if (args.store or args.email or args.upload or args.ecround) and not args.test:
    print('starting in 5 seconds (ctrl+c now if the above is wrong!)')
    time.sleep(5)

  # make it happen
  submit(args.plotdir, not args.onlyaf, not args.onlyec, args.insane, epiweek, args.store, args.email, args.upload, args.ecround, args.test)

  # hospitalization
  epiweek = EpiDate.today().add_weeks(-1).get_ew()
  ec_age_groups = ['rate_overall', 'rate_age_0', 'rate_age_1', 'rate_age_2', 'rate_age_3', 'rate_age_4']
  sub_hosp = Submissions_Hosp(ec_age_groups, 1000)
  ec_hosp = None
  # ec_hosp = sub_hosp.run_epicast(epiweek, 0.001, 0.001)
  ec_hosp = sub_hosp.run_epicast(epiweek, 0.001, 0.13/600)
  print('Finished! Files are:')
  print(' -', ec_hosp)
