import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useSession } from '../hooks/useSession'
import { fetchMe, login, register } from '../api/auth'
import { ApiError } from '../api/client'
import { ErrorText } from '../components/ErrorText'
import { Spinner } from '../components/Spinner'
import { AuthShell } from './AuthShell'

export function RegisterPage() {
  const navigate = useNavigate()
  const { setSession } = useSession()

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register({ email: email.trim(), name: name.trim(), password })
      // Register does not issue tokens — sign in immediately for a smooth path.
      await login({ email: email.trim(), password })
      setSession(await fetchMe())
      navigate('/', { replace: true })
    } catch (err) {
      // 409 "An account with this email already exists" and 422 validation
      // messages are shown verbatim; rate limit (429) gets its hint.
      setError(err instanceof ApiError ? err.message : 'Could not register — try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <AuthShell>
      <h1 className="text-xl font-bold text-slate-100">Create your account</h1>
      <p className="mt-1 text-sm text-slate-400">
        You start with an empty wallet — upload to earn.
      </p>
      <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-4">
        <label className="flex flex-col gap-1.5">
          <span className="text-sm text-slate-300">Name</span>
          <input
            type="text"
            required
            maxLength={255}
            autoComplete="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-sm text-slate-100 outline-none focus:border-coin focus:ring-2 focus:ring-coin/30"
            placeholder="Asha K."
          />
        </label>
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
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-sm text-slate-100 outline-none focus:border-coin focus:ring-2 focus:ring-coin/30"
            placeholder="8+ characters"
          />
        </label>
        <ErrorText error={error} />
        <button
          type="submit"
          disabled={submitting}
          className="flex items-center justify-center gap-2 rounded-lg bg-coin px-4 py-2 text-sm font-semibold text-slate-950 transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {submitting && <Spinner className="h-4 w-4 border-slate-900/40 border-t-transparent" />}
          Create account
        </button>
      </form>
      <p className="mt-4 text-sm text-slate-400">
        Already have an account?{' '}
        <Link to="/login" className="font-medium text-coin hover:underline">
          Sign in
        </Link>
      </p>
    </AuthShell>
  )
}
