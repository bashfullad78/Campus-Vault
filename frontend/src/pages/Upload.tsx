import { useRef, useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { uploadNote } from '../api/notes'
import { listSubjects } from '../api/subjects'
import { getBalance } from '../api/coins'
import { listTransactions } from '../api/coins'
import type { NoteOut } from '../api/types'
import { ErrorText } from '../components/ErrorText'
import { Spinner } from '../components/Spinner'
import { ECONOMY } from '../lib/economy'
import { countTodaysRewards, formatBytes } from '../lib/format'

const MAX_BYTES = ECONOMY.MAX_FILE_SIZE_MB * 1024 * 1024

type UploadOutcome =
  | { kind: 'rewarded'; note: NoteOut; delta: number }
  | { kind: 'capped'; note: NoteOut }
  | { kind: 'uploaded'; note: NoteOut; delta: number | null }

/**
 * Client-side pre-checks mirror the server limits for fast feedback.
 * The server remains the source of truth — these only catch obvious misses.
 */
function validateFile(file: File): string | null {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    return 'Only PDF files are accepted.'
  }
  if (file.size > MAX_BYTES) {
    return `File is larger than the ${ECONOMY.MAX_FILE_SIZE_MB} MB limit (${formatBytes(file.size)}).`
  }
  return null
}

export function UploadPage() {
  const queryClient = useQueryClient()
  const inputRef = useRef<HTMLInputElement>(null)

  const [file, setFile] = useState<File | null>(null)
  const [fileError, setFileError] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const [subjectId, setSubjectId] = useState('')
  const [title, setTitle] = useState('')
  const [chapter, setChapter] = useState('')
  const [outcome, setOutcome] = useState<UploadOutcome | null>(null)

  const subjectsQuery = useQuery({
    queryKey: ['subjects'],
    queryFn: () => listSubjects(),
    staleTime: Infinity,
  })

  // Daily-cap progress ("3/5 rewarded today") is computed client-side from
  // the ledger, counting against UTC midnight to match the server.
  const transactionsQuery = useQuery({
    queryKey: ['transactions', { limit: 50, offset: 0 }],
    queryFn: () => listTransactions({ limit: 50, offset: 0 }),
    staleTime: 30_000,
  })
  const rewardedToday = countTodaysRewards(transactionsQuery.data ?? [])

  const uploadMutation = useMutation({
    mutationFn: async (): Promise<UploadOutcome> => {
      // Capture the balance BEFORE the upload: the response does not say
      // whether the reward was granted (the daily cap is silent server-side),
      // so the UI can only infer it from the delta (frontend.txt §4.2).
      const before = await queryClient.fetchQuery({
        queryKey: ['balance'],
        queryFn: getBalance,
      })
      const note = await uploadNote({
        subject_id: Number(subjectId),
        title: title.trim(),
        chapter: chapter.trim() || undefined,
        file: file!,
      })
      const after = await queryClient.fetchQuery({
        queryKey: ['balance'],
        queryFn: getBalance,
      })
      queryClient.setQueryData(['balance'], after)
      const delta = after.balance - before.balance
      if (delta >= ECONOMY.UPLOAD_REWARD) {
        return { kind: 'rewarded', note, delta }
      }
      if (delta === 0) {
        return { kind: 'capped', note }
      }
      return { kind: 'uploaded', note, delta }
    },
    onSuccess: (result) => {
      setOutcome(result)
      // New note must appear in lists immediately.
      queryClient.invalidateQueries({ queryKey: ['notes'] })
      queryClient.invalidateQueries({ queryKey: ['myNotes'] })
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      // Reset the form for the next upload.
      setFile(null)
      setTitle('')
      setChapter('')
      setSubjectId('')
      if (inputRef.current) inputRef.current.value = ''
    },
  })

  const acceptFile = (candidate: File | null | undefined) => {
    setOutcome(null)
    if (!candidate) return
    setFileError(validateFile(candidate))
    setFile(candidate)
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!file || !subjectId || uploadMutation.isPending) return
    if (fileError) return
    setOutcome(null)
    uploadMutation.mutate()
  }

  const subjects = subjectsQuery.data ?? []

  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <h1 className="text-lg font-bold text-slate-100">Upload a note</h1>

      <p className="tabular text-sm text-slate-400">
        Rewarded today: {rewardedToday}/{ECONOMY.DAILY_REWARD_CAP} · +{ECONOMY.UPLOAD_REWARD}{' '}
        coins per upload
      </p>

      {outcome && (
        <div className="relative rounded-xl border border-credit/40 bg-credit/10 p-4 text-sm text-slate-200">
          {outcome.kind === 'rewarded' && (
            <span
              className="coin-rise tabular absolute -top-1 right-4 font-bold text-coin"
              aria-hidden
            >
              +{outcome.delta} coins
            </span>
          )}
          <p className="font-semibold text-credit">
            Uploaded “{outcome.note.title}”.
          </p>
          <p className="mt-1 text-slate-400">
            {outcome.kind === 'rewarded' && (
              <>
                +{outcome.delta} coins added to your wallet.
              </>
            )}
            {outcome.kind === 'capped' && (
              <>
                Daily reward cap reached ({ECONOMY.DAILY_REWARD_CAP}/{ECONOMY.DAILY_REWARD_CAP}) —
                no coins this time.
              </>
            )}
            {outcome.kind === 'uploaded' && (
              <>
                Your wallet moved by {outcome.delta} coins — see the ledger for details.
              </>
            )}
          </p>
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        {/* Drag-drop target doubles as the file picker trigger. */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => inputRef.current?.click()}
          onKeyDown={(e) => e.key === 'Enter' && inputRef.current?.click()}
          onDragOver={(e) => {
            e.preventDefault()
            setDragging(true)
          }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault()
            setDragging(false)
            acceptFile(e.dataTransfer.files?.[0])
          }}
          className={`cursor-pointer rounded-xl border border-dashed px-4 py-8 text-center transition-colors ${
            dragging ? 'border-coin bg-coin/5' : 'border-line bg-surface hover:border-coin-dim'
          }`}
        >
          {file ? (
            <p className="text-sm text-slate-200">
              {file.name}{' '}
              <span className="tabular text-slate-500">({formatBytes(file.size)})</span>
            </p>
          ) : (
            <>
              <p className="text-sm text-slate-300">Drop a PDF here, or click to choose</p>
              <p className="mt-1 text-xs text-slate-500">
                Max {ECONOMY.MAX_FILE_SIZE_MB} MB · {ECONOMY.MIN_PAGES}–{ECONOMY.MAX_PAGES} pages
              </p>
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept="application/pdf,.pdf"
            className="hidden"
            onChange={(e) => acceptFile(e.target.files?.[0])}
          />
        </div>
        {fileError && <ErrorText error={fileError} />}

        <label className="flex flex-col gap-1.5">
          <span className="text-sm text-slate-300">Subject</span>
          <select
            required
            value={subjectId}
            onChange={(e) => setSubjectId(e.target.value)}
            className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-sm text-slate-100 outline-none focus:border-coin"
          >
            <option value="" disabled>
              Choose a subject…
            </option>
            {subjects.map((subject) => (
              <option key={subject.id} value={subject.id}>
                Sem {subject.semester} · {subject.code} — {subject.name}
              </option>
            ))}
          </select>
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm text-slate-300">Title</span>
          <input
            type="text"
            required
            maxLength={255}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-sm text-slate-100 outline-none focus:border-coin"
            placeholder="e.g. DBMS unit 3 — normalization"
          />
        </label>

        <label className="flex flex-col gap-1.5">
          <span className="text-sm text-slate-300">Chapter (optional)</span>
          <input
            type="text"
            maxLength={255}
            value={chapter}
            onChange={(e) => setChapter(e.target.value)}
            className="rounded-lg border border-line bg-surface-raised px-3 py-2 text-sm text-slate-100 outline-none focus:border-coin"
            placeholder="e.g. Ch 4"
          />
        </label>

        <ErrorText error={uploadMutation.error} />

        <button
          type="submit"
          disabled={!file || !subjectId || Boolean(fileError) || uploadMutation.isPending}
          className="flex items-center justify-center gap-2 rounded-lg bg-coin px-4 py-2 text-sm font-semibold text-slate-950 transition-opacity hover:opacity-90 disabled:opacity-50"
        >
          {uploadMutation.isPending && (
            <>
              <Spinner className="border-slate-900/40 border-t-transparent" />
              Uploading…
            </>
          )}
          {!uploadMutation.isPending && `Upload · earn ${ECONOMY.UPLOAD_REWARD} coins`}
        </button>
      </form>
    </div>
  )
}
