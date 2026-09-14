import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { getNote } from '../api/notes'
import { deleteNote } from '../api/notes'
import { downloadNoteFile, ApiError } from '../api/client'
import { useSession } from '../hooks/useSession'
import { ErrorText } from '../components/ErrorText'
import { Spinner } from '../components/Spinner'
import { ECONOMY } from '../lib/economy'
import { formatBytes, formatDate } from '../lib/format'

export function NoteDetailPage() {
  const noteId = Number(useParams().noteId)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useSession()

  const noteQuery = useQuery({
    queryKey: ['note', noteId],
    queryFn: () => getNote(noteId),
    enabled: Number.isInteger(noteId) && noteId > 0,
  })

  const [downloadError, setDownloadError] = useState<string | null>(null)
  const [downloading, setDownloading] = useState(false)

  const deleteMutation = useMutation({
    mutationFn: () => deleteNote(noteId),
    onSuccess: () => {
      // Soft delete: the note leaves every list, but no coins move.
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      queryClient.invalidateQueries({ queryKey: ['myNotes'] })
      navigate('/my', { replace: true })
    },
  })

  if (noteQuery.isLoading) {
    return (
      <div className="flex justify-center py-16">
        <Spinner className="h-6 w-6" />
      </div>
    )
  }

  if (noteQuery.isError || !noteQuery.data) {
    return (
      <div className="flex flex-col gap-4">
        <ErrorText error={noteQuery.error} />
        <Link to="/" className="text-sm text-coin hover:underline">
          ← Back to notes
        </Link>
      </div>
    )
  }

  const note = noteQuery.data
  const isOwner = user !== null && user.id === note.owner_id

  const handleDownload = async () => {
    setDownloadError(null)
    setDownloading(true)
    try {
      // fetch → blob → click (Authorization header required, so no <a href>).
      await downloadNoteFile(note.id)
      // Balance dropped by 5 (unless self-download) — refresh the chip.
      await queryClient.invalidateQueries({ queryKey: ['balance'] })
    } catch (err) {
      // 409 "Insufficient coins…" arrives here verbatim.
      setDownloadError(err instanceof ApiError ? err.message : 'Download failed — try again.')
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="flex flex-col gap-5">
      <Link to="/" className="text-sm text-slate-400 hover:text-slate-100">
        ← Back to notes
      </Link>

      <div className="rounded-xl border border-line bg-surface p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold text-slate-100">{note.title}</h1>
            <p className="mt-1 text-sm text-slate-400">
              {note.subject.code} — {note.subject.name}
              {note.chapter ? ` · ${note.chapter}` : ''}
            </p>
          </div>
          {isOwner && (
            <span className="rounded-md bg-coin/15 px-2 py-0.5 text-xs font-semibold text-coin">
              Your upload
            </span>
          )}
        </div>

        <dl className="mt-5 grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          <div>
            <dt className="text-xs text-slate-500">Pages</dt>
            <dd className="tabular text-slate-200">{note.page_count}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Size</dt>
            <dd className="tabular text-slate-200">{formatBytes(note.file_size)}</dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">File</dt>
            <dd className="truncate text-slate-200" title={note.original_filename}>
              {note.original_filename}
            </dd>
          </div>
          <div>
            <dt className="text-xs text-slate-500">Uploaded</dt>
            <dd className="text-slate-200">{formatDate(note.created_at)}</dd>
          </div>
        </dl>

        <div className="mt-6 flex flex-wrap items-center gap-3">
          {isOwner ? (
            <>
              <span className="rounded-lg border border-line px-4 py-2 text-sm text-slate-300">
                Download · Free (yours)
              </span>
              <button
                type="button"
                onClick={handleDownload}
                disabled={downloading}
                className="flex items-center gap-2 rounded-lg border border-coin-dim px-4 py-2 text-sm font-semibold text-coin hover:bg-coin/10 disabled:opacity-50"
              >
                {downloading && <Spinner className="border-coin/50 border-t-transparent" />}
                Save a copy
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={handleDownload}
              disabled={downloading}
              className="flex items-center gap-2 rounded-lg bg-coin px-4 py-2 text-sm font-semibold text-slate-950 hover:opacity-90 disabled:opacity-50"
            >
              {downloading && <Spinner className="border-slate-900/40 border-t-transparent" />}
              Download · {ECONOMY.DOWNLOAD_COST} coins
            </button>
          )}
          {isOwner && (
            <button
              type="button"
              onClick={() => {
                if (window.confirm('Delete this note? Other students will lose access. Coins already earned are not clawed back.')) {
                  deleteMutation.mutate()
                }
              }}
              disabled={deleteMutation.isPending}
              className="rounded-lg px-3 py-2 text-sm text-debit hover:underline disabled:opacity-50"
            >
              Delete
            </button>
          )}
        </div>
        {downloadError && (
          <div className="mt-3">
            <ErrorText error={downloadError} />
          </div>
        )}
      </div>
    </div>
  )
}
