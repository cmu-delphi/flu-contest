"""
data preparation procedures for linear regression.
"""
from __future__ import division, print_function
# first party
import utils.epiweek as utils
import flu_contest.src.hosp.hosp_utils as hosp_utils 
from delphi_epidata.src.client.delphi_epidata import Epidata
# third party
import pickle
import numpy as np
import matplotlib.pyplot as plt
from tqdm import tqdm


def update_data(location, time_period, max_lag):
    """ 
    Query data from flusurv API to update data for a time period.

    Args:
        location - the location to focus on in analysis
        time_period - a string representing the starting and ending epiweek
        max_lag - the maximum time lag to consider for each epiweek
    
    Returns:
        data - the queried and processed data source
    """
    # initialize
    data = {}
    # generate epiweeks in the time period
    period = hosp_utils.unravel(time_period)

    for epiweek in tqdm(period):
        for l in range(max_lag+1):
            # for a combination of location and epiweek, query from 0 to maximum lag
            current = Epidata.flusurv(location, epiweek, lag=l)
            if 'epidata' in current:
                cur_data = current['epidata'][0]
                for group in range(5):
                    if (epiweek, group) not in data:
                        data[(epiweek, group)] = []
                    data[(epiweek, group)].append(cur_data['rate_age_'+str(group)])                      
    # fill and save the queried results
    hosp_utils.fill(data)
    with open('data.pickle', 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return data

def fetch(data, epiweek, lag, left_window, right_window, backfill_window, group):
    """ 
    fetch data for a time period specified by epiweek and time window.

    Args:
        data - the data source (included all epiweeks with all lags)
        epiweek - the current epiweek (as string)
        lag - the current time lag
        time_window - the "width" of time period
        backfill_window - the "width" of backfill
        group - the current age group. (as an index from 0 to 4)
    
    Returns:
        the testing data for the current epiweek
    """
    # get the time period
    period = hosp_utils.get_window(epiweek, left_window, right_window)
    # initialize data
    cur_y = data[(epiweek, group)][lag-1]
    y = data[(epiweek, group)][-1:]
    x = np.zeros((left_window+right_window+1, backfill_window))
    
    for pos, epiweek in enumerate(period):
        # for each epiweek, collect testing data for regression
        if (epiweek, group) in data:
            record = data[(epiweek, group)]
            start_ind = lag-pos+left_window-backfill_window
            fill_length = max(0, lag-pos+left_window)-max(0, start_ind)
            x[pos, backfill_window-fill_length:] = record[max(0, start_ind): max(0, lag-pos+left_window)]
    
    return x.reshape(-1, 1), cur_y, y

def prepare(data, time_period, lag, left_window, right_window, backfill_window, group):
    """
    collect data for a time period.

    Args:
        data - the data source (included all epiweeks with all lags)
        time_period - a string representing the starting and ending epiweek
        lag - the current time lag
        time_window - the "width" of time period
        backfill_window - the "width" of backfill
        group - the current age group. (as an index from 0 to 4)
    """
    # initialize
    total_X = []
    total_Y = []
    period = hosp_utils.unravel(time_period)
    
    for epiweek in period:
        if (epiweek, group) in data:
            # get the data for each epiweek within the period
            x, _, y = fetch(data, epiweek, lag, left_window, right_window, backfill_window, group)
            total_X.append(x)
            total_Y.append(y)
    # reformat the data into 2d arrays
    total_X = np.vstack(total_X).reshape(len(total_X), -1)  
    total_Y = np.array(total_Y).squeeze()
    
    return total_X, total_Y
