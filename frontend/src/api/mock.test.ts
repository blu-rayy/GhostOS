import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi, mockScenario } from './mock'
import { loadFixturePlan, resetMockScenario, settle } from '../test/mockHarness'

describe('fixture mock plan rules', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date('2026-10-09T14:12:00.000Z'))
    resetMockScenario()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('uses the expected destinations and collision suffix', async () => {
    const plan = await loadFixturePlan()
    const destination = new Map(plan.operations.map((operation) => [operation.file_id, operation]))

    expect(destination.get('f01')?.destination_relative_path).toBe('Invoices/2026-09/Invoice_INV-2041_Lumen_Design.pdf')
    expect(destination.get('f02')?.destination_relative_path).toBe('Receipts/2026-09/receipt_grab_0912.txt')
    expect(destination.get('f05')?.destination_relative_path).toBe('Other/meeting-notes-client-a.txt')
    expect(destination.get('f07')?.destination_relative_path).toBe('Uncategorized/receipt_office_warehouse.txt')
    expect(destination.get('f08')?.destination_relative_path).toBe('Invoices/2026-09/Invoice_INV-2041_Lumen_Design (2).pdf')
    expect(destination.get('f08')?.collision_suffixed).toBe(true)
    expect(destination.get('f10')?.destination_relative_path).toBe('Uncategorized/random_scan_0098.pdf')
    expect(destination.get('f15')?.destination_relative_path).toBe('Uncategorized/statement_0921.pdf')
    expect(destination.get('f17')?.destination_relative_path).toBe('Uncategorized/receipt-7eleven.txt')
    expect(destination.get('f18')?.destination_relative_path).toBe('Uncategorized/invoice_client_B.pdf')
  })

  it('accepts only complete, reviewed, non-duplicate invoice and receipt rows', async () => {
    const plan = await loadFixturePlan()
    const rows = new Map(plan.report_rows.map((row) => [row.file_id, row]))

    expect(rows.get('f01')?.status).toBe('accepted')
    expect(rows.get('f07')?.status).toBe('needs_review')
    expect(rows.get('f08')?.status).toBe('needs_review')
    expect(rows.get('f10')?.status).toBeUndefined()
    expect(rows.get('f15')).toBeUndefined()
    expect(rows.get('f17')?.status).toBe('needs_review')
    expect(rows.get('f18')?.status).toBe('needs_review')
    expect(plan.blocking_review_count).toBe(7) // incl. f19 birth certificate and f20 uncertain
  })

  it('computes independent currency totals from accepted rows only', async () => {
    const plan = await loadFixturePlan()
    expect(plan.totals).toEqual([
      { currency: 'PHP', amount: '26007.45', row_count: 6 },
      { currency: 'USD', amount: '157.29', row_count: 2 },
    ])
  })

  it('keeps prompt-injection text as data and constructs only safe relative destinations', async () => {
    const plan = await loadFixturePlan()
    const injection = plan.report_rows.find((row) => row.file_id === 'f13')
    expect(injection).toBeUndefined()
    for (const operation of plan.operations) {
      expect(operation.destination_relative_path).not.toMatch(/(^[\\/]|^[A-Za-z]:|\.\.)/)
      expect(operation.destination_relative_path).not.toContain('C:/Windows/System32')
    }
  })

  it('supports review transitions and manual entry for a failed document', async () => {
    const progress = await settle(mockApi.startScan('C:/GhostOS-fixture-root'), 250)
    const before = await settle(mockApi.correctDocument('f07', { amount: '1520.00', accept: false }), 150)
    expect(before.user_corrected).toBe(false)
    expect(before.review_flags).toHaveLength(1)

    const accepted = await settle(mockApi.correctDocument('f07', { amount: '1520.00', accept: true }), 150)
    expect(accepted.user_corrected).toBe(true)
    expect(accepted.review_flags).toEqual([])

    const failed = await settle(mockApi.correctDocument('f10', {
      category: 'invoice',
      merchant: 'Manual Merchant',
      date: '2026-10-01',
      amount: '10.00',
      currency: 'PHP',
      accept: true,
    }), 150)
    expect(failed.classification).toMatchObject({ category: 'invoice', amount: '10.00', currency: 'PHP' })
    expect(failed.user_corrected).toBe(true)

    const plan = await settle(mockApi.getPlan(progress.scan_id), 200)
    expect(plan.blocking_review_count).toBe(6)
    expect(plan.report_rows.find((row) => row.file_id === 'f10')?.status).toBe('accepted')
  })

  it('reports the configured undo conflict deterministically', async () => {
    const plan = await loadFixturePlan()
    mockScenario.undoConflict = true
    const result = await settle(mockApi.undoBatch(plan.plan_id.replace('plan_', 'batch_')), 600)
    expect(result.conflicts).toHaveLength(1)
    expect(result.restored).toBe(plan.operations.length - 1)
  })
})
