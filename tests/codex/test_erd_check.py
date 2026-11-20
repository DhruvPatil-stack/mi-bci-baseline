"""Extra H2 input-validation coverage beyond locked G12."""
import numpy as np
import pytest

from bci.erd_check import band_power, lateralization


def test_band_power_rejects_an_out_of_range_band():
    with pytest.raises(ValueError, match="Nyquist"):
        band_power(np.zeros((2, 3, 160)), 160, (8, 81))


def test_lateralization_needs_both_classes_for_each_subject():
    X = np.ones((3, 2, 160))
    with pytest.raises(ValueError, match="both left and right"):
        lateralization(X, np.array([0, 0, 0]), np.array([1, 1, 1]), 160, 0, 1, (8, 13))
