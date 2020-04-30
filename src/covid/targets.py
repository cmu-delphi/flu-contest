"""Implements the various targets to be forecasted."""

# third party
import numpy as np


class Targets:

  @staticmethod
  def get_peak_week(series):
    # assume first week is 2020w10, ignore values after 2020w35
    return np.argmax(series[:26])

  @staticmethod
  def get_peak_wili(series):
    # assume first week is 2020w10, ignore values after 2020w35
    return np.max(series[:26])

  @staticmethod
  def get_n_week_wili(series, current_week, n):
    # note that this is the only target beyond 2020w35 -- it goes up to 2020w40
    return series[current_week + n]

  @staticmethod
  def get_offset_week(series, baseline):
    # assume first week is 2020w10, ignore *starting weeks* after 2020w35
    # values on 2020w36, 2020w37 could support offset of e.g. 2020w35
    # sortof opposite of onset; below baseline for 3 consecutive weeks
    # return None if this doesn't happen for the given curve and baseline
    for i in range(26):
      if np.all(np.array(series[i:i + 3]) < baseline):
        return i

    # `None` would be returned here implicitly, but doing so explicitly as this
    # is a particularly meaningful result (i.e. wili never "offset")
    return None
