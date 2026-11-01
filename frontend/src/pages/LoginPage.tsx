import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { Globe2, LoaderCircle, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/features/auth/AuthProvider'

const schema = z.object({
  email: z.string().trim().email('Enter a valid email address.'),
  password: z.string().min(1, 'Enter your password.'),
})
type FormValues = z.infer<typeof schema>

export function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [serverError, setServerError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: '', password: '' } })

  async function onSubmit(values: FormValues) {
    setServerError(null)
    setSubmitting(true)
    try {
      await login(values.email, values.password)
      const state = location.state as { from?: { pathname?: string; search?: string; hash?: string } } | null
      navigate(`${state?.from?.pathname || '/app'}${state?.from?.search || ''}${state?.from?.hash || ''}`, { replace: true })
    } catch (error) {
      setServerError(error instanceof Error ? error.message : 'Sign in failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-6">
      <section className="w-full max-w-md rounded-2xl border bg-white p-6 shadow-sm sm:p-8">
        <Link to="/" className="inline-flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-white"><Globe2 size={21} /></span>
          <span><span className="block font-bold">TradeDesk</span><span className="block text-xs text-muted-foreground">Trade management workspace</span></span>
        </Link>
        <div className="mt-8">
          <h1 className="text-2xl font-bold tracking-tight">Welcome back</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">Sign in to manage your organization's trade operations.</p>
        </div>
        <form className="mt-7 space-y-5" onSubmit={form.handleSubmit(onSubmit)} noValidate>
          <div>
            <label htmlFor="email" className="mb-1.5 block text-sm font-medium">Work email</label>
            <input id="email" type="email" autoComplete="username" {...form.register('email')} className="h-11 w-full rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-invalid={Boolean(form.formState.errors.email)} />
            {form.formState.errors.email && <p className="mt-1 text-xs text-rose-700">{form.formState.errors.email.message}</p>}
          </div>
          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium">Password</label>
            <input id="password" type="password" autoComplete="current-password" {...form.register('password')} className="h-11 w-full rounded-md border bg-white px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-invalid={Boolean(form.formState.errors.password)} />
            {form.formState.errors.password && <p className="mt-1 text-xs text-rose-700">{form.formState.errors.password.message}</p>}
          </div>
          {serverError && <div role="alert" className="rounded-md border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800">{serverError}</div>}
          <Button type="submit" className="w-full" disabled={submitting}>
            {submitting ? <><LoaderCircle className="animate-spin" size={16} /> Signing in…</> : 'Sign in'}
          </Button>
        </form>
        <p className="mt-6 text-center text-sm text-muted-foreground">New to TradeDesk? <Link className="font-semibold text-primary underline-offset-4 hover:underline" to="/register">Create an account</Link></p>
        <p className="mt-6 flex items-center justify-center gap-2 border-t pt-5 text-xs text-muted-foreground"><ShieldCheck size={14} /> Secure, organization-scoped access</p>
      </section>
    </main>
  )
}
