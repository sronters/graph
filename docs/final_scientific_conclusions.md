# Final scientific conclusions

## Evidence boundary

The confirmatory detection result is the complete small-scale SEIB-2026
matrix: 225 checksum-verified runs spanning three enterprise profiles, five
held-out seeds, three paired variants, and five methods. Recall and ranking
estimates use the 30 injected graphs; the 15 clean graphs are negative
controls. The enterprise graph, not an individual path, is the statistical
unit. A declared cloud follow-up independently generated 15 injected-mixed
organizations for depth-stratified detection and replicated remediation.
GitHub Actions run `29387806389` completed all 15 graph jobs and its aggregate
gate; the checked-in CSVs and manifest match the immutable workflow artifact.
Medium and large runs remain pending scalability evidence and are not used to
rewrite the small-scale confirmatory result.

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

The cloud depth follow-up reinforces this boundary. At analysis depth six,
GraphTrust exact-path recall was 0.914, 0.600, and 0.333 for planted path
depths two, three, and four; untyped traversal reached 0.914, 0.600, and
0.667. Across all planted depths, GraphTrust plateaued at 0.708 after analysis
depth four, while untyped traversal reached 0.785. Native scope reached 0.185,
and direct and privileged-only audits remained at zero. Because the frozen
benchmark contains no one-hop planted risk, the direct-audit zero is
benchmark-conditional and is not evidence that direct audits never work.

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

The cloud replication evaluated four remediation methods on 15 independent
`(profile, seed)` organizations at requested exposure-reduction levels of
50%, 70%, 80%, 90%, and 95%. Weighted minimum cut produced one unique plan per
organization; the same plan was checked against all five thresholds, so its 75
CSV rows represent 15 independent plans rather than 75 independent samples.

Across those 15 plans, weighted minimum cut reduced modeled exposure by a mean
0.9771 (cluster-bootstrap 95% CI [0.9748, 0.9795]) using a mean 28.13 raw IAM
changes at modeled cost 22.96 and mean runtime 3.62 seconds. All 15 plans met
the 95% target, passed post-application graph recompilation, and preserved all
encoded protected workflows. Profile means were 0.9830 for global hybrid,
0.9747 for regulated finance, and 0.9736 for SaaS scale-up.

At the 95% request, risk greedy achieved mean reduction 0.8706 at cost 7.55,
constraint generation achieved 0.8100 at cost 245.31, and degree greedy
achieved 0.7333 at cost 1430.92. These methods generally did not attain the
requested weighted target, although every produced plan passed counterfactual
verification and workflow checks. Constraint generation uses a distinct
path-count objective, so this is an objective comparison rather than evidence
of an invalid solver. H3 is supported for the encoded weighted min-cut
objective across the 15 frozen synthetic organizations; it does not prove
global minimality or operational safety in a live company.

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
explanation. Across 15 frozen organizations, weighted min-cut counterfactuals reduced
modeled exposure by 97.71% on average while preserving every encoded workflow.
GraphTrust should therefore complement provider-native IAM tools and human
review; it is not autonomous enforcement or evidence of real-world breach
probability.
