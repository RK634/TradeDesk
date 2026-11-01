"""Validated request and response contracts for export management."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Currency = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]
PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
NonNegativeMoney = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]


class ORMOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class ExportOrderItemCreate(BaseModel):
    product_id: UUID
    quantity_ordered: PositiveQuantity
    unit_price: NonNegativeMoney
    description: Annotated[str | None, Field(max_length=1000)] = None

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        return clean_optional(value)


class ExportOrderCreate(BaseModel):
    customer_id: UUID
    inventory_location_id: UUID
    currency: Currency = "EUR"
    destination_country: Annotated[str | None, Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")] = None
    delivery_address: Annotated[str | None, Field(max_length=1000)] = None
    shipping_terms: Annotated[str | None, Field(max_length=120)] = None
    payment_terms_days: int = Field(default=0, ge=0, le=3650)
    requested_ship_date: date | None = None
    requested_delivery_date: date | None = None
    assigned_user_id: UUID | None = None
    notes: Annotated[str | None, Field(max_length=3000)] = None
    items: Annotated[list[ExportOrderItemCreate], Field(min_length=1, max_length=100)]

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("destination_country")
    @classmethod
    def upper_country(cls, value: str | None) -> str | None:
        return value.upper() if value else value

    @field_validator("delivery_address", "shipping_terms", "notes")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return clean_optional(value)

    @model_validator(mode="after")
    def validate_dates(self) -> "ExportOrderCreate":
        if self.requested_ship_date and self.requested_delivery_date and self.requested_delivery_date < self.requested_ship_date:
            raise ValueError("Requested delivery date cannot be before requested ship date.")
        return self


class ExportOrderUpdate(BaseModel):
    customer_id: UUID | None = None
    inventory_location_id: UUID | None = None
    currency: Currency | None = None
    destination_country: Annotated[str | None, Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")] = None
    delivery_address: Annotated[str | None, Field(max_length=1000)] = None
    shipping_terms: Annotated[str | None, Field(max_length=120)] = None
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    requested_ship_date: date | None = None
    requested_delivery_date: date | None = None
    assigned_user_id: UUID | None = None
    notes: Annotated[str | None, Field(max_length=3000)] = None

    @model_validator(mode="after")
    def validate_update(self) -> "ExportOrderUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        if "customer_id" in self.model_fields_set and self.customer_id is None:
            raise ValueError("customer_id cannot be null.")
        if "inventory_location_id" in self.model_fields_set and self.inventory_location_id is None:
            raise ValueError("inventory_location_id cannot be null.")
        if "currency" in self.model_fields_set and self.currency is None:
            raise ValueError("currency cannot be null.")
        if self.currency:
            self.currency = self.currency.upper()
        if self.destination_country:
            self.destination_country = self.destination_country.upper()
        return self

    @field_validator("delivery_address", "shipping_terms", "notes")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return clean_optional(value)


class ExportOrderItemOut(ORMOut):
    id: UUID
    organization_id: UUID
    order_id: UUID
    line_number: int
    product_id: UUID
    product_sku_snapshot: str
    product_name_snapshot: str
    description: str | None
    quantity_ordered: Decimal
    quantity_reserved: Decimal
    quantity_dispatched: Decimal
    quantity_delivered: Decimal
    quantity_not_dispatched: Decimal
    quantity_not_delivered: Decimal
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime
    updated_at: datetime


class ExportOrderStatusHistoryOut(ORMOut):
    id: UUID
    from_status: str | None
    to_status: str
    reason: str | None
    actor_user_id: UUID
    created_at: datetime


class ExportShipmentItemOut(ORMOut):
    id: UUID
    organization_id: UUID
    shipment_id: UUID
    order_id: UUID
    order_item_id: UUID
    quantity_dispatched: Decimal
    quantity_delivered: Decimal
    quantity_remaining: Decimal


class ExportShipmentOut(ORMOut):
    id: UUID
    organization_id: UUID
    order_id: UUID
    shipment_reference: str
    carrier: str | None
    tracking_reference: str | None
    transport_mode: str
    origin: str | None
    destination: str | None
    status: str
    estimated_departure: date | None
    actual_departure: date
    estimated_arrival: date | None
    actual_arrival: date | None
    notes: str | None
    created_by_user_id: UUID
    created_at: datetime
    items: list[ExportShipmentItemOut]


class ExportDeliveryItemOut(ORMOut):
    id: UUID
    organization_id: UUID
    delivery_id: UUID
    order_id: UUID
    shipment_item_id: UUID
    quantity_delivered: Decimal


class ExportDeliveryOut(ORMOut):
    id: UUID
    organization_id: UUID
    order_id: UUID
    shipment_id: UUID
    delivery_reference: str
    idempotency_key: str
    delivered_at: datetime
    notes: str | None
    delivered_by_user_id: UUID
    items: list[ExportDeliveryItemOut]


class ExportOrderOut(ORMOut):
    id: UUID
    organization_id: UUID
    reference: str
    customer_id: UUID
    customer_name: str
    inventory_location_id: UUID
    inventory_location_name: str
    status: str
    currency: str
    destination_country: str | None
    delivery_address: str | None
    shipping_terms: str | None
    payment_terms_days: int
    requested_ship_date: date | None
    requested_delivery_date: date | None
    notes: str | None
    assigned_user_id: UUID | None
    created_by_user_id: UUID
    submitted_at: datetime | None
    approved_by_user_id: UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    archived_at: datetime | None = None
    archived_by_user_id: UUID | None = None
    archive_reason: str | None = None
    goods_total: Decimal
    quantity_ordered: Decimal
    quantity_reserved: Decimal
    quantity_dispatched: Decimal
    quantity_delivered: Decimal
    created_at: datetime
    updated_at: datetime
    items: list[ExportOrderItemOut]
    status_history: list[ExportOrderStatusHistoryOut]
    shipments: list[ExportShipmentOut]


class ExportOrderPage(BaseModel):
    items: list[ExportOrderOut]
    total: int
    page: int
    page_size: int


class ExportShipmentLineCreate(BaseModel):
    order_item_id: UUID
    quantity_dispatched: PositiveQuantity


class ExportShipmentCreate(BaseModel):
    shipment_reference: Annotated[str, Field(min_length=2, max_length=64)]
    idempotency_key: Annotated[str, Field(min_length=8, max_length=80)]
    carrier: Annotated[str | None, Field(max_length=180)] = None
    tracking_reference: Annotated[str | None, Field(max_length=180)] = None
    transport_mode: str = "road"
    origin: Annotated[str | None, Field(max_length=300)] = None
    destination: Annotated[str | None, Field(max_length=300)] = None
    estimated_departure: date | None = None
    estimated_arrival: date | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None
    items: Annotated[list[ExportShipmentLineCreate], Field(min_length=1, max_length=100)]

    @field_validator("shipment_reference", "idempotency_key")
    @classmethod
    def trim_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("carrier", "tracking_reference", "origin", "destination", "notes")
    @classmethod
    def trim_optional_fields(cls, value: str | None) -> str | None:
        return clean_optional(value)

    @field_validator("transport_mode")
    @classmethod
    def validate_transport(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in {"sea", "air", "road", "rail", "courier", "other"}:
            raise ValueError("Unsupported transport mode.")
        return value


class ExportDeliveryLineCreate(BaseModel):
    shipment_item_id: UUID
    quantity_delivered: PositiveQuantity


class ExportDeliveryCreate(BaseModel):
    delivery_reference: Annotated[str, Field(min_length=2, max_length=64)]
    idempotency_key: Annotated[str, Field(min_length=8, max_length=80)]
    notes: Annotated[str | None, Field(max_length=2000)] = None
    items: Annotated[list[ExportDeliveryLineCreate], Field(min_length=1, max_length=100)]

    @field_validator("delivery_reference", "idempotency_key")
    @classmethod
    def trim_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("notes")
    @classmethod
    def trim_notes(cls, value: str | None) -> str | None:
        return clean_optional(value)


class ExportRejectRequest(BaseModel):
    reason: Annotated[str, Field(min_length=3, max_length=2000)]

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("A reason is required.")
        return value
