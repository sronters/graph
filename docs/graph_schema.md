# Canonical graph schema

The canonical graph is a directed heterogeneous multigraph stored in Parquet. `nodes.parquet` identifies stable nodes and their type, provider, status, criticality, authentication strength, organization fields, and provenance. `edges.parquet` identifies source/target IDs, typed relationship, effect, scope, optional condition, direct/derived status, confidence, exploitability, business-removal cost, protection/removability, validity, and source artifact. `conditions.parquet` stores a stable condition ID plus normalized expression and original text.

Supported node classes cover human, external, workload, and service identities; groups; roles; policies; repositories; pipelines; secrets; data stores; infrastructure; applications; and organizational containers. Typed edges include membership/nesting, role assignment/assumption, reads/writes/administers, impersonation/modification, repository-to-pipeline, runs-as, federation, and approved access.

The raw graph is immutable input. Semantic compilation creates a separate effective-capability graph. A derived edge is valid only when its endpoints exist, its condition has a modeled state, and it records both a named derivation rule and the ordered raw evidence edge IDs. Stable serialization preserves IDs and analysis results.
