# Codex inspection of Claude v0.3 branch

Scope: PRD v0.3, tickets S1-S4, and `base/v0.3..claude/speed-stroke` only.

1. HIGH — `data_stroke.py` documents that stroke labels alternate strictly left/right. This makes label correlated with trial order; within-subject results can be confounded by drift. The morning report must retain this limit and no clinical conclusion should be drawn.
2. HIGH — `models_advanced.py` remains outside Claude's edits but cannot accept the 29-channel stroke contract, so EEGNet errors on stroke data. Integration must report the failure rather than describe an all-model stroke comparison.
3. MEDIUM — checkpoint fingerprints include model name, data, groups, and config but not an implementation/version fingerprint. A changed estimator implementation can reuse an old checkpoint. This is a stale-result risk on developer reruns, not a train/test leak in a single run.
4. MEDIUM — the cache defaults to a 4096 MB per-process memory cap. Multiple model workers can exceed host memory; integration observed memory pressure during stroke processing. Bound workers/cache memory before a rerun.
5. MEDIUM — `_download` removes its partial file with `part.unlink()` outside a guarded cleanup path. A filesystem race or readonly partial can mask the original download error.
6. LOW — G10 correctly turns time limits off for deterministic results, but its runtime bookkeeping still reads clocks. This is not used to decide scores/status when disabled.
7. No evaluation fit-on-test-data leak was found: evaluate functions create fresh estimators after supplied subject-aware splits, and cache entries are only stateless filter outputs keyed by raw row content and filter settings.
8. No unit conversion defect was found in the PhysioNet loader; the stroke loader validates microvolt output before returning it.
