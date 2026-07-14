# GraphTrust data layout

- `fixtures/` contains deterministic, reviewable correctness fixtures.
- `generated/` contains reproducible SEIB-2026 datasets and is ignored except for this marker.
- `external/` is reserved for local sanitized, authorized inputs and is never committed by default.

Each generated dataset carries a manifest, checksums, dataset card, quality report, truth-separated Parquet files, and the generator parameters needed to reproduce it. Synthetic structure is not evidence of statistical representativeness of real enterprises.
