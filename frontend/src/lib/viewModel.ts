/**
 * Maps the backend contract (types/api.ts) onto what the screens display.
 * Pure functions only: no fetching, no state.
 */
import type {
  Category,
  DocumentCorrection,
  DocumentRecord,
  FieldProfile,
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

/**
 * The backend's editable-field policy for a document. Only the backend sets it; when it is
 * missing (no classification, or a record typed in by hand) the answer is 'none'. It is
 * never inferred from `category`.
 */
export function fieldProfile(d: DocumentRecord): FieldProfile {
  return d.classification?.field_profile ?? 'none'
}

/**
 * The two explicit decisions for a document that isn't a single payment. Each sends only a
 * safe filing category and accept: never shop, date, amount, document_kind or field_profile.
 * The backend's fixed folder rules then decide the path (other -> Other/, uncertain ->
 * Uncategorized/), and neither category is ever counted in the totals.
 */
export const NON_TRANSACTION_DECISIONS = {
  file: { category: 'other', accept: true },
  leave: { category: 'uncertain', accept: true },
} as const satisfies Record<'file' | 'leave', DocumentCorrection>

/**
 * UI1: builds the transaction correction for the Check panel's primary action.
 *
 * The API 422s `amount: null` (and empty/unparseable strings) — null carries
 * no "clear the amount" semantics — so an untouched empty amount is omitted
 * instead of sent as an explicit null. Accepting without an amount files the
 * document without counting it. Clearing a stored amount is not supported:
 * omitting it would keep a value the screen no longer shows, so the caller
 * must block the action (`clearedStoredAmount`) instead of sending a payload
 * the API has to reject. Merchant/date keep their backend null semantics and
 * are sent only when changed.
 */
export function buildTransactionCorrection(input: {
  initial: { merchant: string | null; date: string | null; amount: string | null }
  current: { merchant: string; date: string; amount: string }
}): { details: Omit<DocumentCorrection, 'accept'>; clearedStoredAmount: boolean } {
  const details: Omit<DocumentCorrection, 'accept'> = {}
  if (input.current.merchant !== (input.initial.merchant ?? '')) {
    details.merchant = input.current.merchant || null
  }
  if (input.current.date !== (input.initial.date ?? '')) {
    details.date = input.current.date || null
  }
  const amount = input.current.amount.trim()
  const initialAmount = input.initial.amount ?? ''
  if (amount !== '' && amount !== initialAmount) details.amount = amount
  return { details, clearedStoredAmount: initialAmount !== '' && amount === '' }
}

/**
 * Counts for the review-choice pop-up, from the scan's documents (the plan has no per-file
 * flags). Only files still blocking Move: status needs_review and not yet decided.
 */
export function reviewChoiceGroups(docs: DocumentRecord[]): { total: number; confirm: number; notReceipts: number; suspicious: number } {
  const open = docs.filter((d) => d.status === 'needs_review' && !d.user_corrected)
  const suspicious = open.filter((d) => d.review_flags.some((f) => f.code === 'possible_injection'))
  const notReceipts = open.filter((d) => !suspicious.includes(d) && fieldProfile(d) !== 'transaction')
  return { total: open.length, confirm: open.length - suspicious.length - notReceipts.length, notReceipts: notReceipts.length, suspicious: suspicious.length }
}

/** document_kind in plain words ("identity or civil record"); "document" when the backend sent none. */
export function documentKindLabel(d: DocumentRecord): string {
  const kind = d.classification?.document_kind ?? null
  const labels: Record<string, string> = {
    receipt: 'receipt',
    invoice: 'invoice',
    statement: 'statement',
    identity_or_civil: 'identity or civil record',
    legal: 'legal paper',
    medical: 'medical record',
    other: 'other document',
    uncertain: 'unclear document',
  }
  return kind ? labels[kind] ?? kind.replaceAll('_', ' ') : 'document'
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

/** Row chip tone for the Check screen. `muted` marks a file the user deferred. */
export type ReviewTone = 'check' | 'done' | 'oops' | 'muted'

export interface ReviewChipState {
  text: string
  tone: ReviewTone
  /** Left-edge stripe colour for the row (mirrors the chip tone). */
  stripe: string
}

/**
 * What the Check-screen row chip says about a document.
 *
 * - `failed` and uncorrected -> "couldn't read" (pink).
 * - corrected to `other` -> "filed under Other" (green).
 * - corrected to `uncertain`, or a failed file left without details ->
 *   "left for review" / "left for later" (grey, never the green check).
 * - backend-accepted (`status: ok`) with no flags and no correction ->
 *   "ready" (green) instead of the yellow attention state.
 * - anything still waiting on the user -> "check this" (yellow).
 */
export function reviewChipState(doc: DocumentRecord | null): ReviewChipState {
  if (!doc) return { text: 'check this', tone: 'check', stripe: '#ffe066' }
  if (doc.status === 'failed' && !doc.user_corrected) {
    return { text: "couldn't read", tone: 'oops', stripe: '#ffb3b3' }
  }
  if (doc.user_corrected) {
    if (doc.status === 'failed') {
      const c = doc.classification
      const hasDetails = Boolean(c?.merchant || c?.date || c?.amount)
      if (hasDetails) return { text: '✓ checked', tone: 'done', stripe: '#9be8b8' }
      return { text: 'left for later', tone: 'muted', stripe: '#cfcfcf' }
    }
    const category = doc.classification?.category
    if (category === 'other') return { text: 'filed under Other', tone: 'done', stripe: '#9be8b8' }
    if (category === 'uncertain') return { text: 'left for review', tone: 'muted', stripe: '#cfcfcf' }
    if (doc.review_disposition === 'filed_uncounted') {
      return { text: 'filed without amount · not counted', tone: 'muted', stripe: '#cfcfcf' }
    }
    return { text: '✓ checked', tone: 'done', stripe: '#9be8b8' }
  }
  if (doc.status === 'ok' && doc.review_flags.length === 0) {
    return { text: 'ready', tone: 'done', stripe: '#9be8b8' }
  }
  return { text: 'check this', tone: 'check', stripe: '#ffe066' }
}

/**
 * Sub-line under the file name. Decided files name their actual decision
 * (never "you checked this file" for a file that was only deferred).
 */
export function reviewReasonText(row: FileRow): string {
  const doc = row.doc
  if (!doc) return row.skip?.detail ?? 'Ready to file.'
  if (doc.user_corrected) {
    if (doc.status === 'failed') {
      const c = doc.classification
      if (!c?.merchant && !c?.date && !c?.amount) {
        return 'left for later → Uncategorized/ · not counted'
      }
    } else {
      const category = doc.classification?.category
      if (category === 'other') return 'filed under Other/ · not counted'
      if (category === 'uncertain') return 'left for review → Uncategorized/ · not counted'
      if (doc.review_disposition === 'filed_uncounted') return 'filed without a usable amount · not counted'
    }
    return doc.classification?.date ? `date added: ${doc.classification.date}` : 'you checked this file'
  }
  return doc.review_flags[0]?.message ?? doc.classification?.explanation ?? 'Ready to file.'
}

/** True when this document blocks approval (mirrors blocking_review_count). */
export function isBlocking(d: DocumentRecord): boolean {
  // A file left for review still blocks a strict plan (backend bf99c68).
  return d.status === 'needs_review' && (!d.user_corrected || d.review_disposition === 'leave_for_review')
}

/** Which field a review flag is about, so the detail panel can show it next to that field. */
export type FlagTarget = 'category' | 'merchant' | 'date' | 'amount' | 'evidence' | 'document'

export const FLAG_TARGET: Record<ReviewFlagCode, FlagTarget> = {
  evidence_not_found: 'evidence',
  amount_unparseable: 'amount',
  amount_conflict: 'amount',
  missing_date: 'date',
  missing_amount: 'amount',
  missing_merchant: 'merchant',
  missing_currency: 'amount',
  invalid_currency: 'amount',
  currency_mismatch: 'amount',
  missing_evidence_quote: 'evidence',
  uncertain_classification: 'category',
  low_confidence: 'category',
  model_error: 'document',
  possible_injection: 'document',
  non_transactional_document: 'category',
  transaction_fields_on_non_transactional: 'category',
  uncertain_document_kind: 'category',
}

/**
 * Field a flag belongs to. Codes the UI doesn't know yet (e.g. a new backend
 * validator code) fall back to 'document' so their message is never dropped.
 */
export function flagTarget(code: string): FlagTarget {
  return Object.hasOwn(FLAG_TARGET, code) ? FLAG_TARGET[code as ReviewFlagCode] : 'document'
}

export function flagsFor(d: DocumentRecord, target: FlagTarget): ReviewFlag[] {
  if (d.user_corrected) return []
  return d.review_flags.filter((f) => flagTarget(f.code) === target)
}

export interface FileRow {
  id: string
  filename: string
  relPath: string
  dir: string
  fileType: string
  category: Category | null
  /** Backend field policy. Shop, date and amount are only filled in for 'transaction'. */
  fieldProfile: FieldProfile
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
    const profile = fieldProfile(d)
    // Statements, IDs, legal and medical papers have no shop/date/amount, even if the model wrote some.
    const tx = profile === 'transaction' ? c : null
    return {
      id: d.file_id,
      filename: basename(d.relative_path),
      relPath: d.relative_path,
      dir: dirname(d.relative_path),
      fileType: d.file_type,
      category: c?.category ?? null,
      fieldProfile: profile,
      merchant: tx?.merchant ?? null,
      date: tx?.date ?? null,
      amount: tx?.amount ?? null,
      currency: tx?.currency ?? null,
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
    fieldProfile: 'none',
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

const REVIEW_FOLDER = 'Uncategorized/'

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
