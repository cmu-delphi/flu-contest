"""Unit tests for submission_loader.py."""

# standard library
import argparse
import unittest

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.utils.submission_loader'


class Tests(unittest.TestCase):
  """Generic unit tests."""

  def test_get_argument_parser(self):
    self.assertIsInstance(get_argument_parser(), argparse.ArgumentParser)
