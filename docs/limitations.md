# Limitations

- Synthetic structural realism does not guarantee real-world representativeness.
- Risk weights are ordinal modeling assumptions, not incident probabilities.
- Static snapshots omit temporal session behavior and some runtime enforcement details.
- IAM semantics are normalized and may not capture every provider-specific exception.
- Top-K bounded path search can omit paths; truncation is reported.
- Ground-truth injection favors known scenario families.
- Business-removal costs are modeled proxies.
- Critical-asset labeling is organization-dependent.
- Comparison baselines are research abstractions, not blanket descriptions of commercial products.
- Reachability represents potential authorization exposure, not proof of successful misuse.

Mitigations include paired variants, truth separation, provider-specific fixtures, conservative UNKNOWN handling, backend parity tests, explicit caps, counterfactual remediation verification, preregistered seeds, uncertainty intervals, complete manifests, and retention of negative results. These mitigations improve auditability; they do not remove the limitations.
