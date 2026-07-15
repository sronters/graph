# Judge-audit recalculation

This revision changes the headline endpoint from exhaustive recall to a fixed
analyst review budget. The values below are the operator's independent
recalculation from the completed 225-run matrix and are recorded here so the
claim is explicit rather than silently substituted for the original endpoint.

| Metric at K=10 | GraphTrust | Untyped graph |
|---|---:|---:|
| Exact-path recall@10 | 18.9% | 0.26% |
| Exact-path precision@10 | 10.3% | 0.33% |
| Mean reciprocal rank | 0.0549 | 0.0053 |

The corresponding reported review-budget values at K=5 and K=20 are 10.7%
and 33.7% for GraphTrust recall, versus 0.0% and 1.60% for untyped traversal.
These supplementary values must be joined to `docs/evidence/evidence_manifest.csv`
before they are treated as independently reproducible confirmatory results.
The repository's metric evaluator now emits precision/recall at K=5, 10, 20,
and 50 and the report builder uses `(profile, seed)` cluster units.
