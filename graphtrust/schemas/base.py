"""Shared schema behavior."""

from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Immutable schema that rejects undeclared fields."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)
