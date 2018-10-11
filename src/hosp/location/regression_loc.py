"""
The module applies linear regression for final-value prediction. Compatible with Python 3.4+.

Functionalities include:
    1. Cross-validation
    2. Report Generation
    3. Prediction
"""
# first party
import flu_contest.src.hosp.location.preparation_loc as preparation_loc
import flu_contest.src.hosp.hosp_utils as hosp_utils 
import utils.epiweek as utils
# third party
import os
import pickle
from tqdm import tqdm

import numpy as np

import sklearn.metrics as metrics
from sklearn.linear_model import LinearRegression 
from sklearn.svm import SVR

import matplotlib.pyplot as plt

def train_model(X, Y, model_type):
    """
    build SVR regression model for final-value prediction.

    Args:
        X - training input
        Y - training output
        X_val - testing input
    
    Returns:
        Y_pred - predicted targets for testing data
    """
    # build SVR model
    if model_type == 'linear':
        model = LinearRegression()
    elif model_type == 'svr':
        model = SVR(kernel='linear', epsilon=5e-3, C=2.0)
    # fit the training data and predict for testing data
    model.fit(X, Y)
    res = Y / model.predict(X) - 1

    return model, res

def validate(data, 
            locations, groups, 
            time_period, lag, 
            left_window, right_window, backfill_window, 
            model_type):
    """
    apply cross-validation for a time period with a certain lag.

    Args:
        data - the data source (included all epiweeks with all lags)
        time_period - a string representing the starting and ending epiweek
        lag - the current time lag
        left_window, right_window - the time period considered for linear regression: 
                                    [cur_time-left_window, cur_time+right_window]
        backfill_window - the backfill period: [cur_time-window, cur_time]
        group - the current age group. (as a index from 0 to 4)
    
    Returns:
        valid_weeks - the active epiweeks for flu
        predictions - the predicted final values
        cur_truth - the final value of series at current time
        ground_truth - the final values provided by CDC after backfill
    """
    # convert time period (string) to epiweek generator
    period = hosp_utils.unravel(time_period)
    # initialize
    predictions = hosp_utils.create_double_list([], len(locations), len(groups))
    predictions_lower = hosp_utils.create_double_list([], len(locations), len(groups))
    predictions_upper = hosp_utils.create_double_list([], len(locations), len(groups))
    ground_truth = hosp_utils.create_double_list([], len(locations), len(groups))
    cur_truth = hosp_utils.create_double_list([], len(locations), len(groups))
    valid_weeks = []

    for epiweek in period:
        # add current week
        valid_weeks.append(epiweek)
        # for each epiweek with current lag, 
        # get data from the latest available one-year period to train regression
        year, week = utils.split_epiweek(epiweek)
        start = utils.add_epiweeks(utils.join_epiweek(year - 2, week), lag)
        end = utils.add_epiweeks(utils.join_epiweek(year - 1, week), lag)
        model_period = hosp_utils.ravel(start, end)

        X, Y = preparation_loc.prepare(data, locations, [model_period], lag, 
                                        left_window, right_window, backfill_window, 
                                        groups)
        model, res = train_model(X, Y, model_type)   

        for l_idx in range(len(locations)):
            location = locations[l_idx]

            for idx in range(len(groups)):
                group = groups[idx]
                
                if (epiweek, group, location) in data:
                    # obtain training and testing data
                    x_val, cur_y_val, y_val = preparation_loc.fetch(data, location, epiweek, lag, 
                                                                    left_window, right_window, 
                                                                    backfill_window, 
                                                                    group)
                    # get prediction
                    res_mean_l, res_mean_u = hosp_utils.bootstrap_mean(res, alpha=0.05)
                    pred = model.predict(x_val.T)
                    pred_l, pred_u = pred * (1 + res_mean_l), pred * (1 + res_mean_u)
                    # record the results
                    cur_truth[l_idx][idx].append(cur_y_val)
                    ground_truth[l_idx][idx].append(y_val)
                    # collect predictions
                    predictions[l_idx][idx].append(pred)
                    predictions_lower[l_idx][idx].append(pred_l)
                    predictions_upper[l_idx][idx].append(pred_u)

            # collapse predictions from 3d to 2d array
            predictions[l_idx][idx] = np.concatenate(
                                                predictions[l_idx][idx], axis=0).squeeze()
            predictions_lower[l_idx][idx] = np.concatenate(
                                                predictions_lower[l_idx][idx], axis=0).squeeze()
            predictions_upper[l_idx][idx] = np.concatenate(
                                                predictions_upper[l_idx][idx], axis=0).squeeze()
            
    return valid_weeks, \
        predictions, predictions_lower, predictions_upper, \
        cur_truth, ground_truth, \
        res

def validate_all(data, 
                locations, groups, 
                time_period, lag, 
                left_window, right_window, backfill_window, 
                model_type):
    start_year, end_year = hosp_utils.get_season(time_period)
    period = hosp_utils.unravel(time_period)
    model_periods = []

    for year in range(2012, 2018):
        if year not in range(start_year, end_year + 1):
            start_week = year * 100 + 44
            end_week = (year + 1) * 100 + 17
            model_periods.append(hosp_utils.ravel(start_week, end_week))

    X, Y = preparation_loc.prepare(data, locations, model_periods, lag, 
                                    left_window, right_window, backfill_window, 
                                    groups)
    model, res = train_model(X, Y, model_type)
    res_mean_l, res_mean_u = hosp_utils.bootstrap_mean(res, alpha=0.05)

    predictions = hosp_utils.create_double_list([], len(locations), len(groups))
    predictions_lower = hosp_utils.create_double_list([], len(locations), len(groups))
    predictions_upper = hosp_utils.create_double_list([], len(locations), len(groups))
    ground_truth = hosp_utils.create_double_list([], len(locations), len(groups))
    cur_truth = hosp_utils.create_double_list([], len(locations), len(groups))
    valid_weeks = []

    for l_idx in range(len(locations)):
        location = locations[l_idx]

        for epiweek in period:
            valid_weeks.append(epiweek)
            # iterate over groups
            for idx in range(len(groups)):
                group = groups[idx]

                if (epiweek, group, location) in data:
                    x_val, cur_y_val, y_val = preparation_loc.fetch(data, location, epiweek, lag, 
                                                                left_window, right_window, 
                                                                backfill_window, 
                                                                group)
                    pred = model.predict(x_val.T)
                    # record the results
                    predictions[l_idx][idx].append(pred)
                    cur_truth[l_idx][idx].append(cur_y_val)
                    ground_truth[l_idx][idx].append(y_val)
        # collapse predictions from 3d to 2d array   
        for idx in range(len(groups)):
            predictions[l_idx][idx] = np.concatenate(predictions[l_idx][idx], axis=0).squeeze()
            predictions_lower[l_idx][idx] = predictions[l_idx][idx] * (1 + res_mean_l)
            predictions_upper[l_idx][idx] = predictions[l_idx][idx] * (1 + res_mean_u)
    
    return valid_weeks, \
        predictions, predictions_lower, predictions_upper, \
        cur_truth, ground_truth, \
        res

def nowcast_report(path, data, 
                    locations, groups, 
                    time_period, 
                    left_window, backfill_window, 
                    mode, model_type):
    """
    generate a report for linear regression.

    Args:
        path - the path where tables and graphs are generated.
        data - the data source (included all epiweeks with all lags)
        time_period - a string representing the starting and ending epiweek
        left_window - the time period considered for linear regression: [cur_time-left_window, cur_time]
        backfill_window - the time period considered for backfill: [cur_time-window, cur_time]
        group - the current age group. (as a index from 0 to 4)
    
    Returns:
        rsq - the explained variance statistics of prediction
        mse - the mean squared error of prediction
    """
    rsq = hosp_utils.create_double_list(None, len(locations), len(groups))
    mse = hosp_utils.create_double_list(None, len(locations), len(groups))
    # run cross validation and calculate statistics
    if mode == 'prev':
        valid_weeks, \
        predictions, predictions_lower, predictions_upper, \
        cur_truth, ground_truth, \
        _ = \
        validate(data, 
                locations, groups,
                time_period, lag=0, 
                left_window=left_window, right_window=0, 
                backfill_window=backfill_window, 
                model_type=model_type)
    elif mode == 'all':
        valid_weeks, \
        predictions, predictions_lower, predictions_upper, \
        cur_truth, ground_truth, \
        res = \
        validate_all(data, 
                    locations, groups,
                    time_period, lag=0, 
                    left_window=left_window, right_window=0, 
                    backfill_window=backfill_window, 
                    model_type=model_type)

    for l_idx in range(len(locations)):
        location = locations[l_idx]

        for idx in range(len(groups)): 
            group = groups[idx]
            rsq[l_idx][idx] = metrics.explained_variance_score(
                                ground_truth[l_idx][idx], predictions[l_idx][idx])
            mse[l_idx][idx] = metrics.mean_squared_error(
                                ground_truth[l_idx][idx], predictions[l_idx][idx])
            # plot with epiweeks as ticks for x-axis
            inds = range(len(valid_weeks))
            week_ticks = [str(epiweek % 100) for epiweek in valid_weeks]
            # plot predicted rate, true rate, and current rate
            plt.figure()
            plt.plot(inds, predictions[l_idx][idx], label='predicted rate')
            plt.plot(inds, predictions_upper[l_idx][idx], label='predicted rate upper bound')
            plt.plot(inds, predictions_lower[l_idx][idx], label='predicted rate lower bound')
            plt.plot(inds, cur_truth[l_idx][idx], label='current rate')
            plt.plot(inds, ground_truth[l_idx][idx], label='true rate')
            plt.xticks(inds, week_ticks, rotation='vertical')
            plt.xlabel('weeks')
            plt.ylabel('hospitalized rate')
            plt.legend()
            plt.savefig(path + '/' + location + '/' + str(group) + '-' +
                        str(left_window) + '-' + str(backfill_window) + '.png', dpi=300)
            plt.close()
            # plot histogram for training residuals
            if mode == 'all':
                plt.figure()
                plt.hist(res, bins=50, facecolor='g')
                plt.xlabel('residuals')
                plt.ylabel('frequencies')
                plt.savefig(path + '/' + location + '/' + 'hist_' + str(group) + '-' +
                            str(left_window) + '-' + str(backfill_window) + '.png', dpi=300)
                plt.close()
        
    return rsq, mse

def plot_results(path, results, name, location, group, colormap):
    descriptions = ['Ages 0-4', 'Ages 5-17', 'Ages 18-49', 
                    'Ages 50-64', 'Ages 65+']
    length, width = results.shape
    fig, ax = plt.subplots()
    ax.imshow(results, cmap=colormap)

    ax.set_title(descriptions[group])
    ax.set_ylabel('window')
    ax.set_xlabel('backfill')
    ax.set_yticks(range(length))
    ax.set_xticks(range(width))

    for i in range(length):
        for j in range(i+1):
            ax.text(j, i, '{:.2f}'.format(results[i][j]), ha='center', va='center', color='w')
    
    fig.tight_layout()
    plt.savefig(path + '/' + location + '/' + name + '_results_' + str(group) + '.png', dpi=300)
    plt.close(fig)

def run_nowcast_experiment(data, location_groups, time_periods, groupings, max_window, mode, model_type):
    """
    run nowcasting experiments for different time periods.

    Args:
        data - the data source (included all epiweeks with all lags)
        time_periods - a list of time period (strings representing the starting and ending epiweek)
        max_window - the maximum time window considered in experiment
        max_backfill - the maximum backfill considered in experiment
    
    Returns:
        None
    """
    record_mat = np.full((max_window + 1, max_window + 1), -np.inf)

    for period in time_periods:
        # create the path for writing reports
        report_path = './nowcast/'+str(period)

        for state in hosp_utils.STATE_LIST:
            cur_path = report_path + '/' + state
            if not os.path.exists(cur_path):
                os.mkdir(cur_path)

        for locations in location_groups:
            for groups in groupings:
                mse_results = hosp_utils.create_double_list(record_mat, len(locations), len(groups))
                rsq_results = hosp_utils.create_double_list(record_mat, len(locations), len(groups))

                for window in tqdm(range(max_window + 1)):
                    for backfill in range(window + 1):
                        rsq, mse = nowcast_report(report_path, data, 
                                                    locations, groups, 
                                                    period, left_window=window, 
                                                    backfill_window=backfill, 
                                                    mode=mode, model_type=model_type)

                        for l_idx in range(len(locations)):
                            for idx in range(len(groups)):
                                mse_results[l_idx][idx][window][backfill] = mse[l_idx][idx]
                                rsq_results[l_idx][idx][window][backfill] = rsq[l_idx][idx]
                
                for l_idx in range(len(locations)):
                    location = locations[l_idx]

                    for idx in range(len(groups)):
                        group = groups[idx]
                        plot_results(report_path, mse_results[l_idx][idx], 
                                    'mse', location, group, 'Reds')
                        plot_results(report_path, rsq_results[l_idx][idx], 
                                    'rsq', location, group, 'Blues')

def predict(data, epiweek, 
            location_groups, groupings, 
            prediction_window, max_window, 
            max_backfill, 
            model_type):
    """
    perform prediction for specific epiweek.

    Args:
        data - the data source (included all epiweeks with all lags)
        epiweek - the epiweek for which we predict the final value
        max_window - the maximum time window considered in modeling
        max_backfill - the maximum backfill considered in modeling
    """
    # create cross-validation period
    year, week = utils.split_epiweek(epiweek)
    val_end = utils.join_epiweek(year-1, week)
    val_start = utils.add_epiweeks(val_end, -prediction_window)
    validate_period = hosp_utils.ravel(val_start, val_end)

    for locations in location_groups:
        for groups in groupings:
            preds = hosp_utils.create_double_list([], len(locations), len(groups))
            preds_upper = hosp_utils.create_double_list([], len(locations), len(groups))
            preds_lower = hosp_utils.create_double_list([], len(locations), len(groups))

            optimal_window = optimal_backfill = 0
            cur_rsq = 0

            # perform cross-validation and select the optimal hyperparameters
            for window in range(0, max_window + 1):
                for backfill in range(1, window + 2):
                    _, predictions, _, _, _, ground_truth, _ = validate(data, 
                                                            locations, groups, 
                                                            validate_period, lag=0, 
                                                            left_window=window, right_window=0, 
                                                            backfill_window=backfill,
                                                            model_type=model_type)
                    rsq = metrics.explained_variance_score(ground_truth, predictions)

                    if rsq > cur_rsq:
                        optimal_window = window
                        optimal_backfill = backfill
                        cur_rsq = rsq
            
            # use validation period (i.e. the latest) to train the model
            # and then make predictions
            X, Y = preparation_loc.prepare(data, 
                                            locations, groups, 
                                            validate_period, lag=0, 
                                            left_window=optimal_window, right_window=0, 
                                            backfill_window=optimal_backfill)
            model, res = train_model(X, Y, model_type)
            res_mean_l, res_mean_u = hosp_utils.bootstrap_mean(res, alpha=0.05)

            for l_idx in range(len(locations)):
                location = locations[l_idx]

                for idx in range(len(groups)):
                    group = groups[idx]
                    X_pred, _, _ = preparation_loc.fetch(data, 
                                                        location, group, 
                                                        epiweek, lag=0, 
                                                        left_window=optimal_window, right_window=0, 
                                                        backfill_window=optimal_backfill) 
                    pred = model.predict(X_pred)
                    pred_u, pred_l = pred * (1 + res_mean_u), pred * (1 + res_mean_l)
                    
                    preds[l_idx][idx].append(pred)
                    preds_upper[l_idx][idx].append(pred_u)
                    preds_lower[l_idx][idx].append(pred_l)
            
            for l_idx in range(len(locations)):
                for idx in range(len(groups)):
                    preds[l_idx][idx] = np.concatenate(preds[l_idx][idx], axis=0).squeeze()
                    preds_upper[l_idx][idx] = np.concatenate(preds_upper[l_idx][idx], axis=0).squeeze()
                    preds_lower[l_idx][idx] = np.concatenate(preds_lower[l_idx][idx], axis=0).squeeze()

    return preds, preds_upper, preds_lower
