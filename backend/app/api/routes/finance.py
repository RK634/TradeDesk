"""Organization-scoped invoice and payment workflows with immutable financial history."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.core.security import utc_now, verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import (
    Customer, ExportOrder, FinancialAuditEvent, ImportOrder, Invoice, InvoiceItem,
    Payment, PaymentAllocation, Supplier, User, UserSession,
)
from app.schemas.finance import (
    FinancialAuditEventOut, InvoiceCreate, InvoiceOut, InvoicePage, InvoiceUpdate,
    PaymentAllocationInput, PaymentCreate, PaymentOut, PaymentPage, PaymentReversalRequest,
)

router = APIRouter(tags=["finance"])
CENT = Decimal("0.01")
ZERO = Decimal("0.00")
ONE = Decimal("1")


def money(value: Decimal) -> Decimal:
    """All invoice/payment amounts use two decimal places, ROUND_HALF_UP."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _verify_mutation(request: Request, csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def _audit(db: Session, organization_id: UUID, entity_type: str, entity_id: UUID,
           action: str, actor_id: UUID, details: dict | None = None) -> None:
    db.add(FinancialAuditEvent(
        organization_id=organization_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details=details or {},
        actor_user_id=actor_id,
    ))


def _line_totals(line) -> tuple[Decimal, Decimal, Decimal]:
    net = money(line.quantity * line.unit_price)
    tax = money(net * line.tax_rate / Decimal("100"))
    return net, tax, money(net + tax)


def _calculate_invoice(items) -> tuple[Decimal, Decimal, list[tuple[Decimal, Decimal, Decimal]]]:
    totals = [_line_totals(item) for item in items]
    return money(sum((row[0] for row in totals), ZERO)), money(sum((row[1] for row in totals), ZERO)), totals


def _invoice_paid_amount(db: Session, invoice_id: UUID, organization_id: UUID) -> Decimal:
    value = db.query(func.coalesce(func.sum(PaymentAllocation.allocated_invoice_amount), 0)).join(
        Payment,
        (Payment.id == PaymentAllocation.payment_id)
        & (Payment.organization_id == PaymentAllocation.organization_id),
    ).filter(
        PaymentAllocation.invoice_id == invoice_id,
        PaymentAllocation.organization_id == organization_id,
        Payment.status == "posted",
    ).scalar()
    return money(Decimal(str(value or 0)))


def _invoice_payload(db: Session, invoice: Invoice) -> dict:
    items = db.query(InvoiceItem).filter(
        InvoiceItem.invoice_id == invoice.id,
        InvoiceItem.organization_id == invoice.organization_id,
    ).order_by(InvoiceItem.line_number.asc()).all()
    if invoice.invoice_type == "supplier":
        partner = db.query(Supplier).filter(
            Supplier.id == invoice.supplier_id,
            Supplier.organization_id == invoice.organization_id,
        ).one()
        order = db.query(ImportOrder).filter(
            ImportOrder.id == invoice.import_order_id,
            ImportOrder.organization_id == invoice.organization_id,
        ).one_or_none() if invoice.import_order_id else None
    else:
        partner = db.query(Customer).filter(
            Customer.id == invoice.customer_id,
            Customer.organization_id == invoice.organization_id,
        ).one()
        order = db.query(ExportOrder).filter(
            ExportOrder.id == invoice.export_order_id,
            ExportOrder.organization_id == invoice.organization_id,
        ).one_or_none() if invoice.export_order_id else None
    amount_paid = _invoice_paid_amount(db, invoice.id, invoice.organization_id)
    outstanding = max(money(invoice.total_amount - amount_paid), ZERO)
    effective_status = invoice.status
    if invoice.status in {"issued", "partially_paid"} and invoice.due_date < utc_now().date() and outstanding > ZERO:
        effective_status = "overdue"
    return {
        "id": invoice.id,
        "organization_id": invoice.organization_id,
        "invoice_number": invoice.invoice_number,
        "invoice_type": invoice.invoice_type,
        "supplier_id": invoice.supplier_id,
        "customer_id": invoice.customer_id,
        "partner_name": partner.name,
        "import_order_id": invoice.import_order_id,
        "export_order_id": invoice.export_order_id,
        "order_reference": order.reference if order else None,
        "status": effective_status,
        "issue_date": invoice.issue_date,
        "due_date": invoice.due_date,
        "currency": invoice.currency,
        "subtotal": invoice.subtotal,
        "tax_amount": invoice.tax_amount,
        "discount_amount": invoice.discount_amount,
        "total_amount": invoice.total_amount,
        "amount_paid": amount_paid,
        "outstanding_balance": outstanding,
        "notes": invoice.notes,
        "issued_by_user_id": invoice.issued_by_user_id,
        "issued_at": invoice.issued_at,
        "created_by_user_id": invoice.created_by_user_id,
        "created_at": invoice.created_at,
        "updated_at": invoice.updated_at,
        "items": items,
    }


def _invoice_out(db: Session, invoice: Invoice) -> InvoiceOut:
    return InvoiceOut.model_validate(_invoice_payload(db, invoice))


def _scoped_invoice(db: Session, user_id: UUID, organization_id: UUID, invoice_id: UUID,
                    permission: str = "invoices.read", *, lock: bool = False) -> Invoice:
    require_org_permission(db, user_id, organization_id, permission)
    query = db.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.organization_id == organization_id,
    )
    if lock:
        query = query.with_for_update()
    invoice = query.one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    return invoice


def _partner_and_order_check(db: Session, organization_id: UUID, payload: InvoiceCreate) -> None:
    if payload.invoice_type == "supplier":
        supplier = db.query(Supplier).filter(
            Supplier.id == payload.supplier_id,
            Supplier.organization_id == organization_id,
        ).one_or_none()
        if supplier is None:
            raise HTTPException(status_code=422, detail="Select a supplier in this organization.")
        if payload.import_order_id:
            order = db.query(ImportOrder).filter(
                ImportOrder.id == payload.import_order_id,
                ImportOrder.organization_id == organization_id,
            ).one_or_none()
            if order is None or order.supplier_id != supplier.id:
                raise HTTPException(status_code=422, detail="The import order must belong to the selected supplier and organization.")
            if order.currency != payload.currency:
                raise HTTPException(status_code=422, detail="Invoice currency must match the linked import order currency.")
    else:
        customer = db.query(Customer).filter(
            Customer.id == payload.customer_id,
            Customer.organization_id == organization_id,
        ).one_or_none()
        if customer is None:
            raise HTTPException(status_code=422, detail="Select a customer in this organization.")
        if payload.export_order_id:
            order = db.query(ExportOrder).filter(
                ExportOrder.id == payload.export_order_id,
                ExportOrder.organization_id == organization_id,
            ).one_or_none()
            if order is None or order.customer_id != customer.id:
                raise HTTPException(status_code=422, detail="The export order must belong to the selected customer and organization.")
            if order.currency != payload.currency:
                raise HTTPException(status_code=422, detail="Invoice currency must match the linked export order currency.")


def _write_invoice_items(db: Session, invoice: Invoice, inputs) -> None:
    db.query(InvoiceItem).filter(
        InvoiceItem.invoice_id == invoice.id,
        InvoiceItem.organization_id == invoice.organization_id,
    ).delete(synchronize_session=False)
    subtotal = ZERO
    tax_amount = ZERO
    for index, line in enumerate(inputs, start=1):
        net, tax, total = _line_totals(line)
        subtotal = money(subtotal + net)
        tax_amount = money(tax_amount + tax)
        db.add(InvoiceItem(
            organization_id=invoice.organization_id,
            invoice_id=invoice.id,
            line_number=index,
            description=line.description,
            quantity=line.quantity,
            unit_price=line.unit_price,
            tax_rate=line.tax_rate,
            net_amount=net,
            tax_amount=tax,
            line_total=total,
        ))
    invoice.subtotal = subtotal
    invoice.tax_amount = tax_amount


def _payment_hash(payload: PaymentCreate) -> str:
    material = payload.model_dump(mode="json")
    material.pop("idempotency_key", None)
    material["allocations"] = sorted(material["allocations"], key=lambda row: row["invoice_id"])
    return hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _payment_payload(db: Session, payment: Payment) -> dict:
    rows = db.query(PaymentAllocation, Invoice).join(
        Invoice,
        (Invoice.id == PaymentAllocation.invoice_id)
        & (Invoice.organization_id == PaymentAllocation.organization_id),
    ).filter(
        PaymentAllocation.payment_id == payment.id,
        PaymentAllocation.organization_id == payment.organization_id,
    ).order_by(Invoice.invoice_number.asc()).all()
    allocations = [{
        "id": allocation.id,
        "invoice_id": invoice.id,
        "invoice_number": invoice.invoice_number,
        "invoice_currency": invoice.currency,
        "allocated_payment_amount": allocation.allocated_payment_amount,
        "allocated_invoice_amount": allocation.allocated_invoice_amount,
        "exchange_rate": allocation.exchange_rate,
        "exchange_rate_date": allocation.exchange_rate_date,
    } for allocation, invoice in rows]
    allocated = money(sum((row["allocated_payment_amount"] for row in allocations), ZERO))
    return {
        "id": payment.id,
        "organization_id": payment.organization_id,
        "payment_reference": payment.payment_reference,
        "payment_type": payment.payment_type,
        "payment_date": payment.payment_date,
        "currency": payment.currency,
        "amount": payment.amount,
        "allocated_amount": allocated,
        "unallocated_amount": max(money(payment.amount - allocated), ZERO) if payment.status == "posted" else ZERO,
        "payment_method": payment.payment_method,
        "external_reference": payment.external_reference,
        "status": payment.status,
        "notes": payment.notes,
        "created_by_user_id": payment.created_by_user_id,
        "reversed_by_user_id": payment.reversed_by_user_id,
        "reversed_at": payment.reversed_at,
        "reversal_reason": payment.reversal_reason,
        "created_at": payment.created_at,
        "allocations": allocations,
    }


def _payment_out(db: Session, payment: Payment) -> PaymentOut:
    return PaymentOut.model_validate(_payment_payload(db, payment))


@router.get("/invoices", response_model=InvoicePage, summary="List organization invoices")
def list_invoices(
    organization_id: UUID,
    invoice_type: str | None = Query(default=None, pattern="^(supplier|customer)$"),
    invoice_status: str | None = Query(default=None, alias="status", pattern="^(draft|issued|partially_paid|paid|overdue|void)$"),
    search: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "invoices.read")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    query = db.query(Invoice).filter(Invoice.organization_id == organization_id)
    if invoice_type:
        query = query.filter(Invoice.invoice_type == invoice_type)
    if start_date:
        query = query.filter(Invoice.issue_date >= start_date)
    if end_date:
        query = query.filter(Invoice.issue_date <= end_date)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Invoice.invoice_number.ilike(pattern), Invoice.notes.ilike(pattern)))
    records = query.order_by(Invoice.issue_date.desc(), Invoice.created_at.desc()).all()
    payloads = [_invoice_payload(db, record) for record in records]
    if invoice_status:
        payloads = [row for row in payloads if row["status"] == invoice_status]
    total = len(payloads)
    start = (page - 1) * page_size
    return InvoicePage(items=[InvoiceOut.model_validate(row) for row in payloads[start:start + page_size]], total=total, page=page, page_size=page_size)


@router.post("/invoices", response_model=InvoiceOut, status_code=status.HTTP_201_CREATED, summary="Create a draft invoice")
def create_invoice(
    payload: InvoiceCreate,
    request: Request,
    organization_id: UUID,
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Read the CSRF header here to keep FastAPI's dependency signature explicit.
    _verify_mutation(request, request.headers.get("X-CSRF-Token"), session)
    require_org_permission(db, user.id, organization_id, "invoices.create")
    _partner_and_order_check(db, organization_id, payload)
    invoice = Invoice(
        organization_id=organization_id,
        invoice_number=payload.invoice_number,
        invoice_type=payload.invoice_type,
        supplier_id=payload.supplier_id,
        customer_id=payload.customer_id,
        import_order_id=payload.import_order_id,
        export_order_id=payload.export_order_id,
        status="draft",
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        currency=payload.currency,
        discount_amount=ZERO,
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    db.add(invoice)
    try:
        db.flush()
        _write_invoice_items(db, invoice, payload.items)
        if money(payload.discount_amount) > money(invoice.subtotal + invoice.tax_amount):
            raise HTTPException(status_code=422, detail="Discount cannot exceed subtotal plus tax.")
        invoice.discount_amount = money(payload.discount_amount)
        invoice.total_amount = money(invoice.subtotal + invoice.tax_amount - invoice.discount_amount)
        _audit(db, organization_id, "invoice", invoice.id, "created_draft", user.id, {
            "invoice_number": invoice.invoice_number, "invoice_type": invoice.invoice_type,
            "currency": invoice.currency, "total_amount": str(invoice.total_amount),
        })
        db.commit()
        db.refresh(invoice)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invoice number already exists or the invoice references are invalid.") from exc
    return _invoice_out(db, invoice)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut, summary="Get invoice details")
def get_invoice(invoice_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invoice = _scoped_invoice(db, user.id, organization_id, invoice_id)
    return _invoice_out(db, invoice)


@router.patch("/invoices/{invoice_id}", response_model=InvoiceOut, summary="Update a draft invoice")
def update_invoice(
    invoice_id: UUID, payload: InvoiceUpdate, request: Request, organization_id: UUID,
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, request.headers.get("X-CSRF-Token"), session)
    invoice = _scoped_invoice(db, user.id, organization_id, invoice_id, "invoices.manage", lock=True)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft invoices can be edited.")
    changes = payload.model_dump(exclude_unset=True)
    if "invoice_number" in changes:
        invoice.invoice_number = changes["invoice_number"].strip()
    if "issue_date" in changes and changes["issue_date"] is not None:
        invoice.issue_date = changes["issue_date"]
    if "due_date" in changes and changes["due_date"] is not None:
        invoice.due_date = changes["due_date"]
    if invoice.due_date < invoice.issue_date:
        raise HTTPException(status_code=422, detail="Due date cannot be before issue date.")
    next_discount = money(changes["discount_amount"]) if "discount_amount" in changes and changes["discount_amount"] is not None else invoice.discount_amount
    if "notes" in changes:
        invoice.notes = changes["notes"]
    if "items" in changes and changes["items"] is not None:
        _write_invoice_items(db, invoice, payload.items)
    if next_discount > money(invoice.subtotal + invoice.tax_amount):
        raise HTTPException(status_code=422, detail="Discount cannot exceed subtotal plus tax.")
    invoice.discount_amount = next_discount
    invoice.total_amount = money(invoice.subtotal + invoice.tax_amount - invoice.discount_amount)
    _audit(db, organization_id, "invoice", invoice.id, "draft_updated", user.id, {"fields": sorted(changes.keys())})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invoice number already exists.") from exc
    db.refresh(invoice)
    return _invoice_out(db, invoice)


@router.post("/invoices/{invoice_id}/issue", response_model=InvoiceOut, summary="Issue a draft invoice")
def issue_invoice(
    invoice_id: UUID, request: Request, organization_id: UUID,
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, request.headers.get("X-CSRF-Token"), session)
    invoice = _scoped_invoice(db, user.id, organization_id, invoice_id, "invoices.manage", lock=True)
    if invoice.status != "draft":
        raise HTTPException(status_code=409, detail="Only draft invoices can be issued.")
    if invoice.total_amount <= ZERO:
        raise HTTPException(status_code=409, detail="An invoice must have a positive total before it can be issued.")
    invoice.status = "issued"
    invoice.issued_by_user_id = user.id
    invoice.issued_at = utc_now()
    _audit(db, organization_id, "invoice", invoice.id, "issued", user.id, {
        "invoice_number": invoice.invoice_number, "total_amount": str(invoice.total_amount),
        "currency": invoice.currency, "issue_date": invoice.issue_date.isoformat(),
        "due_date": invoice.due_date.isoformat(),
    })
    db.commit()
    db.refresh(invoice)
    return _invoice_out(db, invoice)


@router.post("/invoices/{invoice_id}/void", response_model=InvoiceOut, summary="Void an unpaid invoice")
def void_invoice(
    invoice_id: UUID, request: Request, organization_id: UUID, payload: PaymentReversalRequest,
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, request.headers.get("X-CSRF-Token"), session)
    invoice = _scoped_invoice(db, user.id, organization_id, invoice_id, "invoices.adjust", lock=True)
    if invoice.status == "void":
        raise HTTPException(status_code=409, detail="Invoice is already void.")
    if invoice.status == "paid" or _invoice_paid_amount(db, invoice.id, organization_id) > ZERO:
        raise HTTPException(status_code=409, detail="An invoice with posted payments cannot be voided. Reverse the payment through the controlled correction workflow first.")
    invoice.status = "void"
    _audit(db, organization_id, "invoice", invoice.id, "voided", user.id, {"reason": payload.reason})
    db.commit()
    db.refresh(invoice)
    return _invoice_out(db, invoice)


@router.get("/invoices/{invoice_id}/audit", response_model=list[FinancialAuditEventOut], summary="Get invoice financial history")
def get_invoice_audit(invoice_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    invoice = _scoped_invoice(db, user.id, organization_id, invoice_id)
    return db.query(FinancialAuditEvent).filter(
        FinancialAuditEvent.organization_id == organization_id,
        FinancialAuditEvent.entity_type == "invoice",
        FinancialAuditEvent.entity_id == invoice.id,
    ).order_by(FinancialAuditEvent.created_at.asc()).all()


@router.get("/payments", response_model=PaymentPage, summary="List organization payments")
def list_payments(
    organization_id: UUID,
    payment_type: str | None = Query(default=None, pattern="^(incoming|outgoing)$"),
    payment_status: str | None = Query(default=None, alias="status", pattern="^(posted|reversed)$"),
    search: str | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "payments.read")
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be on or before end_date.")
    query = db.query(Payment).filter(Payment.organization_id == organization_id)
    if payment_type:
        query = query.filter(Payment.payment_type == payment_type)
    if payment_status:
        query = query.filter(Payment.status == payment_status)
    if start_date:
        query = query.filter(Payment.payment_date >= start_date)
    if end_date:
        query = query.filter(Payment.payment_date <= end_date)
    if search and search.strip():
        pattern = f"%{search.strip()}%"
        query = query.filter(or_(Payment.payment_reference.ilike(pattern), Payment.external_reference.ilike(pattern)))
    records = query.order_by(Payment.payment_date.desc(), Payment.created_at.desc()).all()
    total = len(records)
    start = (page - 1) * page_size
    return PaymentPage(items=[_payment_out(db, row) for row in records[start:start + page_size]], total=total, page=page, page_size=page_size)


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED, summary="Record and allocate a payment")
def create_payment(
    payload: PaymentCreate, request: Request, organization_id: UUID, response: Response,
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, request.headers.get("X-CSRF-Token"), session)
    require_org_permission(db, user.id, organization_id, "payments.create")
    request_hash = _payment_hash(payload)
    existing = db.query(Payment).filter(
        Payment.organization_id == organization_id,
        Payment.idempotency_key == payload.idempotency_key,
    ).one_or_none()
    if existing:
        if existing.request_hash != request_hash:
            raise HTTPException(status_code=409, detail="Idempotency key was already used with a different payment payload.")
        response.status_code = status.HTTP_200_OK
        return _payment_out(db, existing)

    total_payment_allocation = money(sum((row.allocated_payment_amount for row in payload.allocations), ZERO))
    if total_payment_allocation > payload.amount:
        raise HTTPException(status_code=422, detail="Allocated payment amounts cannot exceed the payment amount.")

    invoice_ids = sorted((row.invoice_id for row in payload.allocations), key=str)
    invoice_rows = db.query(Invoice).filter(
        Invoice.organization_id == organization_id,
        Invoice.id.in_(invoice_ids),
    ).order_by(Invoice.id.asc()).with_for_update().all()
    invoices = {row.id: row for row in invoice_rows}
    if len(invoices) != len(invoice_ids):
        raise HTTPException(status_code=404, detail="One or more invoices were not found in this organization.")

    allocation_calculations: list[tuple[Invoice, Decimal, Decimal, Decimal, date]] = []
    for allocation in payload.allocations:
        invoice = invoices[allocation.invoice_id]
        if invoice.status not in {"issued", "partially_paid"}:
            raise HTTPException(status_code=409, detail=f"Invoice {invoice.invoice_number} is not open for payment.")
        required_direction = "incoming" if invoice.invoice_type == "customer" else "outgoing"
        if payload.payment_type != required_direction:
            raise HTTPException(status_code=422, detail="Payment direction must match the invoice type: incoming for customer invoices, outgoing for supplier invoices.")
        if payload.payment_date < invoice.issue_date:
            raise HTTPException(status_code=422, detail=f"Payment date cannot be before invoice {invoice.invoice_number} issue date.")
        if payload.currency == invoice.currency:
            rate = allocation.exchange_rate or ONE
            if rate != ONE:
                raise HTTPException(status_code=422, detail="Exchange rate must be 1 when payment and invoice currencies are the same.")
        else:
            if allocation.exchange_rate is None or allocation.exchange_rate_date is None:
                raise HTTPException(status_code=422, detail="A positive exchange rate and conversion date are required when currencies differ.")
            rate = allocation.exchange_rate
        invoice_amount = money(allocation.allocated_payment_amount * rate)
        if invoice_amount <= ZERO:
            raise HTTPException(status_code=422, detail="Allocated invoice amount rounds to zero.")
        already_paid = _invoice_paid_amount(db, invoice.id, organization_id)
        outstanding = money(invoice.total_amount - already_paid)
        if invoice_amount > outstanding:
            raise HTTPException(status_code=409, detail=f"Allocation exceeds the outstanding balance on invoice {invoice.invoice_number}.")
        rate_date = allocation.exchange_rate_date or payload.payment_date
        allocation_calculations.append((invoice, money(allocation.allocated_payment_amount), invoice_amount, rate, rate_date))

    payment = Payment(
        organization_id=organization_id,
        payment_reference=payload.payment_reference,
        payment_type=payload.payment_type,
        payment_date=payload.payment_date,
        currency=payload.currency,
        amount=money(payload.amount),
        payment_method=payload.payment_method,
        external_reference=payload.external_reference,
        idempotency_key=payload.idempotency_key,
        request_hash=request_hash,
        status="posted",
        notes=payload.notes,
        created_by_user_id=user.id,
    )
    db.add(payment)
    try:
        db.flush()
        for invoice, payment_amount, invoice_amount, rate, rate_date in allocation_calculations:
            db.add(PaymentAllocation(
                organization_id=organization_id,
                payment_id=payment.id,
                invoice_id=invoice.id,
                allocated_payment_amount=payment_amount,
                allocated_invoice_amount=invoice_amount,
                exchange_rate=rate,
                exchange_rate_date=rate_date,
            ))
            current_paid = _invoice_paid_amount(db, invoice.id, organization_id)
            projected_paid = money(current_paid + invoice_amount)
            invoice.status = "paid" if projected_paid >= invoice.total_amount else "partially_paid"
            _audit(db, organization_id, "invoice", invoice.id, "payment_allocated", user.id, {
                "payment_id": str(payment.id),
                "payment_reference": payment.payment_reference,
                "allocated_invoice_amount": str(invoice_amount),
                "currency": invoice.currency,
            })
        _audit(db, organization_id, "payment", payment.id, "posted", user.id, {
            "payment_reference": payment.payment_reference,
            "payment_type": payment.payment_type,
            "amount": str(payment.amount),
            "currency": payment.currency,
            "allocation_count": len(allocation_calculations),
        })
        db.commit()
        db.refresh(payment)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Payment reference or idempotency key already exists.") from exc
    return _payment_out(db, payment)


@router.post("/payments/{payment_id}/allocations", response_model=PaymentOut, summary="Allocate an unapplied payment balance")
def allocate_existing_payment(
    payment_id: UUID, payload: PaymentAllocationInput, request: Request, organization_id: UUID, response: Response,
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, request.headers.get("X-CSRF-Token"), session)
    require_org_permission(db, user.id, organization_id, "payments.reconcile")
    payment = db.query(Payment).filter(
        Payment.id == payment_id, Payment.organization_id == organization_id,
    ).with_for_update().one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if payment.status != "posted":
        raise HTTPException(status_code=409, detail="Only posted payments can be allocated.")
    invoice = db.query(Invoice).filter(
        Invoice.id == payload.invoice_id, Invoice.organization_id == organization_id,
    ).with_for_update().one_or_none()
    if invoice is None:
        raise HTTPException(status_code=404, detail="Invoice not found.")
    expected_direction = "incoming" if invoice.invoice_type == "customer" else "outgoing"
    if payment.payment_type != expected_direction:
        raise HTTPException(status_code=422, detail="Payment direction does not match the invoice type.")
    if payment.payment_date < invoice.issue_date:
        raise HTTPException(status_code=422, detail="Payment date cannot be before the invoice issue date.")
    if payment.currency == invoice.currency:
        rate = payload.exchange_rate or ONE
        if rate != ONE:
            raise HTTPException(status_code=422, detail="Exchange rate must be 1 when payment and invoice currencies are the same.")
    else:
        if payload.exchange_rate is None or payload.exchange_rate_date is None:
            raise HTTPException(status_code=422, detail="A positive exchange rate and conversion date are required when currencies differ.")
        rate = payload.exchange_rate
    invoice_amount = money(payload.allocated_payment_amount * rate)
    if invoice_amount <= ZERO:
        raise HTTPException(status_code=422, detail="Allocated invoice amount rounds to zero.")
    rate_date = payload.exchange_rate_date or payment.payment_date
    existing_allocation = db.query(PaymentAllocation).filter(
        PaymentAllocation.payment_id == payment.id,
        PaymentAllocation.invoice_id == invoice.id,
        PaymentAllocation.organization_id == organization_id,
    ).one_or_none()
    if existing_allocation:
        if (existing_allocation.allocated_payment_amount == money(payload.allocated_payment_amount)
                and existing_allocation.allocated_invoice_amount == invoice_amount
                and existing_allocation.exchange_rate == rate
                and existing_allocation.exchange_rate_date == rate_date):
            response.status_code = status.HTTP_200_OK
            return _payment_out(db, payment)
        raise HTTPException(status_code=409, detail="This payment already has a different allocation to the selected invoice.")
    if invoice.status not in {"issued", "partially_paid"}:
        raise HTTPException(status_code=409, detail="Invoice is not open for payment allocation.")
    allocated_so_far = db.query(func.coalesce(func.sum(PaymentAllocation.allocated_payment_amount), 0)).filter(
        PaymentAllocation.payment_id == payment.id,
        PaymentAllocation.organization_id == organization_id,
    ).scalar()
    if money(Decimal(str(allocated_so_far or 0)) + payload.allocated_payment_amount) > payment.amount:
        raise HTTPException(status_code=409, detail="Allocation exceeds the payment's unapplied balance.")
    outstanding = money(invoice.total_amount - _invoice_paid_amount(db, invoice.id, organization_id))
    if invoice_amount > outstanding:
        raise HTTPException(status_code=409, detail="Allocation exceeds the invoice outstanding balance.")
    allocation = PaymentAllocation(
        organization_id=organization_id,
        payment_id=payment.id,
        invoice_id=invoice.id,
        allocated_payment_amount=money(payload.allocated_payment_amount),
        allocated_invoice_amount=invoice_amount,
        exchange_rate=rate,
        exchange_rate_date=rate_date,
    )
    db.add(allocation)
    db.flush()
    invoice_paid = _invoice_paid_amount(db, invoice.id, organization_id)
    invoice.status = "paid" if invoice_paid >= invoice.total_amount else "partially_paid"
    _audit(db, organization_id, "invoice", invoice.id, "payment_allocated", user.id, {
        "payment_id": str(payment.id), "payment_reference": payment.payment_reference,
        "allocated_invoice_amount": str(invoice_amount), "currency": invoice.currency,
    })
    _audit(db, organization_id, "payment", payment.id, "allocation_added", user.id, {
        "invoice_id": str(invoice.id), "invoice_number": invoice.invoice_number,
        "allocated_payment_amount": str(payload.allocated_payment_amount),
        "allocated_invoice_amount": str(invoice_amount),
    })
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This payment allocation conflicts with an existing reconciliation.") from exc
    db.refresh(payment)
    return _payment_out(db, payment)


@router.get("/payments/{payment_id}", response_model=PaymentOut, summary="Get payment details")
def get_payment(payment_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_org_permission(db, user.id, organization_id, "payments.read")
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.organization_id == organization_id).one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return _payment_out(db, payment)


@router.post("/payments/{payment_id}/reverse", response_model=PaymentOut, summary="Reverse a posted payment")
def reverse_payment(
    payment_id: UUID, payload: PaymentReversalRequest, request: Request, organization_id: UUID,
    session: UserSession = Depends(get_current_session), user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    _verify_mutation(request, request.headers.get("X-CSRF-Token"), session)
    require_org_permission(db, user.id, organization_id, "payments.adjust")
    payment = db.query(Payment).filter(
        Payment.id == payment_id,
        Payment.organization_id == organization_id,
    ).with_for_update().one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    if payment.status == "reversed":
        raise HTTPException(status_code=409, detail="Payment has already been reversed.")
    allocations = db.query(PaymentAllocation).filter(
        PaymentAllocation.payment_id == payment.id,
        PaymentAllocation.organization_id == organization_id,
    ).all()
    invoice_ids = sorted({row.invoice_id for row in allocations}, key=str)
    invoices = db.query(Invoice).filter(
        Invoice.id.in_(invoice_ids), Invoice.organization_id == organization_id,
    ).order_by(Invoice.id.asc()).with_for_update().all() if invoice_ids else []
    invoice_by_id = {row.id: row for row in invoices}
    payment.status = "reversed"
    payment.reversed_at = utc_now()
    payment.reversed_by_user_id = user.id
    payment.reversal_reason = payload.reason
    db.flush()  # Recalculate balances after the reversal is visible to payment-allocation queries.
    for invoice in invoices:
        paid = _invoice_paid_amount(db, invoice.id, organization_id)
        invoice.status = "paid" if paid >= invoice.total_amount else "partially_paid" if paid > ZERO else "issued"
        _audit(db, organization_id, "invoice", invoice.id, "payment_reversed", user.id, {
            "payment_id": str(payment.id), "payment_reference": payment.payment_reference,
            "reversal_reason": payload.reason, "remaining_paid_amount": str(paid),
        })
    _audit(db, organization_id, "payment", payment.id, "reversed", user.id, {"reason": payload.reason})
    db.commit()
    db.refresh(payment)
    return _payment_out(db, payment)


@router.get("/payments/{payment_id}/audit", response_model=list[FinancialAuditEventOut], summary="Get payment financial history")
def get_payment_audit(payment_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_org_permission(db, user.id, organization_id, "payments.read")
    payment = db.query(Payment).filter(Payment.id == payment_id, Payment.organization_id == organization_id).one_or_none()
    if payment is None:
        raise HTTPException(status_code=404, detail="Payment not found.")
    return db.query(FinancialAuditEvent).filter(
        FinancialAuditEvent.organization_id == organization_id,
        FinancialAuditEvent.entity_type == "payment",
        FinancialAuditEvent.entity_id == payment.id,
    ).order_by(FinancialAuditEvent.created_at.asc()).all()
