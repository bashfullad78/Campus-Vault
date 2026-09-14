import { api, setTokens, clearTokens } from './client'
import type { TokenResponse, UserOut } from './types'

export interface RegisterPayload {
  email: string
  name: string
  password: string
}

export interface LoginPayload {
  email: string
  password: string
}

export async function register(payload: RegisterPayload): Promise<UserOut> {
  // 201 on success; 409 email exists (message shown verbatim).
  return api.post<UserOut>('/auth/register', payload)
}

export async function login(payload: LoginPayload): Promise<TokenResponse> {
  // 401 "Invalid email or password" — identical for unknown email and wrong
  // password by server design, so the UI cannot leak which one failed.
  const tokens = await api.post<TokenResponse>('/auth/login', payload)
  setTokens(tokens.access_token, tokens.refresh_token)
  return tokens
}

export async function fetchMe(): Promise<UserOut> {
  return api.get<UserOut>('/auth/me')
}

/** Local-only sign-out helper; server revocation lives in client.ts logout(). */
export function forgetLocalSession(): void {
  clearTokens()
}
