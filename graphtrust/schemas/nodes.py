"""Canonical node model and enums."""

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any

from pydantic import Field, field_validator

from graphtrust.schemas.base import StrictModel

StableId = Annotated[str, Field(min_length=1, max_length=512)]


class NodeType(StrEnum):
    HUMAN_IDENTITY = "HUMAN_IDENTITY"
    SERVICE_ACCOUNT = "SERVICE_ACCOUNT"
    WORKLOAD_IDENTITY = "WORKLOAD_IDENTITY"
    EXTERNAL_IDENTITY = "EXTERNAL_IDENTITY"
    GROUP = "GROUP"
    ROLE = "ROLE"
    POLICY = "POLICY"
    PERMISSION_SET = "PERMISSION_SET"
    APPLICATION = "APPLICATION"
    REPOSITORY = "REPOSITORY"
    PIPELINE = "PIPELINE"
    SECRET = "SECRET"
    DATASET = "DATASET"
    DATABASE = "DATABASE"
    STORAGE_BUCKET = "STORAGE_BUCKET"
    COMPUTE_RESOURCE = "COMPUTE_RESOURCE"
    CLOUD_ACCOUNT = "CLOUD_ACCOUNT"
    CLOUD_PROJECT = "CLOUD_PROJECT"
    CLOUD_FOLDER = "CLOUD_FOLDER"
    CLOUD_ORGANIZATION = "CLOUD_ORGANIZATION"
    SAAS_TENANT = "SAAS_TENANT"
    NETWORK_ZONE = "NETWORK_ZONE"
    CRITICAL_ASSET = "CRITICAL_ASSET"


class Provider(StrEnum):
    AWS_LIKE = "AWS_LIKE"
    AZURE_LIKE = "AZURE_LIKE"
    GCP_LIKE = "GCP_LIKE"
    SAAS = "SAAS"
    INTERNAL = "INTERNAL"
    GENERIC = "GENERIC"


class Environment(StrEnum):
    PROD = "PROD"
    STAGING = "STAGING"
    DEV = "DEV"
    SHARED = "SHARED"
    CORPORATE = "CORPORATE"


class PrivilegeLabel(StrEnum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    ADMIN = "ADMIN"


class IdentityStatus(StrEnum):
    ACTIVE = "ACTIVE"
    DORMANT = "DORMANT"
    DISABLED = "DISABLED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


def deterministic_json(value: str | dict[str, Any]) -> str:
    """Normalize object JSON so hashes do not depend on insertion order."""
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, dict):
        raise ValueError("tags_json must represent a JSON object")
    return json.dumps(parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class GraphNode(StrictModel):
    """One node in the raw directed property multigraph."""

    node_id: StableId
    node_type: NodeType
    display_name: Annotated[str, Field(min_length=1, max_length=512)]
    provider: Provider
    tenant_id: StableId
    environment: Environment
    department: Annotated[str, Field(min_length=1, max_length=128)] = "SYSTEM"
    owner_node_id: StableId | None = None
    criticality: float = Field(ge=0, le=1)
    privilege_label: PrivilegeLabel = PrivilegeLabel.NONE
    identity_status: IdentityStatus = IdentityStatus.NOT_APPLICABLE
    authentication_strength: float = Field(ge=0, le=1)
    created_at: datetime
    last_used_at: datetime | None = None
    tags_json: str = "{}"
    generator_seed: int
    ground_truth_labels_json: str | None = None

    @field_validator("created_at", "last_used_at")
    @classmethod
    def timestamps_must_be_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise ValueError("timestamps must be timezone-aware UTC")
        return value

    @field_validator("tags_json", "ground_truth_labels_json")
    @classmethod
    def normalize_json(cls, value: str | None) -> str | None:
        return None if value is None else deterministic_json(value)

    def truth_hidden(self) -> "GraphNode":
        """Return the inference-safe view with benchmark labels removed."""
        return self.model_copy(update={"ground_truth_labels_json": None})
