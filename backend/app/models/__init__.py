"""Import all ORM models so metadata and migrations are complete."""

from app.models.archive import ArchiveEvent
from app.models.documents import DocumentRequirement, DocumentVerificationEvent, TradeDocument, TradeDocumentVersion
from app.models.invitation import OrganizationInvitation
from app.models.finance import FinancialAuditEvent, Invoice, InvoiceItem, Payment, PaymentAllocation
from app.models.exports import ExportDelivery, ExportDeliveryItem, ExportOrder, ExportOrderItem, ExportOrderStatusHistory, ExportShipment, ExportShipmentItem, ExportShipmentMilestone
from app.models.imports import (ImportDocument, ImportGoodsReceipt, ImportGoodsReceiptItem, ImportOrder, ImportOrderItem, ImportOrderStatusHistory, ImportShipment, ImportShipmentMilestone)
from app.models.inventory import InventoryBalance, InventoryMovement
from app.models.master_data import Customer, InventoryLocation, Product, Supplier
from app.models.organization import Organization, OrganizationMembership
from app.models.session import UserSession
from app.models.user import User
from app.models.workflow import (ApprovalEvent, ApprovalRequest, ApprovalRule, AutomationLog, Notification, NotificationPreference, Task, TaskComment, TaskStatusHistory)

__all__ = [
    "ArchiveEvent", "Customer", "FinancialAuditEvent", "Invoice", "InvoiceItem", "Payment", "PaymentAllocation", "DocumentRequirement", "DocumentVerificationEvent", "TradeDocument", "TradeDocumentVersion", "ExportDelivery", "ExportDeliveryItem", "ExportOrder", "ExportOrderItem", "ExportOrderStatusHistory", "ExportShipment", "ExportShipmentItem", "ExportShipmentMilestone", "ImportDocument", "ImportGoodsReceipt", "ImportGoodsReceiptItem", "ImportOrder", "ImportOrderItem", "ImportOrderStatusHistory", "ImportShipment", "ImportShipmentMilestone", "InventoryBalance", "InventoryLocation", "InventoryMovement",
    "Organization", "OrganizationInvitation", "OrganizationMembership", "Product",
    "Supplier", "User", "UserSession", "Task", "TaskComment", "TaskStatusHistory", "ApprovalRule", "ApprovalRequest", "ApprovalEvent", "Notification", "NotificationPreference", "AutomationLog",
]
