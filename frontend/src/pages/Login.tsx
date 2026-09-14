import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useSession } from '../hooks/useSession'
import { login } from '../api/auth'
import { fetchMe } from '../api/auth'
import { ApiError } from '../api/client'
import { ErrorText } from '../components/ErrorText'
import { Spinner } from '../components/Spinner'
import { AuthShell } from './AuthShell'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { setSession } = useSession()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await login({ email: email.trim(), password })
      setSession(await fetchMe())
      // Return to the page the user was bounced from, if any.
      const from = (location.state as { from?: string } | null)?.from ?? '/'
      navigate(from, { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Could not sign in — try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <h1 className="text-xl font-bold text-slate-100">Welcome back</h1>
      <p className="mt-1 text-sm text-slate-400">Sign in to browse and share notes.</p>
      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm text-slate-300">Email</span>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-sm text-slate-100 outline-none focus:border-coin focus:ring-2 focus:ring-coin/30"
            placeholder="you@college.edu"
          />
        </label>
        <label className="flex flex-col gap-1.5">
          <span className="text-sm text-slate-300">Password</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-sm text-slate-100 outline-none focus:border-coin focus:ring-2 focus:ring-coin/30"
            placeholder="••••••••"
          />
        </label>
        <ErrorText error={error} />
        <button
          type="submit"
          disabled={submitting}
          className="flex items-center justify-center gap-2 rounded-lg bg-coin px-4 py-2 text-sm font-semibold text-slate-950 transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {submitting && <Spinner className="h-4 w-4 border-slate-900/40 border-t-transparent" />}
          Sign in
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-400">
        New here?{' '}
        <Link to="/register" className="font-medium text-coin hover:underline">
          Create an account
        </Link>
      </p>
    </AuthShell>
  )
}
