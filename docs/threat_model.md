# Threat model and responsible use

GraphTrust models an authorized reviewer examining a static, sanitized IAM snapshot for potential authorization exposure. The protected assets are graph nodes labeled critical; the modeled adverse outcome is an identity obtaining a typed authorization path to such an asset. Controls include conditions, explicit denies, authentication strength, protected edges, and mandatory business workflows.

Out of scope are credential theft, vulnerability exploitation, malware, network reachability, runtime session state, social engineering, probabilistic loss, live tenant enumeration, and automatic enforcement. A path is evidence of modeled reachability, not proof that a person or workload can or did abuse it.

The service accepts local datasets and produces read-only analysis and recommendation artifacts. It has no connector or endpoint that applies IAM changes. Operators must authorize and sanitize any external input, review compiler provenance, validate provider-specific exceptions independently, and test recommendations in a controlled change process.
