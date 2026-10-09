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
  SystemStatus,
} from '../types/api'
import { sumAmounts } from '../lib/money'
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

function needsReview(doc: DocumentRecord): boolean {
  return doc.status === 'needs_review' && !doc.user_corrected
}

const DOCUMENT_KINDS: DocumentKind[] = ['receipt', 'invoice', 'statement', 'identity_or_civil', 'legal', 'medical', 'other', 'uncertain']

/** Mirrors document_awareness.document_kind_for_classification: the explicit kind, else the category. */
function kindOf(c: Classification): DocumentKind {
  const k = c.document_kind
  if (k) return DOCUMENT_KINDS.includes(k) ? k : 'other'
  return c.category
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

function buildPlan(s: ScanResult): PlanPreview {
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
    scan_id: s.scan_id,
    operations,
    report_rows,
    totals,
    blocking_review_count: s.documents.filter((d) => d.status === 'needs_review' && !d.user_corrected).length,
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
    // Mirrors PATCH /api/documents/{id} (bc6a5d6): backend-controlled and unknown fields are a
    // 422; shop/date/amount/currency only when the CURRENT record is a transaction.
    const body = Object.fromEntries(Object.entries(correction).filter(([, v]) => v !== undefined)) as Record<string, unknown>
    const forbidden = ['field_profile', 'editable_fields', 'allowed_fields', 'destination_relative_path', 'operations'].filter((k) => k in body)
    if (forbidden.length) throw unprocessable(`Unsupported backend-controlled fields: ${forbidden.join(', ')}`)
    const unknown = Object.keys(body).filter((k) => !['category', 'merchant', 'date', 'amount', 'currency', 'accept'].includes(k)).sort()
    if (unknown.length) throw unprocessable(`Unsupported correction fields: ${unknown.join(', ')}`)
    const profile = profileOf(doc.classification ?? { category: 'uncertain' } as Classification)
    const money = ['merchant', 'date', 'amount', 'currency'].filter((k) => k in body).sort()
    if (money.length && profile !== 'transaction') {
      throw unprocessable(`Document field profile '${profile}' does not allow transaction corrections: ${money.join(', ')}`)
    }
    if (!doc.classification) {
      // Failed extraction: the backend creates a bare record (no kind, so it derives 'uncertain'/'none').
      doc.classification = {
        category: 'uncertain',
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
    if (correction.accept) {
      doc.user_corrected = true
      doc.review_flags = []
      doc.status = 'ok'
    }
    return clone(withDerived(doc))
  },

  async getPlan(scanId) {
    await delay(200)
    return buildPlan(requireScan(scanId))
  },

  async approvePlan(planId) {
    await delay(800)
    if (!scan) throw new Error('No scan')
    const plan = buildPlan(scan)
    if (plan.plan_id !== planId) throw new Error(`Unknown plan ${planId}`)
    if (plan.blocking_review_count > 0) throw new Error('Plan has unresolved review items')
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
