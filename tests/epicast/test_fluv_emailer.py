"""Unit tests for fluv_emailer.py."""

# standard library
import argparse
import unittest
from unittest.mock import MagicMock

# first party
import delphi.operations.secrets as secrets

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.epicast.fluv_emailer'


class Tests(unittest.TestCase):
  """Basic unit tests."""

  def test_get_argument_parser(self):
      """An ArgumentParser should be returned."""
      self.assertIsInstance(get_argument_parser(), argparse.ArgumentParser)

  def test_connect_to_database(self):
    """Connect to the database with expected credentials."""

    mock_connector = MagicMock()
    mock_connector.connect.return_value = 'connection'

    cnx = connect_to_database(mock_connector)

    self.assertTrue(mock_connector.connect.called)
    self.assertEqual(
        mock_connector.connect.call_args[1],
        {
          'user': secrets.db.epi[0],
          'password': secrets.db.epi[1],
          'database': 'epicast2',
        })
    self.assertEqual(cnx, 'connection')

  def test_main_notifications(self):
    """Send the notification email."""

    args = MagicMock(
        verbose=True,
        test=False,
        print=False,
        force=True,
        type='notifications')
    mock_connector = MagicMock()
    cnx = connect_to_database(mock_connector)
    cur = cnx.cursor()
    cur.inserted = False

    # this is not elegant, but it's a quick way to simulate each query
    def handle_query(sql):

      # get_users
      if sql.startswith('SELECT u.`hash`'):
        cur.__iter__.return_value = []

      # get_scores
      if sql.startswith('SELECT coalesce'):
        cur.__iter__.return_value = [(1, 2, 3, 4)]

      # get_deadline_day_name
      if sql.startswith('SELECT dayname'):
        cur.__iter__.return_value = [('Someday',)]

      # take note of insert
      if sql.startswith('INSERT INTO '):
        cur.inserted = True

    cur.execute = handle_query

    main(args, connector_impl=mock_connector)

    # check for at least one sent email ("force" flag guarantees this)
    self.assertTrue(cur.inserted)

    # check for final database commit as proxy for successful run
    self.assertTrue(cnx.commit.called)

  def test_main_reminders(self):
    """Send the reminder email."""

    args = MagicMock(
        verbose=True,
        test=False,
        print=False,
        force=True,
        type='reminders')
    mock_connector = MagicMock()
    cnx = connect_to_database(mock_connector)
    cur = cnx.cursor()
    cur.inserted = False

    # this is not elegant, but it's a quick way to simulate each query
    def handle_query(sql):

      # get_users
      if sql.startswith('SELECT u.`hash`'):
        cur.__iter__.return_value = []

      # get_scores
      if sql.startswith('SELECT coalesce'):
        cur.__iter__.return_value = [(1, 2, 3, 4)]

      # get_deadline_day_name
      if sql.startswith('SELECT dayname'):
        cur.__iter__.return_value = [('Someday',)]

      # take note of insert
      if sql.startswith('INSERT INTO '):
        cur.inserted = True

    cur.execute = handle_query

    main(args, connector_impl=mock_connector)

    # check for at least one sent email ("force" flag guarantees this)
    self.assertTrue(cur.inserted)

    # check for final database commit as proxy for successful run
    self.assertTrue(cnx.commit.called)
