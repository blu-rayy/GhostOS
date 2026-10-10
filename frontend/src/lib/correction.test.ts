import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../api/mock'
import { resetMockScenario, settle } from '../test/mockHarness'
import { buildTransactionCorrection } from './viewModel'

// UI1 + DA-7 regression against the demo mock: the panel never sends an
// untouched empty amount as null, and accepting as-is a transaction with an
// unresolved amount is rejected (mirrors the backend DA-7 guard).
describe('regression: marking a transaction checked with no amount entered', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetMockScenario()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('omits amount, and a conflicting amount cannot be accepted as-is', async () => {
    const progress = await settle(mockApi.startScan('C:/GhostOS-fixture-root'), 250)
    const scan = await settle(mockApi.getScan(progress.scan_id), 250)
    // f07 (Office Warehouse) is a transaction with an empty amount box and an
    // amount_conflict flag: the reported DA-7 case.
    const c = scan.documents.find((d) => d.file_id === 'f07')!.classification!
    expect(c.amount).toBeNull()

    // What the panel used to send: amount: null for the untouched empty box.
    await expect(settle(mockApi.correctDocument('f07', { merchant: c.merchant, date: c.date, amount: null, accept: true }), 150)).rejects.toThrow(
      /^422 amount must be a parseable monetary value/,
    )

    const { details, clearedStoredAmount } = buildTransactionCorrection({
      initial: { merchant: c.merchant, date: c.date, amount: c.amount },
      current: { merchant: c.merchant ?? '', date: c.date ?? '', amount: '' },
    })
    expect(clearedStoredAmount).toBe(false)
    const body = { ...details, accept: true }
    expect(body).not.toHaveProperty('amount')

    // DA-7: the omitted-amount accept must be rejected, not revived as a value.
    await expect(settle(mockApi.correctDocument('f07', body), 150)).rejects.toThrow(
      /^422 Cannot accept transaction while source validation findings remain unresolved/,
    )
  })

  it('leave for review on a conflict receipt keeps flags; fixing restores counted filing', async () => {
    const progress = await settle(mockApi.startScan('C:/GhostOS-fixture-root'), 250)
    const scan = await settle(mockApi.getScan(progress.scan_id), 250)
    const before = scan.documents.find((d) => d.file_id === 'f07')!
    expect(before.classification!.amount).toBeNull()

    // FU-2: the panel's Leave for review request on a transaction.
    const left = await settle(mockApi.correctDocument('f07', { category: 'uncertain', accept: true }), 150)
    expect(left).toMatchObject({ status: 'needs_review', user_corrected: true, review_disposition: 'leave_for_review' })
    expect(left.classification!.category).toBe('uncertain')
    expect(left.review_flags.map((f) => f.code)).toEqual(['amount_conflict'])

    // Still blocking, bound for Uncategorized/, never counted (no report row
    // at all while the category is uncertain).
    const blocking = await settle(mockApi.getPlan(progress.scan_id), 200)
    expect(blocking.blocking_review_count).toBe(7)
    expect(blocking.operations.find((o) => o.file_id === 'f07')!.destination_relative_path).toBe(
      'Uncategorized/receipt_office_warehouse.txt',
    )
    expect(blocking.report_rows.find((r) => r.file_id === 'f07')).toBeUndefined()
    const blockingPhp = blocking.totals.find((t) => t.currency === 'PHP')!

    // Reviewing it back restores the filing category (what the panel sends).
    const fixed = await settle(
      mockApi.correctDocument('f07', { category: 'receipt', amount: '1520.00', accept: true }),
      150,
    )
    expect(fixed).toMatchObject({ status: 'ok', review_disposition: 'filed' })
    expect(fixed.classification).toMatchObject({ category: 'receipt', amount: '1520.00' })
    expect(fixed.review_flags).toEqual([])

    const filed = await settle(mockApi.getPlan(progress.scan_id), 200)
    expect(filed.blocking_review_count).toBe(6)
    expect(filed.operations.find((o) => o.file_id === 'f07')!.destination_relative_path).toBe(
      'Receipts/2026-09/receipt_office_warehouse.txt',
    )
    expect(filed.report_rows.find((r) => r.file_id === 'f07')).toMatchObject({
      status: 'accepted',
      amount: '1520.00',
    })
    // The fixed receipt now counts exactly once on top of the prior totals.
    const filedPhp = filed.totals.find((t) => t.currency === 'PHP')!
    expect(filedPhp.row_count).toBe(blockingPhp.row_count + 1)
  })
})
