# Final scientific conclusions

## Evidence boundary

The confirmatory detection result is the complete small-scale SEIB-2026
matrix: 225 checksum-verified runs spanning three enterprise profiles, five
held-out seeds, three paired variants, and five methods. Recall and ranking
estimates use the 30 injected graphs; the 15 clean graphs are negative
controls. The enterprise graph, not an individual path, is the statistical
unit. Medium and large runs, when executed, are scalability evidence and must
not be used to rewrite the small-scale confirmatory result. They were not
completed in an authenticated high-memory environment for this submission.

## Detection and ranking

GraphTrust detected transitive risk that direct and privileged-only audits
missed in this benchmark. Mean risky-starting-identity and scenario recall
were both 0.758 (95% bootstrap interval approximately [0.731, 0.781]), while
both narrow baselines were 0.000. Against native-scope auditing, the paired
risky-identity recall gain was +0.367 [0.331, 0.403]. These results support H1
only against the explicitly defined narrow baselines.

GraphTrust did not increase risky-identity or scenario recall over untyped
whole-graph traversal: the paired difference was exactly 0.000 [0.000,
0.000]. Untyped traversal also had higher exact-path recall by 0.036 on
average; GraphTrust minus untyped was -0.036 [-0.049, -0.023]. Therefore the
experiment rejects any claim of universal detection superiority. The winning
endpoint is operational review budget: the operator's independent audit
reanalysis reports GraphTrust recall@10 = 18.9% versus 0.26% for untyped
traversal, and precision@10 = 10.3% versus 0.33% (MRR 0.0549 versus 0.0053).
These supplementary values remain explicitly labeled as audit reanalysis
until the complete raw run manifest is attached.

Typed semantics materially improved prioritization. Mean NDCG@10 was 0.125
for GraphTrust, 0.002 for untyped traversal, and 0.009 for native scope. The
paired GraphTrust-minus-untyped difference was +0.123 [0.083, 0.164], with a
standardized mean effect of 1.05. The five-method Friedman test for NDCG@10
was significant (p = 3.37e-13), and the Holm-corrected GraphTrust/untyped
comparison remained significant. H2 is therefore supported as a ranking
claim, not a recall claim.

## False-positive burden

The clean negative controls expose an important limitation. GraphTrust
reported a mean 13,786.9 unmatched findings per 1,000 identities, close to
untyped traversal at 13,890.0; native scope reported 285.2, and the direct and
privileged-only baselines reported zero. In SEIB-2026, an unmatched path means
"not one of the planted ground-truth conditions," not necessarily a real-world
false alarm. Nevertheless, the result shows that whole-graph reachability
must be ranked, filtered, contextualized, and reviewed rather than treated as
an incident list. GraphTrust's strongest measured benefit is prioritization
and explanation within a large candidate surface.

## Counterfactual remediation

The verified weighted min-cut plan removed 22 raw IAM relationships at modeled
cost 18.58. Recompiling the counterfactual graph blocked 20,632 of 20,675
enumerated paths and reduced modeled exposure by 97.1%, while all protected
workflows remained reachable. The verifier recorded
`counterfactual_verified=true`; no live permission was changed.

This does not prove that 22 changes are globally minimal in a real company.
It is the minimum-cut recommendation under the encoded graph, cost, protected
edge, and bounded-path assumptions. The alternative plans demonstrate the
objective trade-off: risk-greedy used 8 changes and cost 6.37 but left 23.0%
residual exposure; degree-greedy used 76 changes and left 42.7%; the
constraint-generation plan used 111 changes and left 50.4% under its distinct
path-count objective. H3 is supported for the min-cut objective on the
verification instance, not as a universal optimizer ranking.

## Robustness and validity

Across 1,000 deterministic random ZTRI-weight samples, the median Spearman
rank correlation was 0.997; the minimum was 0.928. This supports ranking
stability around the chosen weights on the tested development graph. It does
not calibrate ZTRI as a breach probability. The ablation and sensitivity
analyses use one development graph and remain diagnostic.

The conclusions are limited to deterministic synthetic snapshots. Provider
normalization, ordinal risk weights, planted scenario families, bounded path
search, generated business costs, and generated protected workflows all limit
external validity. Reachability means modeled authorization exposure, not
attacker intent, exploit success, or a confirmed compromise.

## Defensible final claim

Whole-identity graph traversal closes transitive blind spots left by direct
and privileged-only audit abstractions in SEIB-2026. Untyped traversal finds
much of that attack surface, but typed GraphTrust semantics make the queue more
reviewable at a fixed analyst budget and retain hop-level evidence for
explanation. Counterfactual graph recompilation can verify that a cost-aware
remediation reduces modeled exposure without breaking encoded workflows.
GraphTrust should therefore complement provider-native IAM tools and human
review; it is not autonomous enforcement or evidence of real-world breach
probability.
