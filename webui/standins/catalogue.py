"""STAND-IN for ModelsApp (MLE-F-030..031, owned by the ML Engineer).

The WebUI only reads ``ALGORITHMS``. Replace it with ModelsApp's catalogue and
keep ``(key, label, task)``. Names are the ones SRS MLE-F-030/031 require.
"""
from collections import namedtuple

Algorithm = namedtuple("Algorithm", "key label task")

ALGORITHMS = [
    Algorithm("logistic_regression", "Logistic Regression", "classification"),
    Algorithm("decision_tree", "Decision Tree", "classification"),
    Algorithm("random_forest", "Random Forest", "classification"),
    Algorithm("knn", "K-Nearest Neighbours", "classification"),
    Algorithm("svm", "Support Vector Machine", "classification"),
    Algorithm("linear_regression", "Linear Regression", "regression"),
    Algorithm("decision_tree_regressor", "Decision Tree Regressor", "regression"),
    Algorithm("random_forest_regressor", "Random Forest Regressor", "regression"),
]
BY_KEY = {a.key: a for a in ALGORITHMS}
