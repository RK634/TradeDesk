import { useState, type ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Globe2, LoaderCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'

const schema = z.object({
  full_name: z.string().trim().min(2, 'Enter your name.').max(160),
  email: z.string().trim().email('Enter a valid email address.'),
  organization_name: z.string().trim().min(2, 'Enter your organization name.').max(160),
  password: z.string().min(12, 'Use at least 12 characters.').max(128),
})
type FormValues = z.infer<typeof schema>

export function RegisterPage() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [serverError, setServerError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { full_name: '', email: '', organization_name: '', password: '' } })

  async function onSubmit(values: FormValues) {
    setServerError(null)
    setSubmitting(true)
    try {
      await register(values)
      navigate('/app', { replace: true })
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Account creation failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <section className="w-full max-w-lg rounded-2xl border bg-white p-6 shadow-sm sm:p-8">
        <Link to="/" className="inline-flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-white"><Globe2 size={21} /></span>
          <span><span className="block font-bold">TradeDesk</span><span className="block text-xs text-muted-foreground">Trade management workspace</span></span>
        </Link>
        <div className="mt-8">
          <h1 className="text-2xl font-bold tracking-tight">Create your workspace</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">Your account will become the owner of the organization you create.</p>
        </div>
        <form className="mt-7 space-y-4" onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <Field label="Full name" id="full_name" error={form.formState.errors.full_name?.message}>
            <input id="full_name" autoComplete="name" {...form.register('full_name')} className="h-11 w-full rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </Field>
          <Field label="Work email" id="email" error={form.formState.errors.email?.message}>
            <input id="email" type="email" autoComplete="email" {...form.register('email')} className="h-11 w-full rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </Field>
          <Field label="Organization name" id="organization_name" error={form.formState.errors.organization_name?.message}>
            <input id="organization_name" autoComplete="organization" {...form.register('organization_name')} className="h-11 w-full rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </Field>
          <Field label="Password" id="password" error={form.formState.errors.password?.message} hint="Use at least 12 characters.">
            <input id="password" type="password" autoComplete="new-password" {...form.register('password')} className="h-11 w-full rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" />
          </Field>
          {serverError && <div role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{serverError}</div>}
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? <><LoaderCircle className="animate-spin" size={16} /> Creating workspace…</> : 'Create account and workspace'}
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-muted-foreground">Already registered? <Link className="font-semibold text-primary hover:underline" to="/login">Sign in</Link></p>
      </section>
    </main>
  )
}

function Field({ label, id, error, hint, children }: { label: string; id: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>
      {children}
      {hint && !error && <p className="mt-1 text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="mt-1 text-xs text-rose-700">{error}</p>}
    </div>
  )
}
