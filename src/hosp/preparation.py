"""
data preparation procedures for final value prediction task.
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

def _write_data(data):
    """
    write the data to a text file (data.txt) for viewing.

    Args: 
        data - the data source (as python dictionary)
    
    Returns:
        None
    """
    f = open('data.txt', mode='w')
    # sort the keys for viewing
    for key in sorted(data.keys()):
        f.write(str(key) + ';' + str(data[key]) + '\n')
    f.close()

def _fill_data(data, max_lag):
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

def update_data(locations, time_period, max_lag):
    """ 
    Query data from flusurv API to update data for a time period.

    Args:
        locations - the locations we query from
        time_period - a string representing the starting and 
                        ending epiweek
        max_lag - the maximum time lag to consider for each epiweek
    
    Returns:
        data - the queried and processed data source
    """
    data = {}
    # generate epiweeks in the time period
    period = hosp_utils.unravel(time_period)

    for epiweek in tqdm(period):
        for location in tqdm(locations):
            for l in range(max_lag + 1):
                # for a combination of location and epiweek, query from 0 to maximum lag
                current = Epidata.flusurv(location, epiweek, lag=l)
                if 'epidata' in current:
                    cur_data = current['epidata'][0]
                    for group in range(5):
                        if (epiweek, group, location) not in data:
                            data[(epiweek, group, location)] = []
                        data[(epiweek, group, location)].append(cur_data['rate_age_' + str(group)])                      
    # fill and save the queried results
    _fill_data(data)
    _write_data(data)
    # load queried data into a pickle file
    with open('data.pickle', 'wb') as handle:
        pickle.dump(data, handle, protocol=pickle.HIGHEST_PROTOCOL)
    return data

def fetch(data, location, group, epiweek, lag, left_window, right_window, backfill_window):
    """ 
    fetch data for a time period specified by epiweek and time window.

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
    # initialize data
    cur_y = data[(epiweek, group, location)][lag]
    y = data[(epiweek, group, location)][-1:]
    x = np.zeros((left_window + right_window + 1, backfill_window + 1))
    
    for pos, epiweek in enumerate(period):
        # for each epiweek, collect testing data for regression
        if (epiweek, group, location) in data:
            record = data[(epiweek, group, location)]
            start_ind = lag - pos + left_window - backfill_window
            fill_length = max(0, lag - pos + left_window + 1) - max(0, start_ind)
            x[pos, backfill_window + 1 - fill_length:] = \
                record[max(0, start_ind): max(0, lag - pos + left_window + 1)]
    
    return x.reshape(-1, 1), cur_y, y

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
    total_X = []
    total_Y = []

    for time_period in periods:
        period = hosp_utils.unravel(time_period)

        for epiweek in period:
            for location in locations:
                for group in groups:
                    if (epiweek, group, location) in data:
                        # fetch the data for each epiweek, location and group within the period
                        x, _, y = fetch(data, 
                                        location, group, 
                                        epiweek, lag, 
                                        left_window, right_window, backfill_window)
                        total_X.append(x)
                        total_Y.append(y)
    # compress to train-ready dimensions
    if len(total_X) > 0:   
        total_X = np.vstack(total_X).reshape(len(total_X), -1)  
        total_Y = np.array(total_Y).squeeze()
    else:
        total_X = None
        total_Y = None
    
    return total_X, total_Y
