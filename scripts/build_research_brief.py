"""Verify that the evidence-aware research brief and publication tables exist."""

from pathlib import Path


def main() -> None:
    brief = Path("docs/research_brief.md")
    if not brief.is_file():
        raise SystemExit("docs/research_brief.md is missing")
    text = brief.read_text(encoding="utf-8")
    required = ("## Abstract", "## Results with uncertainty", "## References")
    missing = [heading for heading in required if heading not in text]
    if missing:
        raise SystemExit(f"research brief missing sections: {missing}")
    print(f"verified {brief} ({len(text.split())} words)")


if __name__ == "__main__":
    main()
