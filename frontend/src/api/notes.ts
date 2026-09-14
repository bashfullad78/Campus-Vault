import { api } from './client'
import type { NoteListOut, NoteOut, PageParams, UploadPayload } from './types'

function pageQuery(page: PageParams): string {
  const params = new URLSearchParams()
  if (page.limit !== undefined) params.set('limit', String(page.limit))
  if (page.offset !== undefined) params.set('offset', String(page.offset))
  const qs = params.toString()
  return qs ? `?${qs}` : ''
}

export async function listNotes(
  subjectId: number | null,
  page: PageParams = {},
): Promise<NoteListOut> {
  const qs = pageQuery(page)
  const subjectQs = subjectId !== null ? `${qs ? '&' : '?'}subject_id=${subjectId}` : ''
  return api.get<NoteListOut>(`/notes${qs}${subjectQs}`)
}

export async function listMyNotes(page: PageParams = {}): Promise<NoteListOut> {
  return api.get<NoteListOut>(`/notes/my${pageQuery(page)}`)
}

export async function getNote(id: number): Promise<NoteOut> {
  return api.get<NoteOut>(`/notes/${id}`)
}

export async function uploadNote(payload: UploadPayload): Promise<NoteOut> {
  const formData = new FormData()
  formData.append('subject_id', String(payload.subject_id))
  formData.append('title', payload.title)
  if (payload.chapter) formData.append('chapter', payload.chapter)
  formData.append('file', payload.file)
  // 201 on success; 404 unknown subject · 409 duplicate · 413 too large ·
  // 422 invalid PDF — all surfaced verbatim by the upload page.
  return api.upload<NoteOut>('/notes', formData)
}

export async function deleteNote(id: number): Promise<void> {
  // Owner only → 403 otherwise. Soft delete; balance is never clawed back.
  await api.del<{ detail: string }>(`/notes/${id}`)
}
