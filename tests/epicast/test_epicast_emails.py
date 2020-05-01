"""Unit tests for epicast_emails.py."""

# standard library
import re
import unittest

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.epicast.epicast_emails'

# common to all emails
SUBJECT_PATTERN = r'^\[.*?] .*$'
UNSUBSCRIBE_SNIPPETS = [
  'unsubscribe',
  '/preferences.php',
]


class Tests(unittest.TestCase):
  """Basic unit tests."""

  def test_get_alert(self):
    """Get an alert email."""

    user_id = '1234abcd'
    user_name = 'User Name'

    subject, text, html = EpicastEmails.get_alert(user_id, user_name)

    # not much to test since alert is ad hoc by design
    self.assertIn('delphi', text.lower())
    self.assertIn('delphi', html.lower())

    # common to all emails
    self.assertIsNotNone(re.match(SUBJECT_PATTERN, subject))
    for snippet in UNSUBSCRIBE_SNIPPETS:
      self.assertIn(snippet, text.lower())
      self.assertIn(snippet, html.lower())

  def test_get_notification_with_score(self):
    """Get a notification email with a score."""

    user_id = '1234abcd'
    user_name = 'User Name'
    last_score = 5
    last_rank = 6
    total_score = 7
    total_rank = 8

    subject, text, html = EpicastEmails.get_notification(
        user_id, user_name, last_score, last_rank, total_score, total_rank)

    self.assertIn('the cdc has released', text.lower())
    self.assertIn('the cdc has released', html.lower())
    self.assertIn('overall score is: 7', text.lower())
    self.assertIn('ranked #8', text.lower())
    self.assertIn('overall score is: 7', html.lower())
    self.assertIn('ranked #8', html.lower())

    # common to all emails
    self.assertIsNotNone(re.match(SUBJECT_PATTERN, subject))
    for snippet in UNSUBSCRIBE_SNIPPETS:
      self.assertIn(snippet, text.lower())
      self.assertIn(snippet, html.lower())

  def test_get_notification_without_score(self):
    """Get a notification email without a score."""

    user_id = '1234abcd'
    user_name = 'User Name'
    last_score = 0
    last_rank = 0
    total_score = 0
    total_rank = 0

    subject, text, html = EpicastEmails.get_notification(
        user_id, user_name, last_score, last_rank, total_score, total_rank)

    self.assertIn('the cdc has released', text.lower())
    self.assertIn('the cdc has released', html.lower())
    self.assertNotIn('score', text.lower())
    self.assertNotIn('ranked', text.lower())
    self.assertNotIn('score', html.lower())
    self.assertNotIn('ranked', html.lower())

    # common to all emails
    self.assertIsNotNone(re.match(SUBJECT_PATTERN, subject))
    for snippet in UNSUBSCRIBE_SNIPPETS:
      self.assertIn(snippet, text.lower())
      self.assertIn(snippet, html.lower())

  def test_get_reminder(self):
    """Get a reminder email."""

    user_id = '1234abcd'
    user_name = 'User Name'

    subject, text, html = EpicastEmails.get_reminder(user_id, user_name)

    self.assertIn('a friendly reminder', text.lower())
    self.assertIn('a friendly reminder', html.lower())

    # common to all emails
    self.assertIsNotNone(re.match(SUBJECT_PATTERN, subject))
    for snippet in UNSUBSCRIBE_SNIPPETS:
      self.assertIn(snippet, text.lower())
      self.assertIn(snippet, html.lower())
