import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { buildTransactionCorrection } from '../lib/correction'
import { httpApi } from './http'

// The request the real API client sends for a Check-panel correction (network stubbed).
describe('httpApi.correctDocument payload', () => {
  const fetchMock = vi.fn()
  beforeEach(() => {
    fetchMock.mockReset()
    fetchMock.mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  const sentBody = () => JSON.parse(fetchMock.mock.calls[0][1].body as string) as Record<string, unknown>

  it('marks a transaction checked with no amount entered: PATCH without an amount field', async () => {
    const initial = { merchant: 'Office Warehouse', date: '2026-09-05', amount: '' }
    const built = buildTransactionCorrection(initial, { ...initial })
    if (!built.ok) throw new Error(built.error)
    await httpApi.correctDocument('f07', { ...built.correction, accept: true })

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://127.0.0.1:8000/api/documents/f07')
    expect(init.method).toBe('PATCH')
    expect(sentBody()).toEqual({ accept: true })
    expect(sentBody()).not.toHaveProperty('amount')
  })

  it('sends an intentional amount edit as a normalised string, and a cleared date as null', async () => {
    const built = buildTransactionCorrection({ merchant: 'Grab', date: '2026-09-12', amount: '' }, { merchant: 'Grab', date: '', amount: '₱245' })
    if (!built.ok) throw new Error(built.error)
    await httpApi.correctDocument('f02', { ...built.correction, accept: true })
    expect(sentBody()).toEqual({ amount: '245.00', date: null, accept: true })
  })

  it('leaves Leave-for-review and filing decisions unchanged: category and accept only', async () => {
    await httpApi.correctDocument('f20', { category: 'uncertain', accept: true })
    expect(sentBody()).toEqual({ category: 'uncertain', accept: true })
  })
})
