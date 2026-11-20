"""Array-only ERD lateralization analysis (v0.3 H2)."""
from __future__ import annotations

import numpy as np
from scipy.signal import welch
from scipy.stats import spearmanr


def band_power(X, sfreq, band):
    """Integrate Welch PSD in ``band`` and return power in input-unit squared."""
    X = np.asarray(X, dtype=np.float64)
    if X.ndim != 3:
        raise ValueError("X must have shape trials x channels x samples")
    low, high = map(float, band)
    if not 0 < low < high < float(sfreq) / 2 + 1e-12:
        raise ValueError("band must lie inside (0, Nyquist)")
    freqs, density = welch(X, fs=float(sfreq), nperseg=int(sfreq), axis=-1)
    include = (freqs >= low) & (freqs <= high)
    if not include.any():
        raise ValueError("band contains no Welch frequency bins")
    width = float(freqs[1] - freqs[0]) if len(freqs) > 1 else float(sfreq)
    return np.sum(density[..., include], axis=-1) * width


def lateralization(X, y, groups, sfreq, ch_c3, ch_c4, band):
    """Return PRD-v0.3 LS values, keyed by ascending string subject id."""
    X, y, groups = np.asarray(X), np.asarray(y), np.asarray(groups)
    if len(X) != len(y) or len(y) != len(groups):
        raise ValueError("X, y, and groups lengths differ")
    if not (0 <= int(ch_c3) < X.shape[1] and 0 <= int(ch_c4) < X.shape[1]):
        raise ValueError("C3/C4 channel index is outside X")
    power = band_power(X, sfreq, band)
    output = {}
    for subject in np.unique(groups):
        mask = groups == subject
        left, right = mask & (y == 0), mask & (y == 1)
        if not left.any() or not right.any():
            raise ValueError(f"subject {subject} needs both left and right trials")
        c3_right, c3_left = power[right, ch_c3].mean(), power[left, ch_c3].mean()
        c4_right, c4_left = power[right, ch_c4].mean(), power[left, ch_c4].mean()
        values = np.array([c3_right, c3_left, c4_right, c4_left])
        if np.any(values <= 0) or not np.isfinite(values).all():
            raise ValueError(f"subject {subject} has non-positive or non-finite band power")
        output[str(subject)] = float(np.log(c3_right) - np.log(c3_left) - np.log(c4_right) + np.log(c4_left))
    return output


def lateralization_vs_accuracy(ls, acc):
    """Spearman LS/within-subject-accuracy association on shared subjects."""
    ls = {str(subject): value for subject, value in ls.items()}
    acc = {str(subject): value for subject, value in acc.items()}
    ids = sorted(set(ls) & set(acc), key=lambda value: int(value))
    if len(ids) < 2:
        return {"rho": float("nan"), "p": float("nan"), "n": len(ids)}
    result = spearmanr([ls[subject] for subject in ids], [acc[subject] for subject in ids])
    return {"rho": float(result.statistic), "p": float(result.pvalue), "n": len(ids)}
