# Verification status

This ledger records the evidence available on 2026-07-15. It deliberately
separates completed experiments from prepared execution paths. Generated data
and run artifacts are reproducible from committed configuration files and are
accepted by the report only after checksum validation.

## Confirmatory detection evidence

The complete small-scale SEIB-2026 matrix passed the artifact gate:

| Item | Verified status |
|---|---:|
| Enterprise profiles | 3 |
| Held-out seeds | 5 |
| Variants per profile/seed | 3 |
| Detection methods | 5 |
| Immutable run directories | **225/225** |
| Injected paired graph units used for recall/ranking | 30 |
| Clean negative-control graph units | 15 |
| Missing datasets or method cells | **0** |

All reported detection and ranking numbers in the LaTeX paper are generated
from these verified run directories. Incomplete local medium diagnostics are
stored separately and excluded from the final-matrix input.

## Counterfactual remediation evidence

GitHub Actions run `29387806389` completed 15 independent injected-mixed
organizations spanning three profiles and five held-out seeds. The aggregate
artifact passed a strict 15/15 shard gate and contains 300 remediation rows
(four solvers × five requested targets × 15 organizations) plus 1,350
depth-stress rows. The checked-in files match these manifest hashes:

| Artifact | SHA-256 |
|---|---|
| Depth stress CSV | `a91e9dbf8c16fd27338398f1a0e61e5b7aaa0406979f0c66f70ebb176e61e571` |
| Remediation CSV | `6c48a635c55fd6bc2ad8dfce46dd12c2118980af746ff2261b65dd84f634852c` |

Weighted minimum cut produced 15 unique graph plans. Repeating each plan
against five target thresholds yields 75 CSV checks but does not increase the
independent sample size beyond 15.

| Replicated weighted min-cut check | Result |
|---|---:|
| Independent organizations | **15** |
| Mean exposure reduction | **97.71%** |
| Cluster-bootstrap 95% CI | **[97.48%, 97.95%]** |
| Mean raw IAM changes | **28.13** |
| Mean modeled cost | **22.96** |
| Mean runtime | **3.62 s** |
| 95% target attained | **15/15** |
| Protected workflows preserved | **15/15** |
| Counterfactual verified | **15/15** |

These are recommendation-only results under synthetic graph, cost, protected
workflow, and bounded-search assumptions. No live IAM permission was changed,
and the experiment does not establish real-world global minimality.

## Robustness and publication artifacts

- ZTRI sensitivity: 1,000 deterministic Dirichlet weight samples; median
  Spearman rank correlation 0.9969 and minimum 0.928.
- Final report inputs: checksum-validated result JSON/CSV and generated LaTeX
  macros.
- Figures: 17 publication figures in 300-dpi PNG, with selected figures also
  available as SVG; the paper includes a
  graph attack-surface atlas, explainable path, paired effect plot, ranking and
  recall charts, remediation frontier, sensitivity, ablation, heatmap, ZTRI
  distribution/concentration, architecture, schema, and resource plot.
- Documents: a four-page NSRI Research Brief excluding references/appendix and
  a seven-page full figure appendix.

## Medium and large execution boundary

- The 225-run medium extension is **not complete**. Local probes at global path
  caps of 250,000, 30,000, 5,000, 1,000, and 100 exposed an impractical
  repeated source--target search cost. They are diagnostics, not publication
  result cells.
- The frozen medium follow-up configuration uses igraph, depth 6, a 100-path
  global cap, and one path per source and source--target pair.
- Three profile-specific large Colab notebooks and three Kaggle equivalents are
  complete and JSON-valid. They include hosted-runtime gates,
  checkpoint/resume, immutable verification, receipts, and artifact export.
  They have **not** been executed with an authenticated hosted receipt, so no
  Colab or Kaggle runtime/memory result is claimed yet.

## Docker boundary

Dockerfile, Compose definitions, health checks, and a public CI workflow that
builds, starts, and probes the stack are present. GitHub Actions run
`29354250207` successfully built the production images, started GraphTrust,
passed API/frontend health checks, captured logs/state, and stopped the stack.
This is the authoritative Docker startup verification.

## Final code-quality gate

The final gate completed with these results:

- Ruff format check: 126 files formatted; Ruff lint: pass.
- strict MyPy: 89 source files, no issues.
- Pytest: 125 passed, one deselected performance test; one third-party Starlette
  deprecation warning.
- Frontend: TypeScript lint/typecheck pass; Vitest 3/3 pass; Vite production
  build pass.
- Four Colab and three Kaggle notebooks: JSON structure valid.
- Traceability: 225 verified run IDs in the confirmatory evidence ledger, 16
  figures, and review-budget/depth tables; no missing or
  corrupt referenced artifact.
- LaTeX: main paper and figure appendix compile without fatal errors.
- PDF render inspection: every page of the four-page paper and seven-page
  figure appendix inspected after the final build.
- Docker/Compose/workflow YAML: static parse pass and remote engine startup pass.

## Defensible submission status

The small-scale confirmatory study, clustered statistical analysis, 15-graph
counterfactual remediation replication, depth follow-up, figures, and paper
inputs are complete. Docker startup is verified by public CI. The 225-run
medium scalability extension and three authenticated large hosted receipts
remain pending and must not be described as executed.
