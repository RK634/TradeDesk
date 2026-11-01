import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, type Resolver } from 'react-hook-form'
import { z } from 'zod'
import { AlertCircle, ArrowDownToLine, ArrowUpFromLine, ClipboardList, History, LoaderCircle, Package, RefreshCw, ShieldCheck, Warehouse } from 'lucide-react'
import { useOutletContext } from 'react-router-dom'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { EmptyState } from '@/components/shared/EmptyState'
import { ApiError } from '@/features/auth/api'
import { createInventoryMovement, listInventoryBalances, listInventoryMovements, listLocations, listProducts } from '@/features/master-data/api'
import type { InventoryMovementType } from '@/features/master-data/types'

const movementSchema = z.object({
  product_id: z.string().uuid('Choose a product.'),
  location_id: z.string().uuid('Choose a location.'),
  movement_type: z.enum(['goods_received', 'goods_dispatched', 'reservation', 'reservation_release', 'adjustment_increase', 'adjustment_decrease', 'return']),
  quantity: z.string().refine((value) => /^\d+(\.\d{1,4})?$/.test(value) && Number(value) > 0, 'Enter a quantity greater than zero (up to 4 decimals).'),
  notes: z.string().max(1000, 'Notes must be 1,000 characters or fewer.'),
})
type MovementFormValues = z.infer<typeof movementSchema>

const MOVEMENT_LABELS: Record<InventoryMovementType, string> = {
  goods_received: 'Goods received',
  goods_dispatched: 'Goods dispatched',
  reservation: 'Reserve stock',
  reservation_release: 'Release reservation',
  adjustment_increase: 'Adjustment — increase',
  adjustment_decrease: 'Adjustment — decrease',
  return: 'Return received',
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return error instanceof Error ? error.message : 'The request could not be completed.'
}
function numberText(value: string | number): string {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 4 })
}
function dateText(value: string): string {
  return new Date(value).toLocaleString()
}

export function InventoryPage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const queryClient = useQueryClient()
  const [requestError, setRequestError] = useState('')
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID())
  const role = selectedOrganization?.role
  const canAdministerStock = role === 'organization_owner' || role === 'administrator'
  const canOperateStock = canAdministerStock || role === 'operations_staff'
  const movementOptions = useMemo(() => {
    const all: InventoryMovementType[] = ['goods_received', 'goods_dispatched', 'reservation', 'reservation_release', 'adjustment_increase', 'adjustment_decrease', 'return']
    return canAdministerStock ? all : role === 'operations_staff' ? ['goods_received', 'goods_dispatched'] as InventoryMovementType[] : []
  }, [canAdministerStock, role])

  const productsQuery = useQuery({ queryKey: ['master-data', 'products', selectedOrganizationId, 'active'], queryFn: () => listProducts(selectedOrganizationId, '', true), enabled: Boolean(selectedOrganizationId) })
  const locationsQuery = useQuery({ queryKey: ['master-data', 'locations', selectedOrganizationId, 'active'], queryFn: () => listLocations(selectedOrganizationId, true), enabled: Boolean(selectedOrganizationId) })
  const balancesQuery = useQuery({ queryKey: ['inventory', 'balances', selectedOrganizationId], queryFn: () => listInventoryBalances(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) })
  const lowStockQuery = useQuery({ queryKey: ['inventory', 'low-stock', selectedOrganizationId], queryFn: () => listInventoryBalances(selectedOrganizationId, true), enabled: Boolean(selectedOrganizationId) })
  const movementsQuery = useQuery({ queryKey: ['inventory', 'movements', selectedOrganizationId], queryFn: () => listInventoryMovements(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) })

  const form = useForm<MovementFormValues>({
    resolver: zodResolver(movementSchema) as Resolver<MovementFormValues>,
    defaultValues: { product_id: '', location_id: '', movement_type: 'goods_received', quantity: '', notes: '' },
  })

  const movementMutation = useMutation({
    mutationFn: (values: MovementFormValues) => createInventoryMovement({
      organization_id: selectedOrganizationId,
      product_id: values.product_id,
      location_id: values.location_id,
      movement_type: values.movement_type,
      quantity: values.quantity,
      idempotency_key: idempotencyKey,
      ...(values.notes.trim() ? { notes: values.notes.trim() } : {}),
    }),
    onSuccess: async () => {
      setRequestError('')
      setIdempotencyKey(crypto.randomUUID())
      form.reset({ product_id: productsQuery.data?.items[0]?.id ?? '', location_id: locationsQuery.data?.items[0]?.id ?? '', movement_type: 'goods_received', quantity: '', notes: '' })
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['inventory', 'balances', selectedOrganizationId] }),
        queryClient.invalidateQueries({ queryKey: ['inventory', 'low-stock', selectedOrganizationId] }),
        queryClient.invalidateQueries({ queryKey: ['inventory', 'movements', selectedOrganizationId] }),
        queryClient.invalidateQueries({ queryKey: ['dashboard'] }),
      ])
    },
    onError: (error) => setRequestError(errorMessage(error)),
  })

  if (!selectedOrganizationId) return <EmptyState icon={Warehouse} title="Select an organization" description="Choose or create an organization before reviewing stock." />

  const balanceRows = balancesQuery.data?.items ?? []
  const allProducts = productsQuery.data?.items ?? []
  const allLocations = locationsQuery.data?.items ?? []
  const activeProducts = allProducts.filter((product) => product.is_active)
  const activeLocations = allLocations.filter((location) => location.is_active)
  const productLabels = new Map<string, string>(allProducts.map((product): [string, string] => [product.id, `${product.sku} — ${product.name}`]))
  const locationLabels = new Map<string, string>(allLocations.map((location): [string, string] => [location.id, `${location.code} — ${location.name}`]))
  const lowStockCount = lowStockQuery.data?.total ?? 0
  const latestMovements = movementsQuery.data?.items ?? []

  return <div className="space-y-6">
    <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700"><Package size={15} /> Partners & stock</div><h2 className="mt-2 text-2xl font-bold tracking-tight text-slate-900">Inventory</h2><p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">View stock by product and location. Every quantity change is recorded as a ledger movement with the actor, source, and resulting balance.</p></div><button type="button" onClick={() => { void Promise.all([balancesQuery.refetch(), movementsQuery.refetch()]) }} className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50"><RefreshCw size={15} /> Refresh stock</button></div>

    <div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center justify-between text-xs font-medium text-slate-500"><span>Tracked balances</span><ClipboardList size={16} /></div><p className="mt-3 text-2xl font-bold text-slate-900">{balancesQuery.isPending ? '—' : balancesQuery.data?.total ?? 0}</p><p className="mt-1 text-xs text-slate-500">Product and location combinations</p></div><div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center justify-between text-xs font-medium text-slate-500"><span>Low-stock balances</span><AlertCircle size={16} /></div><p className="mt-3 text-2xl font-bold text-amber-700">{balancesQuery.isPending ? '—' : lowStockCount}</p><p className="mt-1 text-xs text-slate-500">Available quantity at or below reorder threshold</p></div><div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><div className="flex items-center justify-between text-xs font-medium text-slate-500"><span>Recent movements</span><History size={16} /></div><p className="mt-3 text-2xl font-bold text-slate-900">{movementsQuery.isPending ? '—' : movementsQuery.data?.total ?? 0}</p><p className="mt-1 text-xs text-slate-500">Latest 50 shown in the ledger</p></div></div>

    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(340px,0.72fr)]">
      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-100 px-5 py-4"><h3 className="font-semibold text-slate-900">Stock by location</h3><p className="mt-1 text-xs text-slate-500">On-hand, reserved, and available quantities</p></div>
        {balancesQuery.isPending ? <div className="space-y-3 p-5">{[0, 1, 2, 3].map((item) => <div key={item} className="h-10 animate-pulse rounded-lg bg-slate-100" />)}</div>
          : balancesQuery.isError ? <div className="m-5 rounded-xl bg-rose-50 p-4 text-sm text-rose-700"><p>{errorMessage(balancesQuery.error)}</p><button type="button" className="mt-2 font-semibold underline" onClick={() => void balancesQuery.refetch()}>Try again</button></div>
          : balanceRows.length === 0 ? <div className="p-5"><EmptyState icon={Package} title="No stock balances yet" description="Create a product and a location, then record a receipt to initialize its stock balance." /></div>
          : <div className="overflow-x-auto"><table className="w-full min-w-[680px] text-left text-sm"><thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3">Product</th><th className="px-4 py-3">Location</th><th className="px-4 py-3 text-right">On hand</th><th className="px-4 py-3 text-right">Reserved</th><th className="px-4 py-3 text-right">Available</th></tr></thead><tbody className="divide-y divide-slate-100">{balanceRows.map((row) => <tr key={row.id} className="hover:bg-slate-50/70"><td className="px-4 py-3"><p className="font-semibold text-slate-800">{row.product_name}</p><p className="mt-0.5 text-[11px] text-slate-500">{row.product_sku}</p>{row.is_low_stock && <span className="mt-1 inline-flex rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-semibold text-amber-800">Low stock</span>}</td><td className="px-4 py-3 text-slate-600"><p>{row.location_name}</p><p className="mt-0.5 text-[11px] text-slate-500">{row.location_code}</p></td><td className="px-4 py-3 text-right tabular-nums text-slate-700">{numberText(row.quantity_on_hand)}</td><td className="px-4 py-3 text-right tabular-nums text-slate-700">{numberText(row.reserved_quantity)}</td><td className="px-4 py-3 text-right tabular-nums font-semibold text-slate-900">{numberText(row.available_quantity)}</td></tr>)}</tbody></table></div>}
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="mb-5"><div className="flex items-center gap-2"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-sky-50 text-sky-700"><ArrowDownToLine size={18} /></span><div><h3 className="font-semibold text-slate-900">Record a stock movement</h3><p className="mt-1 text-xs text-slate-500">Posts a durable ledger entry</p></div></div></div>
        {!canOperateStock || movementOptions.length === 0 ? <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-800">Your current role can view inventory but cannot post stock movements.</div>
          : activeProducts.length === 0 || activeLocations.length === 0 ? <EmptyState icon={Warehouse} title="Master data required" description="Add at least one active product and one active inventory location before recording a stock movement." />
          : <form className="space-y-4" onSubmit={form.handleSubmit((values) => { setRequestError(''); movementMutation.mutate(values) })}>
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Product</span><select {...form.register('product_id')} className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"><option value="">Choose a product</option>{activeProducts.map((product) => <option key={product.id} value={product.id}>{product.sku} — {product.name}</option>)}</select>{form.formState.errors.product_id && <span className="mt-1 block text-xs text-rose-600">{form.formState.errors.product_id.message}</span>}</label>
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Inventory location</span><select {...form.register('location_id')} className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"><option value="">Choose a location</option>{activeLocations.map((location) => <option key={location.id} value={location.id}>{location.code} — {location.name}</option>)}</select>{form.formState.errors.location_id && <span className="mt-1 block text-xs text-rose-600">{form.formState.errors.location_id.message}</span>}</label>
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Movement type</span><select {...form.register('movement_type')} className="h-10 w-full rounded-lg border border-slate-200 bg-white px-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100">{movementOptions.map((option) => <option key={option} value={option}>{MOVEMENT_LABELS[option]}</option>)}</select></label>
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Quantity</span><input {...form.register('quantity')} type="number" min="0.0001" step="0.0001" placeholder="0.0000" className="h-10 w-full rounded-lg border border-slate-200 px-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" />{form.formState.errors.quantity && <span className="mt-1 block text-xs text-rose-600">{form.formState.errors.quantity.message}</span>}</label>
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Notes (optional)</span><textarea {...form.register('notes')} rows={2} placeholder="Reason or context for this stock movement" className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100" /></label>
            {requestError && <p role="alert" className="flex items-start gap-2 rounded-lg bg-rose-50 p-3 text-sm text-rose-700"><AlertCircle size={16} className="mt-0.5 shrink-0" />{requestError}</p>}
            <button type="submit" disabled={movementMutation.isPending} className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-4 text-sm font-semibold text-white hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-60">{movementMutation.isPending ? <LoaderCircle size={16} className="animate-spin" /> : <ArrowUpFromLine size={16} />}{movementMutation.isPending ? 'Posting movement…' : 'Post movement'}</button>
            <p className="text-[11px] leading-5 text-slate-500">The API checks available stock, locks the product row on PostgreSQL, and uses this request's idempotency key so a retry won't post the same movement twice.</p>
          </form>}
      </section>
    </div>

    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><div className="border-b border-slate-100 px-5 py-4"><h3 className="font-semibold text-slate-900">Recent inventory ledger</h3><p className="mt-1 text-xs text-slate-500">Append-only record of stock and reservation changes</p></div>{movementsQuery.isPending ? <div className="space-y-3 p-5">{[0, 1, 2].map((item) => <div key={item} className="h-10 animate-pulse rounded-lg bg-slate-100" />)}</div> : movementsQuery.isError ? <p className="p-5 text-sm text-rose-700">{errorMessage(movementsQuery.error)}</p> : latestMovements.length === 0 ? <div className="p-5"><EmptyState icon={History} title="No ledger movements" description="Every receipt, dispatch, reservation, and adjustment will appear here after posting." /></div> : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Time</th><th className="px-5 py-3">Movement</th><th className="px-5 py-3 text-right">On-hand change</th><th className="px-5 py-3 text-right">Reserved change</th><th className="px-5 py-3">Reference / notes</th></tr></thead><tbody className="divide-y divide-slate-100">{latestMovements.map((movement) => <tr key={movement.id}><td className="whitespace-nowrap px-5 py-3.5 text-xs text-slate-500">{dateText(movement.created_at)}</td><td className="px-5 py-3.5"><span className="font-semibold text-slate-800">{MOVEMENT_LABELS[movement.movement_type]}</span><p className="mt-1 text-[10px] text-slate-500">{productLabels.get(movement.product_id) ?? movement.product_id.slice(0, 8)} · {locationLabels.get(movement.location_id) ?? movement.location_id.slice(0, 8)}</p></td><td className={`px-5 py-3.5 text-right font-semibold tabular-nums ${Number(movement.quantity_delta) < 0 ? 'text-rose-700' : Number(movement.quantity_delta) > 0 ? 'text-emerald-700' : 'text-slate-500'}`}>{Number(movement.quantity_delta) > 0 ? '+' : ''}{numberText(movement.quantity_delta)}</td><td className="px-5 py-3.5 text-right tabular-nums text-slate-600">{Number(movement.reserved_delta) > 0 ? '+' : ''}{numberText(movement.reserved_delta)}</td><td className="px-5 py-3.5 text-xs text-slate-600">{movement.source_reference || '—'}{movement.notes && <p className="mt-1 max-w-56 truncate text-slate-400">{movement.notes}</p>}</td></tr>)}</tbody></table></div>}</section>

    <div className="flex items-start gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3.5 text-xs leading-5 text-slate-500"><ShieldCheck size={16} className="mt-0.5 shrink-0 text-slate-400" /><p>Stock is never changed silently. The ledger records every movement and its resulting balance. Dispatches cannot consume reserved stock, reservations cannot exceed available stock, and negative stock is blocked.</p></div>
  </div>
}
