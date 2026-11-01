export type TaskPriority = 'low' | 'normal' | 'high' | 'urgent'
export type TaskStatus = 'open' | 'in_progress' | 'blocked' | 'completed' | 'cancelled'
export interface TaskComment { id: string; task_id: string; author_user_id: string; author_name: string; body: string; created_at: string }
export interface TaskHistory { id: string; from_status: string | null; to_status: string; note: string | null; actor_user_id: string; actor_name: string; created_at: string }
export interface TaskRecord {
  id: string; organization_id: string; title: string; description: string | null
  assigned_to_user_id: string | null; assigned_to_name: string | null
  related_entity_type: string | null; related_entity_id: string | null
  priority: TaskPriority; status: TaskStatus; due_at: string | null; completed_at: string | null
  created_by_user_id: string; created_by_name: string; created_at: string; updated_at: string
  comments: TaskComment[]; history: TaskHistory[]
}
export interface Page<T> { items: T[]; total: number; page: number; page_size: number }
export interface ApprovalRule {
  id: string | null; organization_id: string; business_action: string; is_enabled: boolean
  required_roles: string[]; minimum_amount: string | number | null; allow_self_approval: boolean; updated_at: string
}
export interface ApprovalEvent { id: string; from_status: string | null; to_status: string; note: string | null; actor_user_id: string; actor_name: string; created_at: string }
export interface ApprovalRecord {
  id: string; organization_id: string; business_action: string; related_entity_type: string; related_entity_id: string
  title: string; requested_by_user_id: string; requested_by_name: string; decided_by_user_id: string | null
  decided_by_name: string | null; status: 'submitted' | 'approved' | 'rejected' | 'returned' | 'cancelled'
  request_note: string | null; decision_note: string | null; requested_amount: string | number | null; currency: string | null
  submitted_at: string; decided_at: string | null; events: ApprovalEvent[]
}
export type NotificationCategory = 'task' | 'approval' | 'invoice' | 'shipment' | 'inventory' | 'document' | 'order' | 'system'
export interface NotificationRecord {
  id: string; organization_id: string; user_id: string; category: NotificationCategory
  title: string; message: string; link_path: string | null; payload: Record<string, unknown>
  read_at: string | null; created_at: string
}
export interface NotificationPage { items: NotificationRecord[]; total: number; unread_count: number; page: number; page_size: number }
export interface NotificationPreference { category: NotificationCategory; in_app_enabled: boolean; updated_at: string }
export interface AutomationLog {
  id: string; event_type: string; subject_type: string; subject_id: string; status: string
  recipient_count: number; attempt_count: number; last_error: string | null; processed_at: string | null; created_at: string
}
