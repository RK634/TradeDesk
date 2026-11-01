"""Contracts for order archive, restoration, and historical access."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ArchiveRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 3:
            raise ValueError("An archive reason of at least three characters is required.")
        return value


class ArchiveRecordOut(BaseModel):
    record_id: UUID
    record_type: Literal["import_order", "export_order"]
    reference: str
    status: str
    partner_name: str
    currency: str
    archived_at: datetime | None = None
    archived_by_user_id: UUID | None = None
    archive_reason: str | None = None
    created_at: datetime


class ArchivePage(BaseModel):
    items: list[ArchiveRecordOut]
    total: int
    page: int
    page_size: int


class ArchiveEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    record_type: str
    record_id: UUID
    record_reference: str
    action: str
    reason: str
    actor_user_id: UUID | None
    created_at: datetime
