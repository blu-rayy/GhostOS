import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../api/mock'
import { resetMockScenario, settle } from '../test/mockHarness'
import { buildTransactionCorrection } from './viewModel'

// UI1 regression against the demo mock, which rejects amount: null like the backend (e5a7a06).
// The builder's own rules are tested in viewModel.test.ts.
describe('regression: marking a transaction checked with no amount entered', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetMockScenario()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('omits amount, and the correction is accepted (the old amount: null payload was a 422)', async () => {
    const progress = await settle(mockApi.startScan('C:/GhostOS-fixture-root'), 250)
    const scan = await settle(mockApi.getScan(progress.scan_id), 250)
    // f07 (Office Warehouse) is a transaction whose amount box is empty: the reported case.
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
    const updated = await settle(mockApi.correctDocument('f07', body), 150)
    expect(updated.user_corrected).toBe(true)
    expect(updated.classification).toMatchObject({ amount: null, field_profile: 'transaction' })
  })
})
