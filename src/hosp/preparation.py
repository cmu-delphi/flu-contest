"""
data preparation procedures for final value prediction task.
"""
# first party
import utils.epiweek as utils
import flu_contest.src.hosp.hosp_utils as hosp_utils

from flu_contest.src.hosp.tools import *
from delphi_epidata.src.client.delphi_epidata import Epidata
# third party
import pickle
import numpy as np
import matplotlib.pyplot as plt

from tqdm import tqdm

def update_data(locations, time_period, max_lag):
    """ 
    Query data from flusurv API to update data for a time period.

    Args:
        locations - the locations we query from
        time_period - a string representing the starting and ending epiweek
        max_lag - the maximum time lag to consider for each epiweek
    
    Returns:
        data - the queried and processed data source
    """
    data = {}
    # generate epiweeks in the time period
    period = hosp_utils.unravel(time_period)

    for epiweek in tqdm(period):
        for location in tqdm(locations):
            # for a combination of location and epiweek, query from 0 to maximum lag
            for l in range(max_lag + 1):
                current = Epidata.flusurv(location, epiweek, lag=l)
                if 'epidata' in current:
                    cur_data = current['epidata'][0]
                    # if record exists, query each age group
                    for group in range(5):
                        if (epiweek, group, location) not in data:
                            data[(epiweek, group, location)] = []
                        data[(epiweek, group, location)].append(cur_data['rate_age_' + str(group)])                      
    # fill and save the queried results
    fill_data(data, max_lag)
    write_data(data, 'data.txt')
    # load queried data into a pickle file
    with open('data.pickle', 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return data

def fetch(data, location, group, epiweek, lag, left_window, right_window, backfill_window):
    """ 
    fetch data for a location and age group specified by epiweek and time window.

    Args:
        data - the data source (included all epiweeks with all lags)
        location - the current location 
        group - the current age group (as an index from 0 to 4)
        epiweek - the current epiweek
        lag - the current time lag
        left_window, right_window - represent the interval 
            [epiweek - left_window, epiweek + right_window]
        backfill_window - the "width" of backfill
    
    Returns:
        the predictors and ground truth for each epiweek
    """
    # get the time period
    period = hosp_utils.get_window(epiweek, left_window, right_window)
    # ground truth and the first release
    cur_y = data[(epiweek, group, location)][lag]
    y = data[(epiweek, group, location)][-1:]
    # create x, and fill entries by 0
    x = np.zeros((left_window + right_window + 1, backfill_window + 1))
    
    for pos, epiweek in enumerate(period):
        # for each epiweek, collect data for regression
        if (epiweek, group, location) in data:
            record = data[(epiweek, group, location)]
            # take the data from start_ind with fill_length
            start_ind = lag - pos + left_window - backfill_window
            fill_length = max(0, lag - pos + left_window + 1) - max(0, start_ind)
            x[pos, backfill_window + 1 - fill_length:] = \
                record[max(0, start_ind): max(0, lag - pos + left_window + 1)]
    # vectorize collected data
    x = x.reshape(-1, 1)
    return x, cur_y, y

def prepare(data, locations, groups, periods, lag, left_window, right_window, backfill_window):
    """
    collect data from different locations, groups, and time periods.

    Args:
        data - the data source (included all epiweeks with all lags)
        locations - a list of all locations to fetch
        groups - a list of all age groups to fetch
        periods - a list of all time periods to fetch
        lag - the current time lag
        left_window, right_window - represent the interval 
            [epiweek - left_window, epiweek + right_window]
        backfill_window - the "width" of backfill
    """
    # collector
    total_X = []
    total_Y = []

    for time_period in periods:
        period = hosp_utils.unravel(time_period)

        for epiweek in period:
            for location in locations:
                for group in groups:
                    # fetch the data for each epiweek, location and group within the period
                    if (epiweek, group, location) in data:
                        x, _, y = fetch(data, 
                                        location, group, epiweek, 
                                        lag, left_window, right_window, backfill_window)
                        # if data exists, collect
                        if np.any(y):
                            total_X.append(x)
                            total_Y.append(y)
    # vectorize data
    total_X = np.vstack(total_X).reshape(len(total_X), -1)  
    total_Y = np.array(total_Y).squeeze()
    return total_X, total_Y
