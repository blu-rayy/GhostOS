import { vi } from 'vitest'
import type { PlanPreview, ScanProgress } from '../types/api'
import { mockApi, mockScenario } from '../api/mock'

export async function settle<T>(promise: Promise<T>, milliseconds: number): Promise<T> {
  const result = promise
  await vi.advanceTimersByTimeAsync(milliseconds)
  return result
}

export async function loadFixturePlan(root = 'C:/GhostOS-fixture-root'): Promise<PlanPreview> {
  const progress: ScanProgress = await settle(mockApi.startScan(root), 250)
  return settle(mockApi.getPlan(progress.scan_id), 200)
}

export function resetMockScenario(): void {
  mockScenario.scanError = false
  mockScenario.undoConflict = false
}
