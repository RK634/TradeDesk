"""Validated request and response schemas for Phase 5 master data."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Name = Annotated[str, Field(min_length=2, max_length=180)]
ShortCode = Annotated[str, Field(min_length=1, max_length=64)]
CurrencyCode = Annotated[str, Field(min_length=3, max_length=3, pattern=r"^[A-Za-z]{3}$")]
CountryCode = Annotated[str | None, Field(min_length=2, max_length=2, pattern=r"^[A-Za-z]{2}$")]
PositivePrice = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
NonnegativeQty = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]


class ORMOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _normalize_required(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("This field cannot be blank.")
    return normalized


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _normalize_email(value: str | None) -> str | None:
    value = _normalize_optional(value)
    if value is None:
        return None
    if len(value) > 320 or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValueError("Enter a valid email address.")
    return value.lower()


def _normalize_currency(value: str) -> str:
    return value.strip().upper()


def _normalize_country(value: str | None) -> str | None:
    return value.strip().upper() if value else None


class CustomerFields(BaseModel):
    customer_code: Annotated[str | None, Field(max_length=48)] = None
    name: Name
    company_name: Annotated[str | None, Field(max_length=180)] = None
    contact_person: Annotated[str | None, Field(max_length=160)] = None
    email: Annotated[str | None, Field(max_length=320)] = None
    phone: Annotated[str | None, Field(max_length=40)] = None
    billing_address: Annotated[str | None, Field(max_length=1000)] = None
    delivery_address: Annotated[str | None, Field(max_length=1000)] = None
    country: CountryCode = None
    tax_id: Annotated[str | None, Field(max_length=80)] = None
    payment_terms_days: Annotated[int, Field(ge=0, le=365)] = 0
    currency: CurrencyCode = "EUR"
    notes: Annotated[str | None, Field(max_length=2000)] = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _normalize_required(value)

    @field_validator("company_name", "contact_person", "phone", "billing_address", "delivery_address", "tax_id", "notes")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("customer_code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        value = _normalize_optional(value)
        return value.upper() if value else None

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        return _normalize_email(value)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return _normalize_currency(value)

    @field_validator("country")
    @classmethod
    def clean_country(cls, value: str | None) -> str | None:
        return _normalize_country(value)


class CustomerCreate(CustomerFields):
    customer_code: Annotated[str | None, Field(max_length=48)] = None


class CustomerUpdate(BaseModel):
    customer_code: Annotated[str | None, Field(max_length=48)] = None
    name: Annotated[str | None, Field(min_length=2, max_length=180)] = None
    company_name: Annotated[str | None, Field(max_length=180)] = None
    contact_person: Annotated[str | None, Field(max_length=160)] = None
    email: Annotated[str | None, Field(max_length=320)] = None
    phone: Annotated[str | None, Field(max_length=40)] = None
    billing_address: Annotated[str | None, Field(max_length=1000)] = None
    delivery_address: Annotated[str | None, Field(max_length=1000)] = None
    country: CountryCode = None
    tax_id: Annotated[str | None, Field(max_length=80)] = None
    payment_terms_days: Annotated[int | None, Field(ge=0, le=365)] = None
    currency: CurrencyCode | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def ensure_change(self) -> "CustomerUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        for field_name in ("name", "payment_terms_days", "currency", "is_active"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _normalize_required(value) if value is not None else None

    @field_validator("customer_code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        value = _normalize_optional(value)
        return value.upper() if value else None

    @field_validator("company_name", "contact_person", "phone", "billing_address", "delivery_address", "tax_id", "notes")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        return _normalize_email(value)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str | None) -> str | None:
        return _normalize_currency(value) if value else value

    @field_validator("country")
    @classmethod
    def clean_country(cls, value: str | None) -> str | None:
        return _normalize_country(value)


class CustomerOut(ORMOut):
    id: UUID
    organization_id: UUID
    customer_code: str | None
    name: str
    company_name: str | None
    contact_person: str | None
    email: str | None
    phone: str | None
    billing_address: str | None
    delivery_address: str | None
    country: str | None
    tax_id: str | None
    payment_terms_days: int
    currency: str
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SupplierFields(BaseModel):
    supplier_code: Annotated[str | None, Field(max_length=48)] = None
    name: Name
    company_name: Annotated[str | None, Field(max_length=180)] = None
    contact_person: Annotated[str | None, Field(max_length=160)] = None
    email: Annotated[str | None, Field(max_length=320)] = None
    phone: Annotated[str | None, Field(max_length=40)] = None
    address: Annotated[str | None, Field(max_length=1000)] = None
    country: CountryCode = None
    tax_id: Annotated[str | None, Field(max_length=80)] = None
    payment_terms_days: Annotated[int, Field(ge=0, le=365)] = 0
    currency: CurrencyCode = "EUR"
    notes: Annotated[str | None, Field(max_length=2000)] = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _normalize_required(value)

    @field_validator("company_name", "contact_person", "phone", "address", "tax_id", "notes")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("supplier_code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        value = _normalize_optional(value)
        return value.upper() if value else None

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        return _normalize_email(value)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return _normalize_currency(value)

    @field_validator("country")
    @classmethod
    def clean_country(cls, value: str | None) -> str | None:
        return _normalize_country(value)


class SupplierCreate(SupplierFields):
    pass


class SupplierUpdate(BaseModel):
    supplier_code: Annotated[str | None, Field(max_length=48)] = None
    name: Annotated[str | None, Field(min_length=2, max_length=180)] = None
    company_name: Annotated[str | None, Field(max_length=180)] = None
    contact_person: Annotated[str | None, Field(max_length=160)] = None
    email: Annotated[str | None, Field(max_length=320)] = None
    phone: Annotated[str | None, Field(max_length=40)] = None
    address: Annotated[str | None, Field(max_length=1000)] = None
    country: CountryCode = None
    tax_id: Annotated[str | None, Field(max_length=80)] = None
    payment_terms_days: Annotated[int | None, Field(ge=0, le=365)] = None
    currency: CurrencyCode | None = None
    notes: Annotated[str | None, Field(max_length=2000)] = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def ensure_change(self) -> "SupplierUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        for field_name in ("name", "payment_terms_days", "currency", "is_active"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _normalize_required(value) if value is not None else None

    @field_validator("supplier_code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        value = _normalize_optional(value)
        return value.upper() if value else None

    @field_validator("company_name", "contact_person", "phone", "address", "tax_id", "notes")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("email")
    @classmethod
    def clean_email(cls, value: str | None) -> str | None:
        return _normalize_email(value)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str | None) -> str | None:
        return _normalize_currency(value) if value else value

    @field_validator("country")
    @classmethod
    def clean_country(cls, value: str | None) -> str | None:
        return _normalize_country(value)


class SupplierOut(ORMOut):
    id: UUID
    organization_id: UUID
    supplier_code: str | None
    name: str
    company_name: str | None
    contact_person: str | None
    email: str | None
    phone: str | None
    address: str | None
    country: str | None
    tax_id: str | None
    payment_terms_days: int
    currency: str
    notes: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductFields(BaseModel):
    sku: ShortCode
    name: Name
    description: Annotated[str | None, Field(max_length=2000)] = None
    category: Annotated[str | None, Field(max_length=100)] = None
    unit_of_measure: Annotated[str, Field(min_length=1, max_length=24)] = "pcs"
    purchase_price: PositivePrice = Decimal("0")
    selling_price: PositivePrice = Decimal("0")
    currency: CurrencyCode = "EUR"
    reorder_threshold: NonnegativeQty = Decimal("0")
    is_active: bool = True

    @field_validator("sku")
    @classmethod
    def clean_sku(cls, value: str) -> str:
        return _normalize_required(value).upper()

    @field_validator("name", "unit_of_measure")
    @classmethod
    def clean_required_strings(cls, value: str) -> str:
        return _normalize_required(value)

    @field_validator("description", "category")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str) -> str:
        return _normalize_currency(value)


class ProductCreate(ProductFields):
    pass


class ProductUpdate(BaseModel):
    sku: ShortCode | None = None
    name: Annotated[str | None, Field(min_length=2, max_length=180)] = None
    description: Annotated[str | None, Field(max_length=2000)] = None
    category: Annotated[str | None, Field(max_length=100)] = None
    unit_of_measure: Annotated[str | None, Field(min_length=1, max_length=24)] = None
    purchase_price: PositivePrice | None = None
    selling_price: PositivePrice | None = None
    currency: CurrencyCode | None = None
    reorder_threshold: NonnegativeQty | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def ensure_change(self) -> "ProductUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        for field_name in ("sku", "name", "unit_of_measure", "purchase_price", "selling_price", "currency", "reorder_threshold", "is_active"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self

    @field_validator("sku")
    @classmethod
    def clean_sku(cls, value: str | None) -> str | None:
        return _normalize_required(value).upper() if value is not None else None

    @field_validator("name", "unit_of_measure")
    @classmethod
    def clean_required_strings(cls, value: str | None) -> str | None:
        return _normalize_required(value) if value is not None else None

    @field_validator("description", "category")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional(value)

    @field_validator("currency")
    @classmethod
    def clean_currency(cls, value: str | None) -> str | None:
        return _normalize_currency(value) if value else value


class ProductOut(ORMOut):
    id: UUID
    organization_id: UUID
    sku: str
    name: str
    description: str | None
    category: str | None
    unit_of_measure: str
    purchase_price: Decimal
    selling_price: Decimal
    currency: str
    reorder_threshold: Decimal
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LocationCreate(BaseModel):
    code: ShortCode
    name: Name
    description: Annotated[str | None, Field(max_length=1000)] = None
    address: Annotated[str | None, Field(max_length=1000)] = None
    is_active: bool = True

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        return _normalize_required(value).upper()

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        return _normalize_required(value)

    @field_validator("description", "address")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional(value)


class LocationUpdate(BaseModel):
    code: ShortCode | None = None
    name: Annotated[str | None, Field(min_length=2, max_length=180)] = None
    description: Annotated[str | None, Field(max_length=1000)] = None
    address: Annotated[str | None, Field(max_length=1000)] = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def ensure_change(self) -> "LocationUpdate":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update.")
        for field_name in ("code", "name", "is_active"):
            if field_name in self.model_fields_set and getattr(self, field_name) is None:
                raise ValueError(f"{field_name} cannot be null.")
        return self

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str | None) -> str | None:
        return _normalize_required(value).upper() if value is not None else None

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str | None) -> str | None:
        return _normalize_required(value) if value is not None else None

    @field_validator("description", "address")
    @classmethod
    def clean_optional_strings(cls, value: str | None) -> str | None:
        return _normalize_optional(value)


class LocationOut(ORMOut):
    id: UUID
    organization_id: UUID
    code: str
    name: str
    description: str | None
    address: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

from typing import Generic, TypeVar

TOut = TypeVar("TOut")


class Page(BaseModel, Generic[TOut]):
    items: list[TOut]
    total: int
    page: int
    page_size: int
