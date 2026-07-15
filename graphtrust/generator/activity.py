"""Generate 180-day aggregate activity evidence."""

from datetime import timedelta

from graphtrust.generator.models import GenerationState


def generate_activity(state: GenerationState) -> None:
    """Generate plausibility evidence without using it as planted truth."""
    identity_types = {
        "HUMAN_IDENTITY",
        "SERVICE_ACCOUNT",
        "WORKLOAD_IDENTITY",
        "EXTERNAL_IDENTITY",
    }
    window_start = state.generated_at - timedelta(days=180)
    for node in state.nodes:
        if node["node_type"] not in identity_types:
            continue
        status = str(node["identity_status"])
        event_count = (
            0
            if status == "DISABLED"
            else int(state.rng.negative_binomial(2, 0.35))
            if status == "DORMANT"
            else 5 + int(state.rng.negative_binomial(8, 0.18))
        )
        state.activity.append(
            {
                "node_id": node["node_id"],
                "window_start": window_start,
                "window_end": state.generated_at,
                "event_count": event_count,
                "last_activity_at": node["last_used_at"],
            }
        )
