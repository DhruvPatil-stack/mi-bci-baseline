"""FROZEN synthetic data with a planted ERD (PRD section 7). Head chef, Phase 0.

Every output made from this data must carry the label "SYNTHETIC - NOT VALID".

Model per trial (unit uV, 64 channels, 480 samples at 160 Hz):
    x_c(t) = gain_s * ( pink_c(t) + a_c * A * sin(2 pi 10 t + phi) )   for c in {0, 1}
    x_c(t) = gain_s * pink_c(t)                                          for c >= 2
    pink_c : independent 1/f noise (power ~ 1/f), scaled to NOISE_STD_UV broadband std per trial.
    A      : OSC_AMP_UV * (1 + AMP_JITTER * N(0, 1)), clipped at 0.
    a_c    : sqrt(0.5) when the channel is desynchronized, 1 otherwise.
             class 0 (left)  -> channel 0 has 50 % less 10 Hz power.
             class 1 (right) -> channel 1 has 50 % less 10 Hz power.
    gain_s : per-subject gain, uniform in [0.5, 2.0].
"""
from __future__ import annotations

import numpy as np

from .contracts import N_CHANNELS, N_SAMPLES, SEED, SFREQ

ERD_FREQ_HZ = 10.0
ERD_POWER_RATIO = 0.5
NOISE_STD_UV = 10.0
OSC_AMP_UV = 30.0
AMP_JITTER = 0.10
GAIN_RANGE = (0.5, 2.0)


def _pink(rng, shape):
    n = shape[-1]
    spec = rng.standard_normal(shape[:-1] + (n // 2 + 1,)) + 1j * rng.standard_normal(shape[:-1] + (n // 2 + 1,))
    f = np.fft.rfftfreq(n, d=1.0 / SFREQ)
    scale = np.zeros_like(f)
    scale[1:] = 1.0 / np.sqrt(f[1:])
    x = np.fft.irfft(spec * scale, n=n, axis=-1)
    x -= x.mean(axis=-1, keepdims=True)
    x /= x.std(axis=-1, keepdims=True)
    return x * NOISE_STD_UV


def make_synthetic(n_subjects=8, trials_per_subject=40, seed=SEED):
    """Return X, y, groups, truth.

    X: (n_subjects * trials_per_subject, 64, 480) float32 uV. y: int64 in {0, 1}, balanced per subject.
    groups: int64 subject ids 1..n_subjects. truth: dict with the planted parameters.
    """
    if trials_per_subject % 2:
        raise ValueError("trials_per_subject must be even")
    rng = np.random.default_rng(seed)
    t = np.arange(N_SAMPLES) / SFREQ
    att = np.sqrt(ERD_POWER_RATIO)
    gains = rng.uniform(GAIN_RANGE[0], GAIN_RANGE[1], size=n_subjects)
    Xs, ys, gs = [], [], []
    for s in range(n_subjects):
        y = np.repeat([0, 1], trials_per_subject // 2)
        y = rng.permutation(y)
        X = _pink(rng, (trials_per_subject, N_CHANNELS, N_SAMPLES))
        for i, label in enumerate(y):
            for ch in (0, 1):
                amp = max(0.0, OSC_AMP_UV * (1.0 + AMP_JITTER * rng.standard_normal()))
                phi = rng.uniform(0, 2 * np.pi)
                a = att if ch == label else 1.0  # class 0 -> ch 0 desynchronized, class 1 -> ch 1
                X[i, ch] += a * amp * np.sin(2 * np.pi * ERD_FREQ_HZ * t + phi)
        Xs.append(gains[s] * X)
        ys.append(y)
        gs.append(np.full(trials_per_subject, s + 1))
    X = np.concatenate(Xs).astype(np.float32)
    y = np.concatenate(ys).astype(np.int64)
    groups = np.concatenate(gs).astype(np.int64)
    truth = {
        "erd_channel_by_class": {0: 0, 1: 1},
        "freq_hz": ERD_FREQ_HZ,
        "power_ratio": ERD_POWER_RATIO,
        "gains": {int(s + 1): float(g) for s, g in enumerate(gains)},
        "label": "SYNTHETIC - NOT VALID",
    }
    return X, y, groups, truth
