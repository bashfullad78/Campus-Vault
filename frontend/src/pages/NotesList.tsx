import { useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { listNotes } from '../api/notes'
import { listSubjects } from '../api/subjects'
import type { SubjectOut } from '../api/types'
import { NoteCard } from '../components/NoteCard'
import { Pagination } from '../components/Pagination'
import { ErrorText } from '../components/ErrorText'
import { Spinner } from '../components/Spinner'

const PAGE_SIZE = 20

/** Group subjects under "Semester N" headings, in catalog order. */
function groupBySemester(subjects: SubjectOut[]): Map<number, SubjectOut[]> {
  const groups = new Map<number, SubjectOut[]>()
  for (const subject of subjects) {
    const list = groups.get(subject.semester) ?? []
    list.push(subject)
    groups.set(subject.semester, list)
  }
  return groups
}

export function NotesListPage() {
  const [subjectId, setSubjectId] = useState<number | null>(null)
  const [offset, setOffset] = useState(0)

  const subjectsQuery = useQuery({
    queryKey: ['subjects'],
    queryFn: () => listSubjects(),
    staleTime: Infinity, // the catalog is seed data; it never changes at runtime
  })

  const notesQuery = useQuery({
    queryKey: ['notes', { subjectId, offset }],
    queryFn: () => listNotes(subjectId, { limit: PAGE_SIZE, offset }),
    placeholderData: keepPreviousData, // keep the grid visible between pages
  })

  const subjects = subjectsQuery.data ?? []
  const groups = groupBySemester(subjects)
  const total = notesQuery.data?.total ?? 0

  const changeSubject = (value: string) => {
    setSubjectId(value === '' ? null : Number(value))
    setOffset(0) // any filter change restarts pagination
  }

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100">Browse notes</h1>
        <label className="flex items-center gap-2 text-sm text-slate-400">
          Subject
          <select
            value={subjectId ?? ''}
            onChange={(e) => changeSubject(e.target.value)}
            className="max-w-60 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-sm text-slate-100 outline-none focus:border-coin"
          >
            <option value="">All subjects</option>
            {[...groups.entries()].map(([semester, list]) => (
              <optgroup key={semester} label={`Semester ${semester}`}>
                {list.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.code} — {subject.name}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
      </div>

      <ErrorText error={notesQuery.error ?? subjectsQuery.error} />

      {notesQuery.isLoading ? (
        <div className="flex justify-center py-16">
          <Spinner className="h-6 w-6" />
        </div>
      ) : (
        <>
          {total === 0 ? (
            <div className="rounded-xl border border-line bg-surface px-4 py-12 text-center">
              <p className="text-sm text-slate-300">
                {subjectId !== null
                  ? 'No notes for this subject yet.'
                  : 'No notes yet — be the first to upload.'}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                Uploads earn +10 coins each (up to 5 a day).
              </p>
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {notesQuery.data?.notes.map((note) => (
                <NoteCard key={note.id} note={note} />
              ))}
            </div>
          )}
          {total > PAGE_SIZE && (
            <Pagination
              total={total}
              limit={PAGE_SIZE}
              offset={offset}
              onPage={setOffset}
            />
          )}
        </>
      )}
    </div>
  )
}
