"""
utilities for hospitalization data analysis.
"""
# first party
import utils.epiweek as utils
# third party
import bootstrapped.bootstrap as bs
import bootstrapped.stats_functions as stat_f

# all states we can query (including the whole network) 
STATE_LIST = ['ca', 'co', 'ct', 
              'ga', 
              'md', 'mi', 'mn', 
              'nm',  
              'oh', 'or', 
              'tn', 'ut',
              'network_all']

def create_double_list(obj, dim_x, dim_y):
    """
    create a 2-dimensional list copies for an object.
    all objects in the list are deep copies of the object.

    Args:
        obj - the original object
        dim_x - the first dimension of the double list
        dim_y - the second dimension of the double list
    
    Returns:
        the 2-dimensional list copies of the object
    """
    return [list(obj for _ in range(dim_y)) for _ in range(dim_x)]

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

    Args:
        start - the starting epiweek
        end - the ending epiweek
    
    Return:
        A string representation of time period
    """
    return str(start)+'-'+str(end)

def bootstrap_mean(residuals, alpha):
    """
    boostrap the confidence interval of the mean from residuals.

    Args:
        residuals - the residuals
        alpha - the significance level
    
    Returns:
        lower_bound, upper_bound - the bound for confidence interval
    """
    interval = bs.bootstrap(residuals, stat_f.mean, alpha=alpha)
    return interval.lower_bound, interval.upper_bound
