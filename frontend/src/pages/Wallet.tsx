import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { getBalance, listTransactions } from '../api/coins'
import { ErrorText } from '../components/ErrorText'
import { Spinner } from '../components/Spinner'
import { ECONOMY } from '../lib/economy'
import { formatCoins, formatDateTime, transactionLabel } from '../lib/format'

const PAGE_SIZE = 25

export function WalletPage() {
  const [offset, setOffset] = useState(0)

  const balanceQuery = useQuery({
    queryKey: ['balance'],
    queryFn: getBalance,
  })

  const txQuery = useQuery({
    queryKey: ['transactions', { limit: PAGE_SIZE, offset }],
    queryFn: () => listTransactions({ limit: PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  })

  const transactions = txQuery.data ?? []
  const canLoadMore = transactions.length === PAGE_SIZE

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5">
      <h1 className="text-lg font-bold text-slate-100">Wallet</h1>

      <div className="rounded-xl border border-line bg-surface p-6">
        <p className="text-xs uppercase tracking-wide text-slate-500">Balance</p>
        <p className="tabular mt-1 flex items-baseline gap-2 text-4xl font-bold text-coin">
          ◎ {balanceQuery.isLoading ? '…' : (balanceQuery.data?.balance ?? '—')}
        </p>
        <p className="mt-2 text-xs text-slate-500">
          Uploads earn +{ECONOMY.UPLOAD_REWARD} (max {ECONOMY.DAILY_REWARD_CAP}/day) · downloads
          cost −{ECONOMY.DOWNLOAD_COST}
        </p>
        {balanceQuery.error && (
          <div className="mt-3">
            <ErrorText error={balanceQuery.error} />
          </div>
        )}
      </div>

      <h2 className="text-sm font-semibold text-slate-300">Ledger</h2>
      <ErrorText error={txQuery.error} />

      {txQuery.isLoading ? (
        <div className="flex justify-center py-10">
          <Spinner className="h-6 w-6" />
        </div>
      ) : transactions.length === 0 ? (
        <p className="rounded-xl border border-line bg-surface px-4 py-10 text-center text-sm text-slate-400">
          No transactions yet — upload a PDF to earn your first coins.
        </p>
      ) : (
        <ul className="overflow-hidden rounded-xl border border-line bg-surface">
          {transactions.map((tx, index) => (
            <li
              key={tx.id}
              className={`flex items-center justify-between gap-3 px-4 py-3 ${
                index > 0 ? 'border-t border-line' : ''
              }`}
            >
              <div className="min-w-0">
                <p className="text-sm text-slate-200">{transactionLabel(tx.transaction_type)}</p>
                <p className="text-xs text-slate-500">{formatDateTime(tx.created_at)}</p>
              </div>
              <p
                className={`tabular shrink-0 text-sm font-semibold ${
                  tx.amount >= 0 ? 'text-credit' : 'text-debit'
                }`}
              >
                {formatCoins(tx.amount)}
              </p>
            </li>
          ))}
        </ul>
      )}

      {canLoadMore && (
        <button
          type="button"
          disabled={txQuery.isFetching}
          onClick={() => setOffset((current) => current + PAGE_SIZE)}
          className="mx-auto rounded-lg border border-line px-4 py-2 text-sm text-slate-300 hover:border-coin-dim disabled:opacity-50"
        >
          {txQuery.isFetching ? 'Loading…' : 'Load more'}
        </button>
      )}
    </div>
  )
}
