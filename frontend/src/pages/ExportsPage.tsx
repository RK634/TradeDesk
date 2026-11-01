import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, type Resolver } from 'react-hook-form'
import { z } from 'zod'
import { ArrowRight, CheckCircle2, ClipboardCheck, LoaderCircle, PackageCheck, Plus, RefreshCw, Send, Ship, Truck } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { EmptyState } from '@/components/shared/EmptyState'
import { ApiError } from '@/features/auth/api'
import { listCustomers, listLocations, listProducts } from '@/features/master-data/api'
import type { CustomerRecord, LocationRecord, ProductRecord } from '@/features/master-data/types'
import {
  approveExportOrder, cancelExportOrder, createExportDelivery, createExportOrder, createExportShipment,
  listExportOrders, rejectExportOrder, submitExportOrder,
} from '@/features/exports/api'
import type { ExportOrder, ExportStatus } from '@/features/exports/types'

const numericQuantity = z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value) && Number(value) > 0, 'Quantity must be greater than zero (up to 4 decimals).')
const nonNegativeMoney = z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value), 'Enter a non-negative amount (up to 4 decimals).')
const exportSchema = z.object({
  customer_id: z.string().uuid('Select a customer.'),
  inventory_location_id: z.string().uuid('Select the stock location.'),
  product_id: z.string().uuid('Select a product.'),
  quantity_ordered: numericQuantity,
  unit_price: nonNegativeMoney,
  currency: z.string().regex(/^[A-Za-z]{3}$/, 'Use a three-letter currency code.'),
  destination_country: z.string().length(2, 'Use a two-letter country code.').or(z.literal('')),
  delivery_address: z.string().max(1000),
  shipping_terms: z.string().max(120),
  payment_terms_days: z.string().regex(/^\d+$/, 'Enter payment terms in days.'),
  requested_ship_date: z.string(),
  requested_delivery_date: z.string(),
  notes: z.string().max(3000),
})
type ExportForm = z.infer<typeof exportSchema>

const STATUS_LABELS: Record<ExportStatus, string> = {
  draft: 'Draft', submitted: 'Awaiting approval', approved: 'Approved', rejected: 'Returned for correction',
  partially_dispatched: 'Partially dispatched', dispatched: 'Dispatched', partially_delivered: 'Partially delivered', delivered: 'Delivered', cancelled: 'Cancelled',
}
const STATUS_STYLES: Record<ExportStatus, string> = {
  draft: 'bg-slate-100 text-slate-700', submitted: 'bg-amber-100 text-amber-800', approved: 'bg-sky-100 text-sky-800',
  rejected: 'bg-rose-100 text-rose-800', partially_dispatched: 'bg-violet-100 text-violet-800', dispatched: 'bg-blue-100 text-blue-800',
  partially_delivered: 'bg-orange-100 text-orange-800', delivered: 'bg-emerald-100 text-emerald-800', cancelled: 'bg-slate-100 text-slate-500',
}
const INPUT = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-100'
function errorMessage(error: unknown) { return error instanceof ApiError ? error.message : error instanceof Error ? error.message : 'The request could not be completed.' }
function quantity(value: string | number) { return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 }) }
function money(value: string | number, currency: string) { return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 2 }).format(Number(value)) }
function Field({ label, children }: { label: string; children: ReactNode }) { return <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">{label}</span>{children}</label> }

export function ExportsPage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [selectedOrderId, setSelectedOrderId] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [notice, setNotice] = useState('')
  const [requestError, setRequestError] = useState('')
  const [rejectReason, setRejectReason] = useState('')
  const [shipmentRef, setShipmentRef] = useState('')
  const [shipmentLineId, setShipmentLineId] = useState('')
  const [shipmentQuantity, setShipmentQuantity] = useState('')
  const [carrier, setCarrier] = useState('')
  const [transportMode, setTransportMode] = useState<'sea' | 'air' | 'road' | 'rail' | 'courier' | 'other'>('road')
  const [deliveryReference, setDeliveryReference] = useState('')
  const [deliveryShipmentId, setDeliveryShipmentId] = useState('')
  const [deliveryItemId, setDeliveryItemId] = useState('')
  const [deliveryQuantity, setDeliveryQuantity] = useState('')

  const role = selectedOrganization?.role
  const canCreate = ['organization_owner', 'administrator', 'export_manager'].includes(role ?? '')
  const canApprove = ['organization_owner', 'administrator'].includes(role ?? '')
  const canDispatch = ['organization_owner', 'administrator', 'export_manager'].includes(role ?? '')
  const canDeliver = ['organization_owner', 'administrator', 'export_manager', 'operations_staff'].includes(role ?? '')

  const ordersQuery = useQuery({ queryKey: ['exports', selectedOrganizationId, search, statusFilter], queryFn: () => listExportOrders(selectedOrganizationId, search, statusFilter), enabled: Boolean(selectedOrganizationId) })
  const customersQuery = useQuery({ queryKey: ['master-data', 'customers', selectedOrganizationId], queryFn: () => listCustomers(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) })
  const productsQuery = useQuery({ queryKey: ['master-data', 'products', selectedOrganizationId], queryFn: () => listProducts(selectedOrganizationId, '', true), enabled: Boolean(selectedOrganizationId) })
  const locationsQuery = useQuery({ queryKey: ['master-data', 'locations', selectedOrganizationId], queryFn: () => listLocations(selectedOrganizationId, true), enabled: Boolean(selectedOrganizationId) })
  const orders = ordersQuery.data?.items ?? []
  const selectedOrder = orders.find((item) => item.id === selectedOrderId) ?? null
  const customers = customersQuery.data?.items ?? []
  const products = productsQuery.data?.items ?? []
  const locations = locationsQuery.data?.items ?? []
  const shipmentItemOptions = useMemo(() => selectedOrder?.shipments.flatMap((shipment) => shipment.items.filter((item) => Number(item.quantity_remaining) > 0).map((item) => ({ ...item, shipment_reference: shipment.shipment_reference, shipment_status: shipment.status }))) ?? [], [selectedOrder])
  const dispatchOptions = selectedOrder?.items.filter((item) => Number(item.quantity_reserved) > 0) ?? []

  const form = useForm<ExportForm>({
    resolver: zodResolver(exportSchema) as Resolver<ExportForm>,
    defaultValues: { customer_id: '', inventory_location_id: '', product_id: '', quantity_ordered: '1', unit_price: '0', currency: 'EUR', destination_country: '', delivery_address: '', shipping_terms: '', payment_terms_days: '0', requested_ship_date: '', requested_delivery_date: '', notes: '' },
  })

  useEffect(() => { if (customers.length && !customers.some((item) => item.id === form.getValues('customer_id'))) form.setValue('customer_id', customers[0].id) }, [customers, form])
  useEffect(() => { if (products.length && !products.some((item) => item.id === form.getValues('product_id'))) form.setValue('product_id', products[0].id) }, [products, form])
  useEffect(() => { if (locations.length && !locations.some((item) => item.id === form.getValues('inventory_location_id'))) form.setValue('inventory_location_id', locations[0].id) }, [locations, form])
  useEffect(() => {
    if (!selectedOrderId && orders.length) setSelectedOrderId(orders[0].id)
    else if (selectedOrderId && orders.length && !orders.some((item) => item.id === selectedOrderId)) setSelectedOrderId(orders[0].id)
  }, [orders, selectedOrderId])
  useEffect(() => {
    const next = dispatchOptions[0]
    if (!dispatchOptions.some((item) => item.id === shipmentLineId)) {
      setShipmentLineId(next?.id ?? '')
      setShipmentQuantity(next ? String(next.quantity_reserved) : '')
    }
  }, [selectedOrder, shipmentLineId])
  useEffect(() => {
    const nextShipment = selectedOrder?.shipments.find((shipment) => shipment.items.some((item) => Number(item.quantity_remaining) > 0))
    const nextItem = nextShipment?.items.find((item) => Number(item.quantity_remaining) > 0)
    if (!nextShipment || !nextItem) {
      setDeliveryShipmentId(''); setDeliveryItemId(''); setDeliveryQuantity('')
    } else if (deliveryShipmentId !== nextShipment.id || deliveryItemId !== nextItem.id) {
      setDeliveryShipmentId(nextShipment.id); setDeliveryItemId(nextItem.id); setDeliveryQuantity(String(nextItem.quantity_remaining))
    }
  }, [selectedOrder, deliveryShipmentId, deliveryItemId])

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['exports', selectedOrganizationId] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'balances', selectedOrganizationId] }),
      queryClient.invalidateQueries({ queryKey: ['inventory', 'movements', selectedOrganizationId] }),
      queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
    ])
  }
  function fail(error: unknown) { setNotice(''); setRequestError(errorMessage(error)) }
  function succeed(message: string) { setRequestError(''); setNotice(message) }

  const createMutation = useMutation({
    mutationFn: (values: ExportForm) => createExportOrder(selectedOrganizationId, {
      customer_id: values.customer_id, inventory_location_id: values.inventory_location_id, currency: values.currency.toUpperCase(),
      destination_country: values.destination_country.toUpperCase() || null, delivery_address: values.delivery_address || null,
      shipping_terms: values.shipping_terms || null, payment_terms_days: Number(values.payment_terms_days),
      requested_ship_date: values.requested_ship_date || null, requested_delivery_date: values.requested_delivery_date || null,
      notes: values.notes || null, items: [{ product_id: values.product_id, quantity_ordered: values.quantity_ordered, unit_price: values.unit_price }],
    }),
    onSuccess: async (order) => { setShowCreate(false); form.reset({ ...form.getValues(), quantity_ordered: '1', unit_price: '0', notes: '' }); await refresh(); setSelectedOrderId(order.id); succeed(`Draft export ${order.reference} created.`) },
    onError: fail,
  })
  const statusMutation = useMutation({
    mutationFn: async (input: { order: ExportOrder; action: 'submit' | 'approve' | 'reject' | 'cancel' }) => {
      if (input.action === 'submit') return submitExportOrder(selectedOrganizationId, input.order.id)
      if (input.action === 'approve') return approveExportOrder(selectedOrganizationId, input.order.id)
      if (input.action === 'reject') return rejectExportOrder(selectedOrganizationId, input.order.id, rejectReason)
      return cancelExportOrder(selectedOrganizationId, input.order.id)
    },
    onSuccess: async (order) => { succeed(`${order.reference} status: ${STATUS_LABELS[order.status]}.`); setRejectReason(''); await refresh() },
    onError: fail,
  })
  const shipmentMutation = useMutation({
    mutationFn: () => {
      if (!selectedOrder || !shipmentLineId) throw new Error('Select a reserved order line before dispatching.')
      return createExportShipment(selectedOrganizationId, selectedOrder.id, {
        shipment_reference: shipmentRef.trim() || `EXS-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-${crypto.randomUUID().slice(0, 6).toUpperCase()}`,
        idempotency_key: crypto.randomUUID(), carrier: carrier.trim() || null, transport_mode: transportMode,
        items: [{ order_item_id: shipmentLineId, quantity_dispatched: shipmentQuantity }],
      })
    },
    onSuccess: async (shipment) => { setShipmentRef(''); setCarrier(''); succeed(`Shipment ${shipment.shipment_reference} dispatched. Reserved stock was deducted.`); await refresh() },
    onError: fail,
  })
  const deliveryMutation = useMutation({
    mutationFn: () => {
      if (!selectedOrder || !deliveryShipmentId || !deliveryItemId) throw new Error('Select an outstanding shipment line to record delivery.')
      return createExportDelivery(selectedOrganizationId, selectedOrder.id, deliveryShipmentId, {
        delivery_reference: deliveryReference.trim() || `DEL-${new Date().toISOString().slice(0, 10).replaceAll('-', '')}-${crypto.randomUUID().slice(0, 6).toUpperCase()}`,
        idempotency_key: crypto.randomUUID(), items: [{ shipment_item_id: deliveryItemId, quantity_delivered: deliveryQuantity }],
      })
    },
    onSuccess: async (delivery) => { setDeliveryReference(''); succeed(`Delivery ${delivery.delivery_reference} recorded.`); await refresh() },
    onError: fail,
  })

  return <div className="space-y-6">
    <section className="flex flex-col justify-between gap-4 rounded-2xl bg-[#122338] px-5 py-6 text-white sm:flex-row sm:items-end sm:px-7">
      <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-200">TRADE OPERATIONS</p><h2 className="mt-2 text-2xl font-bold tracking-tight">Export management</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">Create export orders, reserve available stock after approval, dispatch shipments, and record partial deliveries without duplicate inventory deductions.</p></div>
      <Button onClick={() => setShowCreate((value) => !value)} disabled={!canCreate || !selectedOrganizationId || customers.length === 0 || products.length === 0 || locations.length === 0}><Plus size={16} />{showCreate ? 'Close form' : 'New export order'}</Button>
    </section>

    {!selectedOrganizationId && <EmptyState icon={Truck} title="Select an organization" description="Choose an organization to load its export orders and master data." />}
    {requestError && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{requestError}</div>}
    {notice && <div role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div>}

    {showCreate && <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader><CardTitle>Create draft export order</CardTitle><CardDescription>Choose a customer, source location, and one initial order line. More advanced quotation and order-line editing can be added in a future iteration.</CardDescription></CardHeader><CardContent><form className="grid gap-4 md:grid-cols-2 xl:grid-cols-3" onSubmit={form.handleSubmit((values) => createMutation.mutate(values))}>
      <Field label="Customer"><select className={INPUT} {...form.register('customer_id')}><option value="">Select customer</option>{customers.map((item: CustomerRecord) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>{form.formState.errors.customer_id && <span className="mt-1 block text-xs text-rose-600">{form.formState.errors.customer_id.message}</span>}</Field>
      <Field label="Source inventory location"><select className={INPUT} {...form.register('inventory_location_id')}><option value="">Select location</option>{locations.map((item: LocationRecord) => <option key={item.id} value={item.id}>{item.name} ({item.code})</option>)}</select>{form.formState.errors.inventory_location_id && <span className="mt-1 block text-xs text-rose-600">{form.formState.errors.inventory_location_id.message}</span>}</Field>
      <Field label="Product"><select className={INPUT} {...form.register('product_id')}><option value="">Select product</option>{products.map((item: ProductRecord) => <option key={item.id} value={item.id}>{item.sku} · {item.name}</option>)}</select>{form.formState.errors.product_id && <span className="mt-1 block text-xs text-rose-600">{form.formState.errors.product_id.message}</span>}</Field>
      <Field label="Quantity"><input className={INPUT} inputMode="decimal" {...form.register('quantity_ordered')} />{form.formState.errors.quantity_ordered && <span className="mt-1 block text-xs text-rose-600">{form.formState.errors.quantity_ordered.message}</span>}</Field>
      <Field label="Unit selling price"><input className={INPUT} inputMode="decimal" {...form.register('unit_price')} />{form.formState.errors.unit_price && <span className="mt-1 block text-xs text-rose-600">{form.formState.errors.unit_price.message}</span>}</Field>
      <Field label="Currency"><input className={INPUT} maxLength={3} {...form.register('currency')} /></Field>
      <Field label="Destination country (2-letter code)"><input className={INPUT} maxLength={2} placeholder="DE" {...form.register('destination_country')} /></Field>
      <Field label="Shipping terms"><input className={INPUT} placeholder="DAP, FOB…" {...form.register('shipping_terms')} /></Field>
      <Field label="Payment terms (days)"><input className={INPUT} inputMode="numeric" {...form.register('payment_terms_days')} /></Field>
      <Field label="Requested ship date"><input className={INPUT} type="date" {...form.register('requested_ship_date')} /></Field>
      <Field label="Requested delivery date"><input className={INPUT} type="date" {...form.register('requested_delivery_date')} /></Field>
      <Field label="Delivery address"><input className={INPUT} {...form.register('delivery_address')} /></Field>
      <div className="md:col-span-2 xl:col-span-3"><Field label="Notes"><textarea className={INPUT} rows={2} {...form.register('notes')} /></Field></div>
      <div className="flex items-center gap-2 md:col-span-2 xl:col-span-3"><Button type="submit" disabled={createMutation.isPending}>{createMutation.isPending && <LoaderCircle className="animate-spin" size={15} />}Create draft</Button><Button variant="outline" onClick={() => setShowCreate(false)}>Cancel</Button></div>
    </form></CardContent></Card>}

    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,1.35fr)]">
      <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader><div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><div><CardTitle>Export orders</CardTitle><CardDescription className="mt-1">Organization-scoped orders and live statuses.</CardDescription></div><Button variant="outline" size="sm" onClick={() => ordersQuery.refetch()} disabled={ordersQuery.isFetching}><RefreshCw size={14} className={ordersQuery.isFetching ? 'animate-spin' : ''} />Refresh</Button></div></CardHeader><CardContent className="space-y-3">
        <div className="grid gap-2 sm:grid-cols-2"><input className={INPUT} placeholder="Search order/customer" value={search} onChange={(event) => setSearch(event.target.value)} aria-label="Search export orders" /><select className={INPUT} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)} aria-label="Filter export status"><option value="all">All statuses</option>{Object.entries(STATUS_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        {ordersQuery.isPending && <p className="py-6 text-sm text-slate-500">Loading export orders…</p>}
        {ordersQuery.isError && <div role="alert" className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{errorMessage(ordersQuery.error)}</div>}
        {!ordersQuery.isPending && !orders.length && <EmptyState icon={Truck} title="No export orders yet" description="Create an export order when your customer, product, and stock location are ready." action={canCreate ? <Button onClick={() => setShowCreate(true)}><Plus size={15} />Create export order</Button> : undefined} />}
        <div className="space-y-2">{orders.map((order) => <button key={order.id} type="button" onClick={() => setSelectedOrderId(order.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedOrderId === order.id ? 'border-sky-400 bg-sky-50/70 ring-1 ring-sky-100' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'}`}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{order.reference}</p><p className="mt-1 truncate text-xs text-slate-500">{order.customer_name} · {order.inventory_location_name}</p></div><span className={`shrink-0 rounded-full px-2 py-1 text-[10px] font-semibold ${STATUS_STYLES[order.status]}`}>{STATUS_LABELS[order.status]}</span></div><div className="mt-3 flex items-center justify-between text-xs text-slate-500"><span>{order.items.length} line(s) · delivered {quantity(order.quantity_delivered)} / {quantity(order.quantity_ordered)}</span><span className="font-semibold text-slate-800">{money(order.goods_total, order.currency)}</span></div></button>)}</div>
      </CardContent></Card>

      <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader><CardTitle>Order workflow</CardTitle><CardDescription>Approval reserves stock; dispatch posts inventory movements; delivery records can be partial.</CardDescription></CardHeader><CardContent>
        {!selectedOrder && <EmptyState icon={ClipboardCheck} title="Select an export order" description="Choose an order from the list to view its lines, status history, shipments, and available actions." />}
        {selectedOrder && <div className="space-y-5">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-start"><div><p className="text-xs text-slate-500">Selected order</p><h3 className="mt-1 text-lg font-bold text-slate-900">{selectedOrder.reference}</h3><p className="mt-1 text-sm text-slate-600">{selectedOrder.customer_name} · {selectedOrder.destination_country ?? 'Country not set'}</p></div><span className={`w-fit rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_STYLES[selectedOrder.status]}`}>{STATUS_LABELS[selectedOrder.status]}</span></div>
          <div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-medium text-slate-500">Order value</p><p className="mt-1 text-lg font-bold">{money(selectedOrder.goods_total, selectedOrder.currency)}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-medium text-slate-500">Reserved stock</p><p className="mt-1 text-lg font-bold">{quantity(selectedOrder.quantity_reserved)}</p></div><div className="rounded-xl bg-slate-50 p-3"><p className="text-[11px] font-medium text-slate-500">Delivered</p><p className="mt-1 text-lg font-bold">{quantity(selectedOrder.quantity_delivered)} / {quantity(selectedOrder.quantity_ordered)}</p></div></div>
          <div><h4 className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Order lines</h4><div className="space-y-2">{selectedOrder.items.map((line) => <div key={line.id} className="rounded-lg border border-slate-200 p-3"><div className="flex justify-between gap-3"><div><p className="text-sm font-semibold">{line.product_sku_snapshot} · {line.product_name_snapshot}</p><p className="mt-1 text-xs text-slate-500">Ordered {quantity(line.quantity_ordered)} · reserved {quantity(line.quantity_reserved)} · dispatched {quantity(line.quantity_dispatched)} · delivered {quantity(line.quantity_delivered)}</p></div><p className="shrink-0 text-sm font-semibold">{money(line.line_total, selectedOrder.currency)}</p></div></div>)}</div></div>
          <div className="flex flex-wrap gap-2">
            {(selectedOrder.status === 'draft' || selectedOrder.status === 'rejected') && canCreate && <Button size="sm" onClick={() => statusMutation.mutate({ order: selectedOrder, action: 'submit' })} disabled={statusMutation.isPending}><Send size={14} />Submit for approval</Button>}
            {selectedOrder.status === 'submitted' && canApprove && <><Button size="sm" onClick={() => statusMutation.mutate({ order: selectedOrder, action: 'approve' })} disabled={statusMutation.isPending}><CheckCircle2 size={14} />Approve and reserve stock</Button></>}
            {['draft', 'submitted', 'rejected', 'approved'].includes(selectedOrder.status) && canApprove && <Button size="sm" variant="outline" onClick={() => { if (window.confirm(`Cancel ${selectedOrder.reference}? Any outstanding stock reservation will be released.`)) statusMutation.mutate({ order: selectedOrder, action: 'cancel' }) }} disabled={statusMutation.isPending}>Cancel order</Button>}
          </div>
          {selectedOrder.status === 'submitted' && canApprove && <div className="rounded-xl border border-amber-200 bg-amber-50 p-3"><label className="block text-xs font-semibold text-amber-950">Return for correction reason</label><textarea className={`${INPUT} mt-2`} rows={2} value={rejectReason} onChange={(event) => setRejectReason(event.target.value)} placeholder="Explain what should be corrected." /><Button className="mt-2" size="sm" variant="outline" disabled={statusMutation.isPending || rejectReason.trim().length < 3} onClick={() => statusMutation.mutate({ order: selectedOrder, action: 'reject' })}>Return order for correction</Button></div>}

          {canDispatch && ['approved', 'partially_dispatched', 'partially_delivered'].includes(selectedOrder.status) && dispatchOptions.length > 0 && <div className="rounded-xl border border-slate-200 p-4"><h4 className="flex items-center gap-2 text-sm font-semibold"><Truck size={16} />Dispatch shipment</h4><p className="mt-1 text-xs leading-5 text-slate-500">Dispatch only stock already reserved for this order. The backend enforces remaining quantities and duplicate protection.</p><div className="mt-3 grid gap-3 sm:grid-cols-2"><Field label="Order line"><select className={INPUT} value={shipmentLineId} onChange={(event) => { setShipmentLineId(event.target.value); const line = dispatchOptions.find((item) => item.id === event.target.value); setShipmentQuantity(line ? String(line.quantity_reserved) : '') }}>{dispatchOptions.map((line) => <option key={line.id} value={line.id}>{line.product_sku_snapshot} · reserved {quantity(line.quantity_reserved)}</option>)}</select></Field><Field label="Dispatch quantity"><input className={INPUT} value={shipmentQuantity} onChange={(event) => setShipmentQuantity(event.target.value)} inputMode="decimal" /></Field><Field label="Shipment reference (optional)"><input className={INPUT} value={shipmentRef} onChange={(event) => setShipmentRef(event.target.value)} placeholder="Auto-generated if blank" /></Field><Field label="Carrier (optional)"><input className={INPUT} value={carrier} onChange={(event) => setCarrier(event.target.value)} /></Field><Field label="Transport mode"><select className={INPUT} value={transportMode} onChange={(event) => setTransportMode(event.target.value as typeof transportMode)}><option value="road">Road</option><option value="sea">Sea</option><option value="air">Air</option><option value="rail">Rail</option><option value="courier">Courier</option><option value="other">Other</option></select></Field></div><Button className="mt-3" size="sm" disabled={shipmentMutation.isPending || !shipmentLineId || !shipmentQuantity || Number(shipmentQuantity) <= 0} onClick={() => shipmentMutation.mutate()}>{shipmentMutation.isPending ? <LoaderCircle className="animate-spin" size={14} /> : <Truck size={14} />}Dispatch selected quantity</Button></div>}

          {canDeliver && selectedOrder.shipments.some((shipment) => shipment.items.some((line) => Number(line.quantity_remaining) > 0)) && <div className="rounded-xl border border-slate-200 p-4"><h4 className="flex items-center gap-2 text-sm font-semibold"><PackageCheck size={16} />Record delivery</h4><p className="mt-1 text-xs leading-5 text-slate-500">Record full or partial delivery against a dispatched shipment line.</p><div className="mt-3 grid gap-3 sm:grid-cols-2"><Field label="Shipment / line"><select className={INPUT} value={deliveryItemId} onChange={(event) => { const option = shipmentItemOptions.find((item) => item.id === event.target.value); if (option) { setDeliveryShipmentId(option.shipment_id); setDeliveryItemId(option.id); setDeliveryQuantity(String(option.quantity_remaining)) } }}><option value="">Select shipment line</option>{shipmentItemOptions.map((item) => <option key={item.id} value={item.id}>{item.shipment_reference} · dispatched {quantity(item.quantity_dispatched)} · left {quantity(item.quantity_remaining)}</option>)}</select></Field><Field label="Delivered quantity"><input className={INPUT} value={deliveryQuantity} onChange={(event) => setDeliveryQuantity(event.target.value)} inputMode="decimal" /></Field><Field label="Delivery reference (optional)"><input className={INPUT} value={deliveryReference} onChange={(event) => setDeliveryReference(event.target.value)} placeholder="Auto-generated if blank" /></Field></div><Button className="mt-3" size="sm" disabled={deliveryMutation.isPending || !deliveryShipmentId || !deliveryItemId || !deliveryQuantity || Number(deliveryQuantity) <= 0} onClick={() => deliveryMutation.mutate()}>{deliveryMutation.isPending ? <LoaderCircle className="animate-spin" size={14} /> : <CheckCircle2 size={14} />}Record delivery</Button></div>}

          <div><h4 className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-500"><Ship size={14} />Shipments</h4>{selectedOrder.shipments.length === 0 ? <p className="rounded-lg bg-slate-50 p-3 text-xs text-slate-500">No shipments dispatched yet.</p> : <div className="space-y-2">{selectedOrder.shipments.map((shipment) => <div key={shipment.id} className="rounded-lg border border-slate-200 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><p className="text-sm font-semibold">{shipment.shipment_reference}</p><span className={`rounded-full px-2 py-1 text-[10px] font-semibold ${shipment.status === 'delivered' ? 'bg-emerald-100 text-emerald-800' : shipment.status === 'delayed' ? 'bg-amber-100 text-amber-800' : 'bg-sky-100 text-sky-800'}`}>{shipment.status.replaceAll('_', ' ')}</span></div><p className="mt-1 text-xs text-slate-500">{shipment.carrier ?? 'Carrier not set'} · {shipment.transport_mode.toUpperCase()} · {shipment.items.length} line(s)</p><div className="mt-2 space-y-1">{shipment.items.map((line) => <p key={line.id} className="text-xs text-slate-600">Dispatched {quantity(line.quantity_dispatched)} · delivered {quantity(line.quantity_delivered)} · remaining {quantity(line.quantity_remaining)}</p>)}</div></div>)}</div>}</div>
          <div><h4 className="mb-2 flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-slate-500"><ArrowRight size={14} />Status history</h4>{selectedOrder.status_history?.length ? <ol className="space-y-2">{selectedOrder.status_history.map((item) => <li key={item.id} className="border-l-2 border-slate-200 pl-3"><p className="text-xs font-semibold">{STATUS_LABELS[item.to_status as ExportStatus] ?? item.to_status}</p><p className="mt-0.5 text-[11px] text-slate-500">{new Date(item.created_at).toLocaleString()}{item.reason ? ` · ${item.reason}` : ''}</p></li>)}</ol> : <p className="text-xs text-slate-500">No status history.</p>}</div>
        </div>}
      </CardContent></Card>
    </div>
  </div>
}
