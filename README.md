# GraphTrust

GraphTrust is a reproducible research system for explainable whole-identity graph analysis of multi-hop IAM exposure. It compiles normalized, synthetic IAM relationships into a typed effective-capability graph, ranks potential authorization paths to critical assets, and evaluates recommendation-only remediations under modeled business constraints.

GraphTrust does **not** prove exploitability, collect credentials, enumerate live cloud environments, or execute permission changes. Edge weights are ordinal relative-risk parameters rather than calibrated breach probabilities. Remediation plans are optimal only under their declared costs and constraints.

## Status

The repository is being implemented in the dependency order defined by the engineering specification. Generated metrics and claims will be added only after reproducible experiments create traceable run artifacts.

## Development setup

```bash
uv sync --all-extras
uv run graphtrust --help
uv run pytest -m "not performance"
```

Python 3.11 or 3.12 is required. The canonical datasets are synthetic and must not be represented as measurements of real enterprises.

## Responsible use

Use GraphTrust only with synthetic data or sanitized configuration exports that you are authorized to analyze. The system is defensive and recommendation-only.

## License

Source code is licensed under Apache-2.0. Generated SEIB-2026 datasets are synthetic; their manifests and dataset cards carry the applicable dataset notice and generation parameters.
