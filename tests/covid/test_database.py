"""Unit tests for database.py."""

# standard library
import unittest
from unittest.mock import MagicMock

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.covid.database'


class UnitTests(unittest.TestCase):
  """Basic unit tests."""

  def test_connect_opens_connection(self):
    """Connect to the database."""

    mock_connector = MagicMock()
    database = Database()

    database.connect(connector_impl=mock_connector)

    self.assertTrue(mock_connector.connect.called)

  def test_disconnect_with_rollback(self):
    """Disconnect from the database and rollback."""

    mock_connector = MagicMock()
    database = Database()
    database.connect(connector_impl=mock_connector)

    # rollback
    database.disconnect(False)

    connection = mock_connector.connect()
    self.assertFalse(connection.commit.called)
    self.assertTrue(connection.close.called)

  def test_disconnect_with_commit(self):
    """Disconnect from the database and commit."""

    mock_connector = MagicMock()
    database = Database()
    database.connect(connector_impl=mock_connector)

    # commit
    database.disconnect(True)

    connection = mock_connector.connect()
    self.assertTrue(connection.commit.called)
    self.assertTrue(connection.close.called)

  def test_get_user_predictions(self):
    """Query to get all user-submitted predictions for a given epiweek.

    TODO: Actual behavior should be tested by integration test.
    """

    args = ('epiweek',)
    mock_connector = MagicMock()
    database = Database()
    database.connect(connector_impl=mock_connector)

    database.get_user_predictions(*args)

    connection = mock_connector.connect()
    cursor = connection.cursor()
    self.assertTrue(cursor.execute.called)

    sql, args = cursor.execute.call_args[0]
    self.assertEqual(args, ('epiweek',))

    sql = sql.lower()
    self.assertIn('select', sql)
    self.assertIn('`ec_fluv_users`', sql)
    self.assertIn('`ec_fluv_defaults`', sql)
    self.assertIn('`ec_fluv_user_preferences`', sql)
    self.assertIn('`ec_fluv_submissions`', sql)
    self.assertIn('`ec_fluv_forecast`', sql)
    self.assertIn('`ec_fluv_regions`', sql)
