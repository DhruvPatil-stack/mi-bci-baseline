# Claude branch decisions (claude/speed-stroke, v0.3)

Each ticket's decisions are in its own file (the builders worked in parallel):
- S1 filter cache, csp_rank: [DECISIONS_S1.md](DECISIONS_S1.md)
- S2 evaluate checkpoint and time limit: [DECISIONS_S2.md](DECISIONS_S2.md)
- S3 no 64 channel / 160 Hz assumption: [DECISIONS_S3.md](DECISIONS_S3.md)
- S4 stroke loader: [DECISIONS_S4.md](DECISIONS_S4.md)

Notes for integration (from the builders and the checks):
- Stroke: `load_stroke()` with no argument returns 47 patients. EDF files of patients 5, 15, 49 are copies of 4, 11, 47
  (DECISIONS_S4.md section 3). Stroke labels alternate strictly left/right, so class is confounded with trial parity.
- Checkpoints: the fingerprint does not include code. Use a new checkpoint folder for every full run.
- Filter cache: `.cache/filtered` grows without limit; per-process memory cap $BCI_FILTER_CACHE_MEM_MB (default 4096).
