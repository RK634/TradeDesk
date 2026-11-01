import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Building2, LoaderCircle, MailCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'
import { apiPost } from '@/features/auth/api'
import { getInvitationPreview } from '@/features/auth/api'
import type { AuthMe } from '@/features/auth/types'

const schema = z.object({
  full_name: z.string().trim().min(2, 'Enter your full name.').max(160),
  password: z.string().min(12, 'Use at least 12 characters.').max(128),
})
type FormValues = z.infer<typeof schema>

export function AcceptInvitationPage() {
  const [searchParams] = useSearchParams()
  const token = new URLSearchParams(window.location.hash.replace(/^#/, '')).get('token') ?? searchParams.get('token') ?? ''
  const { auth, refresh, logout } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { full_name: '', password: '' } })
  const previewQuery = useQuery({
    queryKey: ['invitation-preview', token],
    queryFn: () => getInvitationPreview(token),
    enabled: token.length >= 32,
    retry: false,
  })

  async function accept(values?: FormValues) {
    setServerError(null)
    setSubmitting(true)
    try {
      const result = await apiPost<{ accepted: boolean; user?: AuthMe['user']; organizations?: AuthMe['organizations']; csrf_token?: string }>('/auth/accept-invitation', {
        token,
        ...(values ? { full_name: values.full_name, password: values.password } : {}),
      })
      if ('user' in result && result.user) await refresh()
      navigate('/app', { replace: true })
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Could not accept the invitation.')
    } finally {
      setSubmitting(false)
    }
  }

  const preview = previewQuery.data
  const signedInToInvitee = Boolean(auth && preview && auth.user.email.toLowerCase() === preview.email.toLowerCase())

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <section className="w-full max-w-lg rounded-2xl border bg-white p-6 shadow-sm sm:p-8">
        <Link to="/" className="inline-flex items-center gap-2 font-bold"><span className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-white"><Building2 size={18} /></span> TradeDesk</Link>
        <div className="mt-8 flex h-12 w-12 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700"><MailCheck size={23} /></div>
        <h1 className="mt-4 text-2xl font-bold tracking-tight">Accept organization invitation</h1>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">Review the invitation details before joining the workspace.</p>

        {!token || token.length < 32 ? (
          <div role="alert" className="mt-6 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">This invitation link is missing a valid token.</div>
        ) : previewQuery.isPending ? (
          <div className="mt-6 flex items-center gap-2 text-sm text-muted-foreground" role="status"><LoaderCircle className="animate-spin" size={16} /> Checking invitation…</div>
        ) : previewQuery.isError ? (
          <div role="alert" className="mt-6 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{previewQuery.error instanceof Error ? previewQuery.error.message : 'This invitation is invalid or expired.'}</div>
        ) : preview ? (
          <>
            <dl className="mt-6 space-y-3 rounded-xl border bg-slate-50 p-4 text-sm">
              <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Organization</dt><dd className="text-right font-semibold">{preview.organization_name}</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Invited email</dt><dd className="text-right font-semibold">{preview.email}</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Access role</dt><dd className="text-right font-semibold">{preview.role.replaceAll('_', ' ')}</dd></div>
              <div className="flex justify-between gap-4"><dt className="text-muted-foreground">Expires</dt><dd className="text-right">{new Date(preview.expires_at).toLocaleString()}</dd></div>
            </dl>
            {serverError && <div role="alert" className="mt-4 rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{serverError}</div>}
            {signedInToInvitee ? (
              <Button className="mt-5 w-full" disabled={submitting} onClick={() => accept()}>{submitting ? <LoaderCircle className="animate-spin" size={16} /> : <MailCheck size={16} />} Accept invitation</Button>
            ) : preview.user_exists ? (
              <div className="mt-5 space-y-3">
                {auth ? <p className="text-sm text-muted-foreground">You are signed in as {auth.user.email}. Sign in to the invited account to accept this invitation.</p> : <p className="text-sm text-muted-foreground">This email already has an account. Sign in using the invited email, then open this link again.</p>}
                <Button className="w-full" onClick={async () => { if (auth) await logout(); navigate('/login', { state: { from: { pathname: '/accept-invitation', hash: `#token=${encodeURIComponent(token)}` } } }) }}>Continue to sign in</Button>
              </div>
            ) : (
              <form className="mt-5 space-y-4" onSubmit={form.handleSubmit(accept)} noValidate>
                <div><label htmlFor="invite-full-name" className="mb-1.5 block text-sm font-medium">Full name</label><input id="invite-full-name" autoComplete="name" {...form.register('full_name')} className="h-11 w-full rounded-md border px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />{form.formState.errors.full_name && <p className="mt-1 text-xs text-rose-700">{form.formState.errors.full_name.message}</p>}</div>
                <div><label htmlFor="invite-password" className="mb-1.5 block text-sm font-medium">Create password</label><input id="invite-password" type="password" autoComplete="new-password" {...form.register('password')} className="h-11 w-full rounded-md border px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" /><p className="mt-1 text-xs text-muted-foreground">Use at least 12 characters.</p>{form.formState.errors.password && <p className="mt-1 text-xs text-rose-700">{form.formState.errors.password.message}</p>}</div>
                <Button type="submit" className="w-full" disabled={submitting}>{submitting ? <LoaderCircle className="animate-spin" size={16} /> : <MailCheck size={16} />} Create account and join</Button>
              </form>
            )}
          </>
        ) : null}
        <p className="mt-6 text-center text-xs text-muted-foreground"><Link to="/login" className="font-semibold text-primary hover:underline">Back to sign in</Link></p>
      </section>
    </main>
  )
}
