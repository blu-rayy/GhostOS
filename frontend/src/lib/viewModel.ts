/**
 * Maps the backend contract (types/api.ts) onto what the screens display.
 * Pure functions only: no fetching, no state.
 */
import type {
  Category,
  DocumentRecord,
  PlanPreview,
  ProposedOperation,
  ReviewFlag,
  ReviewFlagCode,
  ScanResult,
  SkippedFile,
} from '../types/api'
import type { RowStatus } from '../types/ui'

export function basename(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

export function dirname(path: string): string {
  const i = path.lastIndexOf('/')
  return i >= 0 ? path.slice(0, i + 1) : ''
}

export function docStatus(d: DocumentRecord): RowStatus {
  if (d.user_corrected) return 'reviewed'
  if (d.status === 'failed') return 'failed'
  if (d.status === 'needs_review') return 'needs_review'
  return 'extracted'
}

/** True when this document blocks approval (mirrors blocking_review_count). */
export function isBlocking(d: DocumentRecord): boolean {
  return d.status === 'needs_review' && !d.user_corrected
}

/** Which field a review flag is about, so the detail panel can show it next to that field. */
export type FlagTarget = 'category' | 'merchant' | 'date' | 'amount' | 'evidence' | 'document'

export const FLAG_TARGET: Record<ReviewFlagCode, FlagTarget> = {
  evidence_not_found: 'evidence',
  amount_unparseable: 'amount',
  amount_conflict: 'amount',
  missing_date: 'date',
  missing_amount: 'amount',
  low_confidence: 'category',
  model_error: 'document',
  possible_injection: 'document',
}

export function flagsFor(d: DocumentRecord, target: FlagTarget): ReviewFlag[] {
  if (d.user_corrected) return []
  return d.review_flags.filter((f) => FLAG_TARGET[f.code] === target)
}

export interface FileRow {
  id: string
  filename: string
  relPath: string
  dir: string
  fileType: string
  category: Category | null
  merchant: string | null
  date: string | null
  amount: string | null
  currency: string | null
  status: RowStatus
  flags: ReviewFlag[]
  duplicateOf: string | null
  /** Destination from the plan, or null when the file stays where it is. */
  destination: string | null
  doc: DocumentRecord | null
  skip: SkippedFile | null
}

export function buildFileRows(scan: ScanResult | null, plan: PlanPreview | null): FileRow[] {
  if (!scan) return []
  const ops = new Map((plan?.operations ?? []).map((o) => [o.file_id, o]))
  const docs: FileRow[] = scan.documents.map((d) => {
    const c = d.classification
    return {
      id: d.file_id,
      filename: basename(d.relative_path),
      relPath: d.relative_path,
      dir: dirname(d.relative_path),
      fileType: d.file_type,
      category: c?.category ?? null,
      merchant: c?.merchant ?? null,
      date: c?.date ?? null,
      amount: c?.amount ?? null,
      currency: c?.currency ?? null,
      status: docStatus(d),
      flags: d.user_corrected ? [] : d.review_flags,
      duplicateOf: d.duplicate_of,
      destination: ops.get(d.file_id)?.destination_relative_path ?? null,
      doc: d,
      skip: null,
    }
  })
  const skipped: FileRow[] = scan.skipped.map((s) => ({
    id: `skip:${s.relative_path}`,
    filename: basename(s.relative_path),
    relPath: s.relative_path,
    dir: dirname(s.relative_path),
    fileType: s.relative_path.includes('.') ? s.relative_path.slice(s.relative_path.lastIndexOf('.') + 1) : '—',
    category: null,
    merchant: null,
    date: null,
    amount: null,
    currency: null,
    status: 'skipped',
    flags: [],
    duplicateOf: null,
    destination: null,
    doc: null,
    skip: s,
  }))
  return [...docs, ...skipped]
}

/* ---------- Organization plan ---------- */

export type PlanAction = 'move' | 'review_folder' | 'leave'

export interface PlanWarning {
  kind: 'collision' | 'duplicate' | 'review' | 'failed' | 'skipped'
  message: string
}

export interface PlanRow {
  fileId: string
  from: string
  to: string | null
  action: PlanAction
  category: Category | null
  reason: string
  warnings: PlanWarning[]
  blocking: boolean
}

const REVIEW_FOLDER = 'Needs Review/'

/** One row per scanned document (moves and non-moves) plus skipped files, for the plan screen. */
export function buildPlanRows(scan: ScanResult | null, plan: PlanPreview | null): PlanRow[] {
  if (!scan || !plan) return []
  const ops = new Map<string, ProposedOperation>(plan.operations.map((o) => [o.file_id, o]))
  const byId = new Map(scan.documents.map((d) => [d.file_id, d]))
  const rows: PlanRow[] = scan.documents.map((d) => {
    const op = ops.get(d.file_id)
    const warnings: PlanWarning[] = []
    if (op?.collision_suffixed) warnings.push({ kind: 'collision', message: 'Name already taken at the destination, so a numeric suffix was added. Nothing is overwritten.' })
    if (d.duplicate_of) warnings.push({ kind: 'duplicate', message: `Same content hash as ${basename(byId.get(d.duplicate_of)?.relative_path ?? d.duplicate_of)}. Informational only; nothing is deleted.` })
    if (isBlocking(d)) warnings.push({ kind: 'review', message: d.review_flags[0]?.message ?? 'Needs review before approval.' })
    if (d.status === 'failed' && !d.user_corrected) warnings.push({ kind: 'failed', message: d.review_flags[0]?.message ?? 'Extraction failed.' })
    const to = op?.destination_relative_path ?? null
    return {
      fileId: d.file_id,
      from: d.relative_path,
      to,
      action: !to ? 'leave' : to.startsWith(REVIEW_FOLDER) ? 'review_folder' : 'move',
      category: d.classification?.category ?? null,
      reason: op?.reason ?? 'Already in the right place.',
      warnings,
      blocking: isBlocking(d),
    }
  })
  const skipped: PlanRow[] = scan.skipped.map((s) => ({
    fileId: `skip:${s.relative_path}`,
    from: s.relative_path,
    to: null,
    action: 'leave',
    category: null,
    reason: s.detail,
    warnings: [{ kind: 'skipped', message: s.detail }],
    blocking: false,
  }))
  return [...rows, ...skipped]
}

export function isInsideRoot(rel: string): boolean {
  if (!rel || rel.startsWith('/') || rel.startsWith('\\') || /^[a-zA-Z]:/.test(rel)) return false
  return !rel.split(/[\\/]/).some((seg) => seg === '..')
}
