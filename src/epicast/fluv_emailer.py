"""
===============
=== Purpose ===
===============

Sends emails to Epicast-FLUV users:
  `alerts`: custom, one-time `notifications`-type email for a manual user group
  `notifications`: for all users, says that the CDC published new data
  `reminders`: for users with missing forecasts, a reminder that the deadline
    is soon

Individual user preferences are respected; it won't email people who don't want
to be emailed.


=================
=== Changelog ===
=================

2016-12-14
  + use secrets
2016-01-08
  * Further reverted "notifications" for normal schedule
2016-01-07
  * Reverted "notifications" for normal schedule
2015-12-21
  + Use database to get name of day of upcoming deadline
  * Changed "notifications" for the late release of 2015w50/51
2015-11-30
  * Changed and reverted "notifications" for the late release of 2015w46
2015-11-13
  * Only include score info in "notifications" if score is positive
2015-11-06
  * Updated "alerts" to ask last year's users to join again this year
2015-10-30
  * Updated documentation
  * Use database `epicast2`
  * Updated all scripts to use ET instead of EDT
  * Changed the "alerts" script to be a delphi-only notification for 2015w42
  - Unused `receipts` message type
2015-03-20
  * Updated all scripts to use EDT instead of EST
2015-01-09
  * Changed the "alerts" script for the erroneous deadline notification of 2014w53
  * Reverted the "notifications" script to the normal Monday deadline
2015-01-05
  * Changed the "notifications" script for the late release of 2014w52
2015-01-03
  * Changed the "alerts" script for the late release of 2014w52
2014-12-30
  * Changed the "alerts" script for the late release of 2014w51
2014-11-??
  * Original version
"""

# standard library
import argparse
import base64
import json

# third party
import mysql.connector

# first party
import delphi.operations.emailer as emailer
import delphi.operations.secrets as secrets


#Args and usage
parser = argparse.ArgumentParser()
parser.add_argument('-v', '--verbose', action='store_const', const=True, default=False, help="show extra output")
parser.add_argument('-t', '--test', action='store_const', const=True, default=False, help="only email myself")
parser.add_argument('-p', '--print', action='store_const', const=True, default=False, help="print email to stdout, don't send")
parser.add_argument('-f', '--force', action='store_const', const=True, default=False, help="force match on myself")
parser.add_argument('type', choices=['alerts', 'notifications', 'reminders'], help="email type")
args = parser.parse_args()

#Execute and print SQL
def execute_sql(cur, sql):
  print(sql)
  cur.execute(sql)

#Get all users having some preference
def get_users(cur, name, value):
  sql = "SELECT u.`hash`, u.`name`, u.`email` FROM ec_fluv_defaults d JOIN ec_fluv_users u ON TRUE LEFT JOIN ec_fluv_user_preferences p ON p.`user_id` = u.`id` AND p.`name` = d.`name` WHERE d.`name` = '%s' AND coalesce(p.`value`, d.`value`) = '%s'"%(name, value)
  execute_sql(cur, sql)
  users = []
  for (hash, name, email) in cur:
    users.append((hash[0:8], name, email))
  return set(users)

#Get user score info
def get_scores(cur, user):
  sql = "SELECT coalesce(x.`total`, 0) `total`, coalesce(sum(CASE WHEN s.`total` >= x.`total` THEN 1 ELSE 0 END), (SELECT count(1) FROM ec_fluv_scores)) `total_rank`, coalesce(x.`last`, 0) `last`, coalesce(sum(CASE WHEN s.`last` >= x.`last` THEN 1 ELSE 0 END), (SELECT count(1) FROM ec_fluv_scores)) `last_score` FROM ec_fluv_scores s JOIN (SELECT s.`total`, s.`last` FROM ec_fluv_users u JOIN ec_fluv_scores s ON s.`user_id` = u.`id` WHERE u.`hash` LIKE '%s%%') x ON TRUE"%(user[0])
  execute_sql(cur, sql)
  for (total, total_rank, last, last_rank) in cur:
    pass
  return (int(last), last_rank, int(total), total_rank)

#Get user forecast info
def already_submitted(cur, user):
  defaultNumRegion = 16
  sql = "SELECT count(1) FROM ec_fluv_users u JOIN ec_fluv_submissions s ON s.`user_id` = u.`id` WHERE u.`hash` LIKE '%s%%' AND s.`epiweek_now` = (SELECT max(epiweek) FROM epidata.fluview)"%(user[0])
  execute_sql(cur, sql)
  num = 0
  for (num,) in cur:
    pass
  return num >= defaultNumRegion

#Get deadline day's name
def get_deadline_day_name(cur):
  sql = "SELECT dayname(`deadline`) FROM ec_fluv_round"
  execute_sql(cur, sql)
  name = None
  for (name,) in cur:
    pass
  if name is None:
    raise Exception('couldnt get name of deadline day')
  return name

if __name__ == '__main__':
  #Verbosity-dependent print
  _print = print
  def print(str, force=False):
    if force or args.verbose:
      _print(str)

  #DB connection
  print('Connecting to the database')
  u, p = secrets.db.epi
  cnx = mysql.connector.connect(user=u, password=p, database='epicast2')
  cur = cnx.cursor()
  print('Connected successfully')

  #Get deadline
  deadline_day = get_deadline_day_name(cur)
  print('deadline is this coming %s' % deadline_day)

  #Build the list of recipients
  email_type = args.type
  if email_type == 'alerts':
    email_type = 'notifications'
  users = get_users(cur, 'email_%s' % (email_type), '1') - get_users(cur, '_debug', '1')
  print('%d users selected to receive email %s' % (len(users), args.type), True)
  if args.type == 'alerts':
    #users = users - get_users(cur, '_delphi', '0')
    #print('%d of them are delphi members' % (len(users)), True)
    print('everyone in ec_fluv_users gets invited')
  if args.type == 'reminders':
    temp = []
    for u in users:
      if not already_submitted(cur, u):
        temp.append(u)
    users = set(temp)
    print('%d of them need to be reminded' % (len(users)), True)
  if args.test:
    users = set([u for u in users if u[0] == secrets.flucontest.debug_userid])
    print('test mode - users filtered to %d' % (len(users)), True)
  if args.force:
    users = set([u for u in users if u[0] != secrets.flucontest.debug_userid]) | set([(secrets.flucontest.debug_userid, 'Debug User', secrets.flucontest.email_maintainer)])
    print('force mode - users filtered to %d' % (len(users)), True)

  #Send the emails
  for u in users:
    s = get_scores(cur, u)
    score_text = ''
    score_html = ''
    if s[0] > 0:
      score_text = '''
Your forecast last week received a score of: %d (ranked #%d)

Your overall score is: %d (ranked #%d)

Note: To be listed on the leaderboards, simply enter your initials on the preferences page at http://epicast.org/preferences.php

You can find the leaderboards at http://epicast.org/scores.php
''' % (s[0], s[1], s[2], s[3])
      score_html = '''
<p>
  Your forecast last week received a score of: %d (<i>ranked #%d</i>)
  <br />
  Your overall score is: %d (<i>ranked #%d</i>)
  <br />
  Note: To be listed on the <a href="http://epicast.org/scores.php">leaderboards</a>, simply enter your initials on the preferences page <a href="http://epicast.org/preferences.php?user=%s">here</a>.
</p>
      ''' % (s[0], s[1], s[2], s[3], u[0])
    #Email contents
    emails = {
################################################################################
# ALERTS                                                                       #
################################################################################
      'alerts': {
        'subject': 'Epicast Needs Your Help',
        'text': '''Dear %s...'''%(u[1]),
        'html': '''Dear %s...'''%(u[1]),
      },
################################################################################
# NOTIFICATIONS                                                                #
################################################################################
      'notifications': {
        'subject': '[Epicast] New Data Available (NEW: 90% confidence intervals)',
        'text': '''
        
<b>NEW THIS WEEK</b>: you will notice grey vertical bars on the flu activity levels in the last few weeks of the current season.  This is because these values are subject to future revision.  The vertical bars represent 90% confidence intervals for where the final values will end up being.

Dear %s,
The CDC has released another week of flu surveillance data. A new round of flu forecasting is now underway, and we need your forecasts! We are asking you to please submit your forecasts by <b>10:00 AM (ET)</b> this coming %s.
Thank you so much for your support and cooperation!
 
Accurate forecasting of flu’s spread in different regions is important for timely public alerts, education campaigns, vaccination campaigns, staffing decisions and resource allocations.  For several years now, CDC has been supporting the development of flu forecasting technology via its annual “Predict the Flu” challenge. Epicast was the most accurate forecasting systems in CDC's “Predict the Flu” challenge for the 2016-17 season, in a crowded field of 28 submissions. It was originally developed by David Farrow as part of his PhD thesis.
To login and submit your forecasts, visit http://epicast.org and enter your User ID: %s
%s
Thank you again for your participation, and good luck on your forecasts!
Happy Forecasting!
-The DELPHI Team
        '''%(u[1], deadline_day, u[0], score_text),
        'html': '''


<p>
<b>NEW THIS WEEK</b>: you will notice grey vertical bars on the flu activity levels in the last few weeks of the current season.  This is because these values are subject to future revision.  The vertical bars represent 90% confidence intervals for where the final values will end up being.
</p><p>
  Dear %s,
</p><p>
  The CDC has released another week of flu surveillance data. A new round of flu forecasting is now underway, and we need your forecasts! We are asking you to please submit your forecasts by <b>10:00 AM (ET)</b> this coming Monday.
  Thank you so much for your support and cooperation!
</p><p>
  Accurate forecasting of flu’s spread in different regions is important for timely public alerts, education campaigns, vaccination campaigns, staffing decisions and resource allocations. For several years now, CDC has been supporting the development of flu forecasting technology via its annual “Predict the Flu” challenge.
  Epicast was the most accurate forecasting systems in CDC's “Predict the Flu” challenge for the 2016-17 season, in a crowded field of 28 submissions. It was originally developed by David Farrow as part of his PhD thesis.
</p><p>
  To login and submit your forecasts, click <a href="http://epicast.org/launch.php?user=%s">here</a> or visit http://epicast.org and enter your User ID: %s
</p>%s<p>
  Thank you again for your participation, and good luck on your forecasts!
</p><p>
  Happy Forecasting!
<br />
  -The DELPHI Team
</p>
        '''%(u[1], u[0], u[0], score_html),
      },

      
################################################################################
# REMINDERS                                                                    #
################################################################################
      'reminders': {
        'subject': 'Forecasts Needed (Deadline: Monday 10AM)',
        'text': '''
Dear %s,


This is just a friendly reminder that your flu forecasts are due by 10:00AM (ET) on Monday. 
Thank you so much for your support and cooperation!

To login and submit your forecasts, visit http://epicast.org and enter your User ID: %s


Happy Forecasting!

-The DELPHI Team
        '''%(u[1], u[0]),
        'html': '''
<p>
  Dear %s,
</p><p>
  This is just a friendly reminder that your flu forecasts are due by 10:00AM (ET) on Monday. 
Thank you so much for your support and cooperation!
</p><p>
  To login and submit your forecasts, click <a href="http://epicast.org/launch.php?user=%s">here</a> or visit http://epicast.org and enter your User ID: %s
</p><p>
  Happy Forecasting!
  <br />
  -The DELPHI Team
</p>
        '''%(u[1], u[0], u[0]),
      },
################################################################################
    }
    emails[args.type]['text'] += '''

[This is an automated message. To edit your email preferences or to stop receiving these emails, follow the unsubscribe link below.]

Unsubscribe: http://epicast.org?preferences.php?user=%s
    '''%(u[0])
    emails[args.type]['html'] = '<html><body>' + emails[args.type]['html'] + '''
<hr />
<p style="color: #666; font-size: 0.8em;">
  [This is an automated message. To edit your email preferences or to stop receiving these emails, click the unsubscribe link below.]
  <br />
  <a href="http://epicast.org/preferences.php?user=%s">Unsubscribe</a>
</p>
    '''%(u[0]) + '</body></html>'
    to, subject, body = u[2], emails[args.type]['subject'], emailer.encode(emails[args.type])
    if args.print:
      print('%s -> %s\n%s'%(subject, to, emails[args.type]['text']), True)
    else:
      sql = "INSERT INTO automation.email_queue (`from`, `to`, `subject`, `body`) VALUES ('%s', '%s', '[Epicast] %s', '%s')"%(secrets.flucontest.email_epicast, to, subject, body)
      execute_sql(cur, sql)
  if not args.print:
    sql = "CALL automation.RunStep(2)"
    execute_sql(cur, sql)

  #Cleanup
  cnx.commit()
  cur.close()
  cnx.close()
  print('Done!', True)
