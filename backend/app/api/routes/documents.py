"""Organization-scoped private document API with immutable versions and verification history."""
from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
from datetime import date
from pathlib import PurePath
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_session, get_current_user
from app.core.config import get_settings
from app.core.permissions import require_org_permission
from app.core.security import utc_now, verify_csrf, verify_same_origin_if_present
from app.db.session import get_db
from app.models import (
    DocumentRequirement, DocumentVerificationEvent, ExportOrder, ExportShipment,
    ImportOrder, ImportShipment, TradeDocument, TradeDocumentVersion, User, UserSession,
)
from app.models.documents import DOCUMENT_TYPES, RELATED_ENTITY_TYPES
from app.schemas.documents import (
    DocumentComplianceItem, DocumentComplianceOut, DocumentOut, DocumentRequirementCreate,
    DocumentRequirementOut, DocumentVerificationEventOut, DocumentVersionOut,
    VerificationUpdate,
)
from app.storage import StorageError, get_storage

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)
ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".xlsx", ".docx", ".csv", ".txt"}


def _verify_mutation(request: Request, csrf_token: str | None, session: UserSession) -> None:
    verify_same_origin_if_present(request)
    verify_csrf(request, csrf_token, session)


def _verify_related_entity(db: Session, organization_id: UUID, entity_type: str, entity_id: UUID) -> None:
    model = {
        "import_order": ImportOrder,
        "import_shipment": ImportShipment,
        "export_order": ExportOrder,
        "export_shipment": ExportShipment,
    }.get(entity_type)
    if model is None:
        raise HTTPException(status_code=422, detail="Unsupported related entity type.")
    entity = db.query(model.id).filter(model.id == entity_id, model.organization_id == organization_id).one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Related trade record not found.")


def _safe_filename(filename: str | None) -> str:
    name = PurePath(filename or "upload").name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return (name or "document")[:255]


async def _read_upload(file: UploadFile) -> tuple[str, str, bytes]:
    original_name = _safe_filename(file.filename)
    suffix = PurePath(original_name).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported file type. Allowed types: PDF, PNG, JPG, XLSX, DOCX, CSV, TXT.")
    settings = get_settings()
    content = await file.read(settings.max_upload_bytes + 1)
    await file.close()
    if not content:
        raise HTTPException(status_code=422, detail="The uploaded file is empty.")
    if len(content) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File exceeds the {settings.max_upload_bytes // (1024 * 1024)} MB upload limit.")
    if suffix == ".pdf" and not content.startswith(b"%PDF-"):
        raise HTTPException(status_code=415, detail="The file contents do not match a PDF document.")
    if suffix == ".png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise HTTPException(status_code=415, detail="The file contents do not match a PNG image.")
    if suffix in {".jpg", ".jpeg"} and not content.startswith(b"\xff\xd8\xff"):
        raise HTTPException(status_code=415, detail="The file contents do not match a JPEG image.")
    if suffix in {".xlsx", ".docx"} and not content.startswith(b"PK\x03\x04"):
        raise HTTPException(status_code=415, detail="The file contents do not match a supported Office document.")
    if suffix in {".csv", ".txt"}:
        try:
            decoded = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=415, detail="CSV and text documents must be UTF-8 encoded.") from exc
        if "\x00" in decoded:
            raise HTTPException(status_code=415, detail="CSV and text documents cannot contain binary data.")
    content_type = mimetypes.guess_type(original_name)[0] or "application/octet-stream"
    return original_name, content_type, content


def _document(db: Session, user_id: UUID, organization_id: UUID, document_id: UUID, permission: str = "documents.read", *, lock: bool = False) -> TradeDocument:
    require_org_permission(db, user_id, organization_id, permission)
    query = db.query(TradeDocument).filter(
        TradeDocument.id == document_id,
        TradeDocument.organization_id == organization_id,
    )
    if lock:
        query = query.with_for_update()
    document = query.one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found.")
    # The polymorphic target is checked on every operation; never trust an ID without tenant scope.
    _verify_related_entity(db, organization_id, document.related_entity_type, document.related_entity_id)
    return document


def _document_out(db: Session, document: TradeDocument) -> dict:
    versions = db.query(TradeDocumentVersion).filter(
        TradeDocumentVersion.document_id == document.id,
        TradeDocumentVersion.organization_id == document.organization_id,
    ).order_by(TradeDocumentVersion.version_number.desc()).all()
    current = next((version for version in versions if version.version_number == document.current_version), None)
    if current is None:
        raise HTTPException(status_code=500, detail="Document version metadata is inconsistent.")
    return {
        "id": document.id,
        "organization_id": document.organization_id,
        "document_reference": document.document_reference,
        "document_type": document.document_type,
        "title": document.title,
        "description": document.description,
        "related_entity_type": document.related_entity_type,
        "related_entity_id": document.related_entity_id,
        "verification_status": document.verification_status,
        "verification_notes": document.verification_notes,
        "expiry_date": document.expiry_date,
        "current_version": document.current_version,
        "uploaded_by_user_id": document.uploaded_by_user_id,
        "verified_by_user_id": document.verified_by_user_id,
        "verified_at": document.verified_at,
        "created_at": document.created_at,
        "updated_at": document.updated_at,
        "current_file_name": current.file_name,
        "current_content_type": current.content_type,
        "current_file_size": current.file_size,
        "versions": versions,
    }


def _make_version(*, organization_id: UUID, document_id: UUID, version_number: int, filename: str, content_type: str, content: bytes, storage_key: str, user_id: UUID) -> TradeDocumentVersion:
    return TradeDocumentVersion(
        organization_id=organization_id,
        document_id=document_id,
        version_number=version_number,
        file_name=filename,
        content_type=content_type,
        file_size=len(content),
        sha256=hashlib.sha256(content).hexdigest(),
        storage_key=storage_key,
        uploaded_by_user_id=user_id,
    )


@router.get("", response_model=list[DocumentOut], summary="List private trade documents")
def list_documents(
    organization_id: UUID,
    related_entity_type: str | None = None,
    related_entity_id: UUID | None = None,
    verification_status: str | None = None,
    document_type: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "documents.read")
    query = db.query(TradeDocument).filter(TradeDocument.organization_id == organization_id)
    if related_entity_type:
        if related_entity_type not in RELATED_ENTITY_TYPES:
            raise HTTPException(status_code=422, detail="Unsupported related_entity_type.")
        query = query.filter(TradeDocument.related_entity_type == related_entity_type)
    if related_entity_id:
        query = query.filter(TradeDocument.related_entity_id == related_entity_id)
    if verification_status:
        if verification_status not in {"pending", "verified", "rejected"}:
            raise HTTPException(status_code=422, detail="Unsupported verification_status.")
        query = query.filter(TradeDocument.verification_status == verification_status)
    if document_type:
        query = query.filter(TradeDocument.document_type == document_type)
    rows = query.order_by(TradeDocument.created_at.desc()).limit(500).all()
    result = []
    for row in rows:
        _verify_related_entity(db, organization_id, row.related_entity_type, row.related_entity_id)
        result.append(_document_out(db, row))
    return result


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED, summary="Upload a private trade document")
async def upload_document(
    request: Request,
    organization_id: UUID,
    related_entity_type: str = Form(...),
    related_entity_id: UUID = Form(...),
    document_type: str = Form(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    expiry_date: date | None = Form(default=None),
    file: UploadFile = File(...),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "documents.upload")
    related_entity_type = related_entity_type.strip().lower()
    document_type = document_type.strip().lower()
    if related_entity_type not in RELATED_ENTITY_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported related_entity_type.")
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail=f"document_type must be one of: {', '.join(sorted(DOCUMENT_TYPES))}.")
    _verify_related_entity(db, organization_id, related_entity_type, related_entity_id)
    filename, content_type, content = await _read_upload(file)
    document_id = uuid4()
    storage_key = f"documents/{organization_id}/{document_id.hex}/v1/{uuid4().hex}{PurePath(filename).suffix.lower()}"
    try:
        store = get_storage()
        store.put(storage_key, content, content_type)
    except StorageError as exc:
        logger.exception("Private document storage write failed")
        raise HTTPException(status_code=500, detail="The document could not be stored. Please retry.") from exc
    document = TradeDocument(
        id=document_id,
        organization_id=organization_id,
        document_reference=f"DOC-{document_id.hex[:10].upper()}",
        document_type=document_type,
        title=(title or PurePath(filename).stem).strip()[:180] or "Untitled document",
        description=description.strip()[:2000] if description and description.strip() else None,
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        verification_status="pending",
        expiry_date=expiry_date,
        current_version=1,
        uploaded_by_user_id=user.id,
    )
    db.add(document)
    db.add(_make_version(organization_id=organization_id, document_id=document_id, version_number=1,
                         filename=filename, content_type=content_type, content=content,
                         storage_key=storage_key, user_id=user.id))
    try:
        db.commit()
        db.refresh(document)
    except IntegrityError as exc:
        db.rollback()
        try:
            store.delete(storage_key)
        except StorageError:
            logger.exception("Orphan document cleanup failed after metadata conflict")
        raise HTTPException(status_code=409, detail="The document could not be registered. Reload and retry.") from exc
    except Exception as exc:
        db.rollback()
        try:
            store.delete(storage_key)
        except StorageError:
            logger.exception("Orphan document cleanup failed after metadata failure")
        logger.exception("Could not save document metadata")
        raise HTTPException(status_code=500, detail="The document could not be registered. Please retry.") from exc
    return _document_out(db, document)


@router.get("/requirements", response_model=list[DocumentRequirementOut], summary="List configured document requirements")
def list_document_requirements(
    organization_id: UUID,
    related_entity_type: str,
    related_entity_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "documents.read")
    _verify_related_entity(db, organization_id, related_entity_type, related_entity_id)
    return db.query(DocumentRequirement).filter(
        DocumentRequirement.organization_id == organization_id,
        DocumentRequirement.related_entity_type == related_entity_type,
        DocumentRequirement.related_entity_id == related_entity_id,
    ).order_by(DocumentRequirement.document_type.asc()).all()


@router.post("/requirements", response_model=DocumentRequirementOut, status_code=status.HTTP_201_CREATED, summary="Configure a document requirement for a trade record")
def create_document_requirement(
    organization_id: UUID,
    payload: DocumentRequirementCreate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "documents.upload")
    if payload.document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="Unsupported document_type.")
    _verify_related_entity(db, organization_id, payload.related_entity_type.value, payload.related_entity_id)
    requirement = DocumentRequirement(
        organization_id=organization_id,
        related_entity_type=payload.related_entity_type.value,
        related_entity_id=payload.related_entity_id,
        document_type=payload.document_type,
        label=payload.label,
        is_required=payload.is_required,
        created_by_user_id=user.id,
    )
    db.add(requirement)
    try:
        db.commit()
        db.refresh(requirement)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A requirement for this document type already exists on this record.") from exc
    return requirement


@router.delete("/requirements/{requirement_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Remove a configured document requirement")
def delete_document_requirement(
    requirement_id: UUID,
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    require_org_permission(db, user.id, organization_id, "documents.delete")
    requirement = db.query(DocumentRequirement).filter(
        DocumentRequirement.id == requirement_id,
        DocumentRequirement.organization_id == organization_id,
    ).one_or_none()
    if requirement is None:
        raise HTTPException(status_code=404, detail="Document requirement not found.")
    _verify_related_entity(db, organization_id, requirement.related_entity_type, requirement.related_entity_id)
    db.delete(requirement)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/compliance", response_model=DocumentComplianceOut, summary="Check explicitly configured document requirements")
def get_document_compliance(
    organization_id: UUID,
    related_entity_type: str,
    related_entity_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_org_permission(db, user.id, organization_id, "documents.read")
    _verify_related_entity(db, organization_id, related_entity_type, related_entity_id)
    requirements = db.query(DocumentRequirement).filter(
        DocumentRequirement.organization_id == organization_id,
        DocumentRequirement.related_entity_type == related_entity_type,
        DocumentRequirement.related_entity_id == related_entity_id,
    ).order_by(DocumentRequirement.document_type.asc()).all()
    items = []
    for requirement in requirements:
        docs = db.query(TradeDocument).filter(
            TradeDocument.organization_id == organization_id,
            TradeDocument.related_entity_type == related_entity_type,
            TradeDocument.related_entity_id == related_entity_id,
            TradeDocument.document_type == requirement.document_type,
        ).all()
        uploaded_count = len(docs)
        verified_count = sum(
            1 for doc in docs
            if doc.verification_status == "verified" and (doc.expiry_date is None or doc.expiry_date >= utc_now().date())
        )
        satisfied = not requirement.is_required or verified_count > 0
        items.append(DocumentComplianceItem(
            requirement_id=requirement.id,
            document_type=requirement.document_type,
            label=requirement.label,
            is_required=requirement.is_required,
            uploaded_count=uploaded_count,
            verified_count=verified_count,
            satisfied=satisfied,
        ))
    required_items = [item for item in items if item.is_required]
    satisfied_count = sum(1 for item in required_items if item.satisfied)
    missing_count = len(required_items) - satisfied_count
    return DocumentComplianceOut(
        related_entity_type=related_entity_type,
        related_entity_id=related_entity_id,
        required_count=len(required_items),
        satisfied_count=satisfied_count,
        missing_count=missing_count,
        is_compliant=missing_count == 0,
        items=items,
    )


@router.get("/{document_id}/versions", response_model=list[DocumentVersionOut], summary="List immutable versions of a trade document")
def list_document_versions(document_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = _document(db, user.id, organization_id, document_id)
    return db.query(TradeDocumentVersion).filter(
        TradeDocumentVersion.document_id == document.id,
        TradeDocumentVersion.organization_id == organization_id,
    ).order_by(TradeDocumentVersion.version_number.desc()).all()


@router.post("/{document_id}/versions", response_model=DocumentOut, summary="Upload a new immutable document version")
async def upload_document_version(
    document_id: UUID,
    organization_id: UUID,
    request: Request,
    file: UploadFile = File(...),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    document = _document(db, user.id, organization_id, document_id, "documents.upload", lock=True)
    filename, content_type, content = await _read_upload(file)
    version_number = document.current_version + 1
    storage_key = f"documents/{organization_id}/{document.id.hex}/v{version_number}/{uuid4().hex}{PurePath(filename).suffix.lower()}"
    try:
        store = get_storage()
        store.put(storage_key, content, content_type)
    except StorageError as exc:
        logger.exception("Private document version upload failed")
        raise HTTPException(status_code=500, detail="The document version could not be stored. Please retry.") from exc
    old_status = document.verification_status
    document.current_version = version_number
    document.verification_status = "pending"
    document.verification_notes = None
    document.verified_by_user_id = None
    document.verified_at = None
    db.add(_make_version(organization_id=organization_id, document_id=document.id, version_number=version_number,
                         filename=filename, content_type=content_type, content=content,
                         storage_key=storage_key, user_id=user.id))
    if old_status != "pending":
        db.add(DocumentVerificationEvent(
            organization_id=organization_id, document_id=document.id, version_number=version_number,
            from_status=old_status, to_status="pending", notes="A new version was uploaded; verification is required again.", actor_user_id=user.id,
        ))
    try:
        db.commit()
        db.refresh(document)
    except Exception as exc:
        db.rollback()
        try:
            store.delete(storage_key)
        except StorageError:
            logger.exception("Orphan document version cleanup failed")
        logger.exception("Could not register new document version")
        raise HTTPException(status_code=500, detail="The document version could not be registered. Please retry.") from exc
    return _document_out(db, document)


@router.patch("/{document_id}/verification", response_model=DocumentOut, summary="Verify or reject the current document version")
def update_document_verification(
    document_id: UUID,
    organization_id: UUID,
    payload: VerificationUpdate,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    document = _document(db, user.id, organization_id, document_id, "documents.verify", lock=True)
    next_status = payload.verification_status.value
    previous_status = document.verification_status
    document.verification_status = next_status
    document.verification_notes = payload.verification_notes
    document.verified_by_user_id = None if next_status == "pending" else user.id
    document.verified_at = None if next_status == "pending" else utc_now()
    db.add(DocumentVerificationEvent(
        organization_id=organization_id,
        document_id=document.id,
        version_number=document.current_version,
        from_status=previous_status,
        to_status=next_status,
        notes=payload.verification_notes,
        actor_user_id=user.id,
    ))
    db.commit()
    db.refresh(document)
    return _document_out(db, document)


@router.get("/{document_id}/verification-history", response_model=list[DocumentVerificationEventOut], summary="List document verification audit history")
def list_document_verification_history(document_id: UUID, organization_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    document = _document(db, user.id, organization_id, document_id)
    return db.query(DocumentVerificationEvent).filter(
        DocumentVerificationEvent.document_id == document.id,
        DocumentVerificationEvent.organization_id == organization_id,
    ).order_by(DocumentVerificationEvent.created_at.desc()).all()


@router.get("/{document_id}/download", summary="Download a specific authorized private document version")
def download_document(
    document_id: UUID,
    organization_id: UUID,
    version_number: int | None = Query(default=None, ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    document = _document(db, user.id, organization_id, document_id)
    target_version = version_number or document.current_version
    version = db.query(TradeDocumentVersion).filter(
        TradeDocumentVersion.document_id == document.id,
        TradeDocumentVersion.organization_id == organization_id,
        TradeDocumentVersion.version_number == target_version,
    ).one_or_none()
    if version is None:
        raise HTTPException(status_code=404, detail="Document version not found.")
    try:
        content = get_storage().get(version.storage_key)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="The stored file is no longer available.") from exc
    except StorageError as exc:
        logger.exception("Private document retrieval failed")
        raise HTTPException(status_code=500, detail="The document could not be retrieved. Please retry.") from exc
    filename = quote(version.file_name, safe="")
    return Response(
        content=content,
        media_type=version.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a document and all its stored versions")
def delete_document(
    document_id: UUID,
    organization_id: UUID,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    session: UserSession = Depends(get_current_session),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _verify_mutation(request, x_csrf_token, session)
    document = _document(db, user.id, organization_id, document_id, "documents.delete", lock=True)
    versions = db.query(TradeDocumentVersion).filter(
        TradeDocumentVersion.document_id == document.id,
        TradeDocumentVersion.organization_id == organization_id,
    ).all()
    storage_keys = [version.storage_key for version in versions]
    db.delete(document)
    db.commit()
    try:
        store = get_storage()
        for key in storage_keys:
            try:
                store.delete(key)
            except StorageError:
                # The DB record is gone and the blob remains private; log for operational cleanup.
                logger.exception("Private document blob cleanup failed for a deleted document")
    except StorageError:
        # Metadata deletion has committed; report success and leave the private blob for operator cleanup.
        logger.exception("Private document storage adapter unavailable during post-delete cleanup")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
