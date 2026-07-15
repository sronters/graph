# GraphTrust replicated cloud evidence

## Evidence boundary

This summary uses GitHub Actions run `29387806389` at source commit
`2bb5a44fa2a8187bbdfc7f90a44631dc0d54ae91`. The independent statistical unit
is one frozen synthetic organization, `(profile, seed)`, giving 15 units across
three profiles and five held-out seeds. The complete artifact contains 1,350
depth-stress rows and 300 remediation rows. SHA-256 values match the immutable
workflow manifest.

## Replicated remediation

Weighted minimum cut produced one unique plan per organization. The same plan
was checked against each requested target from 50% through 95%, so its 75 CSV
rows are repeated target checks of 15 plans, not 75 independent observations.

| Result | Weighted minimum cut |
|---|---:|
| Independent organizations | 15 |
| Mean weighted exposure reduction | **97.71%** |
| Cluster-bootstrap 95% CI | **[97.48%, 97.95%]** |
| Mean modeled cost | **22.96** |
| Mean raw IAM changes | **28.13** |
| Mean runtime | **3.62 s** |
| Counterfactual verification | **15/15** |
| Protected workflows preserved | **15/15** |
| 95% target attained | **15/15** |

Profile means at the 95% target:

| Profile | Exposure reduction | Cost | Changes | Runtime |
|---|---:|---:|---:|---:|
| Global hybrid | 98.30% | 23.54 | 31.4 | 3.55 s |
| Regulated finance | 97.47% | 22.55 | 29.6 | 3.37 s |
| SaaS scale-up | 97.36% | 22.78 | 23.4 | 3.20 s |

The alternative solvers did not generally attain the requested weighted target.
At the 95% request, their mean achieved reductions were 87.06% for risk greedy,
81.00% for constraint generation, and 73.33% for degree greedy. All generated
plans nevertheless passed counterfactual verification and preserved encoded
workflows. This comparison is objective-specific: constraint generation uses a
different path-count objective and must not be described as a failed weighted
min-cut implementation.

## Depth-stratified exact-path recall

At analysis depth six:

| Method | Planted depth 2 | Planted depth 3 | Planted depth 4 |
|---|---:|---:|---:|
| GraphTrust | 91.43% | 60.00% | 33.33% |
| Untyped traversal | 91.43% | 60.00% | 66.67% |
| Native scope | 22.86% | 26.67% | 0.00% |
| Direct audit | 0.00% | 0.00% | 0.00% |
| Privileged-only | 0.00% | 0.00% | 0.00% |

Across all planted depths, GraphTrust exact-path recall rose from 0% at analysis
depth one to 55.38% at depth two, 63.08% at depth three, and 70.77% at depth
four; no further gain occurred at depths five or six. Untyped traversal reached
78.46% at depth four. This supports a transitive-coverage claim against narrow
audits but rejects an exhaustive-recall superiority claim over untyped search.

The benchmark contains planted path depths 2, 3, and 4 but no depth-1 planted
risk. Therefore the zero direct-audit result is benchmark-conditional. A future
supplemental benchmark should add frozen one-hop risks and clean twins rather
than silently rewriting the completed experiment.

## Defensible interpretation

The replicated evidence strengthens remediation substantially: weighted minimum
cut consistently reduced modeled exposure by about 97.7% across all 15 frozen
organizations while preserving every encoded workflow. Detection results remain
more nuanced. GraphTrust closes transitive blind spots relative to direct,
privileged-only, and native-scope abstractions, but untyped traversal recovers
more exact depth-4 planted paths. GraphTrust's main detection contribution is
therefore analyst-budget ranking and hop-level explanation, not universal recall.

