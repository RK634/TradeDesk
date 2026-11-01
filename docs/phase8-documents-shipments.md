# Phase 8 — Documents and Shipments

## Delivered functionality

Phase 8 extends the Phase 6 import and Phase 7 export workflows with a unified, organization-scoped document vault and shipment register.

### Private document management

- One document API covers import orders, import shipments, export orders, and export shipments.
- Uploaded files are stored outside the frontend/public asset directory. The local adapter uses a private filesystem root; the S3-compatible adapter stores private objects without public ACLs or public URLs.
- `STORAGE_BACKEND=local` is the development default. Production configuration is rejected unless `APP_ENV=production` also has secure session cookies, `STORAGE_BACKEND=s3`, and a configured S3 bucket.
- Uploads enforce a configurable maximum byte size, an explicit file-extension allowlist, and basic content/signature checks for supported formats. Empty files and extension/content mismatches are rejected.
- Each upload creates version 1 with a SHA-256 checksum. New versions are immutable, receive their own storage key and version number, and put the document back into `pending` verification.
- Document downloads are served through an authenticated and organization-scoped API route. Responses use `Cache-Control: private, no-store`, `Content-Disposition: attachment`, and `X-Content-Type-Options: nosniff`.
- Document verification records the status, actor, timestamp, version, and notes. New versions require verification again.
- Configurable document requirements can be attached to each order or shipment. The system does not assume that a particular trade document is universally required: the organization configures the requirement for the specific record.
- Compliance is satisfied only when at least one matching document is verified and is not expired. An absent requirement list is reported as no configured requirements, not as a jurisdictional/legal compliance determination.
- Deleting a document is restricted to roles with `documents.delete`; metadata and versions are removed, and storage cleanup failures are logged for operator follow-up.

### Unified shipment tracking

- A shared shipment register combines import and export shipments while keeping their existing order and shipment records intact.
- Search and filters support shipment direction, status, transport mode, reference, tracking reference, and carrier.
- Import and export shipments have chronological milestone timelines. A system milestone is created when an import shipment is planned or an export dispatch is recorded; status transitions also append system milestones.
- Authorized operations users can append manually observed milestones. Events are never fabricated and no live carrier API is implied.
- Delay status requires a reason. Resuming an in-transit shipment clears the current delay reason while preserving the historical delay milestone.
- Export delivery remains governed by the Phase 7 delivery workflow; the general tracking endpoint cannot manually mark an export shipment delivered.
- Dashboard shipment indicators use persisted import/export shipment rows and their current status.

## Main API endpoints

All endpoints are under `/api/v1`. The user must have an active membership in the requested organization. Mutations require the session/CSRF/origin safeguards used by the existing application.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/documents` | List documents for the authorized organization; optional entity, document type, and verification filters |
| `POST` | `/documents` | Upload a private document against an import/export order or shipment |
| `GET` | `/documents/{document_id}/versions` | List immutable versions |
| `POST` | `/documents/{document_id}/versions` | Upload a new version and reset verification to pending |
| `GET` | `/documents/{document_id}/download` | Download the current or selected version after authorization |
| `PATCH` | `/documents/{document_id}/verification` | Verify, reject, or return the current version to pending, with an audit event |
| `GET` | `/documents/{document_id}/verification-history` | Read verification audit events |
| `DELETE` | `/documents/{document_id}` | Delete document metadata and associated stored versions, with permission |
| `GET` | `/documents/requirements` | List explicitly configured requirements for one order/shipment |
| `POST` | `/documents/requirements` | Configure a required or optional document type for one order/shipment |
| `DELETE` | `/documents/requirements/{requirement_id}` | Remove a configured requirement |
| `GET` | `/documents/compliance` | Evaluate configured document requirements for one order/shipment |
| `GET` | `/shipments` | Unified import/export shipment register with filters |
| `PATCH` | `/shipments/{shipment_type}/{shipment_id}` | Update allowed tracking fields, status, and delay reason |
| `GET` | `/shipments/{shipment_type}/{shipment_id}/milestones` | List chronological shipment milestones |
| `POST` | `/shipments/{shipment_type}/{shipment_id}/milestones` | Add a manually observed milestone |

The earlier import-specific document and milestone endpoints remain available for compatibility with the Phase 6 UI/workflows. New shared document operations should use `/documents`; unified shipment operations should use `/shipments`.

## Database changes

Alembic revision `0006_documents_shipments`:

- Adds `trade_documents`, `trade_document_versions`, `document_verification_events`, and `document_requirements`.
- Adds `export_shipment_milestones` and the `delay_reason`/`updated_at` fields to export shipments.
- Uses composite foreign keys to ensure document versions and verification events belong to the same organization as their parent document.
- Adds constraints and indexes for valid entity/status values, positive version/file sizes, unique document references, unique version numbers, unique storage keys, and entity-scoped requirement uniqueness.

The polymorphic document target (`related_entity_type`, `related_entity_id`) is validated against the appropriate table and organization in the API on every read or write. This is deliberate because the target may be one of four different trade record tables.

## Frontend changes

- Adds the Trade Documents page for private uploads, current version status, new versions, downloads, verification/rejection, and requirement/compliance management.
- Adds the unified Shipment Tracking page with import/export filters, active/delayed counts, timeline entries, status updates, delay reasons, and manual milestones.
- Adds typed document and shipment API modules and query invalidation on successful mutations.
- Exposes both pages in the authenticated application navigation.

## Configuration

Development defaults to local private storage:

```dotenv
STORAGE_BACKEND=local
PRIVATE_STORAGE_DIR=.private_storage
MAX_UPLOAD_BYTES=15728640
```

To use an S3-compatible private bucket:

```dotenv
APP_ENV=production
SESSION_COOKIE_SECURE=true
STORAGE_BACKEND=s3
S3_BUCKET_NAME=your-private-bucket
S3_REGION=eu-central-1
S3_ENDPOINT_URL=
S3_ACCESS_KEY_ID=
S3_SECRET_ACCESS_KEY=
```

Use secret management rather than committing credentials. Configure bucket-level block-public-access controls, encryption at rest, TLS, least-privilege object access for the application identity, lifecycle/backup policies, and operational monitoring. The application does not create public ACLs or presigned public URLs. Validate the exact S3-compatible provider and its IAM policy before production.

## Verification

- Backend API suite: **42 passed**.
- Python compilation: passed.
- Alembic upgrade through `0006_documents_shipments`: passed against a temporary SQLite database.
- `alembic check`: no new upgrade operations detected.
- Alembic downgrade one revision and upgrade back to head: passed on the temporary SQLite database.
- TypeScript/TSX syntax transpilation: 49 non-declaration source files checked with zero syntax diagnostics.
- Full `npm run typecheck` remains blocked in this environment because `vite/client` is missing from the incomplete `node_modules` installation. A full Vite production build and frontend unit tests have therefore not been claimed.
- Docker/PostgreSQL runtime verification was not available in this environment. PostgreSQL row-locking, object-store integration, and browser-level workflow checks still need to be run with the target services.

## Limitations and explicit non-goals

- Live carrier tracking is not integrated. Tracking numbers are stored, but events must be entered by authorized users until a carrier provider and API credentials are configured.
- Document requirements are organization-configured. The application does not determine applicable customs, tax, licensing, or jurisdictional obligations.
- Upload validation is an allowlist/signature check, not antivirus or content-disarm scanning. Add malware scanning and content inspection before accepting untrusted production files at scale.
- Local filesystem storage is for development/single-instance operation. Use S3-compatible private object storage for multi-instance production deployments.
- Storage/database writes cannot form one distributed transaction. The implementation removes an object when metadata creation fails and logs failed deletion cleanup for operator reconciliation; production operations should add a scheduled orphan-object audit.
- Retention schedules, legal holds, external document-signing, OCR, and automatic regulatory checks are not implemented in this phase.
