"""Classical models (C2): csp_lda and fbcsp_lr. All settings come from bci/config.yaml.

Both are scikit-learn estimators (clone works). Band-pass filtering is stateless (zero-phase Butterworth),
all learned state (CSP filters, scaler, classifier) is fitted inside fit().
"""
from __future__ import annotations

import mne
import numpy as np
from mne.decoding import CSP
from scipy.signal import butter, sosfiltfilt
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler

from bci.contracts import SEED, SFREQ, load_config

mne.set_log_level("ERROR")


class BandPass(BaseEstimator, TransformerMixin):
    """Stateless zero-phase Butterworth band-pass over the last axis. Casts to float64."""

    def __init__(self, low, high, fs=SFREQ, order=4):
        self.low = low
        self.high = high
        self.fs = fs
        self.order = order

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        sos = butter(self.order, [self.low, self.high], btype="bandpass", fs=self.fs, output="sos")
        return sosfiltfilt(sos, np.asarray(X, dtype=np.float64), axis=-1)


def _csp(n_components, reg):
    return CSP(n_components=n_components, reg=reg, log=True)


def make_csp_lda():
    cfg = load_config()
    lo, hi = cfg["csp_band"]
    return Pipeline([
        ("bandpass", BandPass(low=lo, high=hi, fs=SFREQ, order=cfg["filter_order"])),
        ("csp", _csp(cfg["csp_components"], cfg["csp_reg"])),
        ("lda", LinearDiscriminantAnalysis()),
    ])


def make_fbcsp_lr():
    cfg = load_config()
    branches = []
    for i, (lo, hi) in enumerate(cfg["fbcsp_bands"]):
        branches.append((f"band{i}", Pipeline([
            ("bandpass", BandPass(low=lo, high=hi, fs=SFREQ, order=cfg["filter_order"])),
            ("csp", _csp(cfg["fbcsp_components"], cfg["csp_reg"])),
        ])))
    return Pipeline([
        ("features", FeatureUnion(branches)),
        ("scale", StandardScaler()),
        ("lr", LogisticRegression(C=cfg["logreg"]["C"], max_iter=cfg["logreg"]["max_iter"], random_state=SEED)),
    ])


REGISTRY = {"csp_lda": make_csp_lda, "fbcsp_lr": make_fbcsp_lr}
