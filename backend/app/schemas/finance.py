"""Validated request/response contracts for invoices, payments, and allocations."""
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Currency = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=2)]
PositiveMoney = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=2)]
PositiveQuantity = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=4)]
TaxRate = Annotated[Decimal, Field(ge=0, le=100, max_digits=9, decimal_places=4)]
ExchangeRate = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=8)]


class ORMOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


class InvoiceItemInput(BaseModel):
    description: Annotated[str, Field(min_length=1, max_length=1000)]
    quantity: PositiveQuantity
    unit_price: Money
    tax_rate: TaxRate = Decimal("0")

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Line description is required.")
        return cleaned


class InvoiceCreate(BaseModel):
    invoice_number: Annotated[str, Field(min_length=1, max_length=64)]
    invoice_type: Literal["supplier", "customer"]
    supplier_id: UUID | None = None
    customer_id: UUID | None = None
    import_order_id: UUID | None = None
    export_order_id: UUID | None = None
    issue_date: date
    due_date: date
    currency: Currency
    discount_amount: Money = Decimal("0.00")
    notes: Annotated[str | None, Field(max_length=3000)] = None
    items: Annotated[list[InvoiceItemInput], Field(min_length=1, max_length=100)]

    @field_validator("invoice_number")
    @classmethod
    def clean_invoice_number(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Invoice number is required.")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, value: str | None) -> str | None:
        return _clean(value)

    @model_validator(mode="after")
    def validate_invoice_relationship(self) -> "InvoiceCreate":
        if self.due_date < self.issue_date:
            raise ValueError("Due date cannot be before issue date.")
        if self.invoice_type == "supplier":
            if self.supplier_id is None or self.customer_id is not None or self.export_order_id is not None:
                raise ValueError("Supplier invoices require a supplier and cannot reference a customer or export order.")
        else:
            if self.customer_id is None or self.supplier_id is not None or self.import_order_id is not None:
                raise ValueError("Customer invoices require a customer and cannot reference a supplier or import order.")
        return self


class InvoiceUpdate(BaseModel):
    invoice_number: Annotated[str, Field(min_length=1, max_length=64)] | None = None
    issue_date: date | None = None
    due_date: date | None = None
    discount_amount: Money | None = None
    notes: Annotated[str | None, Field(max_length=3000)] = None
    items: Annotated[list[InvoiceItemInput], Field(min_length=1, max_length=100)] | None = None

    @model_validator(mode="after")
    def validate_update(self) -> "InvoiceUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one invoice field to update.")
        if "invoice_number" in self.model_fields_set and not (self.invoice_number or "").strip():
            raise ValueError("Invoice number cannot be empty.")
        return self


class InvoiceItemOut(ORMOut):
    id: UUID
    organization_id: UUID
    invoice_id: UUID
    line_number: int
    description: str
    quantity: Decimal
    unit_price: Decimal
    tax_rate: Decimal
    net_amount: Decimal
    tax_amount: Decimal
    line_total: Decimal


class InvoiceOut(ORMOut):
    id: UUID
    organization_id: UUID
    invoice_number: str
    invoice_type: str
    supplier_id: UUID | None
    customer_id: UUID | None
    partner_name: str
    import_order_id: UUID | None
    export_order_id: UUID | None
    order_reference: str | None
    status: str
    issue_date: date
    due_date: date
    currency: str
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    amount_paid: Decimal
    outstanding_balance: Decimal
    notes: str | None
    issued_by_user_id: UUID | None
    issued_at: datetime | None
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime
    items: list[InvoiceItemOut]


class InvoicePage(BaseModel):
    items: list[InvoiceOut]
    total: int
    page: int
    page_size: int


class PaymentAllocationInput(BaseModel):
    invoice_id: UUID
    allocated_payment_amount: PositiveMoney
    exchange_rate: ExchangeRate | None = None
    exchange_rate_date: date | None = None


class PaymentCreate(BaseModel):
    payment_reference: Annotated[str, Field(min_length=1, max_length=64)]
    payment_type: Literal["incoming", "outgoing"]
    payment_date: date
    currency: Currency
    amount: PositiveMoney
    payment_method: Literal["bank_transfer", "cash", "card", "cheque", "other"]
    external_reference: Annotated[str | None, Field(max_length=160)] = None
    idempotency_key: Annotated[str, Field(min_length=8, max_length=80)]
    notes: Annotated[str | None, Field(max_length=2000)] = None
    allocations: Annotated[list[PaymentAllocationInput], Field(min_length=1, max_length=100)]

    @field_validator("payment_reference", "idempotency_key")
    @classmethod
    def trim_required(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field is required.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("external_reference", "notes")
    @classmethod
    def trim_optional(cls, value: str | None) -> str | None:
        return _clean(value)

    @model_validator(mode="after")
    def unique_invoices(self) -> "PaymentCreate":
        invoice_ids = [item.invoice_id for item in self.allocations]
        if len(set(invoice_ids)) != len(invoice_ids):
            raise ValueError("Each invoice can only be allocated once per payment.")
        return self


class PaymentAllocationOut(ORMOut):
    id: UUID
    invoice_id: UUID
    invoice_number: str
    invoice_currency: str
    allocated_payment_amount: Decimal
    allocated_invoice_amount: Decimal
    exchange_rate: Decimal
    exchange_rate_date: date


class PaymentOut(ORMOut):
    id: UUID
    organization_id: UUID
    payment_reference: str
    payment_type: str
    payment_date: date
    currency: str
    amount: Decimal
    allocated_amount: Decimal
    unallocated_amount: Decimal
    payment_method: str
    external_reference: str | None
    status: str
    notes: str | None
    created_by_user_id: UUID
    reversed_by_user_id: UUID | None
    reversed_at: datetime | None
    reversal_reason: str | None
    created_at: datetime
    allocations: list[PaymentAllocationOut]


class PaymentPage(BaseModel):
    items: list[PaymentOut]
    total: int
    page: int
    page_size: int


class PaymentReversalRequest(BaseModel):
    reason: Annotated[str, Field(min_length=3, max_length=2000)]

    @field_validator("reason")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("A reversal reason is required.")
        return cleaned


class FinancialAuditEventOut(ORMOut):
    id: UUID
    entity_type: str
    entity_id: UUID
    action: str
    details: dict
    actor_user_id: UUID
    created_at: datetime
