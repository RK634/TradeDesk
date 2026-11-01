export interface DashboardWorkspaceMetrics {
  total_members: number
  active_members: number
  inactive_members: number
  new_members: number
  pending_invitations: number | null
  can_view_invitations: boolean
}

export interface MemberJoinTrendPoint {
  date: string
  label: string
  count: number
}

export interface MemberRoleBreakdown {
  role: string
  label: string
  count: number
}

export interface ImportDashboardMetrics {
  active_orders: number
  awaiting_approval: number
  partially_received: number
  received: number
  delayed_shipments: number
}

export interface ExportDashboardMetrics {
  active_orders: number
  awaiting_approval: number
  partially_dispatched: number
  dispatched: number
  partially_delivered: number
  delivered: number
  delayed_shipments: number
}

export interface FinanceCurrencyMetric {
  currency: string
  customer_receivables: string | number
  supplier_payables: string | number
  overdue_customer: string | number
  overdue_supplier: string | number
  open_invoice_count: number
}

export interface DashboardSummary {
  organization_id: string
  organization_name: string
  organization_role: string
  period_start: string
  period_end: string
  generated_at: string
  workspace: DashboardWorkspaceMetrics
  member_join_trend: MemberJoinTrendPoint[]
  members_by_role: MemberRoleBreakdown[]
  import_metrics?: ImportDashboardMetrics | null
  export_metrics?: ExportDashboardMetrics | null
  financial_metrics?: FinanceCurrencyMetric[] | null
}
