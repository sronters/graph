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

The pre-specified full design (commit `b226203`, before final evaluation) is
`3 × 2 × 5 × 3 × 5 = 450` immutable runs:
225 per scale. The completed confirmatory evidence is the entire small-scale
half (225/225 runs). The 225 medium runs are a pending scalability extension
and are not represented as completed evidence. Injected variants are the
primary detection units. Clean variants are negative controls and are not
pooled into recall estimates.

Small graphs use the pre-specified 250,000 global bounded-path cap. Medium
graphs are frozen to a 100-path cap, 1 path per source and source-target pair, and
maximum depth 6 after retained 250,000-, 30,000-, 5,000-, and 1,000-cap
diagnostics demonstrated excessive runtime. Those incomplete diagnostic runs
are excluded from the final matrix. When executed, medium results are bounded
scalability evidence, not an estimate of exhaustive enterprise path recall.
These scale-specific limits are fixed before the final medium matrix, saved in
every resolved configuration, applied symmetrically to the methods, and
reported through per-run truncation warnings. Cross-scale recall is therefore
interpreted together with search completeness rather than as a pure
algorithmic scaling curve.

Primary endpoints are exact-path precision/recall at analyst review budgets
K∈{5,10,20,50}, NDCG@10, and MRR. Exhaustive risky-starting-identity recall,
scenario recall, and exact-path recall remain secondary endpoints. Secondary
outputs include precision/F1, unmatched findings per 1,000 identities,
explanation completeness, runtime, expanded states, candidate paths, and peak
resident memory. Paired inference uses `(profile, seed)` cluster means as the
independent unit, not each variant or enumerated path. The depth-stress runner
reports recall separately for direct, 2-hop, 3-hop, and 4–6-hop planted paths.

## Remediation matrix

The replication runner is configured for 3 profiles × 5 seeds and targets
50%, 70%, 80%, 90%, and 95% exposure reduction. It compares degree greedy,
risk greedy, weighted minimum cut, and iterative CP-SAT constraint generation.
Every plan reports raw IAM changes, modeled cost, departments affected,
enumerated paths blocked, residual weighted exposure, solver status, and search
truncation. A plan is publication-verified only after the proposed raw edges are
removed, effective capabilities are recompiled, analysis is rerun, and all
capability-specific protected workflows remain reachable. The current checked
in evidence remains the registered single-instance verification; the 15-graph
replication is a required run, not a silently inferred result.

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

Submission status: all three notebooks are complete and structurally
validated, but none has an authenticated Colab receipt yet. They must be
described as prepared launches, not completed large runs.

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

## Completion gate and current status

| Gate | Status |
|---|---|
| Exactly 225 verified small runs | **Pass: 225/225** |
| 45 clean controls and 90 injected units at small scale | **Pass** |
| Five methods for every small paired graph unit | **Pass** |
| Run manifests and checksum verification | **Pass** |
| Exactly 225 verified medium runs | **Pending; not claimed** |
| Three authenticated Colab receipts | **Pending; not claimed** |
| Counterfactual remediation after edge application | **Pass on the registered verification instance** |
| Paper/tables/figures regenerated only from verified artifacts | **Pass for the small matrix and remediation instance** |

The paper's inferential conclusions therefore use only the complete small
matrix. Future medium and large receipts may add scalability evidence but may
not retroactively change the pre-specified small-scale result.
