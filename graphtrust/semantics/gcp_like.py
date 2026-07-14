"""Google-Cloud-like scope normalization."""

from graphtrust.semantics.generic import normalize_scope as normalize_generic_scope


def normalize_scope(scope: str) -> str:
    """Normalize project/folder/organization resource names."""
    return normalize_generic_scope(scope).lower()
