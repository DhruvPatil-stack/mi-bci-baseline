"""Training-only covariance and neural-network motor imagery estimators."""
from __future__ import annotations

import numpy as np
from pyriemann.estimation import Covariances
from pyriemann.tangentspace import TangentSpace
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline

from bci.contracts import N_CHANNELS, SEED, load_config


def ts_lr():
    """OAS covariance, training-set tangent reference, then regularized LR."""
    cfg = load_config()
    return make_pipeline(
        Covariances(estimator=cfg["ts_covariance"]),
        TangentSpace(),
        LogisticRegression(**cfg["logreg"], random_state=SEED),
    )


class EEGNetLite(BaseEstimator, ClassifierMixin):
    """Small CPU EEGNet-style classifier with training-only channel scaling."""

    def __init__(self, seed=SEED):
        self.seed = seed

    def _network(self, cfg):
        import torch.nn as nn

        f1, depth, f2 = cfg["F1"], cfg["D"], cfg["F2"]
        k = cfg["kernel_length"]
        return nn.Sequential(
            nn.Conv2d(1, f1, (1, k), padding="same", bias=False),
            nn.BatchNorm2d(f1),
            nn.Conv2d(f1, f1 * depth, (N_CHANNELS, 1), groups=f1, bias=False),
            nn.BatchNorm2d(f1 * depth),
            nn.ELU(),
            nn.AvgPool2d((1, 4)),
            nn.Dropout(cfg["dropout"]),
            nn.Conv2d(f1 * depth, f1 * depth, (1, 16), padding="same", groups=f1 * depth, bias=False),
            nn.Conv2d(f1 * depth, f2, (1, 1), bias=False),
            nn.BatchNorm2d(f2),
            nn.ELU(),
            nn.AvgPool2d((1, 8)),
            nn.Dropout(cfg["dropout"]),
            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(f2, 2),
        )

    def _scaled(self, X):
        X = np.asarray(X, dtype=np.float32)
        if X.ndim != 3 or X.shape[1] != N_CHANNELS:
            raise ValueError(f"expected trials x {N_CHANNELS} channels x samples, got {X.shape}")
        return ((X - self.mean_[None, :, None]) / self.std_[None, :, None])[:, None]

    def fit(self, X, y):
        import torch
        from torch.utils.data import DataLoader, TensorDataset

        cfg = load_config()["eegnet"]
        torch.set_num_threads(cfg["n_threads"])
        torch.manual_seed(self.seed)
        torch.use_deterministic_algorithms(True)
        X = np.asarray(X, dtype=np.float32)
        y = np.asarray(y, dtype=np.int64)
        if set(np.unique(y)) != {0, 1}:
            raise ValueError("fit needs both labels 0 and 1")
        self.classes_ = np.array([0, 1])
        self.mean_ = X.mean(axis=(0, 2), dtype=np.float64).astype(np.float32)
        self.std_ = X.std(axis=(0, 2), dtype=np.float64).astype(np.float32)
        self.std_ = np.maximum(self.std_, 1e-6)
        data = TensorDataset(torch.from_numpy(self._scaled(X)), torch.from_numpy(y))
        loader = DataLoader(data, batch_size=cfg["batch_size"], shuffle=True,
                            generator=torch.Generator().manual_seed(self.seed))
        self.model_ = self._network(cfg).cpu()
        optimizer = torch.optim.Adam(self.model_.parameters(), lr=cfg["learning_rate"])
        for _ in range(cfg["epochs"]):
            self.model_.train()
            for xb, yb in loader:
                optimizer.zero_grad()
                loss = torch.nn.functional.cross_entropy(self.model_(xb), yb)
                loss.backward()
                optimizer.step()
        self.model_.eval()
        return self

    def predict_proba(self, X):
        import torch

        self.model_.eval()
        with torch.no_grad():
            scores = self.model_(torch.from_numpy(self._scaled(X)))
            return torch.softmax(scores, dim=1).cpu().numpy()

    def predict(self, X):
        return self.predict_proba(X).argmax(axis=1)


REGISTRY = {"ts_lr": ts_lr, "eegnet_lite": lambda: EEGNetLite()}
