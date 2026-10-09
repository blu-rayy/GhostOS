import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../api/mock'
import { resetMockScenario, settle } from '../test/mockHarness'
import type { DocumentRecord, ScanResult } from '../types/api'
import { buildFileRows, documentKindLabel, fieldProfile, NON_TRANSACTION_DECISIONS } from './viewModel'

// Document-aware review: the four reference cases from docs/design/document-aware-review.md,
// all in the fixture scan.
const RECEIPT = 'f02' // receipt_grab_0912.txt          -> transaction
const STATEMENT = 'f15' // statement_0921.pdf            -> reference (model also wrote a merchant/amount)
const BIRTH_CERT = 'f19' // birth_certificate_scan.pdf   -> none
const UNCERTAIN = 'f20' // scan_untitled_04.pdf          -> none

async function startScan(): Promise<ScanResult> {
  const progress = await settle(mockApi.startScan('C:/GhostOS-fixture-root'), 250)
  return settle(mockApi.getScan(progress.scan_id), 250)
}

const docOf = (scan: ScanResult, id: string) => scan.documents.find((d) => d.file_id === id)!

describe('document-aware review', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetMockScenario()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('uses the field profile the backend sent for each reference document', async () => {
    const scan = await startScan()
    expect(fieldProfile(docOf(scan, RECEIPT))).toBe('transaction')
    expect(fieldProfile(docOf(scan, STATEMENT))).toBe('reference')
    expect(fieldProfile(docOf(scan, BIRTH_CERT))).toBe('none')
    expect(fieldProfile(docOf(scan, UNCERTAIN))).toBe('none')
    expect(documentKindLabel(docOf(scan, BIRTH_CERT))).toBe('identity or civil record')
    expect(documentKindLabel(docOf(scan, UNCERTAIN))).toBe('unclear document')
  })

  it('never infers the profile from the category', () => {
    const receiptWithoutProfile = {
      classification: { category: 'receipt', merchant: 'Shop', date: '2026-10-01', amount: '10.00', currency: 'PHP' },
    } as unknown as DocumentRecord
    expect(fieldProfile(receiptWithoutProfile)).toBe('none')
    expect(fieldProfile({ classification: null } as unknown as DocumentRecord)).toBe('none')
  })

  it('shows shop, date and amount only for transaction documents', async () => {
    const scan = await startScan()
    const rows = new Map(buildFileRows(scan, null).map((r) => [r.id, r]))
    expect(rows.get(RECEIPT)).toMatchObject({ fieldProfile: 'transaction', merchant: 'Grab', amount: '245.00', currency: 'PHP', date: '2026-09-12' })
    // The statement's classification carries a model-written merchant and amount; the row must not.
    expect(docOf(scan, STATEMENT).classification?.amount).toBe('45000.00')
    for (const id of [STATEMENT, BIRTH_CERT, UNCERTAIN]) {
      expect(rows.get(id)).toMatchObject({ merchant: null, date: null, amount: null, currency: null })
    }
  })

  it('sends only a safe category and accept for the two decisions, never a profile or money fields', () => {
    expect(NON_TRANSACTION_DECISIONS.file).toEqual({ category: 'other', accept: true })
    expect(NON_TRANSACTION_DECISIONS.leave).toEqual({ category: 'uncertain', accept: true })
  })

  it('files or leaves non-transaction documents through the existing correction flow', async () => {
    const scan = await startScan()
    const before = await settle(mockApi.getPlan(scan.scan_id), 200)

    await settle(mockApi.correctDocument(BIRTH_CERT, NON_TRANSACTION_DECISIONS.file), 150)
    await settle(mockApi.correctDocument(STATEMENT, NON_TRANSACTION_DECISIONS.file), 150)
    const left = await settle(mockApi.correctDocument(UNCERTAIN, NON_TRANSACTION_DECISIONS.leave), 150)
    // The backend's kind and profile are untouched by a decision.
    expect(left.classification).toMatchObject({ document_kind: 'uncertain', field_profile: 'none', category: 'uncertain' })
    expect(left.user_corrected).toBe(true)

    const plan = await settle(mockApi.getPlan(scan.scan_id), 200)
    const dest = new Map(plan.operations.map((o) => [o.file_id, o.destination_relative_path]))
    expect(dest.get(BIRTH_CERT)).toBe('Other/birth_certificate_scan.pdf')
    expect(dest.get(STATEMENT)).toBe('Other/statement_0921.pdf')
    expect(dest.get(UNCERTAIN)).toBe('Needs Review/scan_untitled_04.pdf')
    // Deciding unblocks Move, and none of them adds money to the totals.
    expect(plan.blocking_review_count).toBe(before.blocking_review_count - 3)
    for (const id of [STATEMENT, BIRTH_CERT, UNCERTAIN]) expect(plan.report_rows.find((r) => r.file_id === id)).toBeUndefined()
    expect(plan.totals).toEqual(before.totals)
    // The receipt is still filed and counted as before.
    expect(dest.get(RECEIPT)).toBe('Receipts/2026-09/receipt_grab_0912.txt')
    expect(plan.report_rows.find((r) => r.file_id === RECEIPT)?.status).toBe('accepted')
  })
})
