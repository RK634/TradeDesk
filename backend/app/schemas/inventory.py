"""Inventory ledger request and response schemas."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InventoryMovementType(str, Enum):
    GOODS_RECEIVED = "goods_received"
    GOODS_DISPATCHED = "goods_dispatched"
    RESERVATION = "reservation"
    RESERVATION_RELEASE = "reservation_release"
    ADJUSTMENT_INCREASE = "adjustment_increase"
    ADJUSTMENT_DECREASE = "adjustment_decrease"
    RETURN = "return"


PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]


class InventoryMovementCreate(BaseModel):
    organization_id: UUID
    product_id: UUID
    location_id: UUID
    movement_type: InventoryMovementType
    quantity: PositiveQuantity
    idempotency_key: Annotated[str, Field(min_length=8, max_length=80)]
    source_type: Annotated[str | None, Field(max_length=40)] = None
    source_reference: Annotated[str | None, Field(max_length=120)] = None
    notes: Annotated[str | None, Field(max_length=1000)] = None

    @model_validator(mode="after")
    def validate_text(self) -> "InventoryMovementCreate":
        self.idempotency_key = self.idempotency_key.strip()
        if len(self.idempotency_key) < 8:
            raise ValueError("idempotency_key must contain at least 8 non-space characters.")
        if self.source_type is not None:
            self.source_type = self.source_type.strip() or None
        if self.source_reference is not None:
            self.source_reference = self.source_reference.strip() or None
        if self.notes is not None:
            self.notes = self.notes.strip() or None
        return self


class InventoryBalanceOut(BaseModel):
    id: UUID
    organization_id: UUID
    product_id: UUID
    product_sku: str
    product_name: str
    location_id: UUID
    location_code: str
    location_name: str
    quantity_on_hand: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
    reorder_threshold: Decimal
    is_low_stock: bool
    updated_at: datetime


class InventoryMovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    organization_id: UUID
    product_id: UUID
    location_id: UUID
    movement_type: InventoryMovementType
    quantity_delta: Decimal
    reserved_delta: Decimal
    quantity_on_hand_after: Decimal
    reserved_quantity_after: Decimal
    idempotency_key: str
    source_type: str | None
    source_reference: str | None
    notes: str | None
    created_by_user_id: UUID
    created_at: datetime
