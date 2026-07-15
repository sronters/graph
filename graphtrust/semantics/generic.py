"""Provider-neutral scope normalization."""


def normalize_scope(scope: str) -> str:
    """Normalize separators and redundant trailing slashes without provider assumptions."""
    normalized = scope.strip().replace("\\", "/")
    if normalized != "/":
        normalized = normalized.rstrip("/")
    return normalized or "*"
