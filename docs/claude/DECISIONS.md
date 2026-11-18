# Claude branch decisions

## C1 `bci/data.py` (Sous chef)

1. **Data cache inside the repo.** PRD section 5 says "cache outside the repo", but AGENTS.md and the ticket say
   `$BCI_DATA_DIR`, else `<repo>/.cache/mne_data` (git-excluded via `.git/info/exclude`). AGENTS.md / the ticket win.
   `_MNE_FAKE_HOME_DIR` is set (setdefault) to `<repo>/.cache/mne_home` before `import mne`.
2. **Internal MNE event codes 1..k.** MNE event ids should be non-zero, so T1/T2 get internal codes 1/2 (sorted by
   description) and are mapped back to config `event_map` labels (T1 -> 0, T2 -> 1). Selection is by annotation
   description only; T0 and any other annotation are ignored.
3. **Order: average reference, then band-pass** (both linear, so the order does not change the result). Reference
   with `set_eeg_reference("average", projection=False)`; filter with MNE's default zero-phase FIR
   (`raw.filter(1.0, 40.0)`), no other parameter tuned.
4. **Runs are concatenated** with `mne.concatenate_raws`. The filter respects the run boundaries (MNE default
   `skip_by_annotation` includes "edge"); `Epochs` keeps `reject_by_annotation=True`, so an epoch crossing a
   run boundary would be dropped. Measured: no epoch was dropped for subjects 1-3 (each run epoched alone gives
   15 trials; concatenated, 45 per subject).
5. **No `eegbci.standardize`, no montage.** Channels are picked by type (EEG), never by name.
6. **Sampling-rate guard.** `epochs_from_raw` raises if sfreq != 160 Hz (defensive guard; not verified against any
   specific subject here); the 480-sample shape is also asserted.
7. **Fallback.** `load_with_fallback` calls the module-level `load_dataset` (monkeypatchable) up to
   `download_attempts` times, catching any `Exception`, with `time.sleep(2.0)` between attempts (none after the last),
   then prints a `SYNTHETIC - NOT VALID` line and returns `synthetic.make_synthetic()` with source "synthetic".

Measured (subjects 1-3, runs 4/8/12): X (135, 64, 480) float32; 45 trials per subject (23 left / 22 right each);
median |X| = 11.10 uV.

## C3 `bci/evaluate.py` (Sous chef)

1. **Registry at call time.** Each call builds `{**models_classical.REGISTRY, **models_advanced.REGISTRY}`, reading the
   module attribute (so a monkeypatched dict is seen). `bci.models_advanced` is imported with `importlib`; only a
   `ModuleNotFoundError` whose `name == "bci.models_advanced"` falls back to classical only. Any other import error
   inside an existing module is raised. Unknown name -> `KeyError`.
2. **X untouched.** Only `X[fit_idx]` / `X[test_idx]` row slices are passed; no cast, no copy-transform.
   Each estimator is created fresh from the factory, fitted, and used for prediction before the next fit.
3. **Splits use the TRUE labels.** Permutation shuffles labels only after splitting, separately inside each train
   set and each test set, per fold. Generators: within repeat r uses `np.random.default_rng([SEED, r, 0])`,
   cross repeat r uses `np.random.default_rng([SEED, r, 1])` (one generator consumed fold by fold, train then test).
   Repeats: `n_permutations`, or `n_permutations_eegnet` for `eegnet_lite`. Reported value = mean over repeats of
   each repeat's `mean_bal_acc`.
4. **Within per-subject metrics** use the out-of-fold predictions pooled over that subject's folds (each trial
   predicted once). Keys `str(sid)`, ascending. mean = plain mean over subjects; std with `ddof = std_ddof`.
5. **Cross per_fold**: `{fold, test_subjects (sorted ints), acc, bal_acc, kappa}`; mean/std over folds.
6. **Calibration.** source_plus_target fits on `np.union1d(source_idx, calib_idx)`; target_only fits on `calib_idx`
   only (k > 0), `None` at k = 0. Value per k = mean over targets (ascending) of the mean over that target's draws
   of bal_acc on `test_idx`. `k` list is config `calibration_k` as ints.
7. **Defensive guards (not expected to trigger):** Cohen's kappa NaN (only when truth and prediction are both a
   single class) is reported as 0.0; std over a single value (n <= ddof) is reported as 0.0. Every block is passed
   through `contracts.validate_*` before it is returned, so a bad value fails inside evaluate.
8. **run_model** order: within, cross, permutation, then calibration (if asked), so the costly calibration block is
   the one lost on a timeout. The `time_budget_min` deadline (`time.monotonic`) is checked before every fit; a
   single fit already running is not interrupted. On overrun: status `"timeout"`, finished blocks kept, an `"error"`
   string names the step. Any exception: status `"error"` with `"<Type>: <message>"`. `runtime_s` always present.
   Writing BLOCKERS.md on timeout is left to the caller (`run_all.py`, Integration): evaluate has no file side effects.
9. **Runtime vs the 40 min budget (open, see docs/claude/BLOCKERS.md).** evaluate cannot cache transforms (the
   estimators are opaque and evaluate must not transform X). It does not parallelise either, because that would
   break the G2 spy's fit/predict pairing. Measured (SYNTHETIC - NOT VALID): `run_model("csp_lda",
   make_synthetic(), calibration=True)` took 808.4 s wall, status ok. Fit+predict time per fit on
   make_synthetic(20, 44), min of 3, with another python process using the CPU: csp_lda 5.03 s at 836 rows,
   1.73 s at 280, 0.16 s at 24; fbcsp_lr 24.77 s, 9.00 s, 0.75 s. Projection from those numbers (not measured):
   calibration on 20 subjects is 820 source-size fits + 800 calib-only fits, about 69 min for csp_lda and about
   5.6 h for fbcsp_lr, both over budget. run_model then returns status "timeout" with within/cross/permutation kept.
10. **Checked paths:** an unknown name gives `run_model` status "error" with `KeyError: "unknown model 'nope'; ..."`,
    and `within_subject` raises KeyError. With time_budget_min = 0.25 on synth_small: status "timeout" after 15.1 s
    (during permutation), within_subject and cross_subject kept and valid, result JSON-serialisable.
11. **Partial calibration on timeout (Head chef decision, config unchanged).** Calibration is computed k by k in
    ascending order. If the budget runs out during calibration, run_model keeps a calibration block with only the
    finished k values (all three lists cut to the same length, so validate_calibration passes), adds
    `"calibration_partial": true`, and keeps status "timeout". If no k finished, there is no calibration block.
