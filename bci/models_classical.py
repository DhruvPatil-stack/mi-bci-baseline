"""Classical models (C2): csp_lda and fbcsp_lr. All settings come from bci/config.yaml.

Both are scikit-learn estimators (clone works). Band-pass filtering is stateless (zero-phase Butterworth),
all learned state (CSP filters, scaler, classifier) is fitted inside fit().
v0.3 (S1): BandPass.transform goes through bci.cache (stateless filter output only, FILTER CACHE CONTRACT);
mne CSP gets rank=config csp_rank; factories read the sampling rate from contracts.dataset_spec().
"""
from __future__ import annotations

import mne
import numpy as np
from mne.decoding import CSP
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import StandardScaler

from bci import cache
from bci.contracts import SEED, dataset_spec, load_config

mne.set_log_level("ERROR")


class BandPass(BaseEstimator, TransformerMixin):
    """Stateless zero-phase Butterworth band-pass over the last axis. Casts to float64."""

    def __init__(self, low, high, fs=None, order=4):
        self.low = low
        self.high = high
        self.fs = fs
        self.order = order

    def fit(self, X, y=None):
        return self

    def transform(self, X):
        # Same sosfiltfilt math with the cache on or off ($BCI_FILTER_CACHE read at call time, gate G8).
        fs = dataset_spec()["sfreq"] if self.fs is None else self.fs  # fs=None: active dataset's rate
        return cache.filtered(X, self.low, self.high, fs, self.order)


def _csp(n_components, reg, rank):
    # rank = config csp_rank ("full"): no per-fit SVD rank estimate (3.5 s of 6.3 s in v0.2, docs/DECISIONS.md).
    return CSP(n_components=n_components, reg=reg, log=True, rank=rank)


def make_csp_lda():
    cfg = load_config()
    lo, hi = cfg["csp_band"]
    fs = dataset_spec()["sfreq"]
    return Pipeline([
        ("bandpass", BandPass(low=lo, high=hi, fs=fs, order=cfg["filter_order"])),
        ("csp", _csp(cfg["csp_components"], cfg["csp_reg"], cfg["csp_rank"])),
        ("lda", LinearDiscriminantAnalysis()),
    ])


def make_fbcsp_lr():
    cfg = load_config()
    fs = dataset_spec()["sfreq"]
    branches = []
    for i, (lo, hi) in enumerate(cfg["fbcsp_bands"]):
        branches.append((f"band{i}", Pipeline([
            ("bandpass", BandPass(low=lo, high=hi, fs=fs, order=cfg["filter_order"])),
            ("csp", _csp(cfg["fbcsp_components"], cfg["csp_reg"], cfg["csp_rank"])),
        ])))
    return Pipeline([
        ("features", FeatureUnion(branches)),
        ("scale", StandardScaler()),
        ("lr", LogisticRegression(C=cfg["logreg"]["C"], max_iter=cfg["logreg"]["max_iter"], random_state=SEED)),
    ])


REGISTRY = {"csp_lda": make_csp_lda, "fbcsp_lr": make_fbcsp_lr}
