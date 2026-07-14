# Verification status

This ledger records what was actually executed on 2026-07-14. It distinguishes development smoke evidence from the preregistered final evaluation. Generated datasets and artifacts remain git-ignored; reproduce them with the committed commands and verify their checksums.

## Code verification

Verified at commit `1c575ea20e4f2e7fa7bd46320e3752c77634767a`:

- Ruff lint: pass; Ruff format check: pass.
- strict MyPy over `graphtrust`: pass.
- Pytest fast suite: 115 passed, 1 performance test deselected; 89% overall coverage.
- Pytest performance suite: 1 passed.
- Frontend TypeScript lint and typecheck: pass.
- Frontend Vitest: 3 passed, including the API-backed investigation flow and automated accessibility check.
- Frontend production build: pass; initial application chunk 208.75 kB, lazy path-explorer chunk 447.33 kB before gzip.
- Live local API/UI browser inspection: pass, with no console errors or development overlay.
- `docker compose config`: pass. Image build: blocked because the local Docker Desktop Linux engine returned HTTP 500 from its `_ping` endpoint; container startup is therefore not claimed.

## Development dataset

The deterministic `saas_scaleup/small/104729` suite validates without errors:

| Variant | Nodes | Raw edges | Truth paths | Tree checksum |
|---|---:|---:|---:|---|
| clean | 1,920 | 12,000 | 0 | `34fbcdf8312aed3ad6a2aeebe553794ddd78437dca673e121892cada283caf25` |
| injected_low | 1,920 | 12,017 | 4 | `ae2397c8e1d14dd3883dd3b5230e88b79d16c5ca9a79dc5d8165c646f34ee37d` |
| injected_mixed | 1,920 | 12,049 | 13 | `f0c88d625f4704012dfd3e5e4cb5e8b7e040a9606f2baa7cf0b66e86eb1a7080` |
| remediated_truth | 1,920 | 12,049 | 13 | `acf273617f0109e8b8f661cbf7b7ddd3560058f5b2cb01823bd482dec5b1bea5` |

Additional generator verification created valid medium clean datasets for all three profiles at seed `104729` (27,100 nodes and 250,000 raw edges each). These are development artifacts, not final evaluation units.

## Smoke experiment

The committed `configs/smoke_experiments.yaml` scheduled five methods on the injected-mixed development graph with no missing datasets. All immutable runs completed against code commit `eca466dae48aef3b9d40dc8da4b1b053d2ef5a39` and dataset checksum `f0c88d…1a7080`:

| Method | Run ID | Scenario F1 | Risky-source recall | NDCG@10 | Total seconds |
|---|---|---:|---:|---:|---:|
| direct | `run-be96176bc04d10ba2c7d68ec` | 0 | 0 | 0 | 0.8793 |
| privileged | `run-37adf771334c4d47f552bd1d` | 0 | 0 | 0 | 0.8882 |
| untyped | `run-6c7537bd10bb604c070b212e` | 0.006548 | 0.75 | 0 | 34.0797 |
| native_scope | `run-725e982f2240165d213495da` | 0.026810 | 0.4167 | 0.150224 | 1.2936 |
| graphtrust | `run-2dc533caac10b4385cce9745` | 0.006508 | 0.75 | 0.142729 | 35.5646 |

This single development graph is a correctness and pipeline smoke test, not a hypothesis test. It shows a trade-off rather than a favorable headline: GraphTrust ties untyped risky-source recall, ranks relevant paths substantially better than untyped, but native-scope has higher scenario F1 and slightly higher NDCG@10 on this unit. A confidence interval with `n=1` is not inferential evidence.

The extended bundle `extended-c66b8ba2b9fd8106e6b6531a` contains 7 ablations, 30 one-at-a-time settings, and 1,000 deterministic Dirichlet ZTRI weight samples. Its checksum validates. Across Dirichlet samples, mean Spearman rank correlation is 0.9948 (minimum 0.9282) and mean top-K Jaccard is 0.8570. Depth 4 (Spearman 0.7109) and criticality threshold 0.90 (Spearman 0.7571; Jaccard 0.25) show material sensitivity on this graph.

All 10 required figures (SVG and PNG) and all 7 CSV tables were generated under `artifacts/paper`; traceability validation accepts all five run IDs and both extended-result checksums.

## Remediation diagnostic

All four methods executed at target 0.80 after two performance defects were fixed. Degree-greedy fell from an external timeout over 15 minutes to a 79.7-second end-to-end command; risk-greedy fell from a timeout over 10 minutes to 52.1 seconds. Weighted min-cut completed in 51.0 seconds and constraint generation in 177.8 seconds.

No smoke remediation plan is publication-verified. The protected-workflow verifier returned false for the base development problem, so degree-greedy, risk-greedy, and min-cut plans are feasible solver outputs but `counterfactual_verified=false`; constraint generation ended `TIME_LIMIT`. These CLI artifacts do not yet have immutable experiment run IDs and must not be reported as final remediation results.

## Unmet acceptance criteria

- The full final small/medium matrix (3 profiles × 2 scales × 5 final seeds × 3 variants × 5 methods) has not run.
- One large dataset per profile has not run in Colab; the notebook is prepared but unexecuted.
- Paired final confidence intervals and multi-method hypothesis tests therefore have no final artifact basis.
- Large-scale runtime/memory evidence is absent.
- The smoke protected-workflow inconsistency requires investigation before remediation evaluation is publication-ready.
- Docker images were not built or started because the local Docker engine was unhealthy.

Accordingly, the repository implementation and development verification are advanced, but the specification's definition of success is not yet fully met.
