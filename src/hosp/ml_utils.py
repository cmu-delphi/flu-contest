from abc import abstractmethod
import cvxopt as cvx
import numpy as np
from numpy.linalg import matrix_rank

class QuantModel(object):

    def __init__(self, quantile):
        self.beta = None
        self.beta_0 = None
        self.weight = (1 - quantile) / quantile
    
    def _get_matrices(self, X, y):
        n, p = X.shape

        c = np.concatenate((np.zeros(p + 1), np.ones(n)), axis=0)
        c_vec = cvx.matrix(c)

        G_upper = np.concatenate((self.weight * X, self.weight * np.ones((n, 1)), -np.eye(n)), axis=1)
        G_lower = np.concatenate((-X, -np.ones((n, 1)), -np.eye(n)), axis=1)
        G_mat = cvx.matrix(np.concatenate((G_upper, G_lower), axis=0))

        h = np.concatenate((self.weight * y, -y), axis=0)
        h_vec = cvx.matrix(h)

        return c_vec, G_mat, h_vec

    @abstractmethod
    def fit(self, X, y):
        pass 
    
    @abstractmethod
    def predict(self, X):
        pass

class QuantLinear(QuantModel):

    def fit(self, X, y):
        cvx.solvers.options['show_progress'] = False
        _, p = X.shape
        c, G, h = self._get_matrices(X, y)

        solution = cvx.solvers.lp(c, G, h, options={'glpk': {'msg_lev': 'GLP_MSG_OFF'}})
        concat_beta = np.array(solution['x']).reshape(-1)
        self.beta = concat_beta[:p]
        self.beta_0 = concat_beta[p]
    
    def predict(self, X):
        return np.dot(X, self.beta) + self.beta_0

class QuantRidge(QuantModel):

    def __init__(self, quantile, alpha):
        super().__init__(quantile)
        self.alpha = alpha

    def fit(self, X, y):
        cvx.solvers.options['show_progress'] = False

        n, p = X.shape
        c, G, h = self._get_matrices(X, y)
        Q = cvx.matrix(np.diag(
                        np.concatenate(
                            (self.alpha * np.ones(p), np.zeros(n + 1)), axis=0)))

        solution = cvx.solvers.qp(Q, c, G, h)
        concat_beta = np.array(solution['x']).reshape(-1)
        self.beta = concat_beta[:p]
        self.beta_0 = concat_beta[p]
    
    def predict(self, X):
        return np.dot(X, self.beta) + self.beta_0
