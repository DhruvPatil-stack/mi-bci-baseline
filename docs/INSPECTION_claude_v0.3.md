# Inspection: Codex v0.3 (codex/heterogeneity, bf21a5b)

- Who: Claude Opus sous-chef, cross-vendor inspection of Codex files (KITCHEN rule 10). New session.
- Read: PRD_v0.3.md sections 4, 9, 12, 13 (plus section 6 ownership rows); bci/contracts.py "v0.3 ANALYSIS
  CONTRACT" and "v0.3 ERD CONTRACT"; `git diff base/v0.3 codex/heterogeneity`; all changed files in full.
- Date 2026-11-20. Ran on a `git archive` export in .cache/inspect3/src (scratch repo, branch codex/heterogeneity).
- Locked run (G11 + G12 + G5 + tests/codex), exact tail: `25 passed, 1 skipped in 296.18s (0:04:56)`.
  The skip is test_erd.py:40 (needs BCI_REAL_DATA=1). The 10-noise-subject G11 case, which Codex left
  unfinished, passed.
## HIGH
1. Stroke results are labelled synthetic. bci/report.py:225-228 is `if data_source == "physionet": healthy
   volunteers / else: "These are synthetic subjects and trials."`. contracts.py:137 now has
   DATA_SOURCES = ("physionet", "synthetic", "stroke"). Evidence: my render with data_source "stroke"
   (.cache/inspect3/rep_stroke/results.md:95) says "These are synthetic subjects and trials." and then "do
   not establish ... performance for a stroke cohort", so the paragraph contradicts itself and calls
   patients synthetic. The line predates this diff, but report.py is Codex-owned and H3 edits it.
   PRD 9 H3, PRD 13. Fix: add a stroke branch.
## MEDIUM
2. The regression-to-the-mean sentence is not in the Limits paragraph. bci/report.py:146 emits it before
   "## Figures". "## Limits" (report.py:232-234) holds only the cohort sentence. PRD 9 H3 bullet 5 asks for
   one "Limits" paragraph naming regression to the mean AND the 20-subject sample. The sample size is only
   named dynamically ("lists N subjects", report.py:222/224), never tied to the responder count or Spearman.
3. tests/codex has no H3 test (PRD 9 H4: "Tests for H1 to H3"). `git grep` finds no responder_analysis or
   lateralization key in tests/locked/fixtures, so G5 never runs `_v3_analysis_lines` (report.py:97-148).
   My filled-block probe (6 subjects, physionet and stroke) is the only coverage: G5 matcher `unmatched: []`.
4. tests/codex/test_analysis.py:14-26 mostly repeats locked test_responders.py::test_calibration_gain_by_group
   (same seeded-equality and mean-gain asserts). Only test_empty_responder_set_is_explicit is new.
## LOW
5. The null re-stratifies folds on the shuffled labels (analysis.py:41 passes rng.permutation(y) into
   within_subject_splits). Probe (44 trials, SEED): 0 of 5 test folds are shared between obs and null. This
   satisfies "repeat the same cross-validation" as a procedure (same splitter and SEED, like sklearn
   permutation_test_score). docs/codex/DECISIONS.md does not record this choice.
6. analysis.py:117-118: n_responders/n_non_responders count every flag, including subjects absent from
   per_target. Probe: a flagged subject "99" with no calibration row gives n_responders 3, while the mean
   uses 2 subjects.
7. report.py:144 prints the Spearman p with `:.4f`. Probe p = 3e-05 renders "p 0.0000". G5 accepts it only
   through rounding. Use the file's own p_text (report.py:176).
8. erd_check.py:17: Welch silently shrinks nperseg when n_samples < sfreq (scipy warning seen with 100
   samples at 160 Hz), against the contract nperseg=int(sfreq). 480@160 and 1500@500 are unaffected.
9. report.py:111-112 silently skips a per-subject row whose score or p is None. erd_check.py:52 and
   report.py:108/139 use `key=int` and raise on non-integer ids (probe: "P02" -> ValueError). Stroke
   groups are integers per the contract, so this is latent.
10. Report key names (responder_analysis.per_subject.{score,p_value,responder}, summary, calibration_gain,
    erd.{lateralization, association}) are not in the RESULTS SCHEMA. Every access is `.get`-guarded, so a
    renamed key hides the sections while G5 passes. integration/v0.3 run_all.py:404-409 already maps them.
## Verified correct (commands run)
- Responder p: `>=` with (1 + n_perm) (analysis.py:44). obs uses within_subject_splits(n_splits from config,
  SEED) and matches G11's own CV to 1e-12 (G11 passed). Shuffles are seeded by `seed`, and there is a new
  estimator per fit. Strict p < alpha. Clopper-Pearson matches the beta closed form, max |diff| 2.2e-16
  (n in 1, 5, 20). 1/20 gives [0.0013, 0.2487], expected false positives 1.0.
- Gain = spt(k) - spt(k=0) per target. The bootstrap resamples within each group and is seeded. Probe:
  diff 0.2, CI [0.1, 0.3].
- LS: ln of the MEAN power (probe 1.6094 = ln 5, not ln 3 = 1.0986). The sign and C3/C4 order are right
  (G12 passed, and a swap flips the sign). Welch uses density scaling, nperseg=int(sfreq), and bins
  integrated times df. Non-positive power raises ValueError. Spearman runs on common ids in ascending order.
- grep finds no 64 or 160 in analysis.py, erd_check.py or report.py. Imports are limited to contracts/splits
  plus scipy/sklearn. There is no new model family and no search. All changed files are Codex-owned (PRD 6).
  No invented decimals in my renders.

VERDICT: FAIL (1 HIGH: stroke mislabelled synthetic; 2 MEDIUM H3 gaps: RTM outside Limits, no H3 test).
