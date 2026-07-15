"""B2 untyped shortest-path ranking baseline."""

from graphtrust.schemas.findings import PathFinding


def untyped_rank_key(finding: PathFinding) -> tuple[int, float, str]:
    """Rank by hop count, then asset criticality, then canonical edge sequence."""
    return (len(finding.path), -finding.risk.criticality, finding.finding_id)
