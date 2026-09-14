import { ApiError, statusHint } from '../api/client'

/**
 * Error text for forms and data panels. Server detail is shown verbatim;
 * when it is empty or generic, a status-code hint fills in.
 */
export function ErrorText({ error }: { error: unknown }) {
  if (!error) return null
  const message =
    error instanceof ApiError ? error.message : 'Something went wrong — try again.'
  const hint = error instanceof ApiError ? statusHint(error.status) : null

  return (
    <p className="rounded-lg border border-debit/40 bg-debit/10 px-3 py-2 text-sm text-debit" role="alert">
      {message}
      {hint && hint !== message && (
        <span className="block text-xs text-slate-400">{hint}</span>
      )}
    </p>
  )
}
