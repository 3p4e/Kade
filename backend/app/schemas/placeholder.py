from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PlaceholderIn(BaseModel):
    key: str
    label: str
    data_type: str = "string"
    enum_values: list[str] | None = None
    description: str | None = None
    pattern_hints: list[str] | None = None


class PlaceholderOut(PlaceholderIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    occurrence_count: int
    status: str
    discovered_at: datetime
    approved_at: datetime | None = None


class PlaceholderApproval(BaseModel):
    status: str  # approved | deprecated
