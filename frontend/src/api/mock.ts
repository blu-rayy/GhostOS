import type { GhostApi } from './client'
import type {
  Classification,
  CurrencyTotal,
  DocumentKind,
  DocumentRecord,
  FieldProfile,
  PlanPreview,
  ProposedOperation,
  ReportRow,
  ScanResult,
  SortMode,
  SystemStatus,
} from '../types/api'
import { sumAmounts, toCents } from '../lib/money'
import scanFixture from '../fixtures/scan.json'
import statusFixture from '../fixtures/status.json'

// In-memory fake of the FastAPI service, driven by the JSON fixtures.
// The plan-building rules below mirror the build plan's backend contract so
// that the UI behaves the same once the real endpoints land.

/** Demo scan pacing. Slowed down while desktop Pip runs so the animation has time to play. */
export const mockTiming = { scanDurationMs: 4000 }

const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms))
const clone = <T>(v: T): T => structuredClone(v)

let scan: ScanResult | null = null
let scanStartedAt = 0
/** Mode of the most recent plan preview; approval must match it (backend: snapshot.mode). */
let previewMode: SortMode = 'blocking'
let batchCounter = 0
/** Files the last approve actually moved (so undo restores only those). */
let lastBatchMoved: string[] | null = null

/**
 * Opt-in demo scenarios (default off, so default fixture behaviour is unchanged).
 * The Settings screen toggles these while fixtures are active.
 */
export const mockScenario = {
  /** The scan stops with an error partway through. */
  scanError: false,
  /** Undo reports one restore conflict (original path now occupied). */
  undoConflict: false,
  /** Approve reports two files that didn't move (Totals 3d). */
  moveFailures: false,
}

const SIMULATED_MOVE_ERRORS = [
  'Open in another app. Close it, then try again. (simulated)',
  "Windows didn't allow the move (no permission). (simulated)",
]

function requireScan(scanId: string): ScanResult {
  if (!scan || scan.scan_id !== scanId) throw new Error(`Unknown scan ${scanId}`)
  return scan
}

// ---------- plan rules (backend owns these for real) ----------

function basename(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

/** Still waiting on a person, or left for review (backend bf99c68): blocks a strict plan. */
function needsReview(doc: DocumentRecord): boolean {
  return doc.status === 'needs_review' && (!doc.user_corrected || doc.review_disposition === 'leave_for_review')
}

const DOCUMENT_KINDS: DocumentKind[] = ['receipt', 'invoice', 'statement', 'identity_or_civil', 'legal', 'medical', 'other', 'uncertain']

/** Mirrors document_awareness.document_kind_for_classification: the explicit kind, else the category. */
/**
 * Mirrors document_awareness.document_kind_for_classification: a stored kind (null included,
 * which means 'none'); only records that predate the field fall back to their category.
 */
function kindOf(c: Classification): DocumentKind | null {
  if ('document_kind' in c) return normalizeKind(c.document_kind)
  return c.category
}

/** Mirrors schemas.normalize_document_kind (unknown strings become 'other'). */
function normalizeKind(k: unknown): DocumentKind | null {
  if (typeof k !== 'string') return null
  return DOCUMENT_KINDS.includes(k as DocumentKind) ? (k as DocumentKind) : 'other'
}

/** Mirrors derive_field_profile: always from the kind, never from the client. */
function profileOf(c: Classification): FieldProfile {
  const k = kindOf(c)
  if (k === 'receipt' || k === 'invoice') return 'transaction'
  if (k === 'statement') return 'reference'
  return 'none'
}

/** Mirrors session._classification_response: responses always carry the derived kind and profile. */
function withDerived(doc: DocumentRecord): DocumentRecord {
  const c = doc.classification
  return c ? { ...doc, classification: { ...c, document_kind: kindOf(c), field_profile: profileOf(c) } } : doc
}

/** A 422 like FastAPI's, so the UI shows the same error text it would get from the backend. */
const unprocessable = (detail: string) => new Error(`422 ${detail}`)

function destinationFolder(doc: DocumentRecord): { folder: string; reason: string } {
  const c = doc.classification
  if (!c || doc.status === 'failed') return { folder: 'Uncategorized', reason: 'Could not be classified' }
  if (needsReview(doc)) return { folder: 'Uncategorized', reason: 'Waiting for human review' }
  // Like the backend: a document-aware non-transaction paper goes to Other/ once reviewed,
  // whatever its category (orchestrator._build_plan, document_aware branch).
  // "Leave for review" (b584d92): a decided document with category uncertain stays in Uncategorized/.
  if (doc.review_disposition === 'leave_for_review' || (!doc.review_disposition && doc.user_corrected && c.category === 'uncertain')) {
    return { folder: 'Uncategorized', reason: 'Left for human review' }
  }
  if ('document_kind' in c && profileOf(c) !== 'transaction') return { folder: 'Other', reason: 'Non-transactional document' }
  if (c.category === 'invoice' || c.category === 'receipt') {
    if (!c.date) return { folder: 'Uncategorized', reason: `${c.category} without a date` }
    const top = c.category === 'invoice' ? 'Invoices' : 'Receipts'
    return { folder: `${top}/${c.date.slice(0, 7)}`, reason: `${c.category} dated ${c.date}` }
  }
  if (c.category === 'other') return { folder: 'Other', reason: 'Not an invoice or receipt' }
  return { folder: 'Uncategorized', reason: 'Category uncertain' }
}

function withSuffix(name: string, n: number): string {
  const dot = name.lastIndexOf('.')
  return dot > 0 ? `${name.slice(0, dot)} (${n})${name.slice(dot)}` : `${name} (${n})`
}

function buildPlan(s: ScanResult, mode: SortMode = 'blocking'): PlanPreview {
  const taken = new Set<string>()
  const operations: ProposedOperation[] = []

  for (const doc of s.documents) {
    const { folder, reason } = destinationFolder(doc)
    const name = basename(doc.relative_path)
    let dest = `${folder}/${name}`
    let n = 1
    while (taken.has(dest.toLowerCase())) dest = `${folder}/${withSuffix(name, ++n)}`
    taken.add(dest.toLowerCase())
    if (dest === doc.relative_path) continue
    operations.push({
      file_id: doc.file_id,
      original_relative_path: doc.relative_path,
      destination_relative_path: dest,
      reason,
      collision_suffixed: n > 1,
    })
  }

  const report_rows: ReportRow[] = []
  for (const doc of s.documents) {
    const c = doc.classification
    if (!c || (c.category !== 'invoice' && c.category !== 'receipt')) continue
    // Non-transaction papers never reach the totals, whatever the category says.
    if (profileOf(c) !== 'transaction') continue
    // Partial mode: unchecked files are set aside in Uncategorized/ and not counted at all.
    if (mode === 'partial' && needsReview(doc)) continue
    const complete = c.amount !== null && c.currency !== null && c.date !== null
    const accepted = complete && !needsReview(doc) && doc.duplicate_of === null
    report_rows.push({
      file_id: doc.file_id,
      source_filename: doc.relative_path,
      category: c.category,
      date: c.date,
      merchant: c.merchant,
      amount: c.amount,
      currency: c.currency,
      status: accepted ? 'accepted' : 'needs_review',
    })
  }

  const byCurrency = new Map<string, string[]>()
  for (const row of report_rows) {
    if (row.status !== 'accepted' || !row.currency || !row.amount) continue
    byCurrency.set(row.currency, [...(byCurrency.get(row.currency) ?? []), row.amount])
  }
  const totals: CurrencyTotal[] = [...byCurrency].map(([currency, amounts]) => ({
    currency,
    amount: sumAmounts(amounts),
    row_count: amounts.length,
  }))

  return {
    plan_id: `plan_${s.scan_id}`,
    mode,
    scan_id: s.scan_id,
    operations,
    report_rows,
    totals,
    blocking_review_count: s.documents.filter(needsReview).length,
  }
}

// ---------- API ----------

export const mockApi: GhostApi = {
  async getStatus() {
    await delay(100)
    return clone(statusFixture) as SystemStatus
  },

  async startScan(root) {
    await delay()
    scan = { ...(clone(scanFixture) as ScanResult), root, scanned_at: new Date().toISOString() }
    scanStartedAt = Date.now()
    lastBatchMoved = null
    return mockApi.getScanProgress(scan.scan_id)
  },

  async getScanProgress(scanId) {
    const s = requireScan(scanId)
    const total = s.documents.length
    const fraction = Math.min(1, (Date.now() - scanStartedAt) / mockTiming.scanDurationMs)
    const processed = Math.floor(fraction * total)
    if (mockScenario.scanError && processed >= Math.floor(total / 2)) {
      return {
        scan_id: scanId,
        state: 'error',
        files_total: total,
        files_processed: processed,
        current_file: null,
        error: 'Model not loaded: the local Ollama service stopped responding (simulated). No files were changed.',
      }
    }
    return {
      scan_id: scanId,
      state: processed >= total ? 'done' : 'running',
      files_total: total,
      files_processed: processed,
      current_file: processed < total ? s.documents[processed].relative_path : null,
      error: null,
    }
  },

  async getScan(scanId) {
    await delay()
    return clone(requireScan(scanId))
  },

  async correctDocument(fileId, correction) {
    await delay(150)
    const doc = scan?.documents.find((d) => d.file_id === fileId)
    if (!doc) throw new Error(`Unknown file ${fileId}`)
    // Mirrors PATCH /api/documents/{id} on main (0dfdb65): backend-controlled and unknown fields
    // are a 422; document_kind is accepted and normalised; a non-payment kind with an invoice/
    // receipt category is a 422; shop/date/amount/currency only when the record AFTER this
    // change is a transaction.
    const body = Object.fromEntries(Object.entries(correction).filter(([, v]) => v !== undefined)) as Record<string, unknown>
    const forbidden = ['field_profile', 'editable_fields', 'allowed_fields', 'destination_relative_path', 'operations', 'review_disposition'].filter((k) => k in body)
    if (forbidden.length) throw unprocessable(`Unsupported backend-controlled fields: ${forbidden.join(', ')}`)
    const unknown = Object.keys(body).filter((k) => !['category', 'document_kind', 'merchant', 'date', 'amount', 'currency', 'accept'].includes(k)).sort()
    if (unknown.length) throw unprocessable(`Unsupported correction fields: ${unknown.join(', ')}`)
    const proposed = { ...(doc.classification ?? { category: 'uncertain', document_kind: null, field_profile: 'none' }) } as Classification
    if ('category' in body) {
      if (!['invoice', 'receipt', 'other', 'uncertain'].includes(body.category as string)) throw unprocessable('category must be a supported value')
      proposed.category = body.category as Classification['category']
    }
    if ('document_kind' in body) {
      if (body.document_kind !== null && typeof body.document_kind !== 'string') throw unprocessable('document_kind must be a supported string or null')
      proposed.document_kind = normalizeKind(body.document_kind)
    }
    const proposedKind = kindOf(proposed)
    if (proposedKind && ['statement', 'identity_or_civil', 'legal', 'medical', 'other', 'uncertain'].includes(proposedKind) && (proposed.category === 'invoice' || proposed.category === 'receipt')) {
      throw unprocessable(`document_kind '${proposedKind}' cannot use transaction category '${proposed.category}'`)
    }
    const profile = profileOf(proposed)
    // Field formats, like PATCH /documents (e5a7a06). The backend additionally checks a corrected
    // amount against the document's own text; the demo mock does not model that.
    if ('accept' in body && typeof body.accept !== 'boolean') throw unprocessable('accept must be a boolean')
    if ('merchant' in body && body.merchant !== null && typeof body.merchant !== 'string') throw unprocessable('merchant must be a string or null')
    if ('date' in body && body.date !== null && (typeof body.date !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(body.date))) {
      throw unprocessable('date must be an ISO date (YYYY-MM-DD)')
    }
    if ('currency' in body && !(typeof body.currency === 'string' && ['PHP', 'USD', 'EUR', 'GBP', 'SGD', 'JPY'].includes(body.currency.toUpperCase()))) {
      throw unprocessable('currency must be a supported currency code')
    }
    if ('amount' in body && (typeof body.amount !== 'string' || !body.amount.trim() || toCents(body.amount.trim()) === null)) {
      throw unprocessable('amount must be a parseable monetary value')
    }
    const money = ['merchant', 'date', 'amount', 'currency'].filter((k) => k in body).sort()
    if (money.length && profile !== 'transaction') {
      throw unprocessable(`Document field profile '${profile}' does not allow transaction corrections: ${money.join(', ')}`)
    }
    if (!doc.classification) {
      // Failed extraction: the backend creates a record with an explicit null kind ('none').
      doc.classification = {
        category: 'uncertain',
        document_kind: null,
        field_profile: 'none',
        merchant: null,
        date: null,
        amount_text: null,
        amount: null,
        currency: null,
        evidence_quote: null,
        evidence_verified: false,
        explanation: 'Entered manually',
      }
    }
    for (const k of ['category', 'merchant', 'date', 'amount', 'currency'] as const) {
      if (k in body) (doc.classification as unknown as Record<string, unknown>)[k] = body[k]
    }
    if ('document_kind' in body) doc.classification.document_kind = proposed.document_kind
    doc.classification.field_profile = profileOf(doc.classification)

    // DA-7 accept-guard parity: acceptance is not a second source of truth for
    // a transaction. Filing without a usable amount is allowed only when there
    // is nothing anywhere to revive; otherwise unresolved amount findings keep
    // the document blocked. (The real backend revalidates the source text; the
    // demo mock approximates it with the record's amount-related review flags.)
    const AMOUNT_FLAGS = ['amount_conflict', 'amount_unparseable', 'missing_amount', 'invalid_currency', 'currency_mismatch', 'missing_currency', 'evidence_not_found']
    let allowFiledUncounted = false
    // Leave for review (category 'uncertain') accepts nothing, so it skips this guard (backend parity).
    if (correction.accept && profileOf(proposed) === 'transaction' && correction.category !== 'uncertain' && !('amount' in body)) {
      const storedAmount = proposed.amount ?? null
      const storedAmountText = (proposed.amount_text ?? '').trim()
      if (storedAmount === null && storedAmountText === '') {
        allowFiledUncounted = true
      } else if (doc.review_flags.some((f) => AMOUNT_FLAGS.includes(f.code))) {
        throw unprocessable('Cannot accept transaction while source validation findings remain unresolved')
      }
    }

    if (correction.accept) {
      doc.user_corrected = true
      if (correction.category === 'uncertain') {
        // Leave for review (backend bf99c68): flags kept, still needs_review, still blocking.
        doc.review_disposition = 'leave_for_review'
        doc.status = 'needs_review'
      } else if (allowFiledUncounted) {
        // Filed without a usable amount (backend DA-7 + UI1): safe, uncounted.
        doc.review_disposition = 'filed_uncounted'
        doc.review_flags = []
        doc.status = 'ok'
      } else {
        doc.review_disposition = 'filed'
        doc.review_flags = []
        doc.status = 'ok'
      }
    }
    return clone(withDerived(doc))
  },

  async getPlan(scanId, mode = 'blocking') {
    await delay(200)
    previewMode = mode
    return buildPlan(requireScan(scanId), mode)
  },

  async approvePlan(planId, mode = 'blocking') {
    await delay(800)
    if (!scan) throw new Error('No scan')
    // Like the backend: the approval must match the mode of the last preview.
    if (mode !== previewMode) {
      throw new Error(`409 Plan mode is '${previewMode}' but approval requested '${mode}'; refresh the preview before approval`)
    }
    const plan = buildPlan(scan, mode)
    if (plan.plan_id !== planId) throw new Error(`Unknown plan ${planId}`)
    if (mode === 'blocking' && plan.blocking_review_count > 0) throw new Error(`409 Plan has ${plan.blocking_review_count} unresolved review items`)
    const stamp = new Date().toISOString().slice(0, 16).replace(/[-:]/g, '')
    const failed = mockScenario.moveFailures
      ? plan.operations.slice(0, SIMULATED_MOVE_ERRORS.length).map((op, i) => ({ file_id: op.file_id, error: SIMULATED_MOVE_ERRORS[i] }))
      : []
    const failedIds = new Set(failed.map((f) => f.file_id))
    lastBatchMoved = plan.operations.filter((op) => !failedIds.has(op.file_id)).map((op) => op.file_id)
    return {
      batch_id: `batch_${++batchCounter}`,
      moved: lastBatchMoved.length,
      failed,
      report_relative_path: `GhostOS Reports/expenses-${stamp}.csv`,
      committed_at: new Date().toISOString(),
    }
  },

  async undoBatch(batchId) {
    await delay(600)
    if (!scan) throw new Error('No scan')
    const moved = lastBatchMoved
    const ops = buildPlan(scan).operations.filter((op) => moved === null || moved.includes(op.file_id))
    if (mockScenario.undoConflict && ops.length > 0) {
      const op = ops[Math.min(1, ops.length - 1)]
      return {
        batch_id: batchId,
        restored: ops.length - 1,
        conflicts: [
          {
            file_id: op.file_id,
            relative_path: op.original_relative_path,
            reason: 'a different file with this name is in the old spot now (simulated)',
          },
        ],
      }
    }
    return { batch_id: batchId, restored: ops.length, conflicts: [] }
  },
}
