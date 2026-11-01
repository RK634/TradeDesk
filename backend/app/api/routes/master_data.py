"""CRUD APIs for organization-scoped customers, suppliers, products, and locations."""

from typing import Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.permissions import require_org_permission
from app.core.security import verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import Customer, InventoryLocation, Product, Supplier, User, UserSession
from app.schemas.master_data import (
    CustomerCreate, CustomerOut, CustomerUpdate, LocationCreate, LocationOut, LocationUpdate,
    Page, ProductCreate, ProductOut, ProductUpdate, SupplierCreate, SupplierOut, SupplierUpdate,
)

router = APIRouter(tags=["master data"])


def _verify_mutation(request: Request, csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def _list_records(
    db: Session,
    model: type,
    organization_id: UUID,
    search: str | None,
    active: bool | None,
    page: int,
    page_size: int,
    search_columns: Sequence[str],
):
    query = db.query(model).filter(model.organization_id == organization_id)
    if active is not None and hasattr(model, "is_active"):
        query = query.filter(model.is_active.is_(active))
    search_value = search.strip() if search else ""
    if search_value:
        query = query.filter(or_(*(getattr(model, column).ilike(f"%{search_value}%") for column in search_columns)))
    total = query.count()
    rows = query.order_by(model.updated_at.desc(), model.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


def _get_scoped(db: Session, model: type, organization_id: UUID, record_id: UUID, permission: str, user_id: UUID):
    require_org_permission(db, user_id, organization_id, permission)
    record = db.query(model).filter(model.id == record_id, model.organization_id == organization_id).one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return record


def _create_record(db: Session, model: type, organization_id: UUID, payload, duplicate_message: str):
    record = model(organization_id=organization_id, **payload.model_dump())
    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=duplicate_message) from exc
    return record


def _patch_record(db: Session, record, payload, duplicate_message: str):
    values = payload.model_dump(exclude_unset=True)
    for name, value in values.items():
        if value is not None or name in {"customer_code", "supplier_code", "company_name", "contact_person", "email", "phone", "billing_address", "delivery_address", "country", "tax_id", "notes", "address", "description", "category"}:
            setattr(record, name, value)
    try:
        db.commit()
        db.refresh(record)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=duplicate_message) from exc
    return record


# Customers
@router.get("/customers", response_model=Page[CustomerOut], tags=["customers"])
def list_customers(
    organization_id: UUID,
    search: str | None = None,
    active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "customers.read")
    return _list_records(db, Customer, organization_id, search, active, page, page_size, ("name", "company_name", "customer_code", "email"))


@router.post("/customers", response_model=CustomerOut, status_code=status.HTTP_201_CREATED, tags=["customers"])
def create_customer(
    organization_id: UUID,
    payload: CustomerCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "customers.create")
    return _create_record(db, Customer, organization_id, payload, "A customer with this code already exists in the organization.")


@router.get("/customers/{customer_id}", response_model=CustomerOut, tags=["customers"])
def get_customer(customer_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_scoped(db, Customer, organization_id, customer_id, "customers.read", user.id)


@router.patch("/customers/{customer_id}", response_model=CustomerOut, tags=["customers"])
def update_customer(
    customer_id: UUID,
    organization_id: UUID,
    payload: CustomerUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    record = _get_scoped(db, Customer, organization_id, customer_id, "customers.update", user.id)
    return _patch_record(db, record, payload, "A customer with this code already exists in the organization.")


# Suppliers
@router.get("/suppliers", response_model=Page[SupplierOut], tags=["suppliers"])
def list_suppliers(
    organization_id: UUID,
    search: str | None = None,
    active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "suppliers.read")
    return _list_records(db, Supplier, organization_id, search, active, page, page_size, ("name", "company_name", "supplier_code", "email"))


@router.post("/suppliers", response_model=SupplierOut, status_code=status.HTTP_201_CREATED, tags=["suppliers"])
def create_supplier(
    organization_id: UUID,
    payload: SupplierCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "suppliers.create")
    return _create_record(db, Supplier, organization_id, payload, "A supplier with this code already exists in the organization.")


@router.get("/suppliers/{supplier_id}", response_model=SupplierOut, tags=["suppliers"])
def get_supplier(supplier_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_scoped(db, Supplier, organization_id, supplier_id, "suppliers.read", user.id)


@router.patch("/suppliers/{supplier_id}", response_model=SupplierOut, tags=["suppliers"])
def update_supplier(
    supplier_id: UUID,
    organization_id: UUID,
    payload: SupplierUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    record = _get_scoped(db, Supplier, organization_id, supplier_id, "suppliers.update", user.id)
    return _patch_record(db, record, payload, "A supplier with this code already exists in the organization.")


# Products
@router.get("/products", response_model=Page[ProductOut], tags=["products"])
def list_products(
    organization_id: UUID,
    search: str | None = None,
    active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "products.read")
    return _list_records(db, Product, organization_id, search, active, page, page_size, ("name", "sku", "category"))


@router.post("/products", response_model=ProductOut, status_code=status.HTTP_201_CREATED, tags=["products"])
def create_product(
    organization_id: UUID,
    payload: ProductCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "products.create")
    return _create_record(db, Product, organization_id, payload, "A product with this SKU already exists in the organization.")


@router.get("/products/{product_id}", response_model=ProductOut, tags=["products"])
def get_product(product_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_scoped(db, Product, organization_id, product_id, "products.read", user.id)


@router.patch("/products/{product_id}", response_model=ProductOut, tags=["products"])
def update_product(
    product_id: UUID,
    organization_id: UUID,
    payload: ProductUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    record = _get_scoped(db, Product, organization_id, product_id, "products.update", user.id)
    return _patch_record(db, record, payload, "A product with this SKU already exists in the organization.")


# Inventory locations
@router.get("/inventory/locations", response_model=Page[LocationOut], tags=["inventory"])
def list_locations(
    organization_id: UUID,
    search: str | None = None,
    active: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "inventory.read")
    return _list_records(db, InventoryLocation, organization_id, search, active, page, page_size, ("name", "code", "description"))


@router.post("/inventory/locations", response_model=LocationOut, status_code=status.HTTP_201_CREATED, tags=["inventory"])
def create_location(
    organization_id: UUID,
    payload: LocationCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "inventory.adjust")
    return _create_record(db, InventoryLocation, organization_id, payload, "A location with this code already exists in the organization.")


@router.get("/inventory/locations/{location_id}", response_model=LocationOut, tags=["inventory"])
def get_location(location_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _get_scoped(db, InventoryLocation, organization_id, location_id, "inventory.read", user.id)


@router.patch("/inventory/locations/{location_id}", response_model=LocationOut, tags=["inventory"])
def update_location(
    location_id: UUID,
    organization_id: UUID,
    payload: LocationUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    record = _get_scoped(db, InventoryLocation, organization_id, location_id, "inventory.adjust", user.id)
    return _patch_record(db, record, payload, "A location with this code already exists in the organization.")
