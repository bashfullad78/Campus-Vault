import { api } from './client'
import type { PageParams, WalletBalanceOut, WalletTransactionOut } from './types'

export async function getBalance(): Promise<WalletBalanceOut> {
  return api.get<WalletBalanceOut>('/coins/balance')
}

export async function listTransactions(
  page: PageParams = {},
): Promise<WalletTransactionOut[]> {
  const params = new URLSearchParams()
  if (page.limit !== undefined) params.set('limit', String(page.limit))
  if (page.offset !== undefined) params.set('offset', String(page.offset))
  const qs = params.toString()
  return api.get<WalletTransactionOut[]>(`/coins/transactions${qs ? `?${qs}` : ''}`)
}
