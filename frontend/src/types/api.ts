// Shared API response shapes for the GhostOS frontend.
//
// These are the frontend's PROPOSED contract. Developer 1 owns the canonical
// schemas; keep this file in sync with the FastAPI models once they land.
// Field names are snake_case to match the Python side verbatim.

export type Category = 'invoice' | 'receipt' | 'other' | 'uncertain'

export type FileType = 'pdf' | 'txt' | 'csv'

/** GET /api/status — shown permanently in the status bar (offline promise). */
export interface SystemStatus {
  backend_endpoint: string // e.g. "http://127.0.0.1:8000"
  model_name: string // e.g. "qwen3:4b-instruct"
  model_endpoint: string // e.g. "http://127.0.0.1:11434"
  model_loaded: boolean
  external_requests: number // count of non-loopback requests this session; must stay 0
  last_inference_ms: number | null
  last_inference_at: string | null // ISO timestamp
}

/**
 * POST /api/scan  body: ScanRequest  ->  ScanProgress   (starts the job, returns immediately)
 * GET  /api/scans/{scan_id}/progress  ->  ScanProgress  (UI polls ~every 500ms)
 * GET  /api/scans/{scan_id}           ->  ScanResult    (once state === 'done')
 */
export interface ScanRequest {
  root: string // absolute path of the user-selected folder
}

export interface ScanProgress {
  scan_id: string
  state: 'running' | 'done' | 'error'
  files_total: number
  files_processed: number
  current_file: string | null // relative path being classified right now
  error: string | null // e.g. "Folder does not exist", "Model not loaded"
}

export type SkipReason =
  | 'unsupported_type'
  | 'too_large'
  | 'unreadable'
  | 'symlink'
  | 'no_extractable_text'
  | 'file_limit_reached'

export interface SkippedFile {
  relative_path: string
  reason: SkipReason
  detail: string // human-readable, shown verbatim in the UI
}

export interface ScanResult {
  scan_id: string
  root: string
  scanned_at: string // ISO timestamp
  files_seen: number
  max_files: number // 100 per the MVP spec
  documents: DocumentRecord[]
  skipped: SkippedFile[]
}

/** Output of the model call AFTER backend validation. source_id is bound in code, not by the model. */
export interface Classification {
  category: Category
  merchant: string | null
  date: string | null // ISO yyyy-mm-dd, null if not found/unparseable
  amount_text: string | null // raw text as it appears in the document
  amount: string | null // Decimal serialized as string, e.g. "1250.00"; null if unparseable/conflicting
  currency: string | null // ISO 4217, e.g. "PHP"
  evidence_quote: string | null
  evidence_verified: boolean // backend checked evidence_quote occurs in extracted text
  explanation: string
}

export type ReviewFlagCode =
  | 'evidence_not_found'
  | 'amount_unparseable'
  | 'amount_conflict'
  | 'missing_date'
  | 'missing_amount'
  | 'missing_merchant'
  | 'missing_currency'
  | 'invalid_currency'
  | 'currency_mismatch'
  | 'missing_evidence_quote'
  | 'uncertain_classification'
  | 'low_confidence'
  | 'model_error'
  | 'possible_injection'

export interface ReviewFlag {
  code: ReviewFlagCode
  message: string
}

export type DocumentStatus = 'ok' | 'needs_review' | 'failed'

export interface DocumentRecord {
  file_id: string
  relative_path: string // relative to scan root, forward slashes
  file_type: FileType
  size_bytes: number
  sha256: string
  excerpt: string // the bounded text excerpt sent to the model
  status: DocumentStatus
  classification: Classification | null // null when extraction/model failed
  review_flags: ReviewFlag[]
  duplicate_of: string | null // file_id of an exact-hash duplicate (informational only)
  user_corrected: boolean
}

/** PATCH /api/documents/{file_id}  body: DocumentCorrection  ->  DocumentRecord */
export interface DocumentCorrection {
  category?: Category
  merchant?: string | null
  date?: string | null
  amount?: string | null
  currency?: string | null
  /** Mark as reviewed by a human; clears review flags. */
  accept: boolean
}

/** GET /api/scans/{scan_id}/plan  ->  PlanPreview. No writes happen here. */
export interface ProposedOperation {
  file_id: string
  original_relative_path: string
  destination_relative_path: string // constructed by code from the category map, never by the model
  reason: string
  collision_suffixed: boolean
}

export type ReportRowStatus = 'accepted' | 'needs_review'

export interface ReportRow {
  file_id: string
  source_filename: string
  category: 'invoice' | 'receipt'
  date: string | null
  merchant: string | null
  amount: string | null
  currency: string | null
  status: ReportRowStatus
}

export interface CurrencyTotal {
  currency: string
  amount: string // sum of ACCEPTED rows only, Decimal as string
  row_count: number
}

export interface PlanPreview {
  plan_id: string
  scan_id: string
  operations: ProposedOperation[]
  report_rows: ReportRow[]
  totals: CurrencyTotal[]
  blocking_review_count: number // approval is disabled while > 0
}

/** POST /api/plans/{plan_id}/approve  ->  BatchResult */
export interface BatchResult {
  batch_id: string
  moved: number
  failed: { file_id: string; error: string }[]
  report_relative_path: string // e.g. "GhostOS Reports/expenses-2026-10-09T1412.csv"
  committed_at: string
}

/** POST /api/batches/{batch_id}/undo  ->  UndoResult */
export interface UndoResult {
  batch_id: string
  restored: number
  conflicts: { file_id: string; relative_path: string; reason: string }[]
}
