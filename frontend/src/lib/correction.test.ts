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
})
