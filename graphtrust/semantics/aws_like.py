"""AWS-like scope normalization."""

from graphtrust.semantics.generic import normalize_scope as normalize_generic_scope


def normalize_scope(scope: str) -> str:
    """Normalize an ARN-like scope while preserving case-sensitive resource components."""
    normalized = normalize_generic_scope(scope)
    return "arn:" + normalized[4:] if normalized.lower().startswith("arn:") else normalized
