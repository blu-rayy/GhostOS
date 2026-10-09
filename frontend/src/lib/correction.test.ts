import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../api/mock'
import { resetMockScenario, settle } from '../test/mockHarness'
import { buildTransactionCorrection } from './correction'

const empty = { merchant: '', date: '', amount: '' }

describe('transaction correction request (Check · "Looks right")', () => {
  it('omits every field the person did not change, including an untouched empty amount', () => {
    const initial = { merchant: 'Office Warehouse', date: '2026-09-05', amount: '' }
    const built = buildTransactionCorrection(initial, { ...initial })
    expect(built).toEqual({ ok: true, correction: {} })
    expect(built.ok && 'amount' in built.correction).toBe(false)
  })

  it('sends an edited amount normalised, and treats a re-formatted same amount as unchanged', () => {
    expect(buildTransactionCorrection({ ...empty }, { ...empty, amount: '₱1,520' })).toEqual({ ok: true, correction: { amount: '1520.00' } })
    expect(buildTransactionCorrection({ ...empty, amount: '1250.00' }, { ...empty, amount: '1,250.00' })).toEqual({ ok: true, correction: {} })
  })

  it("refuses to clear an existing amount (the backend can't accept amount: null) and sends nothing", () => {
    const built = buildTransactionCorrection({ ...empty, amount: '89.00' }, { ...empty, amount: '' })
    expect(built.ok).toBe(false)
  })

  it('rejects an amount or date it cannot read, before anything is sent', () => {
    expect(buildTransactionCorrection({ ...empty }, { ...empty, amount: 'twelve' }).ok).toBe(false)
    expect(buildTransactionCorrection({ ...empty }, { ...empty, date: '21/09/2026' }).ok).toBe(false)
  })

  it('clears a shop or date explicitly with null, which the backend accepts', () => {
    expect(buildTransactionCorrection({ merchant: 'Grab', date: '2026-09-12', amount: '245.00' }, { merchant: '', date: '', amount: '245.00' })).toEqual({
      ok: true,
      correction: { merchant: null, date: null },
    })
  })
})

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
    const initial = { merchant: c.merchant ?? '', date: c.date ?? '', amount: c.amount ?? '' }
    expect(initial.amount).toBe('')

    // What the panel used to send: amount: null for the untouched empty box.
    await expect(settle(mockApi.correctDocument('f07', { merchant: initial.merchant, date: initial.date, amount: null, accept: true }), 150)).rejects.toThrow(
      /^422 amount must be a parseable monetary value/,
    )

    const built = buildTransactionCorrection(initial, { ...initial })
    if (!built.ok) throw new Error(built.error)
    const body = { ...built.correction, accept: true }
    expect(body).not.toHaveProperty('amount')
    const updated = await settle(mockApi.correctDocument('f07', body), 150)
    expect(updated.user_corrected).toBe(true)
    expect(updated.classification).toMatchObject({ amount: null, field_profile: 'transaction' })
  })
})
