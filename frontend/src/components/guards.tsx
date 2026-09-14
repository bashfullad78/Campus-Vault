import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useSession } from '../hooks/useSession'

/**
 * Route guard. Renders nothing while session restore is in flight (not a
 * spinner — avoids flashing chrome) so protected pages never mount, fetch,
 * and remount.
 */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useSession()
  const location = useLocation()

  if (loading) return null
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <>{children}</>
}

/** Inverse guard: signed-in users have no business on /login or /register. */
export function RedirectIfAuthed({ children }: { children: ReactNode }) {
  const { user, loading } = useSession()

  if (loading) return null
  if (user) return <Navigate to="/" replace />
  return <>{children}</>
}
