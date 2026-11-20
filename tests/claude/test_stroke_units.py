"""Offline unit tests for bci.data_stroke (ticket S4). No EDF data needed; tests/locked/test_stroke.py covers real data."""
from __future__ import annotations

import zipfile

import numpy as np
import pytest

from bci import data_stroke as ds

MI, TRIAL, N = 2000, 4000, 40


def _code_stream(offsets, n=N):
    """Marker codes like the EDF files: 1 at each 4000-sample epoch start, 2 at the given offset, 3 MI later."""
    code = np.zeros(n * TRIAL, dtype=np.int64)
    for k, off in enumerate(offsets):
        code[k * TRIAL] = 1
        code[k * TRIAL + off] = 2
        code[k * TRIAL + off + MI + 1] = 3
    return code


def test_label_map_left_0_right_1():
    np.testing.assert_array_equal(ds.labels_from_trial_type([1, 2, 2, 1]), [0, 1, 1, 0])
    with pytest.raises(ValueError):
        ds.labels_from_trial_type([1, 3])


def test_marker_codes_ignore_non_integer_values():
    code, nonint = ds.marker_codes([0, 1, 0, 2.8147, 2.8147, 0, 3, 1.1864, 0.1207])
    np.testing.assert_array_equal(code, [0, 1, 0, 0, 0, 0, 3, 0, 0])
    assert nonint.sum() == 4
    with pytest.raises(ValueError):
        ds.marker_codes([0, 4, 0])


def test_mi_onsets_regular_and_short_instruction_trials():
    offsets = [1003] * N
    offsets[5] = 1  # instruction and MI markers one sample apart (seen in 23 real trials)
    on = ds.mi_onsets(_code_stream(offsets), N, MI, TRIAL)
    np.testing.assert_array_equal(on, np.arange(N) * TRIAL + np.array(offsets))


def test_mi_onsets_reject_code2_without_break():
    code = _code_stream([1003] * N)
    code[39 * TRIAL + 3800:39 * TRIAL + 3900] = 2  # stuck tail after the last break
    code[24 * TRIAL + 3005] = 2                    # stray code 2 followed by the next trial's code 1
    on = ds.mi_onsets(code, N, MI, TRIAL)
    np.testing.assert_array_equal(on, np.arange(N) * TRIAL + 1003)


def test_mi_onsets_raise_on_missing_or_misplaced_onset():
    code = _code_stream([1003] * N)
    code[7 * TRIAL + 1003] = 0
    with pytest.raises(ValueError, match="39 motor-imagery onsets"):
        ds.mi_onsets(code, N, MI, TRIAL)
    code = _code_stream([1003] * N)
    with pytest.raises(ValueError, match="one per"):
        ds.mi_onsets(code, N, MI, TRIAL // 2)


def test_duplicate_patients_left_out_by_default_and_rejected_explicitly():
    default = ds._subject_list(None, include_duplicates=False)
    assert not set(default) & set(ds.DUPLICATE_EDF)
    assert len(default) == len(ds.SCFG["subjects"]) - len(ds.DUPLICATE_EDF)
    with pytest.raises(ValueError, match="DUPLICATE_EDF"):
        ds._subject_list([4, 5], include_duplicates=False)
    assert ds._subject_list([4, 5], include_duplicates=True) == [4, 5]
    assert len(ds._subject_list(None, include_duplicates=True)) == len(ds.SCFG["subjects"])


def test_safe_extract_rejects_unexpected_member_names(tmp_path):
    zpath = tmp_path / "edffile.zip"
    with zipfile.ZipFile(zpath, "w") as zf:
        zf.writestr("edffile/sub-01/eeg/sub-01_task-motor-imagery_eeg.edf", b"x")
        zf.writestr("../outside.txt", b"x")
    with pytest.raises(ValueError, match="unexpected member names"):
        ds._safe_extract(zpath, tmp_path)
    assert not (tmp_path.parent / "outside.txt").exists()
