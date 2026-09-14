interface PaginationProps {
  total: number
  limit: number
  offset: number
  onPage: (offset: number) => void
}

/** Prev/next pagination for limit/offset lists; shows the visible range. */
export function Pagination({ total, limit, offset, onPage }: PaginationProps) {
  const page = Math.floor(offset / limit) + 1
  const last = Math.max(1, Math.ceil(total / limit))
  const from = total === 0 ? 0 : offset + 1
  const to = Math.min(total, offset + limit)

  return (
    <div className="flex items-center justify-between text-sm text-slate-400">
      <p>
        {from}–{to} of {total}
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          disabled={offset === 0}
          onClick={() => onPage(Math.max(0, offset - limit))}
          className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40 enabled:hover:border-coin-dim"
        >
          ← Prev
        </button>
        <span className="tabular px-1 text-xs">
          {page} / {last}
        </span>
        <button
          type="button"
          disabled={offset + limit >= total}
          onClick={() => onPage(offset + limit)}
          className="rounded-lg border border-line px-3 py-1.5 disabled:opacity-40 enabled:hover:border-coin-dim"
        >
          Next →
        </button>
      </div>
    </div>
  )
}
