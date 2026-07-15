"""Deterministic SEIB-2026 dataset card rendering."""

from graphtrust.schemas.manifests import DatasetManifest


def render_dataset_card(manifest: DatasetManifest) -> str:
    """Render dataset metadata without inventing experimental results."""
    counts = "\n".join(
        f"| {name} | {count:,} |" for name, count in sorted(manifest.realized_counts.items())
    )
    warnings = (
        "\n".join(f"- {warning}" for warning in manifest.warnings)
        if manifest.warnings
        else "- None recorded by generation or validation."
    )
    return f"""# Dataset card: {manifest.dataset_id}

## Summary

This dataset is part of **{manifest.benchmark_name}**, a deterministic synthetic benchmark
for defensive IAM graph research. It is structurally generated and is not statistically
representative of all real enterprises.

- Profile: `{manifest.profile}`
- Scale: `{manifest.scale.value}`
- Variant: `{manifest.variant.value}`
- Generator seed: `{manifest.generator_seed}`
- Git commit: `{manifest.git_commit}`
- Configuration SHA-256: `{manifest.config_sha256}`
- Dependency lock SHA-256: `{manifest.package_lock_sha256}`

## Realized counts

| Measure | Count |
|---|---:|
{counts}

## Truth separation

Ground-truth scenario and path labels are stored only in the dedicated `truth_*.parquet`
files. Canonical `nodes.parquet` and `edges.parquet` are inference-safe and exclude
truth-label columns.

## Intended use and limits

Use this dataset for reproducible evaluation of potential authorization-path detection,
ranking, explanation, and recommendation-only remediation. Reachability is potential
exposure, not proof of exploitability. Relative edge weights are ordinal assumptions, not
calibrated breach probabilities. Remediation optimality is limited to modeled costs and
constraints.

## Recorded warnings

{warnings}
"""
