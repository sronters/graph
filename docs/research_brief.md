# GraphTrust: Explainable Whole-Identity Graph Analysis

**Track:** Zero Trust security research and engineering

## Abstract

Identity risk can emerge from combinations of individually ordinary permissions across groups, roles, workloads, pipelines, service accounts, and cloud resources. GraphTrust is a platform-neutral research framework and synthetic benchmark for testing whether typed, provider-aware multi-hop graph analysis improves detection and ranking of these modeled exposures relative to four explicit audit baselines. It compiles raw authorization records into an effective-capability graph with three-valued conditions and provenance, ranks bounded paths using auditable ordinal parameters, decomposes an identity-level Zero Trust Risk Index, and produces recommendation-only remediations subject to protected workflows and change budgets. SEIB-2026 generates paired clean, injected, and truth-remediated enterprise graphs across three profiles and three scales. Predictions are saved before truth is joined; immutable run manifests retain configuration, environment, checksum, runtime, and negative-result evidence. The implementation includes reference and scalable graph backends, exact and heuristic remediation, a versioned API, investigation interface, Colab workflow, and automated correctness checks. The full preregistered evaluation matrix and three large Colab runs are not yet represented by verified artifacts in this branch; therefore this brief makes no comparative performance conclusion. Its present contribution is an executable, falsifiable protocol for measuring detection, ranking, remediation cost, and scaling with paired uncertainty.

## Research question and hypotheses

Does typed, whole-identity multi-hop analysis improve truth-matched detection and ranking on SEIB-2026 compared with direct-entitlement, privileged-identity, untyped shortest-path, and native-scope baselines? A second hypothesis asks whether constrained optimization reduces modeled exposure with fewer or lower-cost changes than degree- and risk-greedy baselines. The null hypotheses are no paired improvement in the preregistered metrics and no remediation advantage under the same constraints.

## Motivation and relation to Zero Trust

NIST Zero Trust Architecture frames access decisions around subjects, assets, and resources rather than implicit trust from network location. GraphTrust studies one supporting question: what potential authorization exposure becomes visible when identity relationships are considered as typed chains? It does not implement a Zero Trust policy engine or demonstrate compromise.

## Related work and gap

Prior systems establish that IAM graphs and attack-path analysis are not new. PMapper models AWS IAM principals and relationships as a directed graph; BloodHound performs identity attack-path analysis through an extensible graph model; AWS IAM Access Analyzer reports supported internal and external access findings; and IAM-Deescalate studies IAM privilege-escalation remediation. GraphTrust is evaluated instead as a broader, normalized research framework and benchmark: paired synthetic multi-provider graphs, explicit B0–B5 baselines, truth-hidden metrics, backend parity, business-constrained counterfactual remediation, and traceable uncertainty. This scope is a testable integration and evaluation contribution—not a claim to have invented IAM graphs.

## Graph model and benchmark

The directed heterogeneous multigraph covers human/external/workload/service identities, groups, roles, policies, code and pipelines, secrets, data, infrastructure, and applications. Typed edges retain effect, scope, condition, exploitability, control strength, business-removal cost, and provenance. Provider-aware compilation keeps raw and effective graphs separate. SEIB-2026 supplies three organization profiles, deterministic paired variants, twelve scenario families including hard negatives, and small/medium/large scale targets. Truth is physically separated from inference inputs.

## Methods and baselines

B0 examines direct entitlements, B1 privileged identities, B2 untyped shortest paths, and B3 provider-native scope. GraphTrust enumerates bounded typed paths, ranks relative risk, calculates a five-component ZTRI, reports choke points, and emits evidence-linked explanations. Remediation comparisons cover degree greedy (B4), risk greedy (B5), weighted min-cut, and iterative CP-SAT path hitting set. Protected edges and mandatory workflows are verified after each proposed plan.

## Results with uncertainty

No final result is asserted. The full `(3 profiles × 2 scales × 5 final seeds × 3 variants × 5 methods)` preregistered matrix has not yet been verified as a complete immutable artifact set, and large Colab runs are unexecuted in this branch. The reporting code computes paired bootstrap 95% intervals, exact McNemar tests, Friedman/Wilcoxon-Holm comparisons, and effect sizes only from saved run IDs. Figures with unavailable evidence say so explicitly rather than substituting synthetic headline numbers.

One five-method development smoke unit completed and is retained as a pipeline diagnostic. GraphTrust had risky-source recall 0.75, scenario F1 0.00651, and NDCG@10 0.14273; native-scope had recall 0.4167, scenario F1 0.02681, and NDCG@10 0.15022. Thus this unit does not show a general GraphTrust advantage. With `n=1`, no inferential comparison is valid; exact run IDs and checksums are listed in `docs/verification_status.md`.

## Explainability example

For every stored path, the explanation reproduces the exact ordered effective steps, condition states, named compiler rules, and raw evidence IDs. Its score panel shows starting exposure, target criticality, each transition cost, and final bounded relative risk. This makes a ranking auditable without presenting it as a breach probability.

## Remediation example

A plan identifies removable raw edges that hit the currently exposed path set. The verifier applies those removals to a counterfactual graph, recompiles semantics, checks residual reachability and protected workflows, and reports achieved reduction, total modeled cost, change count, solver status, truncation, and whether the claim was actually verified. Alternative plans are retained within the configured cost tolerance.

## Limitations and threats to validity

Synthetic structural realism does not guarantee real-world representativeness. Risk weights are ordinal modeling assumptions, not incident probabilities. Static snapshots omit temporal session behavior and some runtime enforcement details. IAM semantics are normalized and may not capture every provider-specific exception. Top-K bounded path search can omit paths; truncation is reported. Ground-truth injection favors known scenario families. Business-removal costs are modeled proxies. Critical-asset labeling is organization-dependent. Comparison baselines are research abstractions, not blanket descriptions of commercial products. Reachability represents potential authorization exposure, not proof of successful misuse.

## Conclusion

GraphTrust currently provides a reproducible implementation and falsifiable evaluation path. Whether it wins, ties, or exhibits trade-offs must be decided by the complete traceable experiment artifacts, not by the design intent.

## References

1. NIST, [SP 800-207: Zero Trust Architecture](https://csrc.nist.gov/pubs/sp/800/207/final).
2. NIST, [SP 800-207A: A Zero Trust Architecture Model for Access Control in Cloud-Native Applications](https://csrc.nist.gov/pubs/sp/800/207/a/final).
3. NIST NCCoE, [SP 1800-35: Implementing a Zero Trust Architecture](https://www.nccoe.nist.gov/publication/1800-35).
4. AWS, [IAM policy evaluation logic](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_policies_evaluation-logic.html) and [Access Analyzer findings](https://docs.aws.amazon.com/IAM/latest/UserGuide/access-analyzer-findings.html).
5. Microsoft, [Azure RBAC overview](https://learn.microsoft.com/en-us/azure/role-based-access-control/overview) and [role-assignable groups](https://learn.microsoft.com/en-us/entra/identity/role-based-access-control/groups-concept).
6. Google Cloud, [service-account impersonation](https://cloud.google.com/iam/docs/service-account-impersonation).
7. NCC Group, [Principal Mapper](https://github.com/nccgroup/PMapper).
8. SpecterOps, [BloodHound](https://github.com/SpecterOps/BloodHound) and [attack-path terminology](https://bloodhound.specterops.io/resources/glossary/overview).
9. Palo Alto Networks, [IAM-Deescalate](https://github.com/PaloAltoNetworks/IAM-Deescalate).
10. Hu et al., [Fixing Privilege Escalations in Cloud Access Control](https://spark.ece.utexas.edu/pubs/ASE-23-yang.pdf).

## AI Use Transparency Statement

OpenAI Codex assisted with specification interpretation, code and documentation generation/review, debugging, and local verification. Synthetic data are generated deterministically. Metrics may be reported only from saved manifests and checksums. Automated verification completed to date is distinguished from pending full-matrix, Colab, citation, and human review; see `docs/ai_use_statement.md`.
