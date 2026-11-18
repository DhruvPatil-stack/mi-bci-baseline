"""A synthetic monotone estimator establishes the feedback class direction."""
import numpy as np

from bci.feedback_sim import simulate_feedback


class MeanEstimator:
    def predict_proba(self, X):
        p = np.clip(np.mean(X[:, 0], axis=1) / 10, 0, 1)
        return np.column_stack([1 - p, p])


def test_right_probability_and_time_axis(tmp_path):
    trial = np.zeros((64, 480), dtype=np.float32)
    trial[0, 240:] = 10
    t, p = simulate_feedback(MeanEstimator(), trial, 160, tmp_path / "feedback.png")
    assert np.array_equal(t, np.arange(1, 3.01, 0.25))
    assert p[0] == 0 and p[-1] == 1
