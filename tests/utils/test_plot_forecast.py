"""Unit tests for plot_forecast.py."""

# standard library
import argparse
import unittest

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.utils.plot_forecast'


class Tests(unittest.TestCase):
  """Generic unit tests."""

  def test_get_argument_parser(self):
    self.assertIsInstance(get_argument_parser(), argparse.ArgumentParser)
