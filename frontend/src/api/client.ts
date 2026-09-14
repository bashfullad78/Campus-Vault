/*
 * API client — fetch wrapper + auth plumbing.
 *
 * Design notes (frontend.txt §4):
 * - 401 on any protected call (except the refresh call itself) triggers ONE
 *   silent refresh; concurrent 401'd requests queue behind the same promise
 *   and are retried exactly once. A failed refresh wipes storage and
 *   redirects to /login. Never a retry loop.
 * - The refresh token ROTATES server-side: every successful refresh must
 *   overwrite both stored tokens.
 * - Error normalization: FastAPI returns `detail` as a string for service
 *   errors, but as an ARRAY for 422 request-validation errors. Both shapes
 *   are flattened into a human-readable message.
 * - Token storage is localStorage for V1. Known tradeoff: any XSS in this
 *   app can read both tokens; httpOnly-cookie sessions would close that but
 *   need a backend change (CSRF handling, same-site config). Refresh TTL
 *   (7 days) is the hard session ceiling. Revisit at deploy time.
 */

import type { TokenResponse } from './types'

// Set VITE_API_URL at build time for deployed environments (e.g. Vercel env
// vars → https://your-api.onrender.com). Falls back to the local dev server.
const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

const ACCESS_KEY = 'cu.access_token'
const REFRESH_KEY = 'cu.refresh_token'

// --- token storage --------------------------------------------------------

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function setTokens(access: string, refresh: string): void {
  localStorage.setItem(ACCESS_KEY, access)
  localStorage.setItem(REFRESH_KEY, refresh)
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

// --- error model -----------------------------------------------------------

export class ApiError extends Error {
  status: number
  /** True when detail came back as a 422 validation array. */
  isValidation: boolean

  constructor(status: number, message: string, isValidation = false) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.isValidation = isValidation
  }
}

/** Map an HTTP status to the UI copy defined in frontend.txt §3. */
export function statusHint(status: number): string | null {
  switch (status) {
    case 401:
      return 'Please sign in again.'
    case 403:
      return 'You can only manage your own uploads.'
    case 404:
      return 'Not found — it may have been deleted.'
    case 409:
      return null // context-specific (duplicate / insufficient coins)
    case 413:
      return 'File is larger than the 25 MB limit.'
    case 422:
      return null // validation details are shown verbatim
    case 429:
      return 'Slow down — try again in a minute.'
    default:
      return null
  }
}

function flattenDetail(detail: unknown): string {
  // FastAPI 422s: detail = [{loc, msg, type}, ...]. Everything else: string.
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === 'object' && 'msg' in item) {
          const loc = Array.isArray((item as { loc?: unknown[] }).loc)
            ? (item as { loc: (string | number)[] }).loc.slice(1).join('.')
            : ''
          const msg = String((item as { msg: unknown }).msg)
          return loc ? `${loc}: ${msg}` : msg
        }
        return String(item)
      })
      .join('; ')
  }
  return 'Something went wrong'
}

// --- single-flight refresh ---------------------------------------------------

let refreshPromise: Promise<boolean> | null = null

async function doRefresh(): Promise<boolean> {
  const refresh = getRefreshToken()
  if (!refresh) return false
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    if (!res.ok) return false
    const data = (await res.json()) as TokenResponse
    // Rotation: always overwrite BOTH tokens with the fresh pair.
    setTokens(data.access_token, data.refresh_token)
    return true
  } catch {
    return false
  }
}

/**
 * Refresh exactly once even when several requests 401 simultaneously.
 * Resolves true only if the session was successfully renewed.
 */
function singleFlightRefresh(): Promise<boolean> {
  refreshPromise ??= doRefresh().finally(() => {
    refreshPromise = null
  })
  return refreshPromise
}

function forceLogout(): void {
  clearTokens()
  // Full reload clears every in-memory query cache.
  window.location.assign('/login')
}

// --- core request ----------------------------------------------------------

interface RequestOptions {
  method?: string
  body?: unknown // JSON-serializable; ignored when formData is set
  formData?: FormData
  /** Internal: the request has already been retried after a refresh. */
  retried?: boolean
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, formData, retried = false } = options

  const headers: Record<string, string> = {}
  const token = getAccessToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'

  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      body: formData ?? (body !== undefined ? JSON.stringify(body) : undefined),
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server — is the backend running?')
  }

  if (res.status === 401 && !retried && !path.startsWith('/auth/')) {
    // One silent refresh, shared by every concurrent 401. /auth/* paths never
    // retry: refreshing from a 401'd refresh call would loop.
    const renewed = await singleFlightRefresh()
    if (renewed) {
      return request<T>(path, { ...options, retried: true })
    }
    forceLogout()
    throw new ApiError(401, 'Session expired — please sign in again.')
  }

  if (!res.ok) {
    let detail: unknown = null
    try {
      detail = (await res.json()).detail
    } catch {
      // non-JSON error body (shouldn't happen with this backend)
    }
    throw new ApiError(res.status, flattenDetail(detail) || `Request failed (${res.status})`)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: 'POST', body }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: 'POST', formData }),
}

/** POST /auth/refresh without retry wiring — used by session restore. */
export async function refreshSession(): Promise<boolean> {
  return singleFlightRefresh()
}

/** POST /auth/logout — no auth header by design; the refresh token is the credential. */
export async function logout(): Promise<void> {
  const refresh = getRefreshToken()
  if (!refresh) return
  try {
    await fetch(`${BASE_URL}/auth/logout`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
  } catch {
    // Even if the call fails, the local session is done.
  } finally {
    clearTokens()
  }
}

// --- downloads -------------------------------------------------------------

/**
 * Downloads require an Authorization header, so a plain <a href> cannot work.
 * fetch → blob → objectURL → programmatic click → revoke.
 * The backend quotes Content-Disposition with single quotes where double
 * quotes were stripped, so parse loosely rather than trusting a strict RFC
 * pattern.
 */
export async function downloadNoteFile(noteId: number): Promise<void> {
  const res = await fetch(`${BASE_URL}/notes/${noteId}/download`, {
    headers: { Authorization: `Bearer ${getAccessToken() ?? ''}` },
  })
  if (!res.ok) {
    let detail: unknown = null
    try {
      detail = (await res.json()).detail
    } catch {
      /* stream error body may be empty */
    }
    throw new ApiError(res.status, flattenDetail(detail) || 'Download failed')
  }
  const blob = await res.blob()
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)"?/i.exec(disposition)
  const filename = match ? decodeURIComponent(match[1]) : 'note.pdf'

  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  // Give the browser a beat to start the download before releasing the URL.
  setTimeout(() => URL.revokeObjectURL(url), 1_000)
}
