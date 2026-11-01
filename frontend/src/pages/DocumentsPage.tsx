import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useOutletContext } from 'react-router-dom'
import { BadgeCheck, Download, FileCheck2, FilePlus2, FileText, History, LockKeyhole, Plus, Trash2, UploadCloud, XCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { AppShellOutletContext } from '@/components/layout/AppShell'
import { listImportOrders } from '@/features/imports/api'
import { listExportOrders } from '@/features/exports/api'
import { listShipments } from '@/features/shipments/api'
import {
  createDocumentRequirement, deleteDocument, deleteDocumentRequirement, downloadDocument,
  getDocumentCompliance, listDocumentRequirements, listDocuments, uploadDocument,
  uploadDocumentVersion, verifyDocument,
} from '@/features/documents/api'
import type { RelatedEntityType, TradeDocument } from '@/features/documents/types'

const inputClass = 'w-full rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100'
const documentTypes = [
  ['commercial_invoice', 'Commercial invoice'], ['packing_list', 'Packing list'], ['bill_of_lading', 'Bill of lading'],
  ['air_waybill', 'Air waybill'], ['certificate_of_origin', 'Certificate of origin'], ['insurance_certificate', 'Insurance certificate'],
  ['customs_declaration', 'Customs declaration'], ['inspection_certificate', 'Inspection certificate'], ['product_certificate', 'Product certificate'],
  ['import_permit', 'Import permit'], ['export_permit', 'Export permit'], ['purchase_order', 'Purchase order'], ['sales_order', 'Sales order'], ['other', 'Other supporting document'],
] as const
const statusStyles = { pending: 'bg-amber-100 text-amber-800', verified: 'bg-emerald-100 text-emerald-800', rejected: 'bg-rose-100 text-rose-800' }

export function DocumentsPage() {
  const { selectedOrganizationId, selectedOrganization } = useOutletContext<AppShellOutletContext>()
  const queryClient = useQueryClient()
  const [selectedTargetKey, setSelectedTargetKey] = useState('')
  const [documentType, setDocumentType] = useState('commercial_invoice')
  const [documentTitle, setDocumentTitle] = useState('')
  const [expiryDate, setExpiryDate] = useState('')
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [requirementLabel, setRequirementLabel] = useState('')
  const [requirementType, setRequirementType] = useState('commercial_invoice')
  const [verificationNotes, setVerificationNotes] = useState<Record<string, string>>({})
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  const role = selectedOrganization?.role ?? ''
  const canUpload = ['organization_owner', 'administrator', 'import_manager', 'export_manager', 'operations_staff'].includes(role)
  const canReview = ['organization_owner', 'administrator'].includes(role)
  const canDelete = ['organization_owner', 'administrator'].includes(role)

  const importsQuery = useQuery({ queryKey: ['imports', selectedOrganizationId, 'document-targets'], queryFn: () => listImportOrders(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) })
  const exportsQuery = useQuery({ queryKey: ['exports', selectedOrganizationId, 'document-targets'], queryFn: () => listExportOrders(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) })
  const shipmentsQuery = useQuery({ queryKey: ['shipments', selectedOrganizationId, 'document-targets'], queryFn: () => listShipments(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) })
  const documentsQuery = useQuery({ queryKey: ['documents', selectedOrganizationId], queryFn: () => listDocuments(selectedOrganizationId), enabled: Boolean(selectedOrganizationId) })

  const targetOptions = useMemo(() => {
    const options: Array<{ key: string; label: string; type: RelatedEntityType; id: string }> = []
    for (const order of importsQuery.data?.items ?? []) options.push({ key: `import_order:${order.id}`, label: `Import order · ${order.reference}`, type: 'import_order', id: order.id })
    for (const order of exportsQuery.data?.items ?? []) options.push({ key: `export_order:${order.id}`, label: `Export order · ${order.reference}`, type: 'export_order', id: order.id })
    for (const shipment of shipmentsQuery.data ?? []) options.push({ key: `${shipment.shipment_type}_shipment:${shipment.id}`, label: `${shipment.shipment_type === 'import' ? 'Import' : 'Export'} shipment · ${shipment.shipment_reference}`, type: `${shipment.shipment_type}_shipment`, id: shipment.id })
    return options
  }, [importsQuery.data, exportsQuery.data, shipmentsQuery.data])
  useEffect(() => {
    if (!targetOptions.some((option) => option.key === selectedTargetKey) && targetOptions.length > 0) setSelectedTargetKey(targetOptions[0].key)
  }, [targetOptions, selectedTargetKey])
  const selectedTarget = targetOptions.find((option) => option.key === selectedTargetKey)

  const requirementsQuery = useQuery({
    queryKey: ['documents', selectedOrganizationId, 'requirements', selectedTarget?.key],
    queryFn: () => listDocumentRequirements(selectedOrganizationId, selectedTarget!.type, selectedTarget!.id),
    enabled: Boolean(selectedOrganizationId && selectedTarget),
  })
  const complianceQuery = useQuery({
    queryKey: ['documents', selectedOrganizationId, 'compliance', selectedTarget?.key],
    queryFn: () => getDocumentCompliance(selectedOrganizationId, selectedTarget!.type, selectedTarget!.id),
    enabled: Boolean(selectedOrganizationId && selectedTarget),
  })

  function refreshAll() {
    queryClient.invalidateQueries({ queryKey: ['documents', selectedOrganizationId] })
    queryClient.invalidateQueries({ queryKey: ['documents', selectedOrganizationId, 'requirements'] })
    queryClient.invalidateQueries({ queryKey: ['documents', selectedOrganizationId, 'compliance'] })
  }
  function reportSuccess(message: string) { setError(''); setNotice(message) }
  function reportError(err: unknown) { setNotice(''); setError(err instanceof Error ? err.message : 'The request could not be completed.') }

  const uploadMutation = useMutation({
    mutationFn: () => {
      if (!selectedTarget || !selectedFile) throw new Error('Select a related trade record and a file.')
      const form = new FormData()
      form.set('related_entity_type', selectedTarget.type)
      form.set('related_entity_id', selectedTarget.id)
      form.set('document_type', documentType)
      if (documentTitle.trim()) form.set('title', documentTitle.trim())
      if (expiryDate) form.set('expiry_date', expiryDate)
      form.set('file', selectedFile)
      return uploadDocument(selectedOrganizationId, form)
    },
    onSuccess: () => { setSelectedFile(null); setDocumentTitle(''); setExpiryDate(''); reportSuccess('Document uploaded and queued for verification.'); refreshAll() },
    onError: reportError,
  })
  const requirementMutation = useMutation({
    mutationFn: () => {
      if (!selectedTarget) throw new Error('Select a related trade record first.')
      const label = requirementLabel.trim() || documentTypes.find(([type]) => type === requirementType)?.[1] || requirementType
      return createDocumentRequirement(selectedOrganizationId, {
        related_entity_type: selectedTarget.type, related_entity_id: selectedTarget.id,
        document_type: requirementType, label, is_required: true,
      })
    },
    onSuccess: () => { setRequirementLabel(''); reportSuccess('Required document rule added.'); refreshAll() },
    onError: reportError,
  })
  const verificationMutation = useMutation({
    mutationFn: ({ document, result }: { document: TradeDocument; result: 'verified' | 'rejected' }) => verifyDocument(selectedOrganizationId, document.id, result, verificationNotes[document.id] ?? ''),
    onSuccess: (_, variables) => { reportSuccess(`Document marked ${variables.result}.`); refreshAll() },
    onError: reportError,
  })
  const versionMutation = useMutation({
    mutationFn: ({ document, file }: { document: TradeDocument; file: File }) => {
      const form = new FormData(); form.set('file', file)
      return uploadDocumentVersion(selectedOrganizationId, document.id, form)
    },
    onSuccess: () => { reportSuccess('New version uploaded; verification has been reset to pending.'); refreshAll() },
    onError: reportError,
  })
  const deleteMutation = useMutation({
    mutationFn: (documentId: string) => deleteDocument(selectedOrganizationId, documentId),
    onSuccess: () => { reportSuccess('Document and its stored versions were deleted.'); refreshAll() },
    onError: reportError,
  })
  const requirementDeleteMutation = useMutation({
    mutationFn: (requirementId: string) => deleteDocumentRequirement(selectedOrganizationId, requirementId),
    onSuccess: () => { reportSuccess('Document requirement removed.'); refreshAll() },
    onError: reportError,
  })

  async function handleDownload(document: TradeDocument, version?: number) {
    try { await downloadDocument(selectedOrganizationId, document.id, version) } catch (err) { reportError(err) }
  }

  return <div className="space-y-6">
    <section className="rounded-2xl bg-[#122338] px-5 py-6 text-white shadow-lg shadow-slate-900/10 sm:px-7">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end"><div><div className="mb-2 inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/[0.07] px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-sky-200"><LockKeyhole size={13} /> Private document vault</div><h2 className="text-2xl font-bold tracking-tight">Trade documents</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">Upload, version, verify, and download trade documents. Requirements are configured per order or shipment; the system does not assume every document applies to every trade.</p></div><div className="rounded-xl border border-white/15 bg-white/[0.08] px-4 py-3 text-right"><p className="text-[10px] font-semibold uppercase tracking-wider text-slate-300">Stored documents</p><p className="text-2xl font-bold">{documentsQuery.data?.length ?? '—'}</p></div></div>
    </section>

    {notice && <p role="status" className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</p>}
    {error && <p role="alert" className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</p>}

    <section className="grid items-start gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <div className="space-y-5">
        <Card className="rounded-2xl border-slate-200/80 shadow-sm">
          <CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Upload document</CardTitle><CardDescription>Attach a private file to an import/export order or shipment.</CardDescription></CardHeader>
          <CardContent className="space-y-3 p-4 sm:p-5">
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Related trade record</span><select className={inputClass} value={selectedTargetKey} onChange={(event) => setSelectedTargetKey(event.target.value)}><option value="">Select order or shipment…</option>{targetOptions.map((target) => <option key={target.key} value={target.key}>{target.label}</option>)}</select></label>
            <div className="grid gap-3 sm:grid-cols-2"><label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Document category</span><select className={inputClass} value={documentType} onChange={(event) => setDocumentType(event.target.value)}>{documentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Expiry date (optional)</span><input className={inputClass} type="date" value={expiryDate} onChange={(event) => setExpiryDate(event.target.value)} /></label></div>
            <label className="block"><span className="mb-1.5 block text-xs font-semibold text-slate-700">Document title (optional)</span><input className={inputClass} value={documentTitle} onChange={(event) => setDocumentTitle(event.target.value)} placeholder="e.g. Signed commercial invoice" /></label>
            <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-slate-300 bg-slate-50 p-4 hover:bg-slate-100"><UploadCloud size={20} className="shrink-0 text-slate-500" /><span className="min-w-0 flex-1"><span className="block text-xs font-semibold text-slate-700">{selectedFile?.name ?? 'Choose a document file'}</span><span className="mt-0.5 block text-[10px] text-slate-500">PDF, PNG, JPG, XLSX, DOCX, CSV or TXT · maximum configured file size</span></span><input className="sr-only" type="file" accept=".pdf,.png,.jpg,.jpeg,.xlsx,.docx,.csv,.txt" onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)} /></label>
            <Button className="w-full" onClick={() => uploadMutation.mutate()} disabled={!canUpload || !selectedTarget || !selectedFile || uploadMutation.isPending}><FilePlus2 size={15} />{uploadMutation.isPending ? 'Uploading…' : 'Upload private document'}</Button>
            {!canUpload && <p className="text-[11px] text-amber-700">Your role cannot upload documents.</p>}
          </CardContent>
        </Card>

        <Card className="rounded-2xl border-slate-200/80 shadow-sm">
          <CardHeader className="border-b border-slate-100"><CardTitle className="text-base">Document requirements</CardTitle><CardDescription>Define which documents are required for the selected order or shipment. A requirement is satisfied only by a verified, unexpired document of that type.</CardDescription></CardHeader>
          <CardContent className="space-y-3 p-4 sm:p-5">
            {selectedTarget ? <>
              <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-600">{selectedTarget.label}</div>
              <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]"><select className={inputClass} value={requirementType} onChange={(event) => setRequirementType(event.target.value)} aria-label="Required document type">{documentTypes.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select><input className={inputClass} value={requirementLabel} onChange={(event) => setRequirementLabel(event.target.value)} placeholder="Requirement label (optional)" /></div>
              <Button variant="outline" size="sm" onClick={() => requirementMutation.mutate()} disabled={!canUpload || requirementMutation.isPending}><Plus size={14} />Add required document</Button>
              {complianceQuery.data && <div className={`rounded-xl border p-3 ${complianceQuery.data.is_compliant ? 'border-emerald-200 bg-emerald-50' : 'border-amber-200 bg-amber-50'}`}><div className="flex items-center justify-between gap-2"><span className="text-xs font-bold text-slate-800">Requirement compliance</span><span className={`text-xs font-bold ${complianceQuery.data.is_compliant ? 'text-emerald-700' : 'text-amber-700'}`}>{complianceQuery.data.is_compliant ? 'Complete' : `${complianceQuery.data.missing_count} missing`}</span></div><p className="mt-1 text-[11px] text-slate-600">{complianceQuery.data.satisfied_count} of {complianceQuery.data.required_count} required document types satisfied.</p></div>}
              {requirementsQuery.data?.length ? <ul className="space-y-2">{requirementsQuery.data.map((requirement) => <li key={requirement.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 p-3"><span className="min-w-0"><span className="block text-xs font-semibold text-slate-800">{requirement.label}</span><span className="mt-0.5 block text-[10px] text-slate-500">{requirement.document_type.replaceAll('_', ' ')}</span></span><button className="rounded-md p-2 text-slate-400 hover:bg-rose-50 hover:text-rose-600 disabled:opacity-40" type="button" aria-label={`Remove ${requirement.label}`} disabled={!canDelete || requirementDeleteMutation.isPending} onClick={() => requirementDeleteMutation.mutate(requirement.id)}><Trash2 size={14} /></button></li>)}</ul> : <p className="text-xs text-slate-500">No requirements configured for this record yet.</p>}
            </> : <p className="text-xs text-slate-500">Create or select an import/export order or shipment to manage its document requirements.</p>}
          </CardContent>
        </Card>
      </div>

      <Card className="rounded-2xl border-slate-200/80 shadow-sm">
        <CardHeader className="border-b border-slate-100"><div className="flex items-center justify-between gap-3"><div><CardTitle className="text-base">Document register</CardTitle><CardDescription>Latest versions, verification status, and authorized file actions.</CardDescription></div><span className="rounded-lg bg-slate-100 p-2 text-slate-500"><FileCheck2 size={18} /></span></div></CardHeader>
        <CardContent className="space-y-3 p-4 sm:p-5">
          {documentsQuery.isPending ? <p className="py-8 text-center text-sm text-slate-500">Loading documents…</p> : null}
          {documentsQuery.isError ? <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-800">{documentsQuery.error instanceof Error ? documentsQuery.error.message : 'Documents could not be loaded.'}</p> : null}
          {!documentsQuery.isPending && !documentsQuery.isError && (documentsQuery.data ?? []).length === 0 ? <div className="rounded-xl border border-dashed border-slate-300 px-5 py-10 text-center"><FileText size={28} className="mx-auto text-slate-300" /><p className="mt-3 text-sm font-semibold text-slate-700">No documents uploaded</p><p className="mt-1 text-xs text-slate-500">The register will show private trade documents after the first upload.</p></div> : null}
          {(documentsQuery.data ?? []).map((document) => <article key={document.id} className="rounded-xl border border-slate-200 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><h3 className="text-sm font-bold text-slate-900">{document.title}</h3><span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${statusStyles[document.verification_status]}`}>{document.verification_status}</span></div><p className="mt-1 text-[11px] text-slate-500">{document.document_reference} · {document.related_entity_type.replaceAll('_', ' ')} · {document.document_type.replaceAll('_', ' ')}</p></div><span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-bold text-slate-600">v{document.current_version}</span></div>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] text-slate-500"><span>{document.current_file_name}</span><span>{(document.current_file_size / 1024).toFixed(1)} KB</span><span>Expires: {document.expiry_date || 'Not set'}</span></div>
            {document.verification_notes && <p className="mt-2 rounded-md bg-slate-50 p-2 text-[11px] text-slate-600">{document.verification_notes}</p>}
            <div className="mt-3 flex flex-wrap items-center gap-2"><Button size="sm" variant="outline" onClick={() => void handleDownload(document)}><Download size={13} />Download current</Button><label className={`inline-flex h-9 cursor-pointer items-center gap-2 rounded-md border px-3 text-xs font-medium hover:bg-slate-50 ${!canUpload ? 'pointer-events-none opacity-40' : ''}`}><UploadCloud size={13} />New version<input className="sr-only" type="file" accept=".pdf,.png,.jpg,.jpeg,.xlsx,.docx,.csv,.txt" disabled={!canUpload || versionMutation.isPending} onChange={(event) => { const file = event.target.files?.[0]; if (file) versionMutation.mutate({ document, file }); event.currentTarget.value = '' }} /></label>{canReview && document.verification_status !== 'verified' && <Button size="sm" onClick={() => verificationMutation.mutate({ document, result: 'verified' })} disabled={verificationMutation.isPending}><BadgeCheck size={13} />Verify</Button>}{canReview && document.verification_status !== 'rejected' && <Button size="sm" variant="outline" className="border-rose-200 text-rose-700 hover:bg-rose-50" onClick={() => verificationMutation.mutate({ document, result: 'rejected' })} disabled={verificationMutation.isPending}><XCircle size={13} />Reject</Button>}{canDelete && <Button size="sm" variant="ghost" className="text-rose-700 hover:bg-rose-50" onClick={() => deleteMutation.mutate(document.id)} disabled={deleteMutation.isPending}><Trash2 size={13} />Delete</Button>}</div>
            {canReview && <input className={`${inputClass} mt-2`} value={verificationNotes[document.id] ?? ''} onChange={(event) => setVerificationNotes((current) => ({ ...current, [document.id]: event.target.value }))} placeholder="Verification note (optional)" aria-label={`Verification note for ${document.title}`} />}
            <details className="mt-3 border-t border-slate-100 pt-2"><summary className="flex cursor-pointer list-none items-center gap-2 text-[11px] font-semibold text-slate-600"><History size={13} />Version history ({document.versions.length})</summary><div className="mt-2 space-y-2">{document.versions.map((version) => <div key={version.id} className="flex flex-wrap items-center justify-between gap-2 rounded-md bg-slate-50 px-3 py-2 text-[11px]"><span className="text-slate-700">v{version.version_number} · {version.file_name}</span><button type="button" className="font-semibold text-sky-700 hover:underline" onClick={() => void handleDownload(document, version.version_number)}>Download</button></div>)}</div></details>
          </article>)}
        </CardContent>
      </Card>
    </section>
  </div>
}
