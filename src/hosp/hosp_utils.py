"""
utilities for hospitalization data analysis.
"""
# first party
import utils.epiweek as utils

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

def get_season(time_period):
    """ 
    return the epiweek range of the flu season containing the epiweek.

    Args:
        time_period - the string representation of time period
    
    Returns:
        start_year, end_year - the starting and ending year
    """
    start, end = time_period.split('-')
    start_year = int(start) // 100
    end_year = int(end) // 100

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

    Args:
        start - the starting epiweek
        end - the ending epiweek
    
    Return:
        A string representation of time period
    """
    return str(start) + '-' + str(end)
