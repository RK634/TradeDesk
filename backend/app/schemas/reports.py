"""Typed response contracts for organization reports."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class ReportDateRange(BaseModel):
    start_date: date
    end_date: date


class StatusCount(BaseModel):
    status: str
    count: int


class CurrencyTotal(BaseModel):
    currency: str
    amount: Decimal


class OrderReportRow(BaseModel):
    record_id: UUID
    direction: str
    reference: str
    partner_name: str
    status: str
    currency: str
    order_total: Decimal
    created_at: datetime


class ImportCostReportRow(BaseModel):
    record_id: UUID
    reference: str
    supplier_name: str
    status: str
    currency: str
    estimated_goods_total: Decimal
    estimated_costs: Decimal
    estimated_total: Decimal
    actual_costs: Decimal
    actual_total: Decimal
    variance: Decimal
    created_at: datetime


class PartnerReportRow(BaseModel):
    direction: str
    partner_name: str
    currency: str
    order_count: int
    order_value: Decimal


class ShipmentPerformanceRow(BaseModel):
    shipment_id: UUID
    direction: str
    shipment_reference: str
    order_reference: str
    partner_name: str
    status: str
    transport_mode: str
    estimated_arrival: date | None
    actual_arrival: date | None
    days_late: int | None
    delay_reason: str | None
    created_at: datetime


class MissingDocumentReportRow(BaseModel):
    requirement_id: UUID
    related_entity_type: str
    related_entity_id: UUID
    record_reference: str
    partner_name: str
    document_type: str
    label: str
    created_at: datetime


class InventoryReportRow(BaseModel):
    product_id: UUID
    sku: str
    product_name: str
    location_id: UUID
    location_code: str
    location_name: str
    quantity_on_hand: Decimal
    reserved_quantity: Decimal
    available_quantity: Decimal
    reorder_threshold: Decimal
    is_low_stock: bool


class InventoryMovementReportRow(BaseModel):
    id: UUID
    product_id: UUID
    sku: str
    product_name: str
    location_id: UUID
    location_code: str
    movement_type: str
    quantity_delta: Decimal
    reserved_delta: Decimal
    quantity_on_hand_after: Decimal
    reserved_quantity_after: Decimal
    source_type: str | None
    source_reference: str | None
    created_by_user_id: UUID
    created_at: datetime


class FinancialCurrencySummary(BaseModel):
    currency: str
    receivables_outstanding: Decimal
    payables_outstanding: Decimal
    overdue_receivables: Decimal
    overdue_payables: Decimal


class FinancialReport(BaseModel):
    start_date: date
    end_date: date
    by_currency: list[FinancialCurrencySummary]


class ReportSummary(BaseModel):
    start_date: date
    end_date: date
    imports: dict
    exports: dict
    shipments: dict
    inventory: dict
    missing_required_documents: int
    financial: list[FinancialCurrencySummary] | None = None
