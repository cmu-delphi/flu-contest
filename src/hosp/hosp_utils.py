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

def get_start_year(epiweek):
    """ 
    return the starting and ending year of the flu season for an epiweek.

    Args:
        epiweek - the epiweek for season query
    
    Returns:
        the starting year of the season
    """
    year, week = utils.split_epiweek(epiweek)
    if week <= 20:
        return year - 1
    elif week >= 40:
        return year

def get_period(year, start_week, end_week):
    """
    return the corresponding period for a starting year, 
        starting week, and ending week.

    Args:
        year - the start year for a season.
        start_week - the starting week within the season.
        end_week - the ending week within the season.
    
    Returns:
        the starting and ending epiweek of the period.
    """
    if start_week <= end_week:
        if end_week <= 30:
            return utils.join_epiweek(year + 1, start_week), \
                utils.join_epiweek(year + 1, end_week)
        else:
            return utils.join_epiweek(year, start_week), \
                utils.join_epiweek(year, end_week)
    else:
        return utils.join_epiweek(year, start_week), \
            utils.join_epiweek(year + 1, end_week)

def get_max_window(epiweek):
    """
    obtain the maximum window applicable for an epiweek.

    Args:
        epiweek - the current epiweek.
    
    Returns:
        max_window - the maximum window.
    """
    start_year = get_start_year(epiweek)
    start_week = utils.join_epiweek(start_year, 40)
    max_window = utils.delta_epiweeks(start_week, epiweek)

    return max_window

def unravel(time_period):
    """
    convert string representation of a time period to a epiweek generator.

    Args:
        time_period - the string representation of time period

    Returns:
        A generator of epiweeks within the period
    """
    return utils.range_epiweeks(time_period[0], time_period[1], inclusive=True)
