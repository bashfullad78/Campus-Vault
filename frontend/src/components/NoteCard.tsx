import { Link } from 'react-router-dom'
import type { NoteOut } from '../api/types'
import { formatBytes, formatDate } from '../lib/format'

/**
 * One note in the browse grid. Shows "Uploaded {date}" — the API exposes
 * owner_id only, never a name, and the frontend does not get to change that
 * (frontend.txt §4.1).
 */
export function NoteCard({ note }: { note: NoteOut }) {
  return (
    <Link
      to={`/notes/${note.id}`}
      className="flex flex-col gap-2 rounded-xl border border-line bg-surface p-4 transition-colors hover:border-coin-dim"
    >
      <div className="flex items-start justify-between gap-2">
        <h3 className="font-semibold leading-snug text-slate-100">{note.title}</h3>
        <span className="shrink-0 rounded-md bg-surface-raised px-2 py-0.5 text-xs font-medium text-slate-300">
          {note.subject.code}
        </span>
      </div>
      {note.chapter && (
        <p className="text-sm text-slate-400">{note.chapter}</p>
      )}
      <p className="mt-auto text-xs text-slate-500">
        {note.subject.name} · {note.page_count} pages · {formatBytes(note.file_size)}
      </p>
      <p className="text-xs text-slate-500">Uploaded {formatDate(note.created_at)}</p>
    </Link>
  )
}
