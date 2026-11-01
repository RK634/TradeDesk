import { useMemo, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useLocation, useNavigate, useOutletContext } from 'react-router-dom'
import { AlertCircle, ArrowDownLeft, ArrowUpRight, FileText, History, Plus, RefreshCw, Wallet } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { listCustomers, listSuppliers } from '@/features/master-data/api'
import { listImportOrders } from '@/features/imports/api'
import { listExportOrders } from '@/features/exports/api'
import { allocateExistingPayment, createInvoice, createPayment, getInvoiceAudit, getPaymentAudit, issueInvoice, listInvoices, listPayments, reversePayment } from '@/features/finance/api'
import type { FinancialAuditEvent, InvoiceLineInput } from '@/features/finance/types'
import { useAuth } from '@/features/auth/AuthProvider'

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-400 focus:ring-2 focus:ring-sky-100'
const today = new Date().toISOString().slice(0, 10)
const emptyLine: InvoiceLineInput = { description: '', quantity: '1', unit_price: '0.00', tax_rate: '0' }

function amount(value: string | number, currency: string) {
  return new Intl.NumberFormat(undefined, { style: 'currency', currency, minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value || 0))
}

function statusClass(value: string) {
  if (value === 'paid' || value === 'posted') return 'bg-emerald-50 text-emerald-700'
  if (value === 'partially_paid' || value === 'overdue' || value === 'reversed') return 'bg-amber-50 text-amber-700'
  if (value === 'void') return 'bg-slate-100 text-slate-600'
  if (value === 'draft') return 'bg-slate-100 text-slate-600'
  return 'bg-sky-50 text-sky-700'
}

function AuditTrail({ events }: { events: FinancialAuditEvent[] }) {
  if (events.length === 0) return <p className="text-sm text-slate-500">No financial history has been recorded.</p>
  return <ol className="space-y-3 border-l border-slate-200 pl-4">{events.map((event) => <li key={event.id} className="relative"><span className="absolute -left-[21px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-white bg-sky-500 ring-1 ring-sky-200" /><p className="text-sm font-semibold text-slate-800">{event.action.replaceAll('_', ' ')}</p><p className="mt-0.5 text-xs text-slate-500">{new Date(event.created_at).toLocaleString()}</p>{Object.keys(event.details).length > 0 && <pre className="mt-1 overflow-x-auto rounded bg-slate-50 p-2 text-[10px] text-slate-500">{JSON.stringify(event.details, null, 2)}</pre>}</li>)}</ol>
}

export function FinancePage() {
  const location = useLocation()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { auth } = useAuth()
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const activeTab = location.pathname.endsWith('/payments') ? 'payments' : 'invoices'
  const role = selectedOrganization?.role ?? ''
  const canReadFinance = ['organization_owner', 'administrator', 'finance_staff', 'read_only'].includes(role)
  const canManage = ['organization_owner', 'administrator', 'finance_staff'].includes(role)
  const canReverse = ['organization_owner', 'administrator', 'finance_staff'].includes(role)

  const [invoiceSearch, setInvoiceSearch] = useState('')
  const [invoiceStatus, setInvoiceStatus] = useState('all')
  const [invoiceTypeFilter, setInvoiceTypeFilter] = useState('all')
  const [paymentSearch, setPaymentSearch] = useState('')
  const [paymentStatus, setPaymentStatus] = useState('all')
  const [paymentTypeFilter, setPaymentTypeFilter] = useState('all')

  const [invoiceType, setInvoiceType] = useState<'customer' | 'supplier'>('customer')
  const [invoiceNumber, setInvoiceNumber] = useState('')
  const [partnerId, setPartnerId] = useState('')
  const [invoiceOrderId, setInvoiceOrderId] = useState('')
  const [issueDate, setIssueDate] = useState(today)
  const [dueDate, setDueDate] = useState(today)
  const [currency, setCurrency] = useState('EUR')
  const [discount, setDiscount] = useState('0.00')
  const [lines, setLines] = useState<InvoiceLineInput[]>([{ ...emptyLine }])
  const [invoiceNotice, setInvoiceNotice] = useState('')
  const [invoiceError, setInvoiceError] = useState('')
  const [auditInvoiceId, setAuditInvoiceId] = useState('')
  const [auditPaymentId, setAuditPaymentId] = useState('')

  const [selectedPaymentInvoiceId, setSelectedPaymentInvoiceId] = useState('')
  const [paymentReference, setPaymentReference] = useState('')
  const [paymentAmount, setPaymentAmount] = useState('')
  const [paymentDate, setPaymentDate] = useState(today)
  const [paymentMethod, setPaymentMethod] = useState('bank_transfer')
  const [paymentNotice, setPaymentNotice] = useState('')
  const [paymentError, setPaymentError] = useState('')
  const [reversingPayment, setReversingPayment] = useState('')
  const [reversalReason, setReversalReason] = useState('')
  const [reconcilePaymentId, setReconcilePaymentId] = useState('')
  const [reconcileInvoiceId, setReconcileInvoiceId] = useState('')
  const [reconcileAmount, setReconcileAmount] = useState('')

  const invoicesQuery = useQuery({
    queryKey: ['finance', 'invoices', selectedOrganizationId, invoiceSearch, invoiceStatus, invoiceTypeFilter],
    queryFn: () => listInvoices(selectedOrganizationId, invoiceSearch, invoiceStatus, invoiceTypeFilter),
    enabled: Boolean(selectedOrganizationId) && canReadFinance, retry: false,
  })
  const paymentInvoicesQuery = useQuery({
    queryKey: ['finance', 'payment-open-invoices', selectedOrganizationId],
    queryFn: () => listInvoices(selectedOrganizationId),
    enabled: Boolean(selectedOrganizationId) && canReadFinance, retry: false,
  })
  const paymentsQuery = useQuery({
    queryKey: ['finance', 'payments', selectedOrganizationId, paymentSearch, paymentStatus, paymentTypeFilter],
    queryFn: () => listPayments(selectedOrganizationId, paymentSearch, paymentStatus, paymentTypeFilter),
    enabled: Boolean(selectedOrganizationId) && canReadFinance, retry: false,
  })
  const customersQuery = useQuery({ queryKey: ['finance', 'customers', selectedOrganizationId], queryFn: () => listCustomers(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) && canReadFinance && invoiceType === 'customer' })
  const suppliersQuery = useQuery({ queryKey: ['finance', 'suppliers', selectedOrganizationId], queryFn: () => listSuppliers(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) && canReadFinance && invoiceType === 'supplier' })
  const importOrdersQuery = useQuery({ queryKey: ['finance', 'import-orders', selectedOrganizationId], queryFn: () => listImportOrders(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) && canReadFinance && invoiceType === 'supplier' })
  const exportOrdersQuery = useQuery({ queryKey: ['finance', 'export-orders', selectedOrganizationId], queryFn: () => listExportOrders(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) && canReadFinance && invoiceType === 'customer' })
  const auditInvoiceQuery = useQuery({ queryKey: ['finance', 'invoice-audit', selectedOrganizationId, auditInvoiceId], queryFn: () => getInvoiceAudit(selectedOrganizationId, auditInvoiceId), enabled: Boolean(selectedOrganizationId && auditInvoiceId) && canReadFinance })
  const auditPaymentQuery = useQuery({ queryKey: ['finance', 'payment-audit', selectedOrganizationId, auditPaymentId], queryFn: () => getPaymentAudit(selectedOrganizationId, auditPaymentId), enabled: Boolean(selectedOrganizationId && auditPaymentId) && canReadFinance })

  const customers = customersQuery.data?.items ?? []
  const suppliers = suppliersQuery.data?.items ?? []
  const partners = invoiceType === 'customer' ? customers : suppliers
  const invoices = invoicesQuery.data?.items ?? []
  const payments = paymentsQuery.data?.items ?? []
  const openInvoices = useMemo(() => (paymentInvoicesQuery.data?.items ?? []).filter((invoice) => ['issued', 'partially_paid', 'overdue'].includes(invoice.status) && Number(invoice.outstanding_balance) > 0), [paymentInvoicesQuery.data])
  const selectedPaymentInvoice = invoices.find((invoice) => invoice.id === selectedPaymentInvoiceId)
  const invoiceOrders = invoiceType === 'customer'
    ? (exportOrdersQuery.data?.items ?? []).filter((order) => order.customer_id === partnerId)
    : (importOrdersQuery.data?.items ?? []).filter((order) => order.supplier_id === partnerId)
  const selectedReconcilePayment = payments.find((payment) => payment.id === reconcilePaymentId && payment.status === 'posted' && Number(payment.unallocated_amount) > 0)
  const reconcileInvoices = selectedReconcilePayment
    ? openInvoices.filter((invoice) => invoice.currency === selectedReconcilePayment.currency && (selectedReconcilePayment.payment_type === 'incoming' ? invoice.invoice_type === 'customer' : invoice.invoice_type === 'supplier'))
    : []
  const selectedReconcileInvoice = reconcileInvoices.find((invoice) => invoice.id === reconcileInvoiceId)

  const createInvoiceMutation = useMutation({
    mutationFn: () => createInvoice(selectedOrganizationId, {
      invoice_number: invoiceNumber.trim(), invoice_type: invoiceType,
      ...(invoiceType === 'customer' ? { customer_id: partnerId } : { supplier_id: partnerId }),
      ...(invoiceType === 'customer' && invoiceOrderId ? { export_order_id: invoiceOrderId } : {}),
      ...(invoiceType === 'supplier' && invoiceOrderId ? { import_order_id: invoiceOrderId } : {}),
      issue_date: issueDate, due_date: dueDate, currency, discount_amount: discount,
      items: lines.map((line) => ({ description: line.description.trim(), quantity: line.quantity, unit_price: line.unit_price, tax_rate: line.tax_rate })),
    }),
    onSuccess: (invoice) => {
      setInvoiceNotice(`Draft invoice ${invoice.invoice_number} was created. Issue it from the invoice register when it is ready.`)
      setInvoiceError('')
      setInvoiceNumber(''); setPartnerId(''); setInvoiceOrderId(''); setDiscount('0.00'); setLines([{ ...emptyLine }])
      void queryClient.invalidateQueries({ queryKey: ['finance', 'invoices', selectedOrganizationId] })
    },
    onError: (error) => setInvoiceError(error instanceof Error ? error.message : 'Invoice could not be created.'),
  })
  const issueMutation = useMutation({
    mutationFn: (invoiceId: string) => issueInvoice(selectedOrganizationId, invoiceId),
    onSuccess: (invoice) => { setInvoiceNotice(`Invoice ${invoice.invoice_number} has been issued.`); void queryClient.invalidateQueries({ queryKey: ['finance', 'invoices', selectedOrganizationId] }) },
    onError: (error) => setInvoiceError(error instanceof Error ? error.message : 'Invoice could not be issued.'),
  })
  const createPaymentMutation = useMutation({
    mutationFn: () => {
      if (!selectedPaymentInvoice) throw new Error('Select an open invoice.')
      const direction = selectedPaymentInvoice.invoice_type === 'customer' ? 'incoming' : 'outgoing'
      return createPayment(selectedOrganizationId, {
        payment_reference: paymentReference.trim(), payment_type: direction,
        payment_date: paymentDate, currency: selectedPaymentInvoice.currency,
        amount: paymentAmount, payment_method: paymentMethod,
        idempotency_key: crypto.randomUUID(),
        allocations: [{ invoice_id: selectedPaymentInvoice.id, allocated_payment_amount: paymentAmount }],
      })
    },
    onSuccess: (payment) => {
      setPaymentNotice(`Payment ${payment.payment_reference} was recorded and allocated.`)
      setPaymentError(''); setPaymentReference(''); setPaymentAmount(''); setSelectedPaymentInvoiceId('')
      void queryClient.invalidateQueries({ queryKey: ['finance', 'payments', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['finance', 'invoices', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary', selectedOrganizationId] })
    },
    onError: (error) => setPaymentError(error instanceof Error ? error.message : 'Payment could not be recorded.'),
  })
  const reconcileMutation = useMutation({
    mutationFn: () => {
      if (!selectedReconcilePayment || !selectedReconcileInvoice) throw new Error('Select a posted payment and a compatible open invoice.')
      return allocateExistingPayment(selectedOrganizationId, selectedReconcilePayment.id, {
        invoice_id: selectedReconcileInvoice.id, allocated_payment_amount: reconcileAmount,
      })
    },
    onSuccess: (payment) => {
      setPaymentNotice(`Unapplied balance from ${payment.payment_reference} was allocated successfully.`)
      setPaymentError(''); setReconcilePaymentId(''); setReconcileInvoiceId(''); setReconcileAmount('')
      void queryClient.invalidateQueries({ queryKey: ['finance', 'payments', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['finance', 'invoices', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['finance', 'payment-open-invoices', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary', selectedOrganizationId] })
    },
    onError: (error) => setPaymentError(error instanceof Error ? error.message : 'Payment allocation could not be reconciled.'),
  })
  const reverseMutation = useMutation({
    mutationFn: () => reversePayment(selectedOrganizationId, reversingPayment, reversalReason),
    onSuccess: (payment) => {
      setPaymentNotice(`Payment ${payment.payment_reference} was reversed. Its allocations no longer reduce invoice balances.`)
      setReversingPayment(''); setReversalReason('')
      void queryClient.invalidateQueries({ queryKey: ['finance', 'payments', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['finance', 'invoices', selectedOrganizationId] })
      void queryClient.invalidateQueries({ queryKey: ['dashboard', 'summary', selectedOrganizationId] })
    },
    onError: (error) => setPaymentError(error instanceof Error ? error.message : 'Payment could not be reversed.'),
  })

  function submitInvoice(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setInvoiceNotice(''); setInvoiceError('')
    if (dueDate < issueDate) { setInvoiceError('Due date cannot be before invoice date.'); return }
    if (!partnerId) { setInvoiceError(`Select a ${invoiceType} for this invoice.`); return }
    if (invoiceOrderId && !invoiceOrders.some((order) => order.id === invoiceOrderId)) { setInvoiceError('The selected order is no longer available for this partner.'); return }
    if (lines.some((line) => !line.description.trim() || Number(line.quantity) <= 0 || Number(line.unit_price) < 0 || Number(line.tax_rate) < 0 || Number(line.tax_rate) > 100)) {
      setInvoiceError('Check each invoice line. Description, positive quantity, non-negative price, and tax from 0 to 100 are required.'); return
    }
    createInvoiceMutation.mutate()
  }

  function submitReconciliation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPaymentNotice(''); setPaymentError('')
    if (!selectedReconcilePayment || !selectedReconcileInvoice) { setPaymentError('Select a posted payment balance and a compatible open invoice.'); return }
    if (Number(reconcileAmount) <= 0 || Number(reconcileAmount) > Number(selectedReconcilePayment.unallocated_amount) || Number(reconcileAmount) > Number(selectedReconcileInvoice.outstanding_balance)) { setPaymentError('Allocation must be positive and cannot exceed the payment balance or invoice outstanding amount.'); return }
    reconcileMutation.mutate()
  }

  function submitPayment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPaymentNotice(''); setPaymentError('')
    if (!selectedPaymentInvoice) { setPaymentError('Select an open invoice.'); return }
    if (Number(paymentAmount) <= 0 || Number(paymentAmount) > Number(selectedPaymentInvoice.outstanding_balance)) {
      setPaymentError('Payment allocation must be positive and cannot exceed the invoice outstanding balance.'); return
    }
    createPaymentMutation.mutate()
  }

  if (!canReadFinance) return <div className="rounded-xl border border-amber-200 bg-amber-50 p-6"><h2 className="text-base font-semibold text-amber-900">Financial access required</h2><p className="mt-1 text-sm text-amber-800">Your organization role does not include permission to view invoices and payments. Contact an organization administrator if you need access.</p></div>

  const auditEvents = auditInvoiceId ? auditInvoiceQuery.data : auditPaymentQuery.data
  const auditLoading = auditInvoiceId ? auditInvoiceQuery.isPending : auditPaymentQuery.isPending
  const auditError = auditInvoiceId ? auditInvoiceQuery.isError : auditPaymentQuery.isError

  return <div className="space-y-6">
    <section className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div><p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">Finance workspace</p><h2 className="mt-1 text-2xl font-bold tracking-tight text-slate-900">Invoices & payments</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">Create supplier and customer invoices, issue approved financial records, allocate partial payments, and preserve a traceable correction history.</p></div>
      <Button variant="outline" onClick={() => { void invoicesQuery.refetch(); void paymentsQuery.refetch() }} disabled={invoicesQuery.isFetching || paymentsQuery.isFetching}><RefreshCw size={14} className={invoicesQuery.isFetching || paymentsQuery.isFetching ? 'animate-spin' : ''} />Refresh</Button>
    </section>
    <div className="flex gap-2 border-b border-slate-200">
      <button type="button" onClick={() => navigate('/app/invoices')} className={`border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === 'invoices' ? 'border-sky-600 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}><FileText className="mr-2 inline" size={15} />Invoices</button>
      <button type="button" onClick={() => navigate('/app/payments')} className={`border-b-2 px-4 py-3 text-sm font-semibold ${activeTab === 'payments' ? 'border-sky-600 text-sky-700' : 'border-transparent text-slate-500 hover:text-slate-800'}`}><Wallet className="mr-2 inline" size={15} />Payments</button>
    </div>

    {activeTab === 'invoices' ? <>
      {canManage && <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Create invoice draft</CardTitle><CardDescription>Amounts are calculated on the server using decimal arithmetic and two-decimal ROUND_HALF_UP rounding.</CardDescription></CardHeader><CardContent className="p-4 sm:p-5"><form className="space-y-4" onSubmit={submitInvoice}>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <label className="space-y-1.5 text-xs font-semibold text-slate-600">Invoice direction<select className={inputClass} value={invoiceType} onChange={(event) => { setInvoiceType(event.target.value as 'customer' | 'supplier'); setPartnerId(''); setInvoiceOrderId('') }}><option value="customer">Customer invoice (receivable)</option><option value="supplier">Supplier invoice (payable)</option></select></label>
          <label className="space-y-1.5 text-xs font-semibold text-slate-600">Invoice number<input className={inputClass} value={invoiceNumber} onChange={(event) => setInvoiceNumber(event.target.value)} placeholder="INV-2026-001" required /></label>
          <label className="space-y-1.5 text-xs font-semibold text-slate-600">{invoiceType === 'customer' ? 'Customer' : 'Supplier'}<select className={inputClass} value={partnerId} onChange={(event) => { setPartnerId(event.target.value); setInvoiceOrderId('') }} required><option value="">Select {invoiceType}…</option>{partners.map((partner) => <option key={partner.id} value={partner.id}>{partner.name}</option>)}</select></label>
          <label className="space-y-1.5 text-xs font-semibold text-slate-600">Related {invoiceType === 'customer' ? 'export' : 'import'} order (optional)<select className={inputClass} value={invoiceOrderId} onChange={(event) => { const value = event.target.value; setInvoiceOrderId(value); const selected = invoiceOrders.find((order) => order.id === value); if (selected) setCurrency(selected.currency) }} disabled={!partnerId}><option value="">No linked order</option>{invoiceOrders.map((order) => <option key={order.id} value={order.id}>{order.reference} · {order.currency}</option>)}</select></label>
          <label className="space-y-1.5 text-xs font-semibold text-slate-600">Currency<input className={inputClass} value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} minLength={3} maxLength={3} pattern="[A-Za-z]{3}" required disabled={Boolean(invoiceOrderId)} /></label>
          <label className="space-y-1.5 text-xs font-semibold text-slate-600">Invoice date<input className={inputClass} type="date" value={issueDate} onChange={(event) => setIssueDate(event.target.value)} required /></label>
          <label className="space-y-1.5 text-xs font-semibold text-slate-600">Due date<input className={inputClass} type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} min={issueDate} required /></label>
          <label className="space-y-1.5 text-xs font-semibold text-slate-600">Discount amount<input className={inputClass} type="number" min="0" step="0.01" value={discount} onChange={(event) => setDiscount(event.target.value)} /></label>
        </div>
        <div className="space-y-2"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold text-slate-800">Invoice lines</h3><Button type="button" size="sm" variant="outline" onClick={() => setLines((current) => [...current, { ...emptyLine }])}><Plus size={14} />Add line</Button></div>
          {lines.map((line, index) => <div key={index} className="grid gap-2 rounded-xl border border-slate-200 p-3 sm:grid-cols-[minmax(180px,1.6fr)_0.65fr_0.8fr_0.65fr_auto]"><label className="space-y-1 text-[11px] font-semibold text-slate-500">Description<input className={inputClass} value={line.description} onChange={(event) => setLines((current) => current.map((item, i) => i === index ? { ...item, description: event.target.value } : item))} placeholder="Goods or service" required /></label><label className="space-y-1 text-[11px] font-semibold text-slate-500">Quantity<input className={inputClass} type="number" min="0.0001" step="0.0001" value={line.quantity} onChange={(event) => setLines((current) => current.map((item, i) => i === index ? { ...item, quantity: event.target.value } : item))} required /></label><label className="space-y-1 text-[11px] font-semibold text-slate-500">Unit price<input className={inputClass} type="number" min="0" step="0.0001" value={line.unit_price} onChange={(event) => setLines((current) => current.map((item, i) => i === index ? { ...item, unit_price: event.target.value } : item))} required /></label><label className="space-y-1 text-[11px] font-semibold text-slate-500">Tax %<input className={inputClass} type="number" min="0" max="100" step="0.0001" value={line.tax_rate} onChange={(event) => setLines((current) => current.map((item, i) => i === index ? { ...item, tax_rate: event.target.value } : item))} /></label><div className="flex items-end">{lines.length > 1 && <Button type="button" size="sm" variant="ghost" className="text-rose-600" onClick={() => setLines((current) => current.filter((_, i) => i !== index))}>Remove</Button>}</div></div>)}
        </div>
        {invoiceNotice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{invoiceNotice}</p>}{invoiceError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{invoiceError}</p>}
        <Button type="submit" disabled={createInvoiceMutation.isPending || !selectedOrganizationId}><Plus size={15} />{createInvoiceMutation.isPending ? 'Creating…' : 'Create draft invoice'}</Button>
      </form></CardContent></Card>}

      <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Invoice register</CardTitle><CardDescription>Outstanding balances are calculated from posted allocations. Currency balances are never combined.</CardDescription></CardHeader><CardContent className="space-y-4 p-4 sm:p-5">
        <div className="grid gap-2 sm:grid-cols-3"><input className={inputClass} value={invoiceSearch} onChange={(event) => setInvoiceSearch(event.target.value)} placeholder="Search invoice number…" aria-label="Search invoices" /><select className={inputClass} value={invoiceTypeFilter} onChange={(event) => setInvoiceTypeFilter(event.target.value)} aria-label="Filter invoice type"><option value="all">All invoice types</option><option value="customer">Customer invoices</option><option value="supplier">Supplier invoices</option></select><select className={inputClass} value={invoiceStatus} onChange={(event) => setInvoiceStatus(event.target.value)} aria-label="Filter invoice status"><option value="all">All statuses</option>{['draft', 'issued', 'partially_paid', 'paid', 'overdue', 'void'].map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}</select></div>
        {invoicesQuery.isPending ? <p className="py-8 text-center text-sm text-slate-500">Loading invoices…</p> : invoicesQuery.isError ? <p role="alert" className="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">{invoicesQuery.error instanceof Error ? invoicesQuery.error.message : 'Invoices could not be loaded.'}</p> : invoices.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center"><FileText className="mx-auto text-slate-300" size={28} /><p className="mt-3 text-sm font-semibold text-slate-700">No invoices found</p><p className="mt-1 text-xs text-slate-500">Create a customer or supplier invoice draft to get started.</p></div> : <div className="overflow-x-auto"><table className="w-full min-w-[780px] text-left text-sm"><thead className="text-[11px] uppercase tracking-wide text-slate-500"><tr className="border-b"><th className="px-3 py-3">Invoice</th><th className="px-3 py-3">Partner</th><th className="px-3 py-3">Due</th><th className="px-3 py-3 text-right">Total</th><th className="px-3 py-3 text-right">Outstanding</th><th className="px-3 py-3">Status</th><th className="px-3 py-3">Actions</th></tr></thead><tbody>{invoices.map((invoice) => <tr key={invoice.id} className="border-b border-slate-100 last:border-0"><td className="px-3 py-3"><p className="font-semibold text-slate-800">{invoice.invoice_number}</p><p className="text-[10px] uppercase text-slate-400">{invoice.invoice_type} · {invoice.currency}</p></td><td className="px-3 py-3 text-slate-700">{invoice.partner_name}</td><td className="px-3 py-3 text-slate-600">{invoice.due_date}</td><td className="px-3 py-3 text-right font-medium">{amount(invoice.total_amount, invoice.currency)}</td><td className="px-3 py-3 text-right font-semibold">{amount(invoice.outstanding_balance, invoice.currency)}</td><td className="px-3 py-3"><span className={`rounded-full px-2 py-1 text-[10px] font-bold uppercase ${statusClass(invoice.status)}`}>{invoice.status.replaceAll('_', ' ')}</span></td><td className="px-3 py-3"><div className="flex items-center gap-1">{canManage && invoice.status === 'draft' && <Button size="sm" onClick={() => issueMutation.mutate(invoice.id)} disabled={issueMutation.isPending}>Issue</Button>}<Button size="sm" variant="ghost" onClick={() => { setAuditInvoiceId(invoice.id); setAuditPaymentId('') }} title="View financial audit history"><History size={15} /></Button></div></td></tr>)}</tbody></table></div>}
      </CardContent></Card>
    </> : <>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Record a payment</CardTitle><CardDescription>Apply a full or partial payment to an open invoice. The payment currency matches the selected invoice in this form; the API also supports explicit FX allocations.</CardDescription></CardHeader><CardContent className="p-4 sm:p-5"><form className="space-y-3" onSubmit={submitPayment}>
          <label className="block space-y-1.5 text-xs font-semibold text-slate-600">Open invoice<select className={inputClass} value={selectedPaymentInvoiceId} onChange={(event) => { setSelectedPaymentInvoiceId(event.target.value); const selected = openInvoices.find((row) => row.id === event.target.value); setPaymentAmount(selected ? String(selected.outstanding_balance) : '') }} required><option value="">Select an open invoice…</option>{openInvoices.map((invoice) => <option key={invoice.id} value={invoice.id}>{invoice.invoice_number} · {invoice.partner_name} · {amount(invoice.outstanding_balance, invoice.currency)}</option>)}</select></label>
          {selectedPaymentInvoice && <div className="rounded-lg bg-slate-50 p-3 text-xs"><div className="flex justify-between"><span className="text-slate-500">Direction</span><strong>{selectedPaymentInvoice.invoice_type === 'customer' ? 'Incoming payment' : 'Outgoing payment'}</strong></div><div className="mt-1 flex justify-between"><span className="text-slate-500">Outstanding</span><strong>{amount(selectedPaymentInvoice.outstanding_balance, selectedPaymentInvoice.currency)}</strong></div><div className="mt-1 flex justify-between"><span className="text-slate-500">Currency</span><strong>{selectedPaymentInvoice.currency}</strong></div></div>}
          <label className="block space-y-1.5 text-xs font-semibold text-slate-600">Payment reference<input className={inputClass} value={paymentReference} onChange={(event) => setPaymentReference(event.target.value)} placeholder="BANK-PAY-2026-001" required /></label>
          <div className="grid gap-3 sm:grid-cols-2"><label className="space-y-1.5 text-xs font-semibold text-slate-600">Payment amount<input className={inputClass} type="number" min="0.01" step="0.01" value={paymentAmount} onChange={(event) => setPaymentAmount(event.target.value)} required /></label><label className="space-y-1.5 text-xs font-semibold text-slate-600">Payment date<input className={inputClass} type="date" value={paymentDate} onChange={(event) => setPaymentDate(event.target.value)} required /></label></div>
          <label className="block space-y-1.5 text-xs font-semibold text-slate-600">Payment method<select className={inputClass} value={paymentMethod} onChange={(event) => setPaymentMethod(event.target.value)}><option value="bank_transfer">Bank transfer</option><option value="cash">Cash</option><option value="card">Card</option><option value="cheque">Cheque</option><option value="other">Other</option></select></label>
          {paymentNotice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{paymentNotice}</p>}{paymentError && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{paymentError}</p>}
          <Button type="submit" disabled={createPaymentMutation.isPending || !selectedOrganizationId}><Wallet size={15} />{createPaymentMutation.isPending ? 'Recording…' : 'Record and allocate payment'}</Button>
        </form></CardContent></Card>

        <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Payment register</CardTitle><CardDescription>Payment records are retained. Corrections use a reversal with a reason instead of deleting history.</CardDescription></CardHeader><CardContent className="space-y-4 p-4 sm:p-5">
          <div className="grid gap-2 sm:grid-cols-3"><input className={inputClass} value={paymentSearch} onChange={(event) => setPaymentSearch(event.target.value)} placeholder="Search payment…" aria-label="Search payments" /><select className={inputClass} value={paymentTypeFilter} onChange={(event) => setPaymentTypeFilter(event.target.value)} aria-label="Filter payment direction"><option value="all">All directions</option><option value="incoming">Incoming</option><option value="outgoing">Outgoing</option></select><select className={inputClass} value={paymentStatus} onChange={(event) => setPaymentStatus(event.target.value)} aria-label="Filter payment status"><option value="all">All statuses</option><option value="posted">Posted</option><option value="reversed">Reversed</option></select></div>
          {paymentsQuery.isPending ? <p className="py-8 text-center text-sm text-slate-500">Loading payments…</p> : paymentsQuery.isError ? <p role="alert" className="rounded-lg bg-rose-50 p-4 text-sm text-rose-700">{paymentsQuery.error instanceof Error ? paymentsQuery.error.message : 'Payments could not be loaded.'}</p> : payments.length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center"><Wallet className="mx-auto text-slate-300" size={28} /><p className="mt-3 text-sm font-semibold text-slate-700">No payments recorded</p><p className="mt-1 text-xs text-slate-500">Recorded incoming and outgoing payments appear here.</p></div> : <div className="space-y-2">{payments.map((payment) => <div key={payment.id} className="rounded-xl border border-slate-200 p-3"><div className="flex flex-wrap items-start justify-between gap-2"><div className="flex items-start gap-2"><span className={`mt-0.5 rounded-lg p-2 ${payment.payment_type === 'incoming' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{payment.payment_type === 'incoming' ? <ArrowDownLeft size={16} /> : <ArrowUpRight size={16} />}</span><div><p className="text-sm font-semibold text-slate-800">{payment.payment_reference}</p><p className="mt-0.5 text-[11px] text-slate-500">{payment.payment_date} · {payment.payment_method.replaceAll('_', ' ')}</p></div></div><div className="text-right"><p className="text-sm font-bold text-slate-900">{amount(payment.amount, payment.currency)}</p><span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${statusClass(payment.status)}`}>{payment.status}</span></div></div><div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2"><p className="text-[11px] text-slate-500">Allocated {amount(payment.allocated_amount, payment.currency)} · Unallocated {amount(payment.unallocated_amount, payment.currency)} · {payment.allocations.length} invoice(s)</p><div className="flex items-center gap-1"><Button size="sm" variant="ghost" onClick={() => { setAuditPaymentId(payment.id); setAuditInvoiceId('') }} title="View payment audit"><History size={14} /></Button>{canReverse && canManage && payment.status === 'posted' && <Button size="sm" variant="outline" className="text-rose-700" onClick={() => { setReversingPayment(payment.id); setReversalReason('') }}>Reverse</Button>}</div></div>{reversingPayment === payment.id && <div className="mt-3 space-y-2 rounded-lg bg-rose-50 p-3"><label className="block text-xs font-semibold text-rose-800">Reason for reversal<input className={`${inputClass} mt-1 border-rose-200`} value={reversalReason} onChange={(event) => setReversalReason(event.target.value)} minLength={3} placeholder="Explain why this payment is being reversed" /></label><div className="flex gap-2"><Button size="sm" className="bg-rose-700 hover:bg-rose-800" disabled={reverseMutation.isPending || reversalReason.trim().length < 3} onClick={() => reverseMutation.mutate()}>Confirm reversal</Button><Button size="sm" variant="ghost" onClick={() => setReversingPayment('')}>Cancel</Button></div></div>}</div>)}</div>}
        </CardContent></Card>
      </div>
      {canManage && <Card className="rounded-2xl border-slate-200 shadow-sm"><CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Reconcile an unapplied payment balance</CardTitle><CardDescription>Apply the remaining amount of an existing posted payment to another open invoice. This form currently offers same-currency allocations; the API requires an explicit exchange-rate snapshot for cross-currency allocations.</CardDescription></CardHeader><CardContent className="p-4 sm:p-5"><form className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4" onSubmit={submitReconciliation}>
        <label className="space-y-1.5 text-xs font-semibold text-slate-600">Posted payment with remaining balance<select className={inputClass} value={reconcilePaymentId} onChange={(event) => { const id = event.target.value; setReconcilePaymentId(id); setReconcileInvoiceId(''); const selected = payments.find((payment) => payment.id === id); setReconcileAmount(selected ? String(selected.unallocated_amount) : '') }} required><option value="">Select payment…</option>{payments.filter((payment) => payment.status === 'posted' && Number(payment.unallocated_amount) > 0).map((payment) => <option key={payment.id} value={payment.id}>{payment.payment_reference} · {amount(payment.unallocated_amount, payment.currency)} remaining</option>)}</select></label>
        <label className="space-y-1.5 text-xs font-semibold text-slate-600">Compatible open invoice<select className={inputClass} value={reconcileInvoiceId} onChange={(event) => { setReconcileInvoiceId(event.target.value); const selected = reconcileInvoices.find((invoice) => invoice.id === event.target.value); if (selectedReconcilePayment) setReconcileAmount(selected ? String(Math.min(Number(selected.outstanding_balance), Number(selectedReconcilePayment.unallocated_amount))) : '') }} disabled={!selectedReconcilePayment} required><option value="">Select invoice…</option>{reconcileInvoices.map((invoice) => <option key={invoice.id} value={invoice.id}>{invoice.invoice_number} · {amount(invoice.outstanding_balance, invoice.currency)} due</option>)}</select></label>
        <label className="space-y-1.5 text-xs font-semibold text-slate-600">Amount to allocate<input className={inputClass} type="number" min="0.01" step="0.01" value={reconcileAmount} onChange={(event) => setReconcileAmount(event.target.value)} required /></label>
        <div className="flex items-end"><Button type="submit" disabled={reconcileMutation.isPending || !selectedReconcilePayment || !selectedReconcileInvoice}><Wallet size={14} />{reconcileMutation.isPending ? 'Allocating…' : 'Allocate balance'}</Button></div>
      </form></CardContent></Card>}
    </>}

    {(auditInvoiceId || auditPaymentId) && <Card className="rounded-2xl border-sky-200 shadow-sm"><CardHeader className="flex flex-row items-start justify-between border-b border-slate-100"><div><CardTitle className="text-base">Financial audit history</CardTitle><CardDescription>Immutable events associated with this financial record.</CardDescription></div></CardHeader><CardContent className="p-4 sm:p-5">{auditLoading ? <p className="text-sm text-slate-500">Loading audit history…</p> : auditError ? <p role="alert" className="text-sm text-rose-700">Audit history could not be loaded.</p> : <AuditTrail events={auditEvents ?? []} />}</CardContent></Card>}
    {!selectedOrganizationId && <p className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800"><AlertCircle className="mr-2 inline" size={15} />Select an organization to manage financial records.</p>}
    <p className="text-[11px] leading-5 text-slate-400">Signed in as {auth?.user.email}. Invoice/payment operations are authorized by the backend for the active organization. Currency balances are shown separately; no cross-currency totals are combined.</p>
  </div>
}
