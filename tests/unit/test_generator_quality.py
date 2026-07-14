"""Scale-safety tests for generator structural quality checks."""

from graphtrust.generator.quality_report import _group_cycles, _nesting_depth


def nested_edge(index: int, target: int) -> dict[str, object]:
    return {
        "edge_type": "NESTED_IN",
        "active": True,
        "source_id": f"group:{index}",
        "target_id": f"group:{target}",
    }


def test_deep_group_chain_does_not_depend_on_python_recursion_limit() -> None:
    edges = [nested_edge(index, index + 1) for index in range(5_000)]
    assert _group_cycles(edges) == ()
    assert _nesting_depth(edges) == 5_000


def test_iterative_group_cycle_detection_preserves_cycle_evidence() -> None:
    edges = [nested_edge(0, 1), nested_edge(1, 2), nested_edge(2, 0)]
    assert _group_cycles(edges) == (("group:0", "group:1", "group:2", "group:0"),)
