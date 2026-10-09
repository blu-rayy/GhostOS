import type { GhostApi } from './client'
import type {
  CurrencyTotal,
  DocumentRecord,
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

const SCAN_DURATION_MS = 4000

const delay = (ms = 250) => new Promise((r) => setTimeout(r, ms))
const clone = <T>(v: T): T => structuredClone(v)

let scan: ScanResult | null = null
let scanStartedAt = 0
let batchCounter = 0

function requireScan(scanId: string): ScanResult {
  if (!scan || scan.scan_id !== scanId) throw new Error(`Unknown scan ${scanId}`)
  return scan
}

// ---------- plan rules (backend owns these for real) ----------

function basename(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

function needsReview(doc: DocumentRecord): boolean {
  return doc.status !== 'ok' && !doc.user_corrected
}

function destinationFolder(doc: DocumentRecord): { folder: string; reason: string } {
  const c = doc.classification
  if (!c || doc.status === 'failed') return { folder: 'Needs Review', reason: 'Could not be classified' }
  if (needsReview(doc)) return { folder: 'Needs Review', reason: 'Waiting for human review' }
  if (c.category === 'invoice' || c.category === 'receipt') {
    if (!c.date) return { folder: 'Needs Review', reason: `${c.category} without a date` }
    const top = c.category === 'invoice' ? 'Invoices' : 'Receipts'
    return { folder: `${top}/${c.date.slice(0, 7)}`, reason: `${c.category} dated ${c.date}` }
  }
  if (c.category === 'other') return { folder: 'Other', reason: 'Not an invoice or receipt' }
  return { folder: 'Needs Review', reason: 'Category uncertain' }
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
    return mockApi.getScanProgress(scan.scan_id)
  },

  async getScanProgress(scanId) {
    const s = requireScan(scanId)
    const total = s.documents.length
    const fraction = Math.min(1, (Date.now() - scanStartedAt) / SCAN_DURATION_MS)
    const processed = Math.floor(fraction * total)
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
    const { accept, ...fields } = correction
    if (doc.classification) Object.assign(doc.classification, fields)
    if (accept) {
      doc.user_corrected = true
      doc.review_flags = []
    }
    return clone(doc)
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
    return {
      batch_id: `batch_${++batchCounter}`,
      moved: plan.operations.length,
      failed: [],
      report_relative_path: `GhostOS Reports/expenses-${stamp}.csv`,
      committed_at: new Date().toISOString(),
    }
  },

  async undoBatch(batchId) {
    await delay(600)
    if (!scan) throw new Error('No scan')
    return { batch_id: batchId, restored: buildPlan(scan).operations.length, conflicts: [] }
  },
}
