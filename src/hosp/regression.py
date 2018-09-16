"""
The module applies linear regression for final-value prediction. Compatible with both Python 2 and 3.

Functionalities include:
    1. Cross-validation
    2. Report Generation for Cross-validation
    3. Prediction
"""
from __future__ import division, print_function
# first party
import flu_contest.src.hosp.preparation as preparation
import flu_contest.src.hosp.hosp_utils as hosp_utils 
import utils.epiweek as utils
# third party
import os
import pickle
import numpy as np
import matplotlib.pyplot as plt
import sklearn.metrics as metrics
from sklearn.svm import SVR

def regression(X, Y, X_val):
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
    model = SVR(kernel='linear', epsilon=5e-3, C=2.0)
    # fit the training data and predict for testing data
    model.fit(X, Y)
    Y_pred = model.predict(X_val.T)

    return Y_pred

def validate(data, time_period, lag, left_window, right_window, backfill_window, group):
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
    predictions = []
    ground_truth = []
    cur_truth = []
    valid_weeks = []

    for epiweek in period:
        # for each epiweek with current lag, 
        # get data from the latest available one-year period to train SVR regression
        year, week = utils.split_epiweek(epiweek)
        start = utils.add_epiweeks(utils.join_epiweek(year-2, week), lag)
        end = utils.add_epiweeks(utils.join_epiweek(year-1, week), lag)
        model_period = hosp_utils.ravel(start, end)

        if (epiweek, group) in data:
            # obtain training and testing data
            X, Y = preparation.prepare(data, model_period, lag, left_window, right_window, 
                                        backfill_window, group)
            x_val, cur_y_val, y_val = preparation.fetch(data, epiweek, lag, left_window, right_window, 
                                        backfill_window, group)
            # get prediction
            pred = regression(X, Y, x_val)
            valid_weeks.append(epiweek)
            predictions.append(pred)
            cur_truth.append(cur_y_val)
            ground_truth.append(y_val)
    # collapse predictions from 3d to 2d array
    predictions = np.concatenate(predictions, axis=0).squeeze()
    return valid_weeks, predictions, cur_truth, ground_truth

def backcast_report(path, data, time_period, lag, backfill_window, group):
    """
    generate reports for backcasting.

    Args:
        path - the directory path for report.
        data - the data source (included all epiweeks with all lags)
        time_period - a string representing the starting and ending epiweek
        lag - the current time lag.
        backfill_window - the backfill period: [cur_time-window, cur_time]
        group - the current age group. (as a index from 0 to 4)
    
    Returns:
        rsq - the explained variance statistics of prediction
        mse - the mean squared error between ground truth and prediction.
    """
    # run cross validation and calculate statistics
    valid_weeks, predictions, cur_truth, ground_truth = validate(data, time_period, lag=lag, 
                                        left_window=0, right_window=0,
                                        backfill_window=backfill_window, group=group)
    rsq = metrics.explained_variance_score(ground_truth, predictions)
    mse = metrics.mean_squared_error(ground_truth, predictions)
    # plot with epiweeks as ticks for x-axis
    inds = range(len(valid_weeks))
    week_ticks = [str(epiweek%100) for epiweek in valid_weeks]
    # plot and save the figures
    plt.figure()
    plt.plot(inds, predictions, label='predicted rate')
    plt.plot(inds, cur_truth, label='current rate')
    plt.plot(inds, ground_truth, label='true rate')
    plt.xticks(inds, week_ticks, rotation='vertical')
    plt.xlabel('weeks')
    plt.ylabel('hospitalized rate')
    plt.legend()
    plt.savefig(path+'/'+str(group)+'-'+str(lag)+'-'+str(backfill_window)+'.png')

    return rsq, mse

def nowcast_report(path, data, time_period, left_window, backfill_window, group):
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
    # run cross validation and calculate statistics
    valid_weeks, predictions, cur_truth, ground_truth = validate(data, time_period, lag=1, 
                                        left_window=left_window, right_window=0,
                                        backfill_window=backfill_window, group=group)
    rsq = metrics.explained_variance_score(ground_truth, predictions)
    mse = metrics.mean_squared_error(ground_truth, predictions)
    # plot with epiweeks as ticks for x-axis
    inds = range(len(valid_weeks))
    week_ticks = [str(epiweek%100) for epiweek in valid_weeks]
    # plot and save the figures
    plt.figure()
    plt.plot(inds, predictions, label='predicted rate')
    plt.plot(inds, cur_truth, label='current rate')
    plt.plot(inds, ground_truth, label='true rate')
    plt.xticks(inds, week_ticks, rotation='vertical')
    plt.xlabel('weeks')
    plt.ylabel('hospitalized rate')
    plt.legend()
    plt.savefig(path+'/'+str(group)+'-'+str(left_window)+'-'+str(backfill_window)+'.png')

    return rsq, mse

def run_backcast_experiment(data, time_periods, max_lag):
    """
    run backcasting experiments for different time periods.

    Args:
        data - the data source (included all epiweeks with all lags)
        time_periods - a list of time period (strings representing the starting and ending epiweek)
        max_lag - the maximum time lag considered in experiment
    
    Returns:
        None
    """
    for period in time_periods:
        # create the path for writing reports
        report_path = './backcast/'+str(period)
        if not os.path.exists(report_path):
            os.mkdir(report_path)
        # create table and write headers
        f = open(report_path+'/results.csv', mode='w')
        f.write('group,lag,backfill_window,rsq,mse'+'\n') 

        # report for each combination of backfill window and lags
        for group in range(5):
            for l in range(1, max_lag+1):
                for window in range(1, l+1):
                    rsq, mse = backcast_report(report_path, data, period, 
                                                lag=l, backfill_window=window, group=group)
                    # write to table
                    f.write(str(group)+','+str(l)+','+str(window)+','+\
                            '{:.3f}'.format(rsq)+','+'{:.3f}'.format(mse)+'\n')
        # close table
        f.close()

def run_nowcast_experiment(data, time_periods, max_window, max_backfill):
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
        # create table
        f = open(report_path+'/results.csv', mode='w')
        f.write('group,left_window,backfill_window,rsq,mse'+'\n') 
        # report for each combination of backfill window and lags
        for group in range(5):
            for window in range(0, max_window+1):
                for backfill in range(1, window+2):
                    rsq, mse = nowcast_report(report_path, data, period, 
                                left_window=window, backfill_window=backfill, group=group)
                    # write to table
                    f.write(str(group)+','+str(window)+','+str(backfill)+','+\
                            '{:.3f}'.format(rsq)+','+'{:.3f}'.format(mse)+'\n')
        # close table
        f.close()

def predict(data, epiweek, prediction_window, max_window, max_backfill):
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
        for window in range(0, max_window+1):
            for backfill in range(1, window+2):
                _, predictions, ground_truth, _ = validate(data, validate_period, lag=1, 
                                    left_window=window, right_window=0, backfill_window=backfill,
                                    group=group)
                rsq = metrics.explained_variance_score(ground_truth, predictions)

                if rsq > cur_rsq:
                    optimal_window = window
                    optimal_backfill = backfill
                    cur_rsq = rsq
        
        # use validation period (i.e. the latest) to train the model
        # and then make predictions
        X, Y = preparation.prepare(data, validate_period, lag=1, left_window=optimal_window, right_window=0, 
                            backfill_window=optimal_backfill, group=group)
        X_pred, _, _ = preparation.fetch(data, epiweek, lag=1, left_window=optimal_window, right_window=0, 
                            backfill_window=optimal_backfill, group=group) 
        pred = regression(X, Y, X_pred)
        preds.append(pred)
    
    preds = np.concatenate(preds, axis=0).squeeze()
    return preds
