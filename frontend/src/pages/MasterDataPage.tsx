import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, type Resolver } from 'react-hook-form'
import { z } from 'zod'
import { AlertCircle, Check, ChevronDown, CirclePlus, LoaderCircle, Pencil, Search, ShieldCheck, Users, Boxes, Building2, Warehouse, RefreshCw, X } from 'lucide-react'
import { EmptyState } from '@/components/shared/EmptyState'
import { ApiError } from '@/features/auth/api'
import { createMasterData, listMasterData, updateMasterData, type MasterDataResource } from '@/features/master-data/api'
import type { MasterDataRecord } from '@/features/master-data/types'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { useOutletContext } from 'react-router-dom'

type FieldType = 'text' | 'email' | 'number'
interface FieldConfig {
  name: string
  label: string
  type: FieldType
  required?: boolean
  placeholder?: string
  defaultValue?: string
  help?: string
  integer?: boolean
}
interface ColumnConfig { key: string; label: string }
interface MasterDataConfig {
  resource: MasterDataResource
  title: string
  singular: string
  description: string
  icon: typeof Users
  fields: FieldConfig[]
  columns: ColumnConfig[]
}
type FormValues = Record<string, string>
type FormPayload = Record<string, string | number | boolean | null>

const configs: Record<'customers' | 'suppliers' | 'products' | 'locations', MasterDataConfig> = {
  customers: {
    resource: 'customers', title: 'Customers', singular: 'customer', description: 'Manage customer contacts, billing details, countries, and payment terms for export orders.', icon: Users,
    fields: [
      { name: 'customer_code', label: 'Customer code', type: 'text', placeholder: 'e.g. CUST-0001' },
      { name: 'name', label: 'Customer name', type: 'text', required: true, placeholder: 'Customer or trading name' },
      { name: 'company_name', label: 'Company name', type: 'text', placeholder: 'Registered company name' },
      { name: 'contact_person', label: 'Contact person', type: 'text', placeholder: 'Full name' },
      { name: 'email', label: 'Email', type: 'email', placeholder: 'buyer@example.com' },
      { name: 'phone', label: 'Phone', type: 'text', placeholder: '+49 ...' },
      { name: 'country', label: 'Country code', type: 'text', placeholder: 'DE', help: 'Use the two-letter country code.' },
      { name: 'payment_terms_days', label: 'Payment terms (days)', type: 'number', integer: true, defaultValue: '0' },
      { name: 'currency', label: 'Preferred currency', type: 'text', required: true, defaultValue: 'EUR' },
    ],
    columns: [{ key: 'customer_code', label: 'Code' }, { key: 'name', label: 'Customer' }, { key: 'company_name', label: 'Company' }, { key: 'email', label: 'Email' }, { key: 'country', label: 'Country' }],
  },
  suppliers: {
    resource: 'suppliers', title: 'Suppliers', singular: 'supplier', description: 'Maintain supplier contacts, origin countries, and purchasing terms for imports.', icon: Building2,
    fields: [
      { name: 'supplier_code', label: 'Supplier code', type: 'text', placeholder: 'e.g. SUP-0001' },
      { name: 'name', label: 'Supplier name', type: 'text', required: true, placeholder: 'Supplier or trading name' },
      { name: 'company_name', label: 'Company name', type: 'text', placeholder: 'Registered company name' },
      { name: 'contact_person', label: 'Contact person', type: 'text', placeholder: 'Full name' },
      { name: 'email', label: 'Email', type: 'email', placeholder: 'supplier@example.com' },
      { name: 'phone', label: 'Phone', type: 'text', placeholder: '+49 ...' },
      { name: 'country', label: 'Country code', type: 'text', placeholder: 'NL', help: 'Use the two-letter country code.' },
      { name: 'payment_terms_days', label: 'Payment terms (days)', type: 'number', integer: true, defaultValue: '0' },
      { name: 'currency', label: 'Preferred currency', type: 'text', required: true, defaultValue: 'EUR' },
    ],
    columns: [{ key: 'supplier_code', label: 'Code' }, { key: 'name', label: 'Supplier' }, { key: 'company_name', label: 'Company' }, { key: 'email', label: 'Email' }, { key: 'country', label: 'Country' }],
  },
  products: {
    resource: 'products', title: 'Products', singular: 'product', description: 'Maintain product SKUs, units, purchase and selling prices, currency, and reorder thresholds.', icon: Boxes,
    fields: [
      { name: 'sku', label: 'SKU / product code', type: 'text', required: true, placeholder: 'e.g. SKU-001' },
      { name: 'name', label: 'Product name', type: 'text', required: true, placeholder: 'Product name' },
      { name: 'category', label: 'Category', type: 'text', placeholder: 'e.g. Food ingredients' },
      { name: 'unit_of_measure', label: 'Unit of measure', type: 'text', required: true, defaultValue: 'pcs', placeholder: 'pcs, kg, box...' },
      { name: 'purchase_price', label: 'Purchase price', type: 'number', defaultValue: '0' },
      { name: 'selling_price', label: 'Selling price', type: 'number', defaultValue: '0' },
      { name: 'currency', label: 'Currency', type: 'text', required: true, defaultValue: 'EUR' },
      { name: 'reorder_threshold', label: 'Reorder threshold', type: 'number', defaultValue: '0' },
      { name: 'description', label: 'Description', type: 'text', placeholder: 'Optional product details' },
    ],
    columns: [{ key: 'sku', label: 'SKU' }, { key: 'name', label: 'Product' }, { key: 'category', label: 'Category' }, { key: 'unit_of_measure', label: 'Unit' }, { key: 'purchase_price', label: 'Purchase' }, { key: 'selling_price', label: 'Selling' }, { key: 'currency', label: 'Currency' }],
  },
  locations: {
    resource: 'inventory/locations', title: 'Inventory locations', singular: 'location', description: 'Define warehouses and storage locations before recording stock movements.', icon: Warehouse,
    fields: [
      { name: 'code', label: 'Location code', type: 'text', required: true, placeholder: 'e.g. WH-01' },
      { name: 'name', label: 'Location name', type: 'text', required: true, placeholder: 'Main warehouse' },
      { name: 'address', label: 'Address', type: 'text', placeholder: 'Street, city, country' },
      { name: 'description', label: 'Description', type: 'text', placeholder: 'Optional storage details' },
    ],
    columns: [{ key: 'code', label: 'Code' }, { key: 'name', label: 'Location' }, { key: 'address', label: 'Address' }, { key: 'description', label: 'Description' }],
  },
}

function makeSchema(fields: FieldConfig[]) {
  const shape: Record<string, z.ZodType<string>> = {}
  for (const field of fields) {
    let rule: z.ZodType<string> = z.string()
    if (field.type === 'email') rule = z.string().refine((value) => value === '' || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value), 'Enter a valid email address.')
    if (field.type === 'number') rule = z.string().refine((value) => value === '' || ((field.integer ? /^\d+$/.test(value) : /^\d+(\.\d{1,4})?$/.test(value)) && Number(value) >= 0), field.integer ? 'Enter a non-negative whole number.' : 'Enter a non-negative number with up to 4 decimal places.')
    if (field.required) rule = rule.refine((value) => value.trim().length >= 2, `${field.label} is required.`)
    shape[field.name] = rule
  }
  return z.object(shape) as z.ZodType<FormValues>
}

function getRecordValue(record: MasterDataRecord, key: string): string {
  const value = record[key]
  return value === null || value === undefined ? '' : String(value)
}

function asPayload(values: FormValues, fields: FieldConfig[], mode: 'create' | 'update'): FormPayload {
  const payload: FormPayload = {}
  for (const field of fields) {
    const value = (values[field.name] ?? '').trim()
    if (field.type === 'number') {
      if (value === '') continue
      payload[field.name] = Number(value)
      continue
    }
    if (value === '' && !field.required) {
      if (mode === 'update') payload[field.name] = null
      continue
    }
    payload[field.name] = value
  }
  return payload
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : 'The request could not be completed.'
}

export function MasterDataPage({ kind }: { kind: 'customers' | 'suppliers' | 'products' | 'locations' }) {
  const config = configs[kind]
  const Icon = config.icon
  const queryClient = useQueryClient()
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const [search, setSearch] = useState('')
  const [active, setActive] = useState<boolean | 'all'>('all')
  const [formOpen, setFormOpen] = useState(false)
  const [editingRecord, setEditingRecord] = useState<MasterDataRecord | null>(null)
  const [requestError, setRequestError] = useState('')
  const canManage = selectedOrganization?.role === 'organization_owner' || selectedOrganization?.role === 'administrator'
  const schema = useMemo(() => makeSchema(config.fields), [config.fields])
  const form = useForm<FormValues>({ resolver: zodResolver(schema as never) as unknown as Resolver<FormValues>, defaultValues: Object.fromEntries(config.fields.map((field) => [field.name, field.defaultValue ?? ''])) as FormValues })

  const recordsQuery = useQuery({
    queryKey: ['master-data', config.resource, selectedOrganizationId, search, active],
    queryFn: () => listMasterData<MasterDataRecord>({ resource: config.resource, organizationId: selectedOrganizationId, search, active }),
    enabled: Boolean(selectedOrganizationId),
  })

  const saveMutation = useMutation({
    mutationFn: (input: { values: FormValues; record: MasterDataRecord | null }) => input.record
      ? updateMasterData<MasterDataRecord>(config.resource, selectedOrganizationId, input.record.id, asPayload(input.values, config.fields, 'update'))
      : createMasterData<MasterDataRecord>(config.resource, selectedOrganizationId, asPayload(input.values, config.fields, 'create')),
    onSuccess: async () => {
      setRequestError('')
      setFormOpen(false)
      setEditingRecord(null)
      form.reset(Object.fromEntries(config.fields.map((field) => [field.name, field.defaultValue ?? ''])) as FormValues)
      await queryClient.invalidateQueries({ queryKey: ['master-data', config.resource, selectedOrganizationId] })
    },
    onError: (error) => setRequestError(errorMessage(error)),
  })

  const statusMutation = useMutation({
    mutationFn: (record: MasterDataRecord) => updateMasterData<MasterDataRecord>(config.resource, selectedOrganizationId, record.id, { is_active: !record.is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['master-data', config.resource, selectedOrganizationId] }),
    onError: (error) => setRequestError(errorMessage(error)),
  })

  function openCreate() {
    setEditingRecord(null)
    setRequestError('')
    form.reset(Object.fromEntries(config.fields.map((field) => [field.name, field.defaultValue ?? ''])) as FormValues)
    setFormOpen(true)
  }

  function openEdit(record: MasterDataRecord) {
    setEditingRecord(record)
    setRequestError('')
    form.reset(Object.fromEntries(config.fields.map((field) => [field.name, getRecordValue(record, field.name)])) as FormValues)
    setFormOpen(true)
  }

  if (!selectedOrganizationId) {
    return <EmptyState icon={Icon} title="Select an organization" description="Choose or create an organization before managing master data." />
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
        <div><div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700"><Icon size={15} /> Master data</div><h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">{config.title}</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">{config.description}</p></div>
        {canManage && <button type="button" onClick={openCreate} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white shadow-sm hover:bg-slate-700"><CirclePlus size={16} /> Add {config.singular}</button>}
      </div>

      {formOpen && canManage && <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
        <div className="mb-5 flex items-start justify-between gap-3"><div><h3 className="text-base font-bold text-slate-900">{editingRecord ? `Edit ${config.singular}` : `Add ${config.singular}`}</h3><p className="mt-1 text-xs text-slate-500">Fields marked required must be completed. Records are scoped to {selectedOrganization?.organization_name ?? 'the current organization'}.</p></div><button type="button" onClick={() => { setFormOpen(false); setEditingRecord(null); }} aria-label="Close form" className="rounded-lg p-2 text-slate-500 hover:bg-slate-100"><X size={17} /></button></div>
        <form className="space-y-5" onSubmit={form.handleSubmit((values) => saveMutation.mutate({ values, record: editingRecord }))}>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {config.fields.map((field) => <label key={field.name} className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">{field.label}{field.required && <span className="ml-1 text-rose-600">*</span>}</span><input {...form.register(field.name)} type={field.type} min={field.type === 'number' ? '0' : undefined} step={field.type === 'number' ? (field.integer ? '1' : '0.0001') : undefined} placeholder={field.placeholder} aria-invalid={Boolean(form.formState.errors[field.name])} className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-sky-500 focus:ring-2 focus:ring-sky-100 aria-[invalid=true]:border-rose-400" />{field.help && <span className="mt-1 block text-[11px] text-slate-500">{field.help}</span>}{form.formState.errors[field.name] && <span className="mt-1 block text-xs text-rose-600">{String(form.formState.errors[field.name]?.message ?? 'Invalid value')}</span>}</label>)}
          </div>
          {requestError && <p role="alert" className="flex items-start gap-2 rounded-lg bg-rose-50 px-3 py-2.5 text-sm text-rose-700"><AlertCircle size={16} className="mt-0.5 shrink-0" />{requestError}</p>}
          <div className="flex flex-col-reverse gap-2 border-t border-slate-100 pt-4 sm:flex-row sm:justify-end"><button type="button" onClick={() => { setFormOpen(false); setEditingRecord(null); }} className="h-10 rounded-lg border border-slate-200 px-4 text-sm font-semibold text-slate-600 hover:bg-slate-50">Cancel</button><button type="submit" disabled={saveMutation.isPending} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-sky-600 px-4 text-sm font-semibold text-white hover:bg-sky-700 disabled:opacity-60">{saveMutation.isPending ? <LoaderCircle size={16} className="animate-spin" /> : <Check size={16} />}{saveMutation.isPending ? 'Saving…' : editingRecord ? 'Save changes' : `Create ${config.singular}`}</button></div>
        </form>
      </section>}

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-4 sm:flex-row sm:items-center sm:justify-between sm:p-5">
          <div><h3 className="font-semibold text-slate-900">{config.title} directory</h3><p className="mt-1 text-xs text-slate-500">{recordsQuery.data?.total ?? 0} record{recordsQuery.data?.total === 1 ? '' : 's'} in this view</p></div>
          <div className="flex flex-col gap-2 sm:flex-row"><label className="flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-slate-400 focus-within:border-sky-400"><Search size={14} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={`Search ${config.title.toLowerCase()}…`} aria-label={`Search ${config.title}`} className="w-full bg-transparent text-sm text-slate-700 outline-none sm:w-52" /></label><label className="relative flex h-9 items-center gap-2 rounded-lg border border-slate-200 px-3 text-xs text-slate-600"><select aria-label="Filter record status" value={active === 'all' ? 'all' : String(active)} onChange={(event) => setActive(event.target.value === 'all' ? 'all' : event.target.value === 'true')} className="appearance-none bg-transparent pr-4 outline-none"><option value="all">All statuses</option><option value="true">Active</option><option value="false">Inactive</option></select><ChevronDown size={13} className="pointer-events-none absolute right-2 text-slate-400" /></label><button type="button" aria-label="Refresh records" onClick={() => void recordsQuery.refetch()} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-slate-200 px-3 text-xs font-semibold text-slate-600 hover:bg-slate-50"><RefreshCw size={13} />Refresh</button></div>
        </div>
        {recordsQuery.isPending ? <div className="space-y-3 p-5">{[0, 1, 2, 3].map((item) => <div key={item} className="h-11 animate-pulse rounded-lg bg-slate-100" />)}</div>
          : recordsQuery.isError ? <div className="m-5 rounded-xl border border-rose-200 bg-rose-50 p-4"><p className="flex items-center gap-2 text-sm font-semibold text-rose-800"><AlertCircle size={16} />Could not load {config.title.toLowerCase()}</p><p className="mt-1 text-sm text-rose-700">{errorMessage(recordsQuery.error)}</p><button type="button" onClick={() => void recordsQuery.refetch()} className="mt-3 text-sm font-semibold text-rose-800 underline">Try again</button></div>
          : !recordsQuery.data?.items.length ? <div className="p-5"><EmptyState icon={Icon} title={`No ${config.title.toLowerCase()} found`} description={search ? 'Try another search term or change the status filter.' : `Add your first ${config.singular} to start building your organization's master data.`} action={canManage && !search ? <button type="button" onClick={openCreate} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white">Add {config.singular}</button> : undefined} /></div>
          : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-50 text-[11px] font-bold uppercase tracking-wide text-slate-500"><tr>{config.columns.map((column) => <th key={column.key} className="px-5 py-3">{column.label}</th>)}<th className="px-5 py-3">Status</th>{canManage && <th className="px-5 py-3 text-right">Actions</th>}</tr></thead><tbody className="divide-y divide-slate-100">{recordsQuery.data.items.map((record) => <tr key={record.id} className="hover:bg-slate-50/70">{config.columns.map((column) => <td key={column.key} className="max-w-56 truncate px-5 py-3.5 text-slate-600">{getRecordValue(record, column.key) || <span className="text-slate-300">—</span>}</td>)}<td className="px-5 py-3.5"><span className={`inline-flex items-center rounded-full px-2.5 py-1 text-[11px] font-semibold ${record.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>{record.is_active ? 'Active' : 'Inactive'}</span></td>{canManage && <td className="px-5 py-3.5"><div className="flex justify-end gap-1"><button type="button" onClick={() => openEdit(record)} className="inline-flex items-center gap-1 rounded-md px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100"><Pencil size={13} />Edit</button><button type="button" disabled={statusMutation.isPending} onClick={() => { setRequestError(''); statusMutation.mutate(record); }} className="rounded-md px-2.5 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-100 disabled:opacity-50">{record.is_active ? 'Deactivate' : 'Activate'}</button></div></td>}</tr>)}</tbody></table></div>}
        {statusMutation.isError && <p role="alert" className="border-t border-rose-100 px-5 py-3 text-sm text-rose-700">{errorMessage(statusMutation.error)}</p>}
      </section>
      <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-xs leading-5 text-slate-500"><ShieldCheck size={16} className="mt-0.5 shrink-0 text-slate-400" /><p>Records are organization-scoped and changes are validated by the API. Deactivation preserves historical references; permanent deletion is intentionally not offered for master data used by future trade records.</p></div>
    </div>
  )
}
