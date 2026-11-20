# Decisions, ticket S4 (bci/data_stroke.py, stroke loader), Sous chef, 2026-11-20

Dataset: Liu et al. 2024, Scientific Data 11, 131, CC BY 4.0 (license checked in docs/STROKE_DATASET.md).
Raw data stays in `.cache/` (git-excluded). Nothing from it is committed. Every number below was measured
with MNE 1.13.2 and scipy 1.18.1 on the files named. The scripts lived in the session scratchpad and are not in the repo.

## 0. Files read (all md5 match figshare record 21679035 v5)
- `.cache/stroke/edffile.zip`: 462843633 B, md5 aa4f96a0e8456f377f30d1ee8f41be40. 151 members: 50 EDFs plus folders.
  All names have the form `edffile/sub-XX/eeg/sub-XX_task-motor-imagery_eeg.edf`, with no absolute or `..` paths.
  Extracted to `.cache/stroke/edffile/` with zipfile (CRC checked).
- `.cache/stroke/task-motor-imagery_events.tsv`: copied from `.cache/stroke_meta/` (the Head chef's download).
  md5 f1c1f482471b90a7e067d9c502889647, which matches figshare file 38516084.
- Used for verification only, not by the loader:
  - `.cache/stroke_src/sourcedata.zip`: 1874824439 B, md5 4336b1ddbde42f89edb82f513a5c0721 (figshare file 38516555). Raw `.mat` files, read in memory with scipy.io.loadmat.
  - `.cache/stroke_code/code.zip`: md5 a86d243337f57739b18cf0f74a240004 (the authors' MATLAB code). Read as text, never run.

## 1. EDF facts, from inspecting sub-01 and checking all 50 files
- 33 signals, 500.0 Hz. 160000 samples = 320 s = 40 trials x 8 s, in all 50 files. The EDF has 320 records of 1 s.
- The EDF header's physical dimension is `uV` for all 33 signals. MNE returns volts: for sub-01 FP1, median |x| is 7.88e-06 V.
  So we multiply by the top-level config `unit_scale` (1e6). The `stroke` block has no `unit_scale` of its own.
  The physical min and max are about -206 and 155 uV for FP1.
- Signal order: FP1 FP2 Fz F3 F4 F7 F8 FCz FC3 FC4 FT7 FT8 Cz C3 C4 T3 T4 **CPz** CP3 CP4 TP7 TP8 Pz P3 P4 T5 T6
  Oz O1 O2 **HEOL HEOR** and one signal with an **empty name** (the marker).
  - CPz (index 17) is all zeros: sd 0.0 in sub-01. It is the recorded reference, so we drop it.
  - The second EOG signal is called `HEOR` in the EDF. The sidecar channels.tsv calls it `VEOR`. We drop both EOG signals.
  - `TP7` is present at index 20, and `FT7` appears only once (index 10). The paper's Table 2 lists FT7 twice; the files do not.
    We map the 29 channels by name to `bci.channels.STROKE_CHANNELS`, which is the file order with CPz removed.
  - The authors' code `CSP_LDA.m` uses the same selection, `channel = [1:17 19:30]`, and reads the marker from column 33.
- There are no EDF annotations (`len(raw.annotations) == 0`). Events exist only in the marker signal.
- Marker values are 0, 1, 2 and 3 (1 = instruction, 2 = motor-imagery beginning, 3 = break, as defined in events.json).
  Each pulse is one sample wide, and there are 40 pulses of each code. For sub-01, code 1 falls at 4000k
  (k = 0..39, the first at sample 0), code 2 at about 4000k+1003, and code 3 at about 4000k+3005.
- **The EDF is 40 concatenated 4000-sample epochs, one per trial.** Each epoch starts at its code 1, and EDF segment k
  equals raw `.mat` trial k (`rawdata` is 40 x 33 x 4000). Method: 1-40 Hz filter on both, pooled correlation over the 29 channels,
  samples 500-3500 of each epoch.
  - 45 of 50 patients: r >= 0.92 for every trial, and the best match is the same index for every trial.
  - sub-11: the best match is always the same index, but r is lower (min 0.38, median 0.77).
  - sub-13: one trial (trial 9) has r = 0.137. The next lowest is 0.988. Trial 9 holds a large artifact in both sources:
    EDF sd 550.5 uV, raw `.mat` sd 10187.2 uV unfiltered.
  - 5, 15, 49: these are copies of other patients (section 3).
    Their r against their own `.mat` is 0.03-0.08, and 15 and 49 are the only patients where the best match is not always the same index.
  Segment joins are real discontinuities: the median |step| at a join is 7.11 uV (29 channels, CAR, unfiltered),
  while the median |sample difference| elsewhere is 0.53 uV.

## 2. Labels: from task-motor-imagery_events.tsv, verified against the raw .mat of every patient
- The marker signal records the phase, not the hand. The class of each trial is only in events.tsv: for each
  value-2 row, trial_type 1 = left and 2 = right. The file is at the BIDS top level, so it applies to every patient.
- events.tsv has 40 value-2 rows with trial_type 1,2,1,2,..., strictly alternating: 20 left and 20 right.
- **Check:** the `.mat` struct `eeg.label` (40 x 1) of every patient equals that sequence. 50 of 50 match.
  Trial order is checked two ways:
  - the signal correlation in section 1;
  - the MI onsets. With the section 4 rule applied to both the EDF and the `.mat` marker rows, they are equal in 49 of 50 patients.
    The exception is sub-43, trials 24, 25, 26, 30 and 32 (section 4).
- Labels: trial_type -> y with config `stroke.label_map` {1: 0, 2: 1}. YAML keys are cast to int.
- Every patient has 40 trials, 20 left and 20 right (all 50 measured). No label is invented, and no trial is dropped.
- No decoding result and no ERD lateralization were used to choose or check labels.

## 3. Duplicate recordings in the EDF release: patients 5, 15, 49 are left out by default
- I correlated the 29 EEG channels over the full 320 s for all 1225 EDF pairs. Top pairs:
  (4, 5) r = 1.0 (the signals are bit-identical as float32), (47, 49) r = 0.9998, (11, 15) r = 0.9998.
  The next pair is (12, 50) with r = 0.1246.
- Each copy matches the raw `.mat` of the source patient, not its own:
  - EDF-05 vs mat-04: median per-trial r = 0.9946. EDF-05 vs mat-05: 0.073.
  - EDF-49 vs mat-47: 0.9957. EDF-49 vs mat-49: 0.056.
  - EDF-15 vs mat-11: 0.8010. EDF-15 vs mat-15: 0.060.
  - The originals match their own `.mat`: EDF-04 >= 0.99, EDF-47 >= 0.994, EDF-11 0.80 (the weakest, but kept).
  - The `.mat` files of 5, 15 and 49 are different recordings. They have about 107 uV sd of common noise on every channel, which CAR does not remove.
    They are not in the EDF release.
- Decision: `DUPLICATE_EDF = {5: 4, 15: 11, 49: 47}` (copy -> source).
  - `load_stroke()` with no subjects loads config `stroke.subjects` minus these three (47 patients) and prints one line naming them.
  - An explicit list that contains 5, 15 or 49 raises ValueError.
  - `include_duplicates=True` loads them, for audits only.
- Reason: a recording under two patient ids leaks across cross-subject folds (patient 4 in train, its copy 5 in test).
  It would also double-count the recording in the within-subject and responder tallies.
  The decision rests on file identity, made before any model was fit, so it is not selection after the fact.
  Original patient numbers are kept. There is no renumbering.

## 4. Motor-imagery onset rule (from the file, not from events.tsv timing)
- The rule:
  - A marker sample is an event code only if it is an integer (|x - round(x)| <= 1e-3).
  - Events are rising edges.
  - An MI onset is a code-2 event whose next event is code 3, 2000 +/- 25 samples later. 2000 samples is the events.tsv value-2 duration of 4000 ms.
  - We require exactly 40 onsets and onset // 4000 == trial index; otherwise the loader raises.
- Measured code-2 to code-3 gaps over the 2000 accepted trials: 2000 (587 trials), 2001 (726), 2002 (687).
- Irregularities found, all handled by the rule:
  - **Non-integer marker values.** Values such as 2.8147, 2.1270 and 1.1864 appear after the break of trial 39 in
    patients 10, 11, 13, 15, 17, 18, 20, 24, 40 and 44. They also appear in sub-20 trials 4 and 12 at offsets 3020-3093.
    The raw `.mat` holds the same values, so they are junk in the source. Rounding them made false codes (2.81 -> 3, 2.13 -> 2).
    They are ignored now, and the loader raises if one falls inside an MI interval (none does).
    Counts of non-integer samples: sub-10 343, sub-11 296, sub-13 231, sub-15 296, sub-17 274, sub-18 269, sub-20 202, sub-24 246,
    sub-40 114, sub-44 13.
  - **Short-instruction trials.** 23 trials in 12 patients (8, 13, 14, 20, 22, 24, 25, 29, 30, 40, 43, 48) have code 1 at
    offset 0 and code 2 at offset 1. The raw `.mat` signal shows the next trial really starts about 3002-3012 samples into
    such an epoch: the overlap is exact, max |diff| 0 uV (checked for sub-08 t21, sub-14 t20, sub-43 t24/25/26/30/32).
    So these are 6 s trials with no instruction phase, and the onset at offset 1 is correct.
  - **sub-43.** The EDF markers of trials 24, 25, 26, 30 and 32 show the short-instruction pattern. The `.mat` markers
    say code 2 is at 1002, but the `.mat` signal itself shows the next trial starting at offset 3002-3012. So the EDF markers are the
    consistent ones, and we use them. The EEG matches the `.mat` (median r 0.9988).
  - **Late onsets.** sub-06 has MI onsets 1150-1830 samples into most epochs, matching its `.mat` markers. sub-40 (8 trials)
    and sub-20 (1 trial) have onsets at 1150 or 1200.
  - **Other timing.** Measured onsets vs the events.tsv nominal onsets (onset ms / 2): the deviation is at most 28 samples in regular trials.
- Window: config `stroke.window` 0.5 to 3.498 s after the onset gives samples onset+250 .. onset+1749, which is 1500 samples.
  The window never leaves its own epoch: the latest end is offset 1830+1749 = 3579 < 4000.

## 5. Pipeline (all settings from config)
1. Read the marker codes from the unfiltered signal.
2. Keep the 29 channels by name, in STROKE_CHANNELS order (asserted). The set of channel names must be exactly
   the 33 above, or the loader raises.
3. Check that the EDF header unit of the 29 channels is uV (the loader parses the raw header bytes).
4. CAR over the 29 channels (config `stroke.reference: average`).
5. Band-pass the continuous signal with config `stroke.filter_band` [1, 40] Hz. This is MNE's default FIR, as in bci/data.py:
   1651 taps at 500 Hz.
6. `mne.Epochs` with baseline None and `reject_by_annotation=False`. All 40 epochs must be kept.
7. Multiply by `unit_scale`, cast to float32, run `contracts.validate_data(..., "stroke")`.

No resampling (500 Hz is native). No artifact rejection, since it is not in config and the PhysioNet path does not do it.

## 6. Download and extraction
- Data dir: `$BCI_STROKE_DIR` (config `stroke.data_dir_env`), default `<repo>/.cache/stroke`.
- If `edffile/` is missing, the loader md5-checks `edffile.zip` and extracts it. Member names are whitelisted by a regex.
  The extraction goes to a temp folder and is then moved into place with `os.replace`.
- If the zip is missing, the loader downloads it from figshare file 38516654. It tries config `download_attempts` times
  (3), writes to a `.part` file, checks the md5, then moves the file into place with `os.replace`.
- events.tsv is downloaded the same way (file 38516084) and md5-checked on every read.
- Any failure raises. There is no other data source.
- URL, size and md5 are dataset facts from docs/STROKE_DATASET.md, not settings, so they are constants in the module.

## 7. Measured results (`include_duplicates=True` audit over all 50 patients, plus the default call)
- All 50 patients: 40 trials each (min 40, max 40), with 20 left and 20 right each (min and max both 20 for each class).
- Per-patient median |X|: min 1.906 uV (sub-44), max 12.077 uV (sub-13). Median |X| over all 50: 4.194 uV.
- Default `load_stroke()`: 47 patients, X (1880, 29, 1500) float32, y counts [940, 940], median |X| = 4.231 uV,
  all values finite. Load time 10.3 s from extracted EDFs (12.4 s for all 50). These times were measured with a warm OS file cache,
  right after the audit had read every file.
- Smallest per-channel sd (mean over trials) in any patient: 2.05 uV (sub-32). No channel is flat.
- sub-13 trial 9 has a large artifact: mean channel sd 627.6 uV, against a median of 29.3 uV over its trials. It is kept,
  because there is no artifact rejection.

## 8. Risks
- **Splice ringing.** The 1-40 Hz FIR's half-length (825 samples) is longer than the distance from the window to a segment join
  in 37 of 1880 default trials (23 short-instruction trials, 14 late-onset trials). Joins step by a median of 7.11 uV,
  so these windows carry some filter ringing from a join. The ticket requires filtering the continuous signal, so it is kept.
- **Single label source.** The strict left/right alternation means class is confounded with trial parity and with slow
  drifts that alternate. That is a property of the paradigm. It is verified against the raw `.mat` labels.
- **Copy of patient 11.** EDF-11 and EDF-15 match mat-11 at only r = 0.80, lower than the other patients (>= 0.92).
  My interpretation (not measured): both EDFs are a differently processed version of patient 11's recording.
  Patient 11 is kept.
- The paper's EDF pre-processing (0.5-40 Hz filter, baseline removal) comes before our CAR and 1-40 Hz filter.
