"""Unified shipment list, update, and milestone schemas."""
from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ShipmentType(str, Enum):
    IMPORT = "import"
    EXPORT = "export"


class ShipmentStatusUpdate(str, Enum):
    PLANNED = "planned"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class ShipmentOut(BaseModel):
    id: UUID
    organization_id: UUID
    shipment_type: ShipmentType
    order_id: UUID
    order_reference: str
    shipment_reference: str
    carrier: str | None
    tracking_reference: str | None
    transport_mode: str
    origin: str | None
    destination: str | None
    estimated_departure: date | None
    actual_departure: date | None
    estimated_arrival: date | None
    actual_arrival: date | None
    status: str
    delay_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime | None = None


class ShipmentUpdate(BaseModel):
    status: ShipmentStatusUpdate | None = None
    carrier: str | None = Field(default=None, max_length=180)
    tracking_reference: str | None = Field(default=None, max_length=180)
    origin: str | None = Field(default=None, max_length=300)
    destination: str | None = Field(default=None, max_length=300)
    estimated_departure: date | None = None
    actual_departure: date | None = None
    estimated_arrival: date | None = None
    actual_arrival: date | None = None
    delay_reason: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_changes(self) -> "ShipmentUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one shipment field to update.")
        if "actual_arrival" in self.model_fields_set and self.actual_arrival is None:
            raise ValueError("actual_arrival cannot be cleared through this endpoint.")
        if "actual_departure" in self.model_fields_set and self.actual_departure is None:
            raise ValueError("actual_departure cannot be cleared through this endpoint.")
        return self

    @field_validator("carrier", "tracking_reference", "origin", "destination", "delay_reason", "notes")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ShipmentMilestoneCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    occurred_at: datetime

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class ShipmentMilestoneOut(BaseModel):
    id: UUID
    organization_id: UUID
    order_id: UUID
    shipment_id: UUID
    name: str
    description: str | None
    occurred_at: datetime
    created_by_user_id: UUID
    created_at: datetime
