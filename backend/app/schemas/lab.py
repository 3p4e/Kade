from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class LaboratoryIn(BaseModel):
    name: str
    location: str | None = None
    address: str | None = None
    accreditation_body: str | None = None
    accreditation_number: str | None = None
    accreditation_standard: str | None = None
    accreditation_valid_until: date | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    notes: str | None = None


class LaboratoryOut(LaboratoryIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
    updated_at: datetime


class ServiceProviderIn(BaseModel):
    name: str
    contact_name: str | None = None
    contact_email: str | None = None
    contact_phone: str | None = None
    agreement_ref: str | None = None
    notes: str | None = None


class ServiceProviderOut(ServiceProviderIn):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    created_at: datetime
