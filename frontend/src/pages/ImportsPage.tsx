import { useEffect, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, type Resolver } from 'react-hook-form'
import { z } from 'zod'
import {
  AlertCircle, ArrowDownToLine, CheckCircle2, CircleDollarSign, ClipboardCheck,
  FileCheck2, FileUp, LoaderCircle, PackageCheck, Plus, RefreshCw, Send,
  Ship, ShieldCheck, Truck, XCircle,
} from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { EmptyState } from '@/components/shared/EmptyState'
import { ApiError, apiResourceUrl } from '@/features/auth/api'
import { listLocations, listProducts, listSuppliers } from '@/features/master-data/api'
import type { LocationRecord, ProductRecord, SupplierRecord } from '@/features/master-data/types'
import {
  addImportOrderItem, approveImportOrder, cancelImportOrder, createGoodsReceipt,
  createImportOrder, createImportShipment, createShipmentMilestone, deleteImportDocument,
  importDocumentDownloadPath, listGoodsReceipts, listImportDocuments, listImportOrders,
  listImportShipments, listShipmentMilestones, rejectImportOrder, submitImportOrder,
  updateImportCosts, updateImportDocument, updateImportShipment, uploadImportDocument,
} from '@/features/imports/api'
import type { DocumentVerificationStatus, ImportDocument, ImportStatus, ImportShipment, ShipmentStatus } from '@/features/imports/types'

const orderSchema = z.object({
  supplier_id: z.string().uuid('Select a supplier.'),
  currency: z.string().regex(/^[A-Za-z]{3}$/, 'Enter a 3-letter currency code.'),
  purchase_terms: z.string().max(120),
  country_of_origin: z.string().length(2, 'Use a 2-letter country code.').or(z.literal('')),
  destination: z.string().max(300),
  estimated_departure_date: z.string(),
  estimated_arrival_date: z.string(),
  estimated_freight_cost: z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value), 'Enter a non-negative cost (up to 4 decimals).'),
  estimated_insurance_cost: z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value), 'Enter a non-negative cost (up to 4 decimals).'),
  estimated_duties: z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value), 'Enter a non-negative cost (up to 4 decimals).'),
  estimated_other_costs: z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value), 'Enter a non-negative cost (up to 4 decimals).'),
  product_id: z.string().uuid('Select a product.'),
  quantity_ordered: z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value) && Number(value) > 0, 'Quantity must be greater than zero (up to 4 decimals).'),
  unit_price: z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value), 'Enter a non-negative unit price (up to 4 decimals).'),
  notes: z.string().max(3000),
})
type OrderFormValues = z.infer<typeof orderSchema>

const STATUS_LABELS: Record<ImportStatus, string> = {
  draft: 'Draft', submitted: 'Awaiting approval', approved: 'Approved', rejected: 'Returned for correction',
  partially_received: 'Partially received', received: 'Goods received', cancelled: 'Cancelled',
}
const STATUS_STYLES: Record<ImportStatus, string> = {
  draft: 'bg-slate-100 text-slate-700', submitted: 'bg-amber-100 text-amber-800', approved: 'bg-sky-100 text-sky-800',
  rejected: 'bg-rose-100 text-rose-800', partially_received: 'bg-violet-100 text-violet-800', received: 'bg-emerald-100 text-emerald-800', cancelled: 'bg-slate-100 text-slate-500',
}
const SHIPMENT_STATUS_LABELS: Record<ShipmentStatus, string> = {
  planned: 'Planned', in_transit: 'In transit', arrived: 'Arrived', delayed: 'Delayed', delivered: 'Delivered', cancelled: 'Cancelled',
}
const DOC_TYPES = [
  ['commercial_invoice', 'Commercial invoice'], ['packing_list', 'Packing list'], ['bill_of_lading', 'Bill of lading'],
  ['air_waybill', 'Air waybill'], ['certificate_of_origin', 'Certificate of origin'], ['insurance_certificate', 'Insurance certificate'],
  ['customs_declaration', 'Customs declaration'], ['inspection_certificate', 'Inspection certificate'], ['product_certificate', 'Product certificate'],
  ['import_permit', 'Import permit'], ['purchase_order', 'Purchase order'], ['other', 'Other supporting document'],
] as const

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : 'The request could not be completed.'
}
function money(value: string | number, currency: string) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value))
}
function qty(value: string | number) { return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 }) }
function localDate(value: string | null | undefined) { return value ? new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString() : '—' }
function localDateTime(value: string) { return new Date(value).toLocaleString() }
function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: string }) {
  return <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">{label}</span>{children}{hint && <span className="mt-1 block text-[11px] text-slate-500">{hint}</span>}</label>
}
const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100'

export function ImportsPage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedOrderId, setSelectedOrderId] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [notice, setNotice] = useState('')
  const [requestError, setRequestError] = useState('')
  const [newItem, setNewItem] = useState({ product_id: '', quantity_ordered: '', unit_price: '', description: '' })
  const [receiptForm, setReceiptForm] = useState({ location_id: '', order_item_id: '', quantity_received: '', receipt_reference: '', notes: '' })
  const [shipmentForm, setShipmentForm] = useState({ shipment_reference: '', carrier: '', tracking_reference: '', transport_mode: 'sea', estimated_departure: '', estimated_arrival: '', notes: '' })
  const [costForm, setCostForm] = useState({ actual_freight_cost: '0', actual_insurance_cost: '0', actual_duties: '0', actual_other_costs: '0' })
  const [documentType, setDocumentType] = useState('commercial_invoice')
  const [documentExpiry, setDocumentExpiry] = useState('')
  const [uploadFile, setUploadFile] = useState<File | null>(null)
  const [milestoneInputs, setMilestoneInputs] = useState<Record<string, { name: string; occurred_at: string }>>({})
  const role = selectedOrganization?.role
  const canCreate = ['organization_owner', 'administrator', 'import_manager'].includes(role ?? '')
  const canApprove = ['organization_owner', 'administrator'].includes(role ?? '')
  const canReceive = ['organization_owner', 'administrator', 'import_manager', 'operations_staff'].includes(role ?? '')
  const canUpdateCosts = ['organization_owner', 'administrator', 'import_manager', 'finance_staff'].includes(role ?? '')
  const canUploadDocuments = canCreate || role === 'operations_staff'
  const canUpdateShipment = canCreate || role === 'operations_staff'

  const ordersQuery = useQuery({ queryKey: ['imports', selectedOrganizationId, search, statusFilter], queryFn: () => listImportOrders(selectedOrganizationId, search, statusFilter), enabled: Boolean(selectedOrganizationId) })
  const suppliersQuery = useQuery({ queryKey: ['master-data', 'suppliers', selectedOrganizationId], queryFn: () => listSuppliers(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) })
  const productsQuery = useQuery({ queryKey: ['master-data', 'products', selectedOrganizationId], queryFn: () => listProducts(selectedOrganizationId, '', true), enabled: Boolean(selectedOrganizationId) })
  const locationsQuery = useQuery({ queryKey: ['master-data', 'locations', selectedOrganizationId], queryFn: () => listLocations(selectedOrganizationId, true), enabled: Boolean(selectedOrganizationId) })

  const orders = ordersQuery.data?.items ?? []
  const selectedOrder = orders.find((order) => order.id === selectedOrderId) ?? null
  const shipmentsQuery = useQuery({ queryKey: ['imports', selectedOrganizationId, selectedOrderId, 'shipments'], queryFn: () => listImportShipments(selectedOrganizationId, selectedOrderId), enabled: Boolean(selectedOrganizationId && selectedOrderId) })
  const receiptsQuery = useQuery({ queryKey: ['imports', selectedOrganizationId, selectedOrderId, 'receipts'], queryFn: () => listGoodsReceipts(selectedOrganizationId, selectedOrderId), enabled: Boolean(selectedOrganizationId && selectedOrderId) })
  const documentsQuery = useQuery({ queryKey: ['imports', selectedOrganizationId, selectedOrderId, 'documents'], queryFn: () => listImportDocuments(selectedOrganizationId, selectedOrderId), enabled: Boolean(selectedOrganizationId && selectedOrderId) })
  const form = useForm<OrderFormValues>({
    resolver: zodResolver(orderSchema) as Resolver<OrderFormValues>,
    defaultValues: {
      supplier_id: '', currency: 'EUR', purchase_terms: '', country_of_origin: '', destination: '',
      estimated_departure_date: '', estimated_arrival_date: '', estimated_freight_cost: '0', estimated_insurance_cost: '0',
      estimated_duties: '0', estimated_other_costs: '0', product_id: '', quantity_ordered: '1', unit_price: '0', notes: '',
    },
  })

  useEffect(() => {
    if (!selectedOrderId && orders.length) setSelectedOrderId(orders[0].id)
    else if (selectedOrderId && orders.length && !orders.some((item) => item.id === selectedOrderId)) setSelectedOrderId(orders[0].id)
  }, [orders, selectedOrderId])
  useEffect(() => {
    const locations = locationsQuery.data?.items ?? []
    if (locations.length && !locations.some((location) => location.id === receiptForm.location_id)) {
      setReceiptForm((current) => ({ ...current, location_id: locations[0].id }))
    } else if (!locations.length && receiptForm.location_id) {
      setReceiptForm((current) => ({ ...current, location_id: '' }))
    }
  }, [locationsQuery.data, receiptForm.location_id])
  useEffect(() => {
    const openLines = selectedOrder?.items.filter((item) => Number(item.quantity_remaining) > 0) ?? []
    const selectedLine = openLines.find((item) => item.id === receiptForm.order_item_id)
    if (!selectedLine) {
      const firstOpenLine = openLines[0]
      setReceiptForm((current) => ({
        ...current,
        order_item_id: firstOpenLine?.id ?? '',
        quantity_received: firstOpenLine ? String(firstOpenLine.quantity_remaining) : '',
      }))
    }
  }, [selectedOrder, receiptForm.order_item_id])
  useEffect(() => {
    if (selectedOrder) setCostForm({
      actual_freight_cost: String(selectedOrder.actual_freight_cost), actual_insurance_cost: String(selectedOrder.actual_insurance_cost),
      actual_duties: String(selectedOrder.actual_duties), actual_other_costs: String(selectedOrder.actual_other_costs),
    })
  }, [selectedOrder?.id, selectedOrder?.actual_freight_cost, selectedOrder?.actual_insurance_cost, selectedOrder?.actual_duties, selectedOrder?.actual_other_costs])

  async function refreshImports() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['imports', selectedOrganizationId] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'balances', selectedOrganizationId] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'low-stock', selectedOrganizationId] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'movements', selectedOrganizationId] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
    ])
  }
  function setFailure(error: unknown) { setNotice(''); setRequestError(errorMessage(error)) }
  function setSuccess(message: string) { setRequestError(''); setNotice(message) }

  const createMutation = useMutation({
    mutationFn: (values: OrderFormValues) => createImportOrder(selectedOrganizationId, {
      supplier_id: values.supplier_id, currency: values.currency.toUpperCase(), purchase_terms: values.purchase_terms || null,
      country_of_origin: values.country_of_origin.toUpperCase() || null, destination: values.destination || null,
      estimated_departure_date: values.estimated_departure_date || null, estimated_arrival_date: values.estimated_arrival_date || null,
      estimated_freight_cost: values.estimated_freight_cost, estimated_insurance_cost: values.estimated_insurance_cost,
      estimated_duties: values.estimated_duties, estimated_other_costs: values.estimated_other_costs, notes: values.notes || null,
      items: [{ product_id: values.product_id, quantity_ordered: values.quantity_ordered, unit_price: values.unit_price }],
    }),
    onSuccess: async (order) => { setShowCreate(false); form.reset(); await refreshImports(); setSelectedOrderId(order.id); setSuccess(`Draft ${order.reference} was created.`) },
    onError: setFailure,
  })
  const statusMutation = useMutation({
    mutationFn: async (input: { orderId: string; action: 'submit' | 'approve' | 'reject' | 'cancel'; reason?: string }) => {
      if (input.action === 'submit') return submitImportOrder(selectedOrganizationId, input.orderId)
      if (input.action === 'approve') return approveImportOrder(selectedOrganizationId, input.orderId)
      if (input.action === 'reject') return rejectImportOrder(selectedOrganizationId, input.orderId, input.reason ?? '')
      return cancelImportOrder(selectedOrganizationId, input.orderId)
    },
    onSuccess: async (order) => { setSuccess(`${order.reference} status is now ${STATUS_LABELS[order.status]}.`); await refreshImports() },
    onError: setFailure,
  })
  const addLineMutation = useMutation({
    mutationFn: () => addImportOrderItem(selectedOrganizationId, selectedOrder!.id, {
      product_id: newItem.product_id, quantity_ordered: newItem.quantity_ordered, unit_price: newItem.unit_price, description: newItem.description || null,
    }),
    onSuccess: async () => { setNewItem({ product_id: '', quantity_ordered: '', unit_price: '', description: '' }); setSuccess('Import order line added.'); await refreshImports() },
    onError: setFailure,
  })
  const receiptMutation = useMutation({
    mutationFn: () => createGoodsReceipt(selectedOrganizationId, selectedOrder!.id, {
      location_id: receiptForm.location_id, receipt_reference: receiptForm.receipt_reference,
      idempotency_key: crypto.randomUUID(), notes: receiptForm.notes || null,
      items: [{ order_item_id: receiptForm.order_item_id, quantity_received: receiptForm.quantity_received }],
    }),
    onSuccess: async (receipt) => { setReceiptForm((current) => ({ ...current, receipt_reference: '', quantity_received: '', notes: '' })); setSuccess(`Goods receipt ${receipt.receipt_reference} posted and inventory updated.`); await refreshImports(); await Promise.all([receiptsQuery.refetch(), ordersQuery.refetch()]) },
    onError: setFailure,
  })
  const shipmentMutation = useMutation({
    mutationFn: () => createImportShipment(selectedOrganizationId, selectedOrder!.id, {
      shipment_reference: shipmentForm.shipment_reference, carrier: shipmentForm.carrier || null,
      tracking_reference: shipmentForm.tracking_reference || null, transport_mode: shipmentForm.transport_mode,
      estimated_departure: shipmentForm.estimated_departure || null, estimated_arrival: shipmentForm.estimated_arrival || null,
      notes: shipmentForm.notes || null,
    }),
    onSuccess: async (shipment) => { setShipmentForm({ shipment_reference: '', carrier: '', tracking_reference: '', transport_mode: 'sea', estimated_departure: '', estimated_arrival: '', notes: '' }); setSuccess(`Shipment ${shipment.shipment_reference} recorded. Carrier live tracking is not connected.`); await shipmentsQuery.refetch() },
    onError: setFailure,
  })
  const shipmentStatusMutation = useMutation({
    mutationFn: (input: { shipmentId: string; status: ShipmentStatus }) => updateImportShipment(selectedOrganizationId, input.shipmentId, { status: input.status }),
    onSuccess: async (shipment) => { setSuccess(`Shipment ${shipment.shipment_reference} updated to ${SHIPMENT_STATUS_LABELS[shipment.status]}.`); await shipmentsQuery.refetch() },
    onError: setFailure,
  })
  const milestoneMutation = useMutation({
    mutationFn: (input: { shipmentId: string }) => {
      const values = milestoneInputs[input.shipmentId]
      if (!values?.name.trim() || !values.occurred_at) throw new Error('Enter the milestone name and time.')
      return createShipmentMilestone(selectedOrganizationId, input.shipmentId, { name: values.name.trim(), occurred_at: new Date(values.occurred_at).toISOString() })
    },
    onSuccess: async (milestone) => { setMilestoneInputs((current) => ({ ...current, [milestone.shipment_id]: { name: '', occurred_at: '' } })); setSuccess('Manual shipment milestone recorded.'); await milestonesQueriesRefetch() },
    onError: setFailure,
  })
  const costsMutation = useMutation({
    mutationFn: () => updateImportCosts(selectedOrganizationId, selectedOrder!.id, {
      actual_freight_cost: costForm.actual_freight_cost, actual_insurance_cost: costForm.actual_insurance_cost,
      actual_duties: costForm.actual_duties, actual_other_costs: costForm.actual_other_costs,
    }),
    onSuccess: async () => { setSuccess('Actual import costs saved.'); await refreshImports() },
    onError: setFailure,
  })
  const documentUploadMutation = useMutation({
    mutationFn: () => {
      if (!uploadFile) throw new Error('Choose a file first.')
      const data = new FormData()
      data.append('file', uploadFile)
      data.append('document_type', documentType)
      if (documentExpiry) data.append('expiry_date', documentExpiry)
      return uploadImportDocument(selectedOrganizationId, selectedOrder!.id, data)
    },
    onSuccess: async (document) => { setUploadFile(null); setDocumentExpiry(''); setSuccess(`${document.file_name} uploaded to private storage.`); await documentsQuery.refetch() },
    onError: setFailure,
  })
  const documentVerifyMutation = useMutation({
    mutationFn: (input: { documentId: string; status: DocumentVerificationStatus }) => updateImportDocument(selectedOrganizationId, selectedOrder!.id, input.documentId, { verification_status: input.status }),
    onSuccess: async (document) => { setSuccess(`${document.file_name} marked ${document.verification_status}.`); await documentsQuery.refetch() },
    onError: setFailure,
  })
  const documentDeleteMutation = useMutation({
    mutationFn: (documentId: string) => deleteImportDocument(selectedOrganizationId, selectedOrder!.id, documentId),
    onSuccess: async () => { setSuccess('Document deleted.'); await documentsQuery.refetch() },
    onError: setFailure,
  })

  // Milestone data is loaded per shipment, only when needed, and kept scoped by the selected organization.
  const shipmentIds = (shipmentsQuery.data ?? []).map((shipment) => shipment.id)
  const milestoneQueryKey = ['imports', selectedOrganizationId, selectedOrderId, 'milestones']
  const milestonesQuery = useQuery({
    queryKey: milestoneQueryKey,
    queryFn: async () => Promise.all((shipmentsQuery.data ?? []).map(async (shipment) => ({ shipmentId: shipment.id, items: await listShipmentMilestones(selectedOrganizationId, shipment.id) }))),
    enabled: Boolean(selectedOrganizationId && selectedOrderId && shipmentIds.length),
  })
  async function milestonesQueriesRefetch() { await queryClient.invalidateQueries({ queryKey: milestoneQueryKey }) }

  const activeCount = orders.filter((order) => ['submitted', 'approved', 'partially_received'].includes(order.status)).length
  const waitingCount = orders.filter((order) => order.status === 'submitted').length
  const receivedCount = orders.filter((order) => order.status === 'received').length
  const supplierItems: SupplierRecord[] = suppliersQuery.data?.items ?? []
  const productItems: ProductRecord[] = (productsQuery.data?.items ?? []).filter((item) => item.is_active)
  const locationItems: LocationRecord[] = (locationsQuery.data?.items ?? []).filter((item) => item.is_active)
  const canReceiveSelected = Boolean(selectedOrder && ['approved', 'partially_received'].includes(selectedOrder.status) && canReceive)
  const canCreateShipment = Boolean(selectedOrder && ['approved', 'partially_received'].includes(selectedOrder.status) && ['organization_owner', 'administrator', 'import_manager'].includes(role ?? ''))

  if (!selectedOrganizationId) return <EmptyState icon={PackageCheck} title="Select an organization" description="Choose or create an organization before managing import orders." />

  return <div className="space-y-6">
    <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-end">
      <div><div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700"><PackageCheck size={15} /> TRADE OPERATIONS</div><h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">Import management</h2><p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">Create purchase orders, route them for approval, track shipments and documents, and receive goods into inventory with a duplicate-safe stock ledger.</p></div>
      <div className="flex gap-2"><button type="button" onClick={() => { void ordersQuery.refetch(); if (selectedOrderId) { void shipmentsQuery.refetch(); void receiptsQuery.refetch(); void documentsQuery.refetch() } }} className="inline-flex h-10 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50"><RefreshCw size={15} /> Refresh</button>{canCreate && <button type="button" onClick={() => setShowCreate((value) => !value)} className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-700"><Plus size={16} /> New import order</button>}</div>
    </div>

    {requestError && <div role="alert" className="flex items-start gap-2 rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800"><AlertCircle size={17} className="mt-0.5 shrink-0" /><span className="flex-1">{requestError}</span><button className="font-semibold" onClick={() => setRequestError('')} aria-label="Dismiss error">×</button></div>}
    {notice && <div role="status" className="flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"><CheckCircle2 size={17} className="mt-0.5 shrink-0" /><span className="flex-1">{notice}</span><button className="font-semibold" onClick={() => setNotice('')} aria-label="Dismiss confirmation">×</button></div>}

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="Import orders" value={String(ordersQuery.data?.total ?? '—')} note="All matching orders" icon={PackageCheck} />
      <Metric label="Active workflow" value={String(activeCount)} note="Submitted, approved, or receiving" icon={Truck} />
      <Metric label="Awaiting approval" value={String(waitingCount)} note="Submitted for review" icon={ClipboardCheck} />
      <Metric label="Goods received" value={String(receivedCount)} note="Fully received orders" icon={CircleDollarSign} />
    </div>

    {showCreate && <section className="rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex items-start justify-between border-b border-slate-100 px-5 py-4"><div><h3 className="font-semibold text-slate-900">Create draft import order</h3><p className="mt-1 text-xs text-slate-500">Add the supplier and first product line. More lines can be added before submission.</p></div><button type="button" onClick={() => setShowCreate(false)} aria-label="Close form" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><XCircle size={18} /></button></div>
      {supplierItems.length === 0 || productItems.length === 0 ? <div className="p-5"><EmptyState icon={PackageCheck} title="Master data required" description="Create at least one active supplier and one active product in the Suppliers and Products pages before creating an import order." /></div> : <form onSubmit={form.handleSubmit((values) => { if (values.estimated_departure_date && values.estimated_arrival_date && values.estimated_arrival_date < values.estimated_departure_date) { setRequestError('Estimated arrival cannot be before estimated departure.'); return } setRequestError(''); createMutation.mutate(values) })} className="space-y-5 p-5">
        <div className="grid gap-4 md:grid-cols-3"><Field label="Supplier *"><select {...form.register('supplier_id')} className={inputClass}><option value="">Select supplier</option>{supplierItems.filter((item) => item.is_active).map((item) => <option key={item.id} value={item.id}>{item.supplier_code ? `${item.supplier_code} · ` : ''}{item.name}</option>)}</select>{form.formState.errors.supplier_id && <ErrorText>{form.formState.errors.supplier_id.message}</ErrorText>}</Field><Field label="Currency *"><input {...form.register('currency')} maxLength={3} className={inputClass} /></Field><Field label="Purchase / shipping terms"><input {...form.register('purchase_terms')} placeholder="e.g. FOB Hamburg" className={inputClass} /></Field></div>
        <div className="grid gap-4 md:grid-cols-3"><Field label="Country of origin"><input {...form.register('country_of_origin')} maxLength={2} placeholder="CN" className={inputClass} /></Field><Field label="Destination"><input {...form.register('destination')} placeholder="Port or delivery destination" className={inputClass} /></Field><Field label="Notes"><input {...form.register('notes')} placeholder="Internal notes" className={inputClass} /></Field></div>
        <div className="grid gap-4 md:grid-cols-2"><Field label="Estimated departure"><input type="date" {...form.register('estimated_departure_date')} className={inputClass} /></Field><Field label="Estimated arrival"><input type="date" {...form.register('estimated_arrival_date')} className={inputClass} /></Field></div>
        <div className="rounded-xl border border-slate-200 p-4"><h4 className="mb-3 text-sm font-semibold text-slate-900">First product line</h4><div className="grid gap-4 md:grid-cols-3"><Field label="Product *"><select {...form.register('product_id')} className={inputClass}><option value="">Select product</option>{productItems.map((item) => <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>)}</select>{form.formState.errors.product_id && <ErrorText>{form.formState.errors.product_id.message}</ErrorText>}</Field><Field label="Ordered quantity *"><input {...form.register('quantity_ordered')} inputMode="decimal" className={inputClass} /></Field><Field label="Unit purchase price *"><input {...form.register('unit_price')} inputMode="decimal" className={inputClass} /></Field></div></div>
        <div className="rounded-xl border border-slate-200 p-4"><h4 className="mb-3 text-sm font-semibold text-slate-900">Estimated additional costs</h4><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{(['estimated_freight_cost', 'estimated_insurance_cost', 'estimated_duties', 'estimated_other_costs'] as const).map((key) => <Field key={key} label={{ estimated_freight_cost: 'Freight', estimated_insurance_cost: 'Insurance', estimated_duties: 'Customs duties', estimated_other_costs: 'Other costs' }[key]}><input {...form.register(key)} inputMode="decimal" className={inputClass} />{form.formState.errors[key] && <ErrorText>{form.formState.errors[key]?.message}</ErrorText>}</Field>)}</div><p className="mt-3 text-[11px] leading-5 text-slate-500">All cost calculations use decimal monetary fields and the order currency. Estimated costs are kept separate from actual costs.</p></div>
        <div className="flex justify-end gap-2"><button type="button" onClick={() => setShowCreate(false)} className="h-10 rounded-lg border border-slate-200 px-4 text-sm font-semibold text-slate-600">Cancel</button><button type="submit" disabled={createMutation.isPending} className="inline-flex h-10 items-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white disabled:opacity-60">{createMutation.isPending && <LoaderCircle size={15} className="animate-spin" />}{createMutation.isPending ? 'Creating…' : 'Create draft'}</button></div>
      </form>}</section>}

    <div className="grid gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.4fr)]">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-100 p-4"><div className="flex items-center justify-between gap-3"><h3 className="font-semibold text-slate-900">Import orders</h3><span className="text-xs text-slate-500">{ordersQuery.data?.total ?? 0} records</span></div><div className="mt-3 grid gap-2 sm:grid-cols-[1fr_180px]"><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search reference or supplier…" aria-label="Search import orders" className={inputClass} /><select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter import status" className={inputClass}><option value="all">All statuses</option>{Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div></div>
        {ordersQuery.isPending ? <RowsSkeleton /> : ordersQuery.isError ? <div className="p-5 text-sm text-rose-700">{errorMessage(ordersQuery.error)} <button className="ml-2 font-semibold underline" onClick={() => void ordersQuery.refetch()}>Retry</button></div> : orders.length === 0 ? <div className="p-6"><EmptyState icon={PackageCheck} title="No import orders yet" description="Create a draft order to begin tracking a supplier purchase." /></div> : <div className="max-h-[760px] overflow-auto"><table className="w-full min-w-[520px] text-left text-sm"><thead className="sticky top-0 bg-slate-50 text-[10px] font-bold uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Order / supplier</th><th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Estimated total</th></tr></thead><tbody className="divide-y divide-slate-100">{orders.map((order) => <tr key={order.id} className={`cursor-pointer transition hover:bg-slate-50 ${selectedOrderId === order.id ? 'bg-sky-50/70' : ''}`} onClick={() => setSelectedOrderId(order.id)} aria-selected={selectedOrderId === order.id}><td className="px-4 py-3.5"><p className="font-semibold text-slate-900">{order.reference}</p><p className="mt-1 max-w-52 truncate text-xs text-slate-500">{order.supplier_name}</p><p className="mt-1 text-[10px] text-slate-400">Updated {localDate(order.updated_at)}</p></td><td className="px-4 py-3.5"><StatusPill status={order.status} /></td><td className="whitespace-nowrap px-4 py-3.5 text-right text-xs font-semibold tabular-nums text-slate-700">{money(order.estimated_total_cost, order.currency)}</td></tr>)}</tbody></table></div>}
      </section>

      <section className="min-w-0 space-y-5">
        {!selectedOrder ? <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><EmptyState icon={ClipboardCheck} title="Select an import order" description="Choose an order from the list to review its items, approval history, shipments, receipts, costs, and documents." /></div> : <>
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="flex flex-col justify-between gap-4 border-b border-slate-100 p-5 sm:flex-row sm:items-start"><div><div className="flex flex-wrap items-center gap-2"><h3 className="text-lg font-bold text-slate-900">{selectedOrder.reference}</h3><StatusPill status={selectedOrder.status} /></div><p className="mt-1 text-sm text-slate-500">Supplier: <span className="font-semibold text-slate-700">{selectedOrder.supplier_name}</span></p><p className="mt-1 text-xs text-slate-500">{selectedOrder.country_of_origin || 'Origin not set'} → {selectedOrder.destination || 'Destination not set'} · {selectedOrder.currency}</p></div><div className="flex flex-wrap gap-2">{['draft', 'rejected'].includes(selectedOrder.status) && canCreate && <button type="button" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate({ orderId: selectedOrder.id, action: 'submit' })} className="inline-flex h-9 items-center gap-2 rounded-lg bg-sky-700 px-3 text-xs font-semibold text-white hover:bg-sky-800"><Send size={14} /> Submit</button>}{selectedOrder.status === 'submitted' && canApprove && <><button type="button" disabled={statusMutation.isPending} onClick={() => statusMutation.mutate({ orderId: selectedOrder.id, action: 'approve' })} className="inline-flex h-9 items-center gap-2 rounded-lg bg-emerald-700 px-3 text-xs font-semibold text-white hover:bg-emerald-800"><CheckCircle2 size={14} /> Approve</button><button type="button" disabled={statusMutation.isPending} onClick={() => { const reason = window.prompt('Reason for returning this order for correction:'); if (reason?.trim()) statusMutation.mutate({ orderId: selectedOrder.id, action: 'reject', reason: reason.trim() }) }} className="inline-flex h-9 items-center gap-2 rounded-lg border border-rose-200 px-3 text-xs font-semibold text-rose-700 hover:bg-rose-50"><XCircle size={14} /> Return</button></>}{['draft', 'rejected', 'approved'].includes(selectedOrder.status) && canApprove && <button type="button" disabled={statusMutation.isPending} onClick={() => { if (window.confirm(`Cancel ${selectedOrder.reference}? This cannot be undone.`)) statusMutation.mutate({ orderId: selectedOrder.id, action: 'cancel' }) }} className="h-9 rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-600 hover:bg-slate-50">Cancel order</button>}</div></div>
            {selectedOrder.rejection_reason && <div className="border-b border-rose-100 bg-rose-50 px-5 py-3 text-sm text-rose-800"><strong>Correction requested:</strong> {selectedOrder.rejection_reason}</div>}
            <div className="grid gap-4 p-5 sm:grid-cols-3"><CostStat label="Goods value" value={money(selectedOrder.estimated_goods_total, selectedOrder.currency)} /><CostStat label="Estimated landed total" value={money(selectedOrder.estimated_total_cost, selectedOrder.currency)} /><CostStat label="Actual landed total" value={money(selectedOrder.actual_total_cost, selectedOrder.currency)} /></div>
            <div className="overflow-x-auto border-t border-slate-100"><table className="w-full min-w-[610px] text-left text-sm"><thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Product</th><th className="px-4 py-3 text-right">Ordered</th><th className="px-4 py-3 text-right">Received</th><th className="px-4 py-3 text-right">Remaining</th><th className="px-5 py-3 text-right">Line total</th></tr></thead><tbody className="divide-y divide-slate-100">{selectedOrder.items.map((item) => <tr key={item.id}><td className="px-5 py-3.5"><p className="font-semibold text-slate-800">{item.product_name_snapshot}</p><p className="mt-1 text-[11px] text-slate-500">{item.product_sku_snapshot}{item.description ? ` · ${item.description}` : ''}</p></td><td className="px-4 py-3.5 text-right tabular-nums">{qty(item.quantity_ordered)}</td><td className="px-4 py-3.5 text-right tabular-nums">{qty(item.quantity_received)}</td><td className="px-4 py-3.5 text-right tabular-nums">{qty(item.quantity_remaining)}</td><td className="whitespace-nowrap px-5 py-3.5 text-right font-semibold tabular-nums">{money(item.line_total, selectedOrder.currency)}</td></tr>)}{selectedOrder.items.length === 0 && <tr><td colSpan={5} className="px-5 py-6 text-center text-sm text-slate-500">No product lines. Add at least one before submitting.</td></tr>}</tbody></table></div>
            {['draft', 'rejected'].includes(selectedOrder.status) && canCreate && <form onSubmit={(event) => { event.preventDefault(); if (!newItem.product_id || !newItem.quantity_ordered || !newItem.unit_price) { setRequestError('Choose a product, quantity, and unit price to add a line.'); return } addLineMutation.mutate() }} className="grid gap-3 border-t border-slate-100 bg-slate-50/70 p-4 sm:grid-cols-4"><Field label="Add product"><select value={newItem.product_id} onChange={(event) => setNewItem({ ...newItem, product_id: event.target.value })} className={inputClass}><option value="">Product</option>{productItems.map((item) => <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>)}</select></Field><Field label="Quantity"><input value={newItem.quantity_ordered} onChange={(event) => setNewItem({ ...newItem, quantity_ordered: event.target.value })} inputMode="decimal" className={inputClass} /></Field><Field label="Unit price"><input value={newItem.unit_price} onChange={(event) => setNewItem({ ...newItem, unit_price: event.target.value })} inputMode="decimal" className={inputClass} /></Field><div className="flex items-end"><button type="submit" disabled={addLineMutation.isPending} className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"><Plus size={14} /> Add line</button></div></form>}
          </div>

          <div className="grid gap-5 2xl:grid-cols-2">
            <section className="rounded-2xl border border-slate-200 bg-white shadow-sm"><SectionHeader icon={Ship} title="Shipments" subtitle="Manual shipment details and milestone events" />
              {shipmentsQuery.isPending ? <RowsSkeleton /> : (shipmentsQuery.data ?? []).length === 0 ? <div className="p-5"><EmptyState icon={Truck} title="No shipments recorded" description="Once approved, create a shipment to track planned dates and manual milestone updates." /></div> : <div className="divide-y divide-slate-100">{(shipmentsQuery.data ?? []).map((shipment) => <ShipmentRow key={shipment.id} shipment={shipment} milestones={(milestonesQuery.data ?? []).find((entry) => entry.shipmentId === shipment.id)?.items ?? []} milestoneInput={milestoneInputs[shipment.id] ?? { name: '', occurred_at: '' }} onMilestoneInput={(values) => setMilestoneInputs((current) => ({ ...current, [shipment.id]: values }))} onMilestoneSubmit={() => milestoneMutation.mutate({ shipmentId: shipment.id })} milestonePending={milestoneMutation.isPending} canUpdate={canUpdateShipment} onStatusChange={(nextStatus) => shipmentStatusMutation.mutate({ shipmentId: shipment.id, status: nextStatus })} statusPending={shipmentStatusMutation.isPending} />)}</div>}
              {canCreateShipment && <form onSubmit={(event) => { event.preventDefault(); if (!shipmentForm.shipment_reference.trim()) { setRequestError('Enter a shipment reference.'); return } shipmentMutation.mutate() }} className="space-y-3 border-t border-slate-100 p-4"><h4 className="text-sm font-semibold text-slate-900">Record shipment</h4><div className="grid gap-3 sm:grid-cols-2"><Field label="Shipment reference *"><input value={shipmentForm.shipment_reference} onChange={(event) => setShipmentForm({ ...shipmentForm, shipment_reference: event.target.value })} className={inputClass} placeholder="SHP-2026-001" /></Field><Field label="Carrier"><input value={shipmentForm.carrier} onChange={(event) => setShipmentForm({ ...shipmentForm, carrier: event.target.value })} className={inputClass} /></Field><Field label="Tracking reference"><input value={shipmentForm.tracking_reference} onChange={(event) => setShipmentForm({ ...shipmentForm, tracking_reference: event.target.value })} className={inputClass} /></Field><Field label="Transport mode"><select value={shipmentForm.transport_mode} onChange={(event) => setShipmentForm({ ...shipmentForm, transport_mode: event.target.value })} className={inputClass}><option value="sea">Sea</option><option value="air">Air</option><option value="road">Road</option><option value="rail">Rail</option><option value="courier">Courier</option><option value="other">Other</option></select></Field><Field label="Estimated departure"><input type="date" value={shipmentForm.estimated_departure} onChange={(event) => setShipmentForm({ ...shipmentForm, estimated_departure: event.target.value })} className={inputClass} /></Field><Field label="Estimated arrival"><input type="date" value={shipmentForm.estimated_arrival} onChange={(event) => setShipmentForm({ ...shipmentForm, estimated_arrival: event.target.value })} className={inputClass} /></Field></div><button type="submit" disabled={shipmentMutation.isPending} className="inline-flex h-9 items-center gap-2 rounded-lg bg-slate-900 px-3 text-xs font-semibold text-white"><Plus size={14} /> Record shipment</button><p className="text-[11px] text-slate-500">Tracking events are entered manually; live carrier tracking is not configured.</p></form>}
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white shadow-sm"><SectionHeader icon={PackageCheck} title="Goods receipts" subtitle="Partial receipts update stock and ledger atomically" />
              {receiptsQuery.isPending ? <RowsSkeleton /> : (receiptsQuery.data ?? []).length === 0 ? <div className="p-5"><EmptyState icon={PackageCheck} title="No goods received yet" description="Post a receipt after the import order is approved. Stock is not increased before receipt confirmation." /></div> : <div className="divide-y divide-slate-100">{(receiptsQuery.data ?? []).map((receipt) => <div key={receipt.id} className="p-4"><div className="flex items-start justify-between gap-3"><div><p className="text-sm font-semibold text-slate-900">{receipt.receipt_reference}</p><p className="mt-1 text-xs text-slate-500">{localDateTime(receipt.received_at)}</p></div><span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold text-emerald-700">Posted to stock</span></div><ul className="mt-3 space-y-1.5 text-xs text-slate-600">{receipt.items.map((item) => <li key={item.id} className="flex justify-between gap-4"><span>{item.product_sku} · {item.product_name}</span><strong className="tabular-nums">+{qty(item.quantity_received)}</strong></li>)}</ul></div>)}</div>}
              {canReceiveSelected && <form onSubmit={(event) => { event.preventDefault(); if (!receiptForm.location_id || !receiptForm.order_item_id || !receiptForm.receipt_reference.trim() || !/^\d+(\.\d{1,4})?$/.test(receiptForm.quantity_received) || Number(receiptForm.quantity_received) <= 0) { setRequestError('Choose a location and remaining order line, enter a receipt reference and positive quantity.'); return } receiptMutation.mutate() }} className="space-y-3 border-t border-slate-100 p-4"><h4 className="text-sm font-semibold text-slate-900">Receive goods</h4><div className="grid gap-3 sm:grid-cols-2"><Field label="Stock location *"><select value={receiptForm.location_id} onChange={(event) => setReceiptForm({ ...receiptForm, location_id: event.target.value })} className={inputClass}><option value="">Select location</option>{locationItems.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.name}</option>)}</select></Field><Field label="Order line *"><select value={receiptForm.order_item_id} onChange={(event) => { const item = selectedOrder.items.find((row) => row.id === event.target.value); setReceiptForm({ ...receiptForm, order_item_id: event.target.value, quantity_received: item ? String(item.quantity_remaining) : '' }) }} className={inputClass}><option value="">Select open line</option>{selectedOrder.items.filter((item) => Number(item.quantity_remaining) > 0).map((item) => <option key={item.id} value={item.id}>{item.product_sku_snapshot} · remaining {qty(item.quantity_remaining)}</option>)}</select></Field><Field label="Receipt reference *"><input value={receiptForm.receipt_reference} onChange={(event) => setReceiptForm({ ...receiptForm, receipt_reference: event.target.value })} className={inputClass} placeholder="GRN-0001" /></Field><Field label="Quantity received *"><input value={receiptForm.quantity_received} onChange={(event) => setReceiptForm({ ...receiptForm, quantity_received: event.target.value })} inputMode="decimal" className={inputClass} /></Field><div className="sm:col-span-2"><Field label="Receipt notes"><input value={receiptForm.notes} onChange={(event) => setReceiptForm({ ...receiptForm, notes: event.target.value })} className={inputClass} /></Field></div></div><button type="submit" disabled={receiptMutation.isPending || !locationItems.length || !selectedOrder.items.some((item) => Number(item.quantity_remaining) > 0)} className="inline-flex h-9 items-center gap-2 rounded-lg bg-emerald-700 px-3 text-xs font-semibold text-white disabled:opacity-50">{receiptMutation.isPending && <LoaderCircle size={14} className="animate-spin" />}<PackageCheck size={14} /> Post goods receipt</button><p className="text-[11px] leading-5 text-slate-500">The API prevents duplicate receipts and over-receiving, and commits the receipt, item totals, inventory balance, and ledger movements in a single transaction.</p></form>}
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white shadow-sm"><SectionHeader icon={FileCheck2} title="Order documents" subtitle="Private files with verification status" />
              {documentsQuery.isPending ? <RowsSkeleton /> : (documentsQuery.data ?? []).length === 0 ? <div className="p-5"><EmptyState icon={FileCheck2} title="No documents attached" description="Upload purchase and transport documents to the private storage area." /></div> : <div className="divide-y divide-slate-100">{(documentsQuery.data ?? []).map((document) => <DocumentRow key={document.id} document={document} organizationId={selectedOrganizationId} orderId={selectedOrder.id} canVerify={canApprove} canDelete={['organization_owner', 'administrator'].includes(role ?? '')} verifying={documentVerifyMutation.isPending} deleting={documentDeleteMutation.isPending} onVerify={(nextStatus) => documentVerifyMutation.mutate({ documentId: document.id, status: nextStatus })} onDelete={() => { if (window.confirm(`Delete ${document.file_name}?`)) documentDeleteMutation.mutate(document.id) }} />)}</div>}
              {canUploadDocuments && <form onSubmit={(event) => { event.preventDefault(); if (!uploadFile) { setRequestError('Choose a document file first.'); return } documentUploadMutation.mutate() }} className="space-y-3 border-t border-slate-100 p-4"><h4 className="text-sm font-semibold text-slate-900">Upload document</h4><div className="grid gap-3 sm:grid-cols-2"><Field label="Document category"><select value={documentType} onChange={(event) => setDocumentType(event.target.value)} className={inputClass}>{DOC_TYPES.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></Field><Field label="Expiry date (if applicable)"><input type="date" value={documentExpiry} onChange={(event) => setDocumentExpiry(event.target.value)} className={inputClass} /></Field><div className="sm:col-span-2"><Field label="File (PDF, image, XLSX, DOCX, CSV, or TXT)" hint={uploadFile ? `${uploadFile.name} · ${(uploadFile.size / 1024).toFixed(0)} KB` : 'Private storage; maximum size is configured by the backend.'}><input type="file" accept=".pdf,.png,.jpg,.jpeg,.xlsx,.docx,.csv,.txt" onChange={(event) => setUploadFile(event.target.files?.[0] ?? null)} className={`${inputClass} file:mr-3 file:rounded-md file:border-0 file:bg-slate-100 file:px-3 file:py-1.5 file:text-xs file:font-semibold`} /></Field></div></div><button type="submit" disabled={documentUploadMutation.isPending} className="inline-flex h-9 items-center gap-2 rounded-lg bg-slate-900 px-3 text-xs font-semibold text-white">{documentUploadMutation.isPending ? <LoaderCircle size={14} className="animate-spin" /> : <FileUp size={14} />} Upload privately</button></form>}
            </section>

            <section className="rounded-2xl border border-slate-200 bg-white shadow-sm"><SectionHeader icon={CircleDollarSign} title="Cost tracking" subtitle="Keep estimates separate from actual logistics costs" />
              <div className="space-y-4 p-4"><div className="grid gap-3 sm:grid-cols-2"><CostStat label="Estimated freight / insurance / duties / other" value={money(Number(selectedOrder.estimated_freight_cost) + Number(selectedOrder.estimated_insurance_cost) + Number(selectedOrder.estimated_duties) + Number(selectedOrder.estimated_other_costs), selectedOrder.currency)} /><CostStat label="Actual freight / insurance / duties / other" value={money(Number(selectedOrder.actual_freight_cost) + Number(selectedOrder.actual_insurance_cost) + Number(selectedOrder.actual_duties) + Number(selectedOrder.actual_other_costs), selectedOrder.currency)} /></div>{canUpdateCosts && !['draft', 'cancelled'].includes(selectedOrder.status) && <form onSubmit={(event) => { event.preventDefault(); const inputs = Object.values(costForm); if (inputs.some((value) => !/^\d+(\.\d{1,4})?$/.test(value))) { setRequestError('Actual costs must be non-negative amounts with up to four decimal places.'); return } costsMutation.mutate() }} className="space-y-3 border-t border-slate-100 pt-4"><div className="grid gap-3 sm:grid-cols-2">{(['actual_freight_cost', 'actual_insurance_cost', 'actual_duties', 'actual_other_costs'] as const).map((key) => <Field key={key} label={{ actual_freight_cost: 'Actual freight', actual_insurance_cost: 'Actual insurance', actual_duties: 'Actual duties', actual_other_costs: 'Actual other costs' }[key]}><input value={costForm[key]} onChange={(event) => setCostForm({ ...costForm, [key]: event.target.value })} inputMode="decimal" className={inputClass} /></Field>)}</div><button type="submit" disabled={costsMutation.isPending} className="inline-flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"><CircleDollarSign size={14} /> Save actual costs</button></form>}<p className="text-[11px] leading-5 text-slate-500">Actual total includes the product line total plus actual logistics cost fields. Supplier invoices and payment reconciliation can be managed from the Finance section.</p></div>
            </section>
          </div>

          <section className="rounded-2xl border border-slate-200 bg-white shadow-sm"><SectionHeader icon={ClipboardCheck} title="Approval and status history" subtitle="Recorded transitions with actor and reason" />{selectedOrder.status_history.length === 0 ? <p className="p-5 text-sm text-slate-500">No status history recorded.</p> : <ol className="space-y-0 p-5">{selectedOrder.status_history.map((entry, index) => <li key={entry.id} className="relative flex gap-3 pb-5 last:pb-0"><span className="mt-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600"><CheckCircle2 size={14} /></span>{index !== selectedOrder.status_history.length - 1 && <span className="absolute bottom-0 left-[13px] top-8 w-px bg-slate-200" />}<div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold text-slate-800">{entry.from_status ? `${STATUS_LABELS[entry.from_status as ImportStatus] ?? entry.from_status} → ` : ''}{STATUS_LABELS[entry.to_status as ImportStatus] ?? entry.to_status}</p><time className="text-[11px] text-slate-400">{localDateTime(entry.created_at)}</time></div>{entry.reason && <p className="mt-1 text-xs text-slate-500">{entry.reason}</p>}<p className="mt-1 truncate text-[10px] text-slate-400">Actor ID: {entry.actor_user_id}</p></div></li>)}</ol>}</section>
        </>}
      </section>
    </div>
    <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-xs leading-5 text-slate-500"><ShieldCheck size={16} className="mt-0.5 shrink-0 text-slate-400" /><p>All import actions are authorized by the backend and scoped to the active organization. Goods receipts update inventory only after an approved order is received, over-receipts are rejected, and stock ledger postings are committed with the receipt. This page does not imply live carrier integrations.</p></div>
  </div>
}

function Metric({ label, value, note, icon: Icon }: { label: string; value: string; note: string; icon: typeof PackageCheck }) {
  return <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-start justify-between gap-3"><p className="text-xs font-semibold text-slate-500">{label}</p><span className="rounded-lg bg-sky-50 p-2 text-sky-700"><Icon size={17} /></span></div><p className="mt-3 text-2xl font-bold tracking-tight text-slate-900">{value}</p><p className="mt-1 text-[11px] text-slate-500">{note}</p></div>
}
function CostStat({ label, value }: { label: string; value: string }) { return <div className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-semibold text-slate-500">{label}</p><p className="mt-1 text-base font-bold tabular-nums text-slate-900">{value}</p></div> }
function StatusPill({ status }: { status: ImportStatus }) { return <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-[10px] font-bold ${STATUS_STYLES[status]}`}>{STATUS_LABELS[status]}</span> }
function SectionHeader({ icon: Icon, title, subtitle }: { icon: typeof Ship; title: string; subtitle: string }) { return <div className="flex items-start gap-3 border-b border-slate-100 px-4 py-4"><span className="rounded-lg bg-slate-100 p-2 text-slate-700"><Icon size={17} /></span><div><h3 className="text-sm font-semibold text-slate-900">{title}</h3><p className="mt-1 text-xs leading-5 text-slate-500">{subtitle}</p></div></div> }
function ErrorText({ children }: { children?: ReactNode }) { return children ? <span className="mt-1 block text-[11px] text-rose-600">{children}</span> : null }
function RowsSkeleton() { return <div className="space-y-3 p-5">{[0, 1, 2].map((id) => <div key={id} className="h-10 animate-pulse rounded-lg bg-slate-100" />)}</div> }
function ShipmentRow({ shipment, milestones, milestoneInput, onMilestoneInput, onMilestoneSubmit, milestonePending, canUpdate, onStatusChange, statusPending }: {
  shipment: ImportShipment; milestones: { id: string; name: string; occurred_at: string; description: string | null }[]
  milestoneInput: { name: string; occurred_at: string }; onMilestoneInput: (value: { name: string; occurred_at: string }) => void
  onMilestoneSubmit: () => void; milestonePending: boolean; canUpdate: boolean; onStatusChange: (status: ShipmentStatus) => void; statusPending: boolean
}) {
  return <div className="p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-sm font-semibold text-slate-900">{shipment.shipment_reference}</p><p className="mt-1 text-xs text-slate-500">{shipment.carrier || 'Carrier not set'} · {shipment.transport_mode.toUpperCase()}{shipment.tracking_reference ? ` · ${shipment.tracking_reference}` : ''}</p><p className="mt-1 text-[11px] text-slate-500">ETA {localDate(shipment.estimated_arrival)}{shipment.actual_arrival ? ` · Actual ${localDate(shipment.actual_arrival)}` : ''}</p></div><select aria-label={`Shipment ${shipment.shipment_reference} status`} value={shipment.status} disabled={!canUpdate || statusPending} onChange={(event) => onStatusChange(event.target.value as ShipmentStatus)} className="rounded-lg border border-slate-200 px-2 py-1.5 text-xs font-semibold"><option value="planned">Planned</option><option value="in_transit">In transit</option><option value="arrived">Arrived</option><option value="delayed">Delayed</option><option value="delivered">Delivered</option><option value="cancelled">Cancelled</option></select></div>
    {milestones.length > 0 && <ol className="mt-3 space-y-2 border-l border-slate-200 pl-3">{milestones.map((milestone) => <li key={milestone.id} className="text-xs"><p className="font-semibold text-slate-700">{milestone.name}</p><p className="mt-0.5 text-[10px] text-slate-500">{localDateTime(milestone.occurred_at)}{milestone.description ? ` · ${milestone.description}` : ''}</p></li>)}</ol>}
    {canUpdate && <form onSubmit={(event) => { event.preventDefault(); onMilestoneSubmit() }} className="mt-3 grid gap-2 sm:grid-cols-[1fr_190px_auto]"><input aria-label={`Milestone name for ${shipment.shipment_reference}`} value={milestoneInput.name} onChange={(event) => onMilestoneInput({ ...milestoneInput, name: event.target.value })} className={inputClass} placeholder="Milestone name" /><input aria-label={`Milestone date for ${shipment.shipment_reference}`} type="datetime-local" value={milestoneInput.occurred_at} onChange={(event) => onMilestoneInput({ ...milestoneInput, occurred_at: event.target.value })} className={inputClass} /><button type="submit" disabled={milestonePending} className="h-10 rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-700">Add milestone</button></form>}
  </div>
}
function DocumentRow({ document, organizationId, orderId, canVerify, canDelete, verifying, deleting, onVerify, onDelete }: {
  document: ImportDocument; organizationId: string; orderId: string; canVerify: boolean; canDelete: boolean; verifying: boolean; deleting: boolean
  onVerify: (status: DocumentVerificationStatus) => void; onDelete: () => void
}) {
  const statusClass = document.verification_status === 'verified' ? 'bg-emerald-100 text-emerald-800' : document.verification_status === 'rejected' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'
  return <div className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center"><span className="rounded-lg bg-slate-100 p-2.5 text-slate-600"><FileCheck2 size={17} /></span><div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold text-slate-800">{document.file_name}</p><p className="mt-1 text-[11px] text-slate-500">{document.document_type.replaceAll('_', ' ')} · {(document.file_size / 1024).toFixed(0)} KB · {localDate(document.created_at)}</p><span className={`mt-1.5 inline-flex rounded-full px-2 py-0.5 text-[10px] font-bold ${statusClass}`}>{document.verification_status}</span></div><div className="flex flex-wrap items-center gap-2"><a href={apiResourceUrl(importDocumentDownloadPath(organizationId, orderId, document.id))} className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"><ArrowDownToLine size={13} /> Download</a>{canVerify && document.verification_status === 'pending' && <><button type="button" disabled={verifying} onClick={() => onVerify('verified')} title="Mark document verified" className="rounded-lg p-2 text-emerald-700 hover:bg-emerald-50"><CheckCircle2 size={16} /></button><button type="button" disabled={verifying} onClick={() => onVerify('rejected')} title="Reject document" className="rounded-lg p-2 text-rose-700 hover:bg-rose-50"><XCircle size={16} /></button></>}{canDelete && <button type="button" disabled={deleting} onClick={onDelete} title="Delete document" className="rounded-lg p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-700">×</button>}</div></div>
}
