"""Validated API contracts for Phase 6 import management."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Currency = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]
Cost = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
OptionalCountry = Annotated[str | None, Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")]


class ImportStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    APPROVED = "approved"
    REJECTED = "rejected"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class TransportMode(str, Enum):
    SEA = "sea"
    AIR = "air"
    ROAD = "road"
    RAIL = "rail"
    COURIER = "courier"
    OTHER = "other"


class ShipmentStatus(str, Enum):
    PLANNED = "planned"
    IN_TRANSIT = "in_transit"
    ARRIVED = "arrived"
    DELAYED = "delayed"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class DocumentVerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class ORMOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("This field cannot be blank.")
    return value


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class ImportItemCreate(BaseModel):
    product_id: UUID
    quantity_ordered: PositiveQuantity
    unit_price: Cost
    description: Annotated[str | None, Field(max_length=1000)] = None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ImportItemUpdate(BaseModel):
    quantity_ordered: PositiveQuantity | None = None
    unit_price: Cost | None = None
    description: Annotated[str | None, Field(max_length=1000)] = None

    @model_validator(mode="after")
    def validate_update(self) -> "ImportItemUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        for key in ("quantity_ordered", "unit_price"):
            if key in self.model_fields_set and getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null.")
        return self

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ImportItemOut(ORMOut):
    id: UUID
    organization_id: UUID
    order_id: UUID
    line_number: int
    product_id: UUID
    product_sku_snapshot: str
    product_name_snapshot: str
    description: str | None
    quantity_ordered: Decimal
    quantity_received: Decimal
    quantity_remaining: Decimal
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime
    updated_at: datetime


class ImportOrderCreate(BaseModel):
    supplier_id: UUID
    currency: Currency = "EUR"
    purchase_terms: Annotated[str | None, Field(max_length=120)] = None
    country_of_origin: OptionalCountry = None
    destination: Annotated[str | None, Field(max_length=300)] = None
    estimated_departure_date: date | None = None
    estimated_arrival_date: date | None = None
    estimated_freight_cost: Cost = Decimal("0")
    estimated_insurance_cost: Cost = Decimal("0")
    estimated_duties: Cost = Decimal("0")
    estimated_other_costs: Cost = Decimal("0")
    assigned_user_id: UUID | None = None
    notes: Annotated[str | None, Field(max_length=3000)] = None
    items: Annotated[list[ImportItemCreate], Field(max_length=100)] = Field(default_factory=list)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("country_of_origin")
    @classmethod
    def clean_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("purchase_terms", "destination", "notes")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "ImportOrderCreate":
        if self.estimated_departure_date and self.estimated_arrival_date and self.estimated_arrival_date < self.estimated_departure_date:
            raise ValueError("Estimated arrival cannot be before estimated departure.")
        return self


class ImportOrderUpdate(BaseModel):
    currency: Currency | None = None
    purchase_terms: Annotated[str | None, Field(max_length=120)] = None
    country_of_origin: OptionalCountry = None
    destination: Annotated[str | None, Field(max_length=300)] = None
    estimated_departure_date: date | None = None
    estimated_arrival_date: date | None = None
    assigned_user_id: UUID | None = None
    notes: Annotated[str | None, Field(max_length=3000)] = None

    @model_validator(mode="after")
    def validate_update(self) -> "ImportOrderUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        if "currency" in self.model_fields_set and self.currency is None:
            raise ValueError("currency cannot be null.")
        if self.currency:
            self.currency = self.currency.upper()
        if self.country_of_origin:
            self.country_of_origin = self.country_of_origin.upper()
        return self

    @field_validator("purchase_terms", "destination", "notes")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ImportCostUpdate(BaseModel):
    actual_freight_cost: Cost | None = None
    actual_insurance_cost: Cost | None = None
    actual_duties: Cost | None = None
    actual_other_costs: Cost | None = None

    @model_validator(mode="after")
    def ensure_cost_update(self) -> "ImportCostUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one actual cost field.")
        for key in self.model_fields_set:
            if getattr(self, key) is None:
                raise ValueError(f"{key} cannot be null.")
        return self


class ImportOrderStatusHistoryOut(ORMOut):
    id: UUID
    from_status: str | None
    to_status: str
    reason: str | None
    actor_user_id: UUID
    created_at: datetime


class ImportOrderOut(ORMOut):
    id: UUID
    organization_id: UUID
    reference: str
    supplier_id: UUID
    supplier_name: str
    status: ImportStatus
    currency: str
    purchase_terms: str | None
    country_of_origin: str | None
    destination: str | None
    estimated_departure_date: date | None
    estimated_arrival_date: date | None
    actual_departure_date: date | None
    actual_arrival_date: date | None
    estimated_freight_cost: Decimal
    estimated_insurance_cost: Decimal
    estimated_duties: Decimal
    estimated_other_costs: Decimal
    estimated_goods_total: Decimal
    estimated_total_cost: Decimal
    actual_freight_cost: Decimal
    actual_insurance_cost: Decimal
    actual_duties: Decimal
    actual_other_costs: Decimal
    actual_total_cost: Decimal
    assigned_user_id: UUID | None
    notes: str | None
    created_by_user_id: UUID
    submitted_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    archived_at: datetime | None = None
    archived_by_user_id: UUID | None = None
    archive_reason: str | None = None
    created_at: datetime
    updated_at: datetime
    items: list[ImportItemOut] = Field(default_factory=list)
    status_history: list[ImportOrderStatusHistoryOut] = Field(default_factory=list)


class ImportOrderPage(BaseModel):
    items: list[ImportOrderOut]
    total: int
    page: int
    page_size: int


class RejectImportRequest(BaseModel):
    reason: Annotated[str, Field(min_length=3, max_length=2000)]

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return _required_text(value)


class ImportShipmentCreate(BaseModel):
    shipment_reference: Annotated[str, Field(min_length=2, max_length=64)]
    carrier: Annotated[str | None, Field(max_length=180)] = None
    tracking_reference: Annotated[str | None, Field(max_length=180)] = None
    transport_mode: TransportMode = TransportMode.SEA
    origin: Annotated[str | None, Field(max_length=300)] = None
    destination: Annotated[str | None, Field(max_length=300)] = None
    estimated_departure: date | None = None
    estimated_arrival: date | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None

    @field_validator("shipment_reference")
    @classmethod
    def clean_reference(cls, value: str) -> str:
        return _required_text(value).upper()

    @field_validator("carrier", "tracking_reference", "origin", "destination", "notes")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "ImportShipmentCreate":
        if self.estimated_departure and self.estimated_arrival and self.estimated_arrival < self.estimated_departure:
            raise ValueError("Estimated arrival cannot be before estimated departure.")
        return self


class ImportShipmentUpdate(BaseModel):
    carrier: Annotated[str | None, Field(max_length=180)] = None
    tracking_reference: Annotated[str | None, Field(max_length=180)] = None
    origin: Annotated[str | None, Field(max_length=300)] = None
    destination: Annotated[str | None, Field(max_length=300)] = None
    estimated_departure: date | None = None
    actual_departure: date | None = None
    estimated_arrival: date | None = None
    actual_arrival: date | None = None
    status: ShipmentStatus | None = None
    delay_reason: Annotated[str | None, Field(max_length=2000)] = None
    notes: Annotated[str | None, Field(max_length=2000)] = None

    @model_validator(mode="after")
    def validate_update(self) -> "ImportShipmentUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self

    @field_validator("carrier", "tracking_reference", "origin", "destination", "delay_reason", "notes")
    @classmethod
    def clean_optional(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ImportShipmentOut(ORMOut):
    id: UUID
    organization_id: UUID
    order_id: UUID
    shipment_reference: str
    carrier: str | None
    tracking_reference: str | None
    transport_mode: TransportMode
    origin: str | None
    destination: str | None
    estimated_departure: date | None
    actual_departure: date | None
    estimated_arrival: date | None
    actual_arrival: date | None
    status: ShipmentStatus
    delay_reason: str | None
    notes: str | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class ShipmentMilestoneCreate(BaseModel):
    name: Annotated[str, Field(min_length=2, max_length=120)]
    description: Annotated[str | None, Field(max_length=1000)] = None
    occurred_at: datetime

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _required_text(value)

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return _optional_text(value)


class ShipmentMilestoneOut(ORMOut):
    id: UUID
    organization_id: UUID
    order_id: UUID
    shipment_id: UUID
    name: str
    description: str | None
    occurred_at: datetime
    created_by_user_id: UUID
    created_at: datetime


class GoodsReceiptItemCreate(BaseModel):
    order_item_id: UUID
    quantity_received: PositiveQuantity


class GoodsReceiptCreate(BaseModel):
    location_id: UUID
    receipt_reference: Annotated[str, Field(min_length=2, max_length=64)]
    idempotency_key: Annotated[str, Field(min_length=8, max_length=80)]
    notes: Annotated[str | None, Field(max_length=2000)] = None
    items: Annotated[list[GoodsReceiptItemCreate], Field(min_length=1, max_length=100)]

    @field_validator("receipt_reference")
    @classmethod
    def clean_reference(cls, value: str) -> str:
        return _required_text(value).upper()

    @field_validator("idempotency_key")
    @classmethod
    def clean_idempotency_key(cls, value: str) -> str:
        value = _required_text(value)
        if len(value) < 8:
            raise ValueError("idempotency_key must contain at least 8 non-space characters.")
        return value

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def ensure_unique_lines(self) -> "GoodsReceiptCreate":
        item_ids = [item.order_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("A receipt cannot contain the same order line more than once.")
        return self


class GoodsReceiptItemOut(ORMOut):
    id: UUID
    order_id: UUID
    receipt_id: UUID
    order_item_id: UUID
    quantity_received: Decimal
    product_id: UUID
    product_sku: str
    product_name: str


class GoodsReceiptOut(ORMOut):
    id: UUID
    organization_id: UUID
    order_id: UUID
    location_id: UUID
    receipt_reference: str
    idempotency_key: str
    received_at: datetime
    notes: str | None
    received_by_user_id: UUID
    items: list[GoodsReceiptItemOut] = Field(default_factory=list)


class ImportDocumentOut(ORMOut):
    id: UUID
    organization_id: UUID
    order_id: UUID
    document_reference: str
    document_type: str
    file_name: str
    content_type: str
    file_size: int
    verification_status: DocumentVerificationStatus
    verification_notes: str | None
    expiry_date: date | None
    uploaded_by_user_id: UUID
    verified_by_user_id: UUID | None
    verified_at: datetime | None
    created_at: datetime


class ImportDocumentUpdate(BaseModel):
    verification_status: DocumentVerificationStatus | None = None
    verification_notes: Annotated[str | None, Field(max_length=2000)] = None
    expiry_date: date | None = None

    @model_validator(mode="after")
    def ensure_update(self) -> "ImportDocumentUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        return self

    @field_validator("verification_notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return _optional_text(value)
