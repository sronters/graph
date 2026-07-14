"""Stable SHA-256 helpers for datasets and experiment artifacts."""

import hashlib
from collections.abc import Iterable
from pathlib import Path


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    """Return a streaming SHA-256 digest for one file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_bytes(value: bytes) -> str:
    """Return the SHA-256 digest of in-memory bytes."""
    return hashlib.sha256(value).hexdigest()


def file_checksums(root: Path, relative_paths: Iterable[str]) -> dict[str, str]:
    """Hash declared files in canonical relative-path order."""
    return {relative: sha256_file(root / relative) for relative in sorted(relative_paths)}


def write_checksum_file(root: Path, relative_paths: Iterable[str]) -> dict[str, str]:
    """Write a standard sha256sum-compatible checksum inventory."""
    checksums = file_checksums(root, relative_paths)
    content = "".join(f"{digest}  {relative}\n" for relative, digest in checksums.items())
    (root / "checksums.sha256").write_text(content, encoding="utf-8", newline="\n")
    return checksums


def read_checksum_file(path: Path) -> dict[str, str]:
    """Parse a strict checksum inventory."""
    checksums: dict[str, str] = {}
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        try:
            digest, relative = line.split("  ", maxsplit=1)
        except ValueError as error:
            raise ValueError(f"Malformed checksum line {line_number}") from error
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"Invalid SHA-256 digest on line {line_number}")
        if Path(relative).is_absolute() or ".." in Path(relative).parts:
            raise ValueError(f"Unsafe checksum path on line {line_number}")
        if relative in checksums:
            raise ValueError(f"Duplicate checksum entry: {relative}")
        checksums[relative] = digest
    return checksums


def verify_checksum_file(root: Path) -> tuple[bool, tuple[str, ...]]:
    """Verify every file declared by checksums.sha256."""
    expected = read_checksum_file(root / "checksums.sha256")
    failures: list[str] = []
    for relative, digest in expected.items():
        path = root / relative
        if not path.is_file():
            failures.append(f"missing:{relative}")
        elif sha256_file(path) != digest:
            failures.append(f"mismatch:{relative}")
    return not failures, tuple(failures)


def combined_checksum(checksums: dict[str, str]) -> str:
    """Hash a filename-aware checksum mapping into a stable tree digest."""
    canonical = "".join(f"{relative}\0{checksums[relative]}\n" for relative in sorted(checksums))
    return sha256_bytes(canonical.encode("utf-8"))
