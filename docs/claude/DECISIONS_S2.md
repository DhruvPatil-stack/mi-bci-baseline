# Ticket S2 decisions (`bci/evaluate.py`: checkpoint, time limit as safety stop; Sous chef)

Contracts: TIME LIMIT CONTRACT and EVALUATE CHECKPOINT CONTRACT in `bci/contracts.py`. Gate: G10
(`tests/locked/test_wallclock.py`). Extra branch checks: `tests/claude/test_evaluate_checkpoint.py`.

1. **Time gate.** One helper `_deadline(cfg, budget_min)` returns `time.monotonic() + budget*60` only when
   `contracts.enforce_time_budget(cfg)` is True, else `None`. `_check_time(None)` reads no clock. So with the limit
   off, the only clock reads are `time.perf_counter()` for `runtime_s` (and per-stage seconds written to the
   checkpoint file); neither decides a branch. `run_calibration` follows the same rule for its own budget
   (`calibration_time_budget_min` passed by run_all.py): with the limit off it never times out.
2. **runtime_s clock.** `runtime_s` now uses `time.perf_counter()` (v0.2: `time.monotonic()`); both are
   reporting-only. The deadline keeps `time.monotonic()`.
3. **Fingerprint** = sha256 over: a checkpoint format version (`CHECKPOINT_VERSION = 1`), the model name,
   X dtype + shape + raw bytes, y and groups cast to int64 (dtype + shape + bytes), and
   `json.dumps(config, sort_keys=True, default=str)`. Not included (contract): the calibration flag. Also not
   included, by decision: the estimator class / its parameters, environment variables (`BCI_DATASET`,
   `BCI_ENFORCE_TIME_BUDGET`, cache switches) and the code version. Reason: the contract lists exactly name, X, y,
   groups, config; G10 swaps the estimator under the same name and requires a clean load. Consequence (open
   risk): after a code change in a model, the integrator must delete the old checkpoint files or use a new path.
   X is hashed from a local contiguous view; the X passed to fits is never replaced (G2 spy).
4. **Checkpoint layout** (one file per model, path chosen by the caller; `checkpoint=None` means no file at all):
   `{"version": 1, "fingerprint": hex, "model": name, "stages": {within_subject, cross_subject, permutation,
   calibration: block}, "stage_runtime_s": {stage: seconds}}`. Only fully finished stages are written; status,
   error and a partial calibration (timeout) are never stored as finished. Timing lives only in the file, never
   in the returned block, so a resumed run returns exactly what a fresh run returns.
5. **Atomic write.** `tempfile.mkstemp` in the checkpoint's own folder, write, flush, `os.fsync`, then
   `os.replace` (retried up to 5 times on `PermissionError`, Windows reader lock); the temp file is removed in a
   `finally` if the replace fails. The parent folder is created on demand.
6. **Load rules.** A missing, unreadable, non-JSON, other-version or other-fingerprint file is ignored and is
   overwritten at the next finished stage (not before: a run that fails at once leaves the old file alone). Each
   loaded stage is re-checked with its `contracts.validate_*`; a stage that fails is dropped and recomputed.
   Loaded stages stay in the file when new ones are added (a calibration rerun keeps within/cross/permutation).
7. **Calibration flag on rerun.** Only the stages asked for are returned: a calibration stored by an earlier
   `calibration=True` run stays in the file but is not returned when `calibration=False`.
8. **Checkpoint write failure** (OSError) does not change any result and does not stop the run; it is reported as
   `"checkpoint_error"` in the returned block (key present only on failure). Reason: the scores are valid; only
   resume is lost, and hiding it would be wrong.
9. **`run_calibration(name, X, y, groups, budget_min, checkpoint=None)`.** Optional `checkpoint` added (signature
   is backward compatible). Same file and fingerprint as `run_model`: a finished calibration there is loaded, a
   newly finished one is added.
10. **Granularity = stage**, as the contract says. Permutation repeats and calibration k values are not
    checkpointed one by one (a stage cut by a crash or a timeout is recomputed in full on the rerun).
11. **Per-subject table.** `within_subject.per_subject` already exists (v0.2) and is kept. Decision: no
    `per_subject` table is added to `cross_subject`. The contract requires it only for within; `validate_cross`
    does not ask for it; the cross block already lists `test_subjects` per fold; adding numbers to results.json
    no consumer asked for is scope drift.
12. **Leak rules unchanged.** The procedures `_within`, `_cross`, `_permutation`, `_calibration` are not changed:
    fresh estimator per fit, X row slices only, splits from `bci.splits`, permutation shuffles only inside each
    train and each test set with seeded generators, every fit followed by its predict. No stage uses RNG state
    from another stage, so a stage computed alone after a resume equals the one from a full run.
