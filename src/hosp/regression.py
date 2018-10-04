"""
The module applies linear regression for final-value prediction. Compatible with Python 3.4+.

Functionalities include:
    1. Cross-validation
    2. Report Generation
    3. Prediction
"""
# first party
import flu_contest.src.hosp.preparation as preparation
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

def train_model(X, Y, model_type='linear'):
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

def validate(data, time_period, lag, 
            left_window, right_window, backfill_window, 
            groups, model_type):
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
    start = groups[0]
    # initialize
    predictions = [[]] * len(groups)
    predictions_lower = [[]] * len(groups)
    predictions_upper = [[]] * len(groups)
    ground_truth = [[]] * len(groups)
    cur_truth = [[]] * len(groups)
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

        X, Y = preparation.prepare(data, [model_period], lag, 
                                    left_window, right_window, backfill_window, 
                                    groups)
        model, res = train_model(X, Y, model_type)   

        for group in groups:
            idx = group - start
            
            if (epiweek, group) in data:
                # obtain training and testing data
                x_val, cur_y_val, y_val = preparation.fetch(data, epiweek, lag, 
                                            left_window, right_window, backfill_window, 
                                            group)
                # get prediction
                res_mean_l, res_mean_u = hosp_utils.bootstrap_mean(res, alpha=0.05)
                pred = model.predict(x_val.T)
                pred_l, pred_u = pred * (1 + res_mean_l), pred * (1 + res_mean_u)
                # record the results
                
                cur_truth[idx].append(cur_y_val)
                ground_truth[idx].append(y_val)

                predictions[idx].append(pred)
                predictions_lower[idx].append(pred_l)
                predictions_upper[idx].append(pred_u)

            # collapse predictions from 3d to 2d array
            predictions[idx] = np.concatenate(predictions[idx], axis=0).squeeze()
            predictions_lower[idx] = np.concatenate(predictions_lower[idx], axis=0).squeeze()
            predictions_upper[idx] = np.concatenate(predictions_upper[idx], axis=0).squeeze()
            
    return valid_weeks, predictions, predictions_lower, predictions_upper, cur_truth, ground_truth, res

def validate_all(data, time_period, lag, 
                left_window, right_window, backfill_window, 
                groups, model_type):
    start_year, end_year = hosp_utils.get_season(time_period)
    period = hosp_utils.unravel(time_period)
    model_periods = []

    for year in range(2012, 2018):
        if year not in range(start_year, end_year + 1):
            start_week = year * 100 + 44
            end_week = (year + 1) * 100 + 17
            model_periods.append(hosp_utils.ravel(start_week, end_week))

    X, Y = preparation.prepare(data, model_periods, lag, 
                                left_window, right_window, backfill_window, 
                                groups)
    model, res = train_model(X, Y, model_type)
    res_mean_l, res_mean_u = hosp_utils.bootstrap_mean(res, alpha=0.05)

    predictions = [[]] * len(groups)
    predictions_lower = [[]] * len(groups)
    predictions_upper = [[]] * len(groups)
    ground_truth = [[]] * len(groups)
    cur_truth = [[]] * len(groups)
    valid_weeks = []
    start = groups[0]

    for epiweek in period:
        valid_weeks.append(epiweek)
        # iterate over groups
        for group in groups:
            idx = group - start

            if (epiweek, group) in data:
                x_val, cur_y_val, y_val = preparation.fetch(data, epiweek, lag, 
                                                            left_window, right_window, backfill_window, 
                                                            group)
                pred = model.predict(x_val.T)
                # record the results
                predictions[idx].append(pred)
                cur_truth[idx].append(cur_y_val)
                ground_truth[idx].append(y_val)
        
    for group in groups:
        idx = group - start
        # collapse predictions from 3d to 2d array
        predictions[idx] = np.concatenate(predictions[idx], axis=0).squeeze()
        predictions_lower[idx] = predictions[idx] * (1 + res_mean_l)
        predictions_upper[idx] = predictions[idx] * (1 + res_mean_u)
    
    return valid_weeks, predictions, predictions_lower, predictions_upper, cur_truth, ground_truth, res

def nowcast_report(path, data, time_period, 
                    left_window, backfill_window, 
                    groups, mode, model_type):
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
    start = groups[0]
    rsq = [None] * len(groups)
    mse = [None] * len(groups)
    # run cross validation and calculate statistics
    if mode == 'prev':
        valid_weeks, predictions, predictions_lower, predictions_upper, cur_truth, ground_truth, _ = \
        validate(data, time_period, lag=0, 
                left_window=left_window, right_window=0, backfill_window=backfill_window, 
                groups=groups, model_type=model_type)
    elif mode == 'all':
        valid_weeks, predictions, predictions_lower, predictions_upper, cur_truth, ground_truth, res = \
        validate_all(data, time_period, lag=0, 
                    left_window=left_window, right_window=0, backfill_window=backfill_window, 
                    groups=groups, model_type=model_type)

    for group in groups: 
        idx = group - start 

        rsq[idx] = metrics.explained_variance_score(ground_truth[idx], predictions[idx])
        mse[idx] = metrics.mean_squared_error(ground_truth[idx], predictions[idx])
        # plot with epiweeks as ticks for x-axis
        inds = range(len(valid_weeks))
        week_ticks = [str(epiweek % 100) for epiweek in valid_weeks]
        # plot predicted rate, true rate, and current rate
        plt.figure()
        plt.plot(inds, predictions[idx], label='predicted rate')
        plt.plot(inds, predictions_upper[idx], label='predicted rate upper bound')
        plt.plot(inds, predictions_lower[idx], label='predicted rate lower bound')
        plt.plot(inds, cur_truth[idx], label='current rate')
        plt.plot(inds, ground_truth[idx], label='true rate')
        plt.xticks(inds, week_ticks, rotation='vertical')
        plt.xlabel('weeks')
        plt.ylabel('hospitalized rate')
        plt.legend()
        plt.savefig(path + '/' + str(group) + '-' +
                    str(left_window) + '-' + str(backfill_window) + '.png', dpi=300)
        plt.close()
        # plot histogram for training residuals
        plt.figure()
        plt.hist(res, bins=50, facecolor='g')
        plt.xlabel('residuals')
        plt.ylabel('frequencies')
        plt.savefig(path + '/' + 'hist_' + str(group) + '-' +
                    str(left_window) + '-' + str(backfill_window) + '.png', dpi=300)
        plt.close()
        
    return rsq, mse

def plot_results(path, results, name, group, colormap):
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
    plt.savefig(path + '/' + name + '_results_' + str(group) + '.png', dpi=300)
    plt.close(fig)

def run_nowcast_experiment(data, time_periods, groupings, max_window, mode, model_type):
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

    for period in time_periods:
        # create the path for writing reports
        report_path = './nowcast/'+str(period)
        if not os.path.exists(report_path):
            os.mkdir(report_path)

        for groups in tqdm(groupings):
            start = groups[0]
            mse_results = [np.full((max_window + 1, max_window + 1), -np.inf) for _ in range(len(groups))]
            rsq_results = [np.full((max_window + 1, max_window + 1), -np.inf) for _ in range(len(groups))]

            for window in tqdm(range(max_window + 1)):
                for backfill in range(window + 1):
                    rsq, mse = nowcast_report(report_path, data, period,
                                                left_window=window, backfill_window=backfill, 
                                                groups=groups, mode=mode, model_type=model_type)
                    for group in groups:
                        idx = group - start
                        mse_results[idx][window][backfill] = mse[idx]
                        rsq_results[idx][window][backfill] = rsq[idx]
            
            for group in groups:
                idx = group - start
                plot_results(report_path, mse_results[idx], 'mse', group, 'Reds')
                plot_results(report_path, rsq_results[idx], 'rsq', group, 'Blues')

def predict(data, epiweek, prediction_window, max_window, max_backfill, model_type):
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
    preds = []

    for group in range(5):
        optimal_window = optimal_backfill = 0
        cur_rsq = 0

        # perform cross-validation and select the optimal hyperparameters
        for window in range(0, max_window + 1):
            for backfill in range(1, window + 2):
                _, predictions, ground_truth, _ = validate(data, validate_period, lag=0, 
                                    left_window=window, right_window=0, backfill_window=backfill,
                                    group=group, model_type=model_type)
                rsq = metrics.explained_variance_score(ground_truth, predictions)

                if rsq > cur_rsq:
                    optimal_window = window
                    optimal_backfill = backfill
                    cur_rsq = rsq
        
        # use validation period (i.e. the latest) to train the model
        # and then make predictions
        X, Y = preparation.prepare(data, validate_period, lag=0, left_window=optimal_window, right_window=0, 
                                    backfill_window=optimal_backfill, group=group)
        X_pred, _, _ = preparation.fetch(data, epiweek, lag=0, left_window=optimal_window, right_window=0, 
                                            backfill_window=optimal_backfill, group=group) 
        model = train_model(X, Y, model_type)
        pred = model.predict(X_pred)
        preds.append(pred)
    
    preds = np.concatenate(preds, axis=0).squeeze()
    return preds
