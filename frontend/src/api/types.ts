/*
 * Client-side types mirroring backend/schemas — kept hand-written and exact.
 * NoteOut excludes storage_key and file_hash on the server; that must stay
 * true here too. Internal storage details never reach the client.
 */

// --- auth / users ---------------------------------------------------------

export interface UserOut {
  id: number
  email: string
  name: string
  role: string
  is_active: boolean
  created_at: string
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string // always "bearer"
}

// --- subjects -------------------------------------------------------------

export interface SubjectOut {
  id: number
  code: string
  name: string
  semester: number
  created_at: string
}

// --- notes ----------------------------------------------------------------

export type NoteStatus = 'ACTIVE' | 'DELETED'

export interface NoteOut {
  id: number
  owner_id: number
  subject_id: number
  title: string
  chapter: string | null
  original_filename: string
  file_size: number
  page_count: number
  status: NoteStatus
  subject: SubjectOut
  created_at: string
  updated_at: string
}

export interface NoteListOut {
  notes: NoteOut[]
  total: number
}

export interface UploadPayload {
  subject_id: number
  title: string
  chapter?: string
  file: File
}

// --- coins / wallet -------------------------------------------------------

export type TransactionType =
  | 'UPLOAD_REWARD'
  | 'NOTE_DOWNLOAD'
  | 'ADMIN_ADJUSTMENT'

export type ReferenceType = 'NOTE' | 'ADMIN'

export interface WalletBalanceOut {
  balance: number
}

export interface WalletTransactionOut {
  id: number
  amount: number // signed: + credit, − debit
  transaction_type: TransactionType
  reference_type: ReferenceType | null
  reference_id: number | null
  created_at: string
}

// --- shared ---------------------------------------------------------------

/** Pagination envelope shared by list endpoints (limit/offset + total). */
export interface PageParams {
  limit?: number
  offset?: number
}
