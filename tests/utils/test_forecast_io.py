"""Unit tests for forecast_io.py."""

# standard library
import unittest

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.utils.forecast_io'


class Tests(unittest.TestCase):
  """Generic unit tests."""

  def test_extract_epiweek_and_team(self):
    # nominal operation and edge cases
    for name, expected in (
      ('EW51-delphi-epicast-2018-01-03.csv', (201751, 'delphi-epicast')),
      ('EW40-delphi-stat-2015-06-01.csv', (201440, 'delphi-stat')),
      ('EW10-hello-2018-06-01.csv', (201810, 'hello')),
      ('EW52-world-2017-12-31.csv', (201752, 'world')),
    ):
      with self.subTest(name=name):
        actual = ForecastIO.extract_epiweek_and_team(name)
        self.assertEquals(actual, expected)

    # invalid names
    for name in (
      'EW54-x-2018-01-03.csv',
      'EW00-x-2018-01-03.csv',
      'nothing.csv',
    ):
      with self.subTest(name=name):
        with self.assertRaises(Exception):
          ForecastIO.extract_epiweek_and_team(name)
