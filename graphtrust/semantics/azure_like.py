"""Azure-like scope normalization."""

from graphtrust.semantics.generic import normalize_scope as normalize_generic_scope


def normalize_scope(scope: str) -> str:
    """Normalize an Azure resource ID into a stable slash-prefixed form."""
    normalized = normalize_generic_scope(scope)
    if normalized == "*":
        return normalized
    return "/" + normalized.lstrip("/")
