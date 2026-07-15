"""B1 privileged-identity seed-selection baseline."""

from graphtrust.schemas.nodes import GraphNode, PrivilegeLabel


def is_privileged_start(node: GraphNode) -> bool:
    return node.privilege_label in {PrivilegeLabel.HIGH, PrivilegeLabel.ADMIN}
