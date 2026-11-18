"""Offline probability feedback for a single motor-imagery epoch."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from bci.contracts import load_config


def simulate_feedback(estimator, trial, sfreq, out_png):
    """Return window-end times and right-fist probabilities; save a feedback plot."""
    import matplotlib.pyplot as plt

    cfg = load_config()["feedback"]
    trial = np.asarray(trial, dtype=np.float32)
    if trial.ndim != 2 or sfreq <= 0:
        raise ValueError("trial must be channels x samples, with positive sfreq")
    window = round(cfg["window_s"] * sfreq)
    step = round(cfg["step_s"] * sfreq)
    if window < 1 or step < 1 or trial.shape[1] < window:
        raise ValueError("trial is too short for the configured window")
    starts = range(0, trial.shape[1] - window + 1, step)
    windows = np.stack([trial[:, i:i + window] for i in starts])
    times = np.array([(i + window) / sfreq for i in starts], dtype=float)
    p_right = np.asarray(estimator.predict_proba(windows), dtype=float)[:, 1]
    if p_right.shape != times.shape or not np.all(np.isfinite(p_right)):
        raise ValueError("estimator returned invalid probabilities")
    for t, p in zip(times, p_right):
        filled = int(round(float(p) * 20))
        print(f"{t:5.2f} s  right [{('#' * filled):<20}] {p:.2f}")
    out = Path(out_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 3))
    ax.plot(times, p_right, marker="o")
    ax.fill_between(times, 0, p_right, alpha=0.2)
    ax.set(xlabel="Time after epoch start (s)", ylabel="P(right fist)",
           ylim=(0, 1), xlim=(0, trial.shape[1] / sfreq))
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    plt.close(fig)
    return times, p_right
