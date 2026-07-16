import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Coa(Base):
    __tablename__ = "coas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )

    doc_code: Mapped[str | None] = mapped_column(String)
    batch_number: Mapped[str | None] = mapped_column(String)
    sample_id: Mapped[str | None] = mapped_column(String)

    product_name: Mapped[str | None] = mapped_column(String)
    product_specification: Mapped[str | None] = mapped_column(Text)
    strain_name: Mapped[str | None] = mapped_column(String)
    potency: Mapped[str | None] = mapped_column(String)

    laboratory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("laboratories.id", ondelete="SET NULL")
    )
    service_provider_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("service_providers.id", ondelete="SET NULL")
    )

    manufacturer_name: Mapped[str | None] = mapped_column(String)
    manufacturer_address: Mapped[str | None] = mapped_column(Text)

    sample_receipt_date: Mapped[date | None] = mapped_column(Date)
    analysis_start_date: Mapped[date | None] = mapped_column(Date)
    analysis_completion_date: Mapped[date | None] = mapped_column(Date)

    overall_status: Mapped[str | None] = mapped_column(String)

    original_filename: Mapped[str | None] = mapped_column(String)
    file_path: Mapped[str | None] = mapped_column(String)
    file_sha256: Mapped[str | None] = mapped_column(String)
    ingestion_method: Mapped[str] = mapped_column(String, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    extracted_text: Mapped[str | None] = mapped_column(Text)
    extra_fields: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coas.id", ondelete="SET NULL")
    )

    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    parameters: Mapped[list["CoaParameter"]] = relationship(
        back_populates="coa", cascade="all, delete-orphan", order_by="CoaParameter.sort_order"
    )
    chunks: Mapped[list["CoaChunk"]] = relationship(
        back_populates="coa", cascade="all, delete-orphan"
    )


class CoaParameter(Base):
    __tablename__ = "coa_parameters"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    coa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coas.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    method: Mapped[str | None] = mapped_column(String)
    result: Mapped[str | None] = mapped_column(String)
    units: Mapped[str | None] = mapped_column(String)
    specification: Mapped[str | None] = mapped_column(String)
    pass_fail: Mapped[str | None] = mapped_column(String)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    coa: Mapped[Coa] = relationship(back_populates="parameters")


class CoaChunk(Base):
    __tablename__ = "coa_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    coa_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("coas.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384))
    token_count: Mapped[int | None] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    coa: Mapped[Coa] = relationship(back_populates="chunks")
