"""Size-based generator performance guardrails."""

import time

import pytest

from graphtrust.generator.models import SCALE_SPECS
from graphtrust.generator.runner import build_clean_state


@pytest.mark.performance
def test_medium_clean_generation_meets_declared_size() -> None:
    started = time.perf_counter()
    state, _, _ = build_clean_state("regulated_finance", "medium", 2750159)
    elapsed = time.perf_counter() - started
    spec = SCALE_SPECS["medium"]
    assert len(state.edges) == spec.raw_edges
    assert len(state.nodes) == (
        spec.humans + spec.non_humans + spec.groups + spec.roles + spec.resources
    )
    assert elapsed < 180
