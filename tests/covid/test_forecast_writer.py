"""Unit tests for generate_forecast.py."""

# standard library
import unittest

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.covid.forecast_writer'


class UnitTests(unittest.TestCase):
  """Basic unit tests."""

  def test_get_location_name(self):
    """Test display formatting of various location codes."""

    self.assertEqual(
        ForecastWriter.get_location_name('nat'),
        'US National')
    self.assertEqual(
        ForecastWriter.get_location_name('hhs1'),
        'HHS Region 1')
    self.assertEqual(
        ForecastWriter.get_location_name('pa'),
        'Pennsylvania')
    self.assertEqual(
        ForecastWriter.get_location_name('dc'),
        'District of Columbia')
    self.assertEqual(
        ForecastWriter.get_location_name('ny_minus_jfk'),
        'New York')
