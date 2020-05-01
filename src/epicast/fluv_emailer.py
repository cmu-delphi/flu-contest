"""Sends emails to Epicast-FLUV users.

Individual user preferences are respected; it won't email people who don't want
to be emailed.
"""

# standard library
import argparse
import base64
import json
import random

# third party
import mysql.connector

# first party
from delphi.flu_contest.epicast.epicast_emails import EpicastEmails
import delphi.operations.emailer as emailer
import delphi.operations.secrets as secrets


def get_argument_parser():
  """Define command line arguments and usage."""

  parser = argparse.ArgumentParser()
  parser.add_argument(
      '-v',
      '--verbose',
      action='store_const',
      const=True,
      default=False,
      help='show extra output')
  parser.add_argument(
      '-t',
      '--test',
      action='store_const',
      const=True,
      default=False,
      help='only email myself')
  parser.add_argument(
      '-p',
      '--print',
      action='store_const',
      const=True,
      default=False,
      help='print email to stdout, don\'t send')
  parser.add_argument(
      '-f',
      '--force',
      action='store_const',
      const=True,
      default=False,
      help='force match on myself')
  parser.add_argument(
      'type',
      choices=[
        'alerts',
        'notifications',
        'reminders',
      ],
      help='email type')
  return parser


def execute_sql(cur, sql):
  """Print and execute SQL."""

  print(sql)
  cur.execute(sql)


def get_users(cur, name, value):
  """Return all users having some preference."""

  sql = "SELECT u.`hash`, u.`name`, u.`email` FROM ec_fluv_defaults d JOIN ec_fluv_users u ON TRUE LEFT JOIN ec_fluv_user_preferences p ON p.`user_id` = u.`id` AND p.`name` = d.`name` WHERE d.`name` = '%s' AND coalesce(p.`value`, d.`value`) = '%s'" % (name, value)
  execute_sql(cur, sql)

  users = []
  for (hash, name, email) in cur:
    users.append((hash[0:8], name, email))
  return set(users)


def get_scores(cur, user):
  """Return user score info."""

  sql = "SELECT coalesce(x.`total`, 0) `total`, coalesce(sum(CASE WHEN s.`total` >= x.`total` THEN 1 ELSE 0 END), (SELECT count(1) FROM ec_fluv_scores)) `total_rank`, coalesce(x.`last`, 0) `last`, coalesce(sum(CASE WHEN s.`last` >= x.`last` THEN 1 ELSE 0 END), (SELECT count(1) FROM ec_fluv_scores)) `last_score` FROM ec_fluv_scores s JOIN (SELECT s.`total`, s.`last` FROM ec_fluv_users u JOIN ec_fluv_scores s ON s.`user_id` = u.`id` WHERE u.`hash` LIKE '%s%%') x ON TRUE" % (user[0])
  execute_sql(cur, sql)

  for (total, total_rank, last, last_rank) in cur:
    pass
  return (int(last), last_rank, int(total), total_rank)


def already_submitted(cur, user):
  """Return whether a user has already submitted all predictions."""

  defaultNumRegion = 11
  sql = "SELECT count(1) FROM ec_fluv_users u JOIN ec_fluv_submissions s ON s.`user_id` = u.`id` WHERE u.`hash` LIKE '%s%%' AND s.`epiweek_now` = (SELECT max(epiweek) FROM epidata.fluview)" % (user[0])
  execute_sql(cur, sql)

  num = 0
  for (num,) in cur:
    pass
  return num >= defaultNumRegion


def get_deadline_day_name(cur):
  """Return the name of the deadline day."""

  sql = "SELECT dayname(`deadline`) FROM ec_fluv_round"
  execute_sql(cur, sql)

  name = None
  for (name,) in cur:
    pass
  if name is None:
    raise Exception('couldnt get name of deadline day')
  return name


def connect_to_database(connector_impl):
  """Connect to the database and return a cursor."""

  u, p = secrets.db.epi
  return connector_impl.connect(user=u, password=p, database='epicast2')


def main(args, connector_impl=mysql.connector, emailer_impl=emailer):
  """Generate and submit various emails to epicast participants."""

  #Verbosity-dependent print
  def log(str, force=False):
    if force or args.verbose:
      print(str)

  #DB connection
  log('Connecting to the database')
  cnx = connect_to_database(connector_impl)
  cur = cnx.cursor()
  log('Connected successfully')

  #Get deadline
  deadline_day = get_deadline_day_name(cur)
  log('deadline is this coming %s' % deadline_day)

  #Build the list of recipients
  email_type = args.type
  if email_type == 'alerts':
    email_type = 'notifications'
  users = get_users(cur, 'email_%s' % (email_type), '1') - get_users(cur, '_debug', '1')

  log('%d users selected to receive email %s' % (len(users), args.type), True)
  if args.type == 'alerts':
    #users = users - get_users(cur, '_delphi', '0')
    #log('%d of them are delphi members' % (len(users)), True)
    log('everyone in ec_fluv_users gets invited')
  if args.type == 'reminders':
    temp = []
    for u in users:
      if not already_submitted(cur, u):
        temp.append(u)
    users = set(temp)
    log('%d of them need to be reminded' % (len(users)), True)
  if args.test:
    users = set([u for u in users if u[0] == secrets.flucontest.debug_userid])
    log('test mode - users filtered to %d' % (len(users)), True)
  if args.force:
    users = set([u for u in users if u[0] != secrets.flucontest.debug_userid]) | set([(secrets.flucontest.debug_userid, 'Debug User', secrets.flucontest.email_maintainer)])
    log('force mode - users filtered to %d' % (len(users)), True)
    log(users, True)

  #Send the emails
  for u in users:
    user_id, user_name, user_email = u
    last_score, last_rank, total_score, total_rank = get_scores(cur, u)

    if args.type == 'alerts':
      subject, text, html = EpicastEmails.get_alert(user_id, user_name)

    elif args.type == 'notifications':
      subject, text, html = EpicastEmails.get_notification(
          user_id, user_name, last_score, last_rank, total_score, total_rank)

    elif args.type == 'reminders':
      subject, text, html = EpicastEmails.get_reminder(user_id, user_name)

    else:
      raise Exception('not implemented')

    if args.print:
      log('%s -> %s\n%s' % (subject, user_email, text), True)
    else:
      # smear emails over time by setting a random priority which the emailer
      # will use to determine email batches
      priority = random.random()
      emailer_impl.queue_email(
          to=user_email,
          subject=subject,
          text=text,
          html=html,
          priority=priority)

  if not args.print:
    emailer_impl.call_emailer()

  #Cleanup
  cur.close()
  cnx.close()
  log('Done!', True)


if __name__ == '__main__':
  main(get_argument_parser().parse_args())
