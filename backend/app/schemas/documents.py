"""Schemas for cross-workflow document storage, verification, and requirements."""
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RelatedEntityType(str, Enum):
    IMPORT_ORDER = "import_order"
    IMPORT_SHIPMENT = "import_shipment"
    EXPORT_ORDER = "export_order"
    EXPORT_SHIPMENT = "export_shipment"


class VerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class DocumentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    version_number: int
    file_name: str
    content_type: str
    file_size: int
    sha256: str
    uploaded_by_user_id: UUID
    created_at: datetime


class DocumentOut(BaseModel):
    id: UUID
    organization_id: UUID
    document_reference: str
    document_type: str
    title: str
    description: str | None
    related_entity_type: RelatedEntityType
    related_entity_id: UUID
    verification_status: VerificationStatus
    verification_notes: str | None
    expiry_date: date | None
    current_version: int
    uploaded_by_user_id: UUID
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    created_at: datetime
    updated_at: datetime
    current_file_name: str
    current_content_type: str
    current_file_size: int
    versions: list[DocumentVersionOut] = Field(default_factory=list)


class VerificationUpdate(BaseModel):
    verification_status: VerificationStatus
    verification_notes: str | None = Field(default=None, max_length=2000)

    @field_validator("verification_notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class DocumentRequirementCreate(BaseModel):
    related_entity_type: RelatedEntityType
    related_entity_id: UUID
    document_type: str = Field(min_length=2, max_length=64)
    label: str = Field(min_length=2, max_length=180)
    is_required: bool = True

    @field_validator("document_type")
    @classmethod
    def clean_document_type(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("label")
    @classmethod
    def clean_label(cls, value: str) -> str:
        return value.strip()


class DocumentRequirementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    organization_id: UUID
    related_entity_type: RelatedEntityType
    related_entity_id: UUID
    document_type: str
    label: str
    is_required: bool
    created_by_user_id: UUID
    created_at: datetime


class DocumentComplianceItem(BaseModel):
    requirement_id: UUID
    document_type: str
    label: str
    is_required: bool
    uploaded_count: int
    verified_count: int
    satisfied: bool


class DocumentComplianceOut(BaseModel):
    related_entity_type: RelatedEntityType
    related_entity_id: UUID
    required_count: int
    satisfied_count: int
    missing_count: int
    is_compliant: bool
    items: list[DocumentComplianceItem]


class DocumentVerificationEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    document_id: UUID
    version_number: int
    from_status: str
    to_status: str
    notes: str | None
    actor_user_id: UUID
    created_at: datetime
