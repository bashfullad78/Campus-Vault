import { api } from './client'
import type { SubjectOut } from './types'

export async function listSubjects(semester?: number): Promise<SubjectOut[]> {
  const query = semester !== undefined ? `?semester=${semester}` : ''
  return api.get<SubjectOut[]>(`/subjects${query}`)
}
