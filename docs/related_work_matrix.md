# Related-work boundary

GraphTrust is not the first identity or permission-flow graph. The claim is
narrower: a controlled, truth-separated benchmark evaluates analyst-budget
ranking, explanation fidelity, and counterfactual workflow-preserving
remediation across normalized identity semantics.

| System | Multi-hop | Cross-platform | Controlled ground truth | Ranking evaluation | Counterfactual workflow verification |
|---|---:|---:|---:|---:|---:|
| PMapper | Yes | No (AWS) | No | No | No |
| AWS IAM Access Analyzer | Partial, scope-dependent | No (AWS) | No | No | No |
| BloodHound OpenGraph | Yes | Yes | No public benchmark truth | Limited/product-oriented | Product guidance |
| TAC / IAMVulGen | Yes | AWS-oriented | Synthetic | Detection-focused | No workflow check |
| IAMPERE | Yes | AWS | Synthetic + two real configurations | Repair-focused | Repair validation |
| **GraphTrust** | **Yes** | **Normalized synthetic** | **Paired synthetic truth held out until scoring** | **Precision/recall at review budgets** | **Yes, after graph recompilation** |

The closest overlap is IAMPERE, which repairs IAM privilege escalations with
an approximately minimal MaxSAT/GNN-assisted patch. GraphTrust differs in
endpoint and protocol: it measures how typed semantics concentrate evidence in
a bounded analyst queue, retains hop-level provenance, and checks that a
counterfactual cut preserves explicitly encoded business workflows. These are
complementary capabilities, not a claim that GraphTrust dominates IAMPERE.

Sources: NCC Group's PMapper repository, SpecterOps OpenGraph documentation,
AWS IAM Access Analyzer documentation, TAC/IAMVulGen as discussed by Hu et al.
(2023), and IAMPERE (Hu et al., 2023, ASE paper).
