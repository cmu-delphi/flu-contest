"""Unit tests for constants.py."""

# standard library
import unittest

# py3tester coverage target
__test_target__ = 'delphi.flu_contest.covid.constants'


class UnitTests(unittest.TestCase):
  """Basic unit tests."""

  def test_sanity_checks(self):
    """Make sure constants are sane."""

    self.assertGreater(BACKFILL_MODEL_NUM_SAMPLES, 0)
    self.assertTrue(0 < UNIFORM_WEIGHT < 1)
    self.assertTrue(202030 <= MAX_EPIWEEK <= 202052)
    self.assertGreater(len(BASELINES), 0)
    self.assertGreater(len(LOCATION_NAMES), 0)
    self.assertGreater(len(COMMON_TARGETS), 0)
    self.assertGreater(len(TARGET_NAMES), 0)
