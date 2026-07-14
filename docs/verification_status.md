# Verification status

This ledger records the evidence available on 2026-07-14. It deliberately
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

The registered injected-mixed verification instance was analyzed with four
remediation approaches. Weighted min-cut proposed 22 raw IAM relationship
changes at modeled cost 18.583579. After applying those changes, recompiling
the effective graph, and rerunning bounded reachability, the verifier recorded:

| Check | Result |
|---|---:|
| Enumerated paths before remediation | 20,675 |
| Enumerated paths blocked | 20,632 |
| Relative exposure reduction | **97.141%** |
| Protected workflows preserved | **true** |
| `counterfactual_verified` | **true** |

This verifies the recommendation under the encoded graph, cost, protected-edge,
workflow, and bounded-search assumptions. It does not modify a live IAM system
and does not establish global minimality for a real organization.

## Robustness and publication artifacts

- ZTRI sensitivity: 1,000 deterministic Dirichlet weight samples; median
  Spearman rank correlation 0.9969 and minimum 0.928.
- Final report inputs: checksum-validated result JSON/CSV and generated LaTeX
  macros.
- Figures: 16 publication figures in SVG and 300-dpi PNG; the paper includes a
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
- Three profile-specific large Colab notebooks are complete, JSON-valid, and
  include high-RAM gates, checkpoint/resume, immutable verification, receipts,
  and artifact download. They have **not** been executed in authenticated
  Google Colab, so no Colab runtime/memory result is claimed.

## Docker boundary

Dockerfile, Compose definitions, health checks, and a public CI workflow that
builds, starts, and probes the stack are present. GitHub Actions run
`29354250207` successfully built the production images, started GraphTrust,
passed API/frontend health checks, captured logs/state, and stopped the stack.
This is the authoritative Docker startup verification.

## Final code-quality gate

The final gate completed with these results:

- Ruff format check: 121 files formatted; Ruff lint: pass.
- strict MyPy: 96 source files, no issues.
- Pytest: 121 passed; one third-party Starlette deprecation warning.
- Frontend: TypeScript lint/typecheck pass; Vitest 3/3 pass; Vite production
  build pass.
- Four Colab notebooks: JSON structure valid.
- Traceability: 225 verified run IDs in the confirmatory evidence ledger, 16
  figures, and review-budget/depth tables; no missing or
  corrupt referenced artifact.
- LaTeX: main paper and figure appendix compile without fatal errors.
- PDF render inspection: every page of the four-page paper and seven-page
  figure appendix inspected after the final build.
- Docker/Compose/workflow YAML: static parse pass and remote engine startup pass.

## Defensible submission status

The small-scale confirmatory study, statistical analysis, counterfactual
remediation verification, figures, and paper are complete. Medium/large
scalability results and Docker startup remain explicitly pending. They must not
be described as executed until authenticated receipts or CI logs exist.
