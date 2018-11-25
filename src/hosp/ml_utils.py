# first party
from flu_contest.src.hosp.constants import *
# thrid party
from abc import abstractmethod

from sklearn.linear_model import LinearRegression, Ridge
from sklearn.ensemble import GradientBoostingRegressor

import bootstrapped.bootstrap as bs
import bootstrapped.stats_functions as stat_f

import cvxopt as cvx
import numpy as np

class RegModel(object):

    def __init__(self, quantile):
        self.quantile = quantile
        self.res = None
        self.model = None
    
    @staticmethod
    def _add_intercept(X):
        n, _ = X.shape
        X = np.concatenate((X, np.ones(n, 1)), axis=1)
    
    def _get_quantile(self, residuals):
        sig_level = (1 - max(1 - self.quantile, self.quantile)) * 2
        interval = bs.bootstrap(residuals, stat_f.mean, alpha=sig_level)

        if self.quantile >= 0.5:
            return interval.upper_bound
        else:
            return interval.lower_bound
    
    def fit(self, X, y):
        self.model.fit(X, y)
        train_res = y - self.model.predict(X)
        self.res = self._get_quantile(train_res)
    
    def predict(self, X):
        return self.model.predict(X) + self.res

class RegLinear(RegModel):

    def __init__(self, quantile):
        super().__init__(quantile)
        self.model = LinearRegression()

class RegRidge(RegModel):

    def __init__(self, quantile):
        super().__init__(quantile)
        self.model = Ridge(alpha=RIDGE_ALPHA)

class RegGBDT(RegModel):

    def __init__(self, quantile):
        super().__init__(quantile)
        self.model = GradientBoostingRegressor(loss='ls', n_estimators=ESTIMATIORS, 
                                                max_depth=DEPTH)

class QuantModel(object):

    def __init__(self, quantile):
        self.beta = None
        self.beta_0 = None
        self.weight = (1 - quantile) / quantile

    def _get_matrices(self, X, y):
        n, p = X.shape
        c = np.concatenate((np.zeros(p + 1), np.ones(n)), axis=0)

        G_upper = np.concatenate((self.weight * X, self.weight * np.ones((n, 1)), 
                                -np.eye(n)), axis=1)
        G_lower = np.concatenate((-X, -np.ones((n, 1)), -np.eye(n)), axis=1)
        G = np.concatenate((G_upper, G_lower), axis=0)

        h = np.concatenate((self.weight * y, -y), axis=0)

        return c, G, h
    
    @staticmethod
    def _get_interactive_matrices(upper_model, mid_model, lower_model,
                                    X_train, y_train):
        n_train, p = X_train.shape
        train_zero_mat = np.zeros((2 * n_train, n_train + p + 1))

        test_mat = np.eye(p + 1)
        test_small_zero_mat = np.zeros((p + 1, n_train))
        test_large_zero_mat = np.zeros((p + 1, n_train + p + 1))

        upper_c, upper_G, upper_h = upper_model._get_matrices(X_train, y_train)
        mid_c, mid_G, mid_h = mid_model._get_matrices(X_train, y_train)
        lower_c, lower_G, lower_h = lower_model._get_matrices(X_train, y_train)

        upper_G = np.concatenate((upper_G, train_zero_mat, train_zero_mat), axis=1)
        mid_G = np.concatenate((train_zero_mat, mid_G, train_zero_mat), axis=1)
        lower_G = np.concatenate((train_zero_mat, train_zero_mat, lower_G), axis=1)

        upper_test_mat = np.concatenate((-test_mat, test_small_zero_mat,
                                        test_mat, test_small_zero_mat,
                                        test_large_zero_mat), axis=1)
        lower_test_mat = np.concatenate((test_large_zero_mat,
                                        -test_mat, -test_small_zero_mat,
                                        test_mat, test_small_zero_mat), axis=1)
        
        c = np.concatenate((upper_c, mid_c, lower_c), axis=0)
        G = np.concatenate((upper_G, mid_G, lower_G, upper_test_mat, lower_test_mat), axis=0)
        h = np.concatenate((upper_h, mid_h, lower_h, -EPS * np.ones(2 * (p + 1))), axis=0)

        return cvx.matrix(c), cvx.matrix(G), cvx.matrix(h)
    
    @staticmethod
    def _assign_solutions(upper_model, mid_model, lower_model,
                        solution, n, p):
        concat_beta = np.array(solution['x']).reshape(-1)

        upper_lb, upper_ub = 0, p
        mid_lb, mid_ub = n + p + 1, (n + p + 1) + p
        lower_lb, lower_ub = (n + p + 1) * 2, (n + p + 1) * 2 + p

        upper_model.beta = concat_beta[upper_lb: upper_ub]
        upper_model.beta_0 = concat_beta[upper_ub]

        mid_model.beta = concat_beta[mid_lb: mid_ub]
        mid_model.beta_0 = concat_beta[mid_ub]

        lower_model.beta = concat_beta[lower_lb: lower_ub]
        lower_model.beta_0 = concat_beta[lower_ub]

class QuantLinear(QuantModel):

    @staticmethod
    def fit(upper_model, mid_model, lower_model, X_train, y_train):
        n, p = X_train.shape
        c, G, h = QuantLinear._get_interactive_matrices(upper_model, mid_model, lower_model, 
                                                        X_train, y_train)
        solution = cvx.solvers.lp(c, G, h, solver='glpk', 
                                    options={'glpk': {'msg_lev': 'GLP_MSG_OFF'}})
        QuantLinear._assign_solutions(upper_model, mid_model, lower_model, 
                                        solution, n, p)
    
    def predict(self, X):
        return np.dot(X, self.beta) + self.beta_0

class QuantRidge(QuantModel):

    @staticmethod
    def fit(upper_model, mid_model, lower_model, X_train, y_train):
        cvx.solvers.options['show_progress'] = False

        n, p = X_train.shape
        c, G, h = QuantRidge._get_interactive_matrices(upper_model, mid_model, lower_model,
                                                        X_train, y_train)
        q = np.concatenate((RIDGE_ALPHA * np.ones(p), np.zeros(n + 1),
                            RIDGE_ALPHA * np.ones(p), np.zeros(n + 1), 
                            RIDGE_ALPHA * np.ones(p), np.zeros(n + 1)), axis=0)
        Q = cvx.matrix(np.diag(q))
        solution = cvx.solvers.qp(Q, c, G, h)
        QuantRidge._assign_solutions(upper_model, mid_model, lower_model, 
                                    solution, n, p)
    
    def predict(self, X):
        return np.dot(X, self.beta) + self.beta_0

class QuantGBDT(object):
    
    def __init__(self, quantile):
        self.model = GradientBoostingRegressor(loss='quantile', alpha=quantile, 
                    n_estimators=ESTIMATIORS, max_depth=DEPTH)
    
    def fit(self, X, y):
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)
