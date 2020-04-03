"""Unit tests for fluv_emailer.py."""

# standard library
import argparse
import unittest

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.epicast.fluv_emailer'


class Tests(unittest.TestCase):
  """Basic unit tests."""

  def test_get_argument_parser(self):
      """An ArgumentParser should be returned."""
      self.assertIsInstance(get_argument_parser(), argparse.ArgumentParser)
