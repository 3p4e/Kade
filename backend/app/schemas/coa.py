from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CoaParameterIn(BaseModel):
    name: str
    method: str | None = None
    result: str | None = None
    units: str | None = None
    specification: str | None = None
    pass_fail: str | None = None
    sort_order: int = 0


class CoaParameterOut(CoaParameterIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID


class CoaBase(BaseModel):
    doc_code: str | None = None
    batch_number: str | None = None
    sample_id: str | None = None
    product_name: str | None = None
    product_specification: str | None = None
    strain_name: str | None = None
    potency: str | None = None
    laboratory_id: UUID | None = None
    service_provider_id: UUID | None = None
    manufacturer_name: str | None = None
    manufacturer_address: str | None = None
    sample_receipt_date: date | None = None
    analysis_start_date: date | None = None
    analysis_completion_date: date | None = None
    overall_status: str | None = None
    extra_fields: dict[str, Any] = Field(default_factory=dict)


class CoaCreate(CoaBase):
    ingestion_method: str = "upload"
    parameters: list[CoaParameterIn] = Field(default_factory=list)


class CoaUpdate(CoaBase):
    parameters: list[CoaParameterIn] | None = None


class CoaOut(CoaBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    ingestion_method: str
    ingested_at: datetime
    original_filename: str | None = None
    file_path: str | None = None
    file_sha256: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime
    parameters: list[CoaParameterOut] = Field(default_factory=list)


class CoaListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    doc_code: str | None
    batch_number: str | None
    product_name: str | None
    strain_name: str | None
    laboratory_id: UUID | None
    overall_status: str | None
    analysis_completion_date: date | None
    ingestion_method: str
    ingested_at: datetime


class CoaListResponse(BaseModel):
    items: list[CoaListItem]
    total: int
    limit: int
    offset: int


class IngestPreview(BaseModel):
    """Auto-extracted fields shown to the user before saving."""

    extracted_text_preview: str
    fields: dict[str, Any]
    parameters: list[CoaParameterIn]
    discovered_placeholders: list[str]
    file_sha256: str
    file_path: str
    original_filename: str
    duplicate_of: UUID | None = None
