"""Generate application, repository, pipeline, and execution-identity workflows."""

from graphtrust.generator.models import GenerationState
from graphtrust.generator.resources import ResourceCatalog


def generate_workload_relationships(
    state: GenerationState,
    resources: ResourceCatalog,
) -> None:
    """Connect owned systems through plausible CI/CD and workload execution chains."""
    applications = list(resources.by_type["APPLICATION"])
    repositories = list(resources.by_type["REPOSITORY"])
    pipelines = list(resources.by_type["PIPELINE"])
    compute = list(resources.by_type["COMPUTE_RESOURCE"])
    secrets = [
        item for item in resources.by_type["SECRET"] if item not in resources.critical_assets
    ]
    service_accounts = state.nodes_by_type["SERVICE_ACCOUNT"]
    workload_identities = state.nodes_by_type["WORKLOAD_IDENTITY"]
    active_humans = [
        node_id
        for node_id in state.nodes_by_type["HUMAN_IDENTITY"]
        if state.node_by_id[node_id]["identity_status"] == "ACTIVE"
    ]
    chain_count = max(len(applications), len(repositories), len(pipelines))
    for index in range(chain_count):
        application = applications[index % len(applications)]
        repository = repositories[index % len(repositories)]
        pipeline = pipelines[index % len(pipelines)]
        workload = workload_identities[index % len(workload_identities)]
        service = service_accounts[(index * 3) % len(service_accounts)]
        owner = str(state.node_by_id[application]["owner_node_id"])
        if owner not in active_humans:
            owner = active_humans[index % len(active_humans)]
        state.add_edge(owner, application, "OWNS", protected=True, business_removal_cost=10)
        state.add_edge(
            owner,
            repository,
            "MANAGES",
            business_removal_cost=state.random_cost(protected=True),
            protected=True,
        )
        state.add_edge(repository, pipeline, "CAN_TRIGGER", relative_exploitability=0.72)
        state.add_edge(pipeline, workload, "RUNS_AS", relative_exploitability=0.88)
        state.add_edge(application, service, "RUNS_AS", relative_exploitability=0.88)
        state.add_edge(
            pipeline,
            compute[index % len(compute)],
            "DEPLOYS_TO",
            relative_exploitability=0.82,
        )
        if secrets:
            state.add_edge(
                service,
                secrets[index % len(secrets)],
                "READS",
                relative_exploitability=0.95,
            )


def ensure_production_execution_identities(
    state: GenerationState,
    resources: ResourceCatalog,
) -> tuple[str, ...]:
    """Return production pipelines that still lack a RUNS_AS edge."""
    execution_sources = {
        str(edge["source_id"]) for edge in state.edges if edge["edge_type"] == "RUNS_AS"
    }
    return tuple(
        pipeline
        for pipeline in resources.by_type["PIPELINE"]
        if state.node_by_id[pipeline]["environment"] == "PROD" and pipeline not in execution_sources
    )
