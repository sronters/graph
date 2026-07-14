# Final experiment matrix and execution protocol

This document is the authoritative map from the research questions to executable
GraphTrust experiments. Numerical claims may enter the paper only after the
corresponding run directory passes checksum and manifest verification.

## Primary detection matrix

| Factor | Levels |
|---|---|
| Enterprise profile | `saas_scaleup`, `regulated_finance`, `global_hybrid` |
| Scale | `small` (1,920 nodes, about 12k raw edges), `medium` (27,100 nodes, at least 250k raw edges) |
| Held-out final seed | 2,750,159; 3,681,131; 4,264,387; 5,000,011; 6,500,027 |
| Dataset variant | `clean`, `injected_low`, `injected_mixed` |
| Detection method | direct, privileged-only, untyped graph, native scope, GraphTrust |

The full matrix is `3 × 2 × 5 × 3 × 5 = 450` immutable runs: 225 per
scale. Injected variants are the primary detection units. Clean variants are
negative controls and are not pooled into recall estimates.

Small graphs use the preregistered 250,000 global bounded-path cap. Medium
graphs use a 100-path cap, 1 path per source and source-target pair, and
maximum depth 6 after retained 250,000-, 30,000-, 5,000-, and 1,000-cap
diagnostics demonstrated excessive memory or runtime. Those diagnostic runs
are excluded from the final matrix. Medium results are therefore bounded
scalability evidence, not an estimate of exhaustive enterprise path recall.
These scale-specific limits are fixed before the final medium matrix, saved in
every resolved configuration, applied symmetrically to the methods, and
reported through per-run truncation warnings. Cross-scale recall is therefore
interpreted together with search completeness rather than as a pure
algorithmic scaling curve.

Primary endpoints are risky-starting-identity recall, scenario recall,
exact-path recall, and NDCG@10. Secondary endpoints are precision/F1,
unmatched findings per 1,000 identities, explanation completeness, runtime,
expanded states, candidate paths, and peak resident memory. Paired inference
uses the enterprise graph `(profile, seed, variant)` as the independent unit,
not each enumerated path.

## Remediation matrix

The same injected-mixed verification graph and target exposure reduction are
given to degree greedy, risk greedy, weighted minimum cut, and iterative CP-SAT
constraint generation. Every plan reports raw IAM changes, modeled cost,
enumerated paths blocked, residual weighted exposure, solver status, and search
truncation. A plan is publication-verified only after the proposed raw edges are
removed, effective capabilities are recompiled, analysis is rerun, and all
capability-specific protected workflows remain reachable.

## Large-profile launches

Three separate notebooks run GraphTrust on one 227,000-node, 2.5-million-edge
injected-mixed graph at seed 2,750,159:

1. `GraphTrust_Colab_Large_saas_scaleup.ipynb`
2. `GraphTrust_Colab_Large_regulated_finance.ipynb`
3. `GraphTrust_Colab_Large_global_hybrid.ipynb`

Each notebook refuses to certify a result unless `COLAB_RELEASE_TAG` is present,
the immutable run directory verifies, and the runtime has at least 10 GiB of
RAM. Large launches use a 10,000 global path cap and are treated as scalability
evidence rather than as additional units in the primary hypothesis test. The
receipt stores the realized graph counts, dataset checksum, run ID,
Python/platform information, Colab release tag, verification result, runtime,
and peak memory. Local executions are useful diagnostics but are never labeled
as Colab evidence.

## Execution commands

```bash
# Small final matrix
graphtrust experiment \
  --registry configs/experiments_small.yaml \
  --workers 4 --data-root data/generated \
  --output-root artifacts/final_matrix

# Medium final matrix, scalable igraph backend
graphtrust experiment \
  --registry configs/experiments_medium.yaml \
  --config configs/scalable.yaml \
  --workers 4 --data-root data/generated \
  --output-root artifacts/final_matrix

# Report; rejects corrupt artifacts
python scripts/build_final_results.py \
  --runs artifacts/final_matrix \
  --artifact-root artifacts \
  --output artifacts/final_paper/generated
```

## Completion gate

- Exactly 225 verified small runs and 225 verified medium runs.
- Exactly 45 clean negative-control units and 90 injected primary units per scale.
- Five methods present for every paired graph unit.
- All run manifests identify one committed source revision per batch and include
  configuration, dependency-lock, environment, artifact, and dataset hashes.
- Three large receipts may be called “Colab runs” only when their environment
  flag and immutable artifacts verify.
- Remediation conclusions require post-application counterfactual verification,
  not solver feasibility alone.
- The paper, tables, and figures must be regenerated after the gate passes; no
  manually typed headline number is accepted.
