"""
utilities for hospitalization data analysis.
"""
# first party
import utils.epiweek as utils
# third party
import bootstrapped.bootstrap as bs
import bootstrapped.stats_functions as stat_f

def get_window(epiweek, left_window, right_window):
    """
    generate a time period [epiweek-left_window, epiweek+right_window]

    Args:
        epiweek - the "central" epiweek for a period
        left_window - the length of "left side"
        right_window - the length of "right side"
    
    Returns:
        A generator of epiweeks within the period
    """
    start = utils.add_epiweeks(epiweek, -left_window)
    end = utils.add_epiweeks(epiweek, right_window)
    return utils.range_epiweeks(start, end, inclusive=True)

def fill(data):
    """
    fill the series to length 52 (i.e. a year)

    Args:
        data - the data source (included all epiweeks with all lags)
    
    Returns:
        the modified data source
    """
    for _, series in data.items():
        # for all series, repeat the last value until length = 52
        final_val = series[-1]
        series.extend([final_val] * (52 - len(series)))
    
    return data

def get_season(time_period):
    """ return the epiweek range of the flu season containing the epiweek """
    start, end = time_period.split('-')
    start_year = (int(start) - 40) // 100
    end_year = (int(end) - 40) // 100

    return start_year, end_year

def unravel(time_period):
    """
    convert string representation of a time period to a epiweek generator.

    Args:
        time_period - the string representation of time period

    Returns:
        A generator of epiweeks within the period
    """
    timeframe = time_period.split('-')
    start = int(timeframe[0])
    end = int(timeframe[1])
    return utils.range_epiweeks(start, end, inclusive=True)

def ravel(start, end):
    """
    given start and end of a time period, return the string representation of that period. 
    """
    return str(start)+'-'+str(end)

def bootstrap_mean(residuals, alpha):
    interval = bs.bootstrap(residuals, stat_f.mean, alpha=alpha)
    return interval.lower_bound, interval.upper_bound
