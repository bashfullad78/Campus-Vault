/*
 * Display formatting helpers. All coin amounts use tabular numerals (CSS
 * handles the font side); these helpers handle signs and copy.
 */

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

/** Signed amount with an explicit plus for credits. */
export function formatCoins(amount: number): string {
  return amount > 0 ? `+${amount}` : String(amount)
}

export function formatBalance(amount: number): string {
  return String(amount)
}

// --- ledger copy -----------------------------------------------------------

const TRANSACTION_LABEL: Record<string, string> = {
  UPLOAD_REWARD: 'Upload reward',
  NOTE_DOWNLOAD: 'Note download',
  ADMIN_ADJUSTMENT: 'Admin adjustment',
}

export function transactionLabel(type: string): string {
  return TRANSACTION_LABEL[type] ?? type
}

// --- daily-cap accounting --------------------------------------------------

/** Uploads reward +10 coins, capped at 5 successful rewards per UTC day. */
export const DAILY_REWARD_CAP = 5

/**
 * Count UPLOAD_REWARD rows that landed today, in UTC — the server counts
 * against UTC midnight, so the client progress indicator must match that,
 * not local midnight.
 */
export function countTodaysRewards(
  transactions: { amount: number; transaction_type: string; created_at: string }[],
): number {
  const todayPrefix = new Date().toISOString().slice(0, 10) // UTC YYYY-MM-DD
  return transactions.filter(
    (t) => t.transaction_type === 'UPLOAD_REWARD' && t.created_at.startsWith(todayPrefix),
  ).length
}
