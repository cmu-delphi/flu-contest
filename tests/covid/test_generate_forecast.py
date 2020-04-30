"""Unit tests for generate_forecast.py."""

# standard library
import argparse
import unittest

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.covid.generate_forecast'


class UnitTests(unittest.TestCase):
  """Basic unit tests."""

  def test_get_argument_parser(self):
    """Return a parser for command-line arguments."""

    self.assertIsInstance(get_argument_parser(), argparse.ArgumentParser)
