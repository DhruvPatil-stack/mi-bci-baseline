"""FROZEN channel map (PRD_v0.3 section 7 item 3). Head chef, Phase 0. No cook edits this file.

PhysioNet EEGMMI channel order as stored in the EDF files and as kept by bci.data (all 64 EEG channels, no
reordering), after mne.datasets.eegbci.standardize(raw). Verified on S001R04.edf with MNE 1.13.2
(docs/DECISIONS.md, "v0.3 channel indices"): raw name 'C3..' -> 'C3' at index 8, 'Cz..' -> 'Cz' at index 10,
'C4..' -> 'C4' at index 12.

Stroke dataset (Liu et al. 2024) channel order: task-motor-imagery_channels.tsv on figshare (29 EEG rows,
then HEOL, VEOR). The loader keeps the 29 EEG channels in that order (docs/STROKE_DATASET.md).
"""
from __future__ import annotations

PHYSIONET_CHANNELS = (
    "FC5", "FC3", "FC1", "FCz", "FC2", "FC4", "FC6", "C5", "C3", "C1", "Cz", "C2", "C4", "C6",
    "CP5", "CP3", "CP1", "CPz", "CP2", "CP4", "CP6", "Fp1", "Fpz", "Fp2", "AF7", "AF3", "AFz", "AF4", "AF8",
    "F7", "F5", "F3", "F1", "Fz", "F2", "F4", "F6", "F8", "FT7", "FT8", "T7", "T8", "T9", "T10", "TP7", "TP8",
    "P7", "P5", "P3", "P1", "Pz", "P2", "P4", "P6", "P8", "PO7", "PO3", "POz", "PO4", "PO8", "O1", "Oz", "O2",
    "Iz",
)
CH_C3 = 8
CH_CZ = 10
CH_C4 = 12

STROKE_CHANNELS = (
    "FP1", "FP2", "Fz", "F3", "F4", "F7", "F8", "FCz", "FC3", "FC4", "FT7", "FT8", "Cz", "C3", "C4", "T3", "T4",
    "CP3", "CP4", "TP7", "TP8", "Pz", "P3", "P4", "T5", "T6", "Oz", "O1", "O2",
)
STROKE_CH_C3 = STROKE_CHANNELS.index("C3")  # 13
STROKE_CH_CZ = STROKE_CHANNELS.index("Cz")  # 12
STROKE_CH_C4 = STROKE_CHANNELS.index("C4")  # 14

CHANNELS = {"physionet": PHYSIONET_CHANNELS, "stroke": STROKE_CHANNELS}
MOTOR = {"physionet": {"C3": CH_C3, "Cz": CH_CZ, "C4": CH_C4},
         "stroke": {"C3": STROKE_CH_C3, "Cz": STROKE_CH_CZ, "C4": STROKE_CH_C4}}

assert len(PHYSIONET_CHANNELS) == 64 and len(set(PHYSIONET_CHANNELS)) == 64
assert PHYSIONET_CHANNELS[CH_C3] == "C3" and PHYSIONET_CHANNELS[CH_CZ] == "Cz" and PHYSIONET_CHANNELS[CH_C4] == "C4"
assert len(STROKE_CHANNELS) == 29 and len(set(STROKE_CHANNELS)) == 29
