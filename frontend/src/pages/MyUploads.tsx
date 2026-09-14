import { useState } from 'react'
import { Link } from 'react-router-dom'
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { deleteNote, listMyNotes } from '../api/notes'
import type { NoteOut } from '../api/types'
import { ErrorText } from '../components/ErrorText'
import { Pagination } from '../components/Pagination'
import { Spinner } from '../components/Spinner'
import { formatBytes, formatDate } from '../lib/format'

const PAGE_SIZE = 20

export function MyUploadsPage() {
  const queryClient = useQueryClient()
  const [offset, setOffset] = useState(0)
  const [deletingId, setDeletingId] = useState<number | null>(null)

  const notesQuery = useQuery({
    queryKey: ['myNotes', offset],
    queryFn: () => listMyNotes({ limit: PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  })

  const deleteMutation = useMutation({
    mutationFn: (noteId: number) => deleteNote(noteId),
    onSuccess: () => {
      // Soft delete: the note disappears from lists. Coins are NOT clawed
      // back server-side, so there is deliberately no coin animation here.
      queryClient.invalidateQueries({ queryKey: ['myNotes'] })
      queryClient.invalidateQueries({ queryKey: ['notes'] })
    },
    onSettled: () => setDeletingId(null),
  })

  const handleDelete = (note: NoteOut) => {
    const sure = window.confirm(
      `Delete “${note.title}”? Students will no longer find it. Coins already earned are kept.`,
    )
    if (sure) {
      setDeletingId(note.id)
      deleteMutation.mutate(note.id)
    }
  }

  const notes = notesQuery.data?.notes ?? []
  const total = notesQuery.data?.total ?? 0

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100">My uploads</h1>
        <Link
          to="/upload"
          className="rounded-lg bg-coin px-3 py-1.5 text-sm font-semibold text-slate-950 hover:opacity-90"
        >
          + Upload
        </Link>
      </div>

      <ErrorText error={notesQuery.error ?? deleteMutation.error} />

      {notesQuery.isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-6 w-6" />
        </div>
      ) : notes.length === 0 ? (
        <div className="rounded-xl border border-line bg-surface px-4 py-12 text-center">
          <p className="text-sm text-slate-300">You haven't uploaded anything yet.</p>
          <p className="mt-1 text-xs text-slate-500">
            Your first PDF earns +10 coins.
          </p>
        </div>
      ) : (
        <ul className="flex flex-col gap-3">
          {notes.map((note) => (
            <li
              key={note.id}
              className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-surface p-4"
            >
              <div className="min-w-0 flex-1">
                <Link
                  to={`/notes/${note.id}`}
                  className="font-semibold text-slate-100 hover:text-coin"
                >
                  {note.title}
                </Link>
                <p className="mt-0.5 text-xs text-slate-500">
                  {note.subject.code} · {note.page_count} pages ·{' '}
                  {formatBytes(note.file_size)} · Uploaded {formatDate(note.created_at)}
                </p>
              </div>
              <Link
                to={`/notes/${note.id}`}
                className="rounded-lg border border-line px-3 py-1.5 text-sm text-slate-300 hover:border-coin-dim"
              >
                View
              </Link>
              <button
                type="button"
                onClick={() => handleDelete(note)}
                disabled={deleteMutation.isPending && deletingId === note.id}
                className="rounded-lg px-3 py-1.5 text-sm text-debit hover:underline disabled:opacity-50"
              >
                {deleteMutation.isPending && deletingId === note.id ? 'Deleting…' : 'Delete'}
              </button>
            </li>
          ))}
        </ul>
      )}

      {total > PAGE_SIZE && (
        <Pagination total={total} limit={PAGE_SIZE} offset={offset} onPage={setOffset} />
      )}
    </div>
  )
}
