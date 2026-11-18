# Decisions

- `ts_lr` uses OAS covariance, a tangent reference fitted on training covariances, and logistic regression. A StandardScaler degraded measured synthetic recovery, so it was removed.
- EEGNet uses fixed config settings, CPU, training-only channel normalization, and seeded deterministic PyTorch operations.
- Feedback time points mark the end of each 1-second window. The right-fist probability is probability column 1.
- The report uses supplied JSON statistics when present; it computes paired Wilcoxon and Holm results when the statistics block is absent.
- The Codex CLI could not initialize its app-server client under the workspace sandbox. Ticket work and local checks were completed in this session; the error is logged in `.sync/LOG.md`.
