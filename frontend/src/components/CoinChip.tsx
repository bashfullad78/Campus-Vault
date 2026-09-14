import { useQuery } from '@tanstack/react-query'
import { getBalance } from '../api/coins'
import { ECONOMY } from '../lib/economy'
import { formatBalance } from '../lib/format'

/**
 * The coin chip in the nav: live balance + a short pop animation whenever
 * the balance changes (frontend.txt §7 build item 7).
 *
 * The animation replays via the `key` prop: a new balance remounts the
 * <span>, restarting the CSS animation — no state, no effect.
 */
export function CoinChip() {
  const { data } = useQuery({
    queryKey: ['balance'],
    queryFn: getBalance,
    staleTime: 15_000,
  })

  const balance = data?.balance

  return (
    <span
      key={balance}
      className={`tabular inline-flex items-center gap-1.5 rounded-lg border border-line bg-surface px-2.5 py-1 text-sm font-semibold text-coin ${
        balance !== undefined ? 'coin-pop' : ''
      }`}
      title={`Uploads earn ${ECONOMY.UPLOAD_REWARD} coins (max ${ECONOMY.DAILY_REWARD_CAP}/day) · Downloads cost ${ECONOMY.DOWNLOAD_COST}`}
    >
      <span aria-hidden>◎</span>
      {balance === undefined ? '—' : formatBalance(balance)}
    </span>
  )
}
