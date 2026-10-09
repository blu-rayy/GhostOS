import { vi } from 'vitest'
import type { PlanPreview, ScanProgress } from '../types/api'
import { mockApi, mockScenario } from '../api/mock'

/**
 * Advances fake timers so a mock call can finish, then returns its promise. A call that is meant
 * to fail (a 422/409 checked with `expect(...).rejects`) rejects while the timers run, before the
 * test attaches its handler, so it is marked as handled here first. The returned promise still
 * rejects exactly as before; this only stops Vitest reporting an unhandled rejection (exit code 1).
 */
export async function settle<T>(promise: Promise<T>, milliseconds: number): Promise<T> {
  promise.catch(() => undefined)
  await vi.advanceTimersByTimeAsync(milliseconds)
  return promise
}

export async function loadFixturePlan(root = 'C:/GhostOS-fixture-root'): Promise<PlanPreview> {
  const progress: ScanProgress = await settle(mockApi.startScan(root), 250)
  return settle(mockApi.getPlan(progress.scan_id), 200)
}

export function resetMockScenario(): void {
  mockScenario.scanError = false
  mockScenario.undoConflict = false
}
