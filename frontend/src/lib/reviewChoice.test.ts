import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../api/mock'
import { resetMockScenario, settle } from '../test/mockHarness'
import { reviewChoiceGroups } from './viewModel'

// docs/design/review-choice-popup.md: the pop-up's counts, and "set all aside" = partial mode.
async function startScan() {
  const progress = await settle(mockApi.startScan('C:/GhostOS-fixture-root'), 250)
  const scan = await settle(mockApi.getScan(progress.scan_id), 250)
  return scan
}

describe('review choice pop-up', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    resetMockScenario()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('groups the files that block Move from the scan documents', async () => {
    const scan = await startScan()
    // f07 amount conflict, f17 no date, f18 evidence | f15 statement, f19 birth cert, f20 unclear | f13 injection
    expect(reviewChoiceGroups(scan.documents)).toEqual({ total: 7, confirm: 3, notReceipts: 3, suspicious: 1 })
    const blocking = await settle(mockApi.getPlan(scan.scan_id), 200)
    expect(blocking.blocking_review_count).toBe(7)
  })

  it('sets every unchecked file aside in Uncategorized/ without counting it or changing any document', async () => {
    const scan = await startScan()
    const before = JSON.stringify(scan.documents)
    const blocking = await settle(mockApi.getPlan(scan.scan_id), 200)
    const partial = await settle(mockApi.getPlan(scan.scan_id, 'partial'), 200)
    expect(partial.mode).toBe('partial')
    const unresolved = scan.documents.filter((d) => d.status === 'needs_review' && !d.user_corrected).map((d) => d.file_id)
    for (const id of unresolved) {
      expect(partial.operations.find((o) => o.file_id === id)?.destination_relative_path).toMatch(/^Uncategorized\//)
      expect(partial.report_rows.find((r) => r.file_id === id)).toBeUndefined()
    }
    expect(partial.totals).toEqual(blocking.totals)
    const after = await settle(mockApi.getScan(scan.scan_id), 250)
    expect(JSON.stringify(after.documents)).toBe(before)
  })

  it('only approves in the mode that was previewed', async () => {
    const scan = await startScan()
    const blocking = await settle(mockApi.getPlan(scan.scan_id), 200)
    await expect(settle(mockApi.approvePlan(blocking.plan_id), 800)).rejects.toThrow(/^409 Plan has 7 unresolved/)
    await expect(settle(mockApi.approvePlan(blocking.plan_id, 'partial'), 800)).rejects.toThrow(/^409 Plan mode is 'blocking'/)
    const partial = await settle(mockApi.getPlan(scan.scan_id, 'partial'), 200)
    await expect(settle(mockApi.approvePlan(partial.plan_id), 800)).rejects.toThrow(/^409 Plan mode is 'partial'/)
    const batch = await settle(mockApi.approvePlan(partial.plan_id, 'partial'), 800)
    expect(batch.moved).toBe(partial.operations.length)
  })
})
