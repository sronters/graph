# Methodology

## Research design

The experimental unit is one `(profile, scale, seed, variant)` graph. Methods are paired within the same unit. The three profiles are SaaS scale-up, regulated finance, and global hybrid; the preregistered small and medium scales contain respectively 1,920/12,000 and 27,100/250,000 target nodes/raw edges. Final evaluation seeds are `2750159`, `3681131`, `4264387`, `5000011`, and `6500027`; development seeds never enter final estimates. One large dataset per profile is reserved for Colab scaling evidence.

Inference receives nodes, raw edges, conditions, activity, and protected workflow requirements. It does not receive truth paths or scenario labels. Evaluation joins saved predictions to truth afterward.

## Semantic model

The compiler evaluates each condition in three-valued logic: TRUE, FALSE, or UNKNOWN. Conservative analysis retains UNKNOWN transitions and marks them; strict analysis excludes them. Provider modules normalize AWS-like policy evaluation, Azure-like transitive role/group relationships, GCP-like service-account impersonation, and generic workload/federation chains. A deny that matches the modeled scope overrides the corresponding allow. Raw and effective graphs remain separate; every effective edge contains a named derivation rule and raw evidence IDs.

## Risk formulas

For starting identity \(i\),

\[
E_i=\operatorname{clip}_{[0,1]}(0.35+0.35(1-a_i)+0.20d_i+0.10x_i),
\]

where \(a_i\) is authentication strength, \(d_i\) denotes dormant status, and \(x_i\) denotes an external identity. For effective edge \(e\),

\[
c_e=-\log q_e+0.08+0.35u_e+0.40s_e,
\]

where \(q_e\) is ordinal relative exploitability, \(u_e\) is one for UNKNOWN conditions, and \(s_e\) is control strength. A path \(p:i\leadsto t\) has relative risk

\[
R(p)=\operatorname{clip}_{[0,1]}\left(C_t E_i\exp(-\sum_{e\in p}c_e)\right).
\]

These values rank modeled exposure; they are not incident probabilities.

For source identity \(i\), the Zero Trust Risk Index is

\[
ZTRI_i=100(0.30CR_i+0.30BP_i+0.15PD_i+0.15BR_i+0.10CW_i).
\]

`CR` is criticality-weighted, depth-decayed reach; `BP` is best path risk; `PD` is edge-disjoint path count capped and normalized at five; `BR` is reachable criticality divided by total graph criticality; and `CW` combines authentication weakness (0.55), dormancy (0.20), external status (0.15), and UNKNOWN-step share (0.10). Components and the final score are bounded explicitly.

## Parameters

| Parameter | Primary value |
|---|---:|
| Maximum depth | 8 |
| Top-K per source/target | 20 |
| Top-K per source | 100 |
| Global path cap | 250,000 |
| Criticality threshold | 0.70 |
| Length penalty | 0.08 |
| UNKNOWN penalty | 0.35 |
| Control-strength penalty | 0.40 |
| Remediation change penalty | 0.05 |
| Solver time limit | 120 s |
| Solver iteration cap | 100 |
| Bootstrap resamples | 10,000 |

Edge-type exploitability defaults and the complete versioned parameter record are in `configs/scoring.yaml`; business constraints are in `configs/remediation.yaml`. Sensitivity analysis varies depth 4–10, condition mode, thresholds 0.60–0.90, path caps, edge multipliers, and all weights by ±20%, plus 1,000 seeded Dirichlet ZTRI weight draws.

## Methods and baselines

| ID | Definition |
|---|---|
| B0 / `direct` | Direct-entitlement findings only. |
| B1 / `privileged` | Findings from identities already labeled privileged. |
| B2 / `untyped` | Untyped shortest-path graph audit. |
| B3 / `native_scope` | Provider-native effective access within one modeled scope. |
| GraphTrust | Typed semantic compilation, bounded ranked paths, ZTRI, provenance, and explanations. |
| B4 / `degree_greedy` | Remove feasible high-degree edges first. |
| B5 / `risk_greedy` | Greedily maximize modeled risk reduction per removal cost. |
| `min_cut` | Weighted removable-edge cut with protected-edge constraints. |
| `constraint_generation` | CP-SAT path hitting set, adding residual paths until verified or capped. |

Remediation minimizes removal cost plus residual-exposure and change penalties subject to protected edges, mandatory workflows, global/department/provider budgets, and target reduction. Every returned plan is counterfactually re-run; `verified` is never inferred from solver status alone.

## Metrics and uncertainty

Detection metrics are exact-path precision/recall/F1, scenario precision/recall/F1, risky-source recall, critical-target coverage, unmatched findings per 1,000 identities, Recall@5/10/20, NDCG@10/20, and mean reciprocal rank. Remediation metrics include verified exposure reduction, residual reachability, removal cost, change count, protected-workflow preservation, feasibility, and solver status. Runtime includes wall time and sampled peak resident memory.

Uncertainty uses paired graph-level bootstrap 95% confidence intervals with 10,000 resamples and standardized paired mean effects. Binary paired scenario outcomes use exact two-sided McNemar tests. Multi-method comparisons use a Friedman omnibus test followed by paired Wilcoxon tests with Holm correction and rank-biserial effects. Negative, truncated, timed-out, and infeasible results remain in the artifact set.
