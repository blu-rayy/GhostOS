import type {
  BatchResult,
  DocumentCorrection,
  DocumentRecord,
  PlanPreview,
  ScanProgress,
  ScanResult,
  SortMode,
  SystemStatus,
  UndoResult,
} from '../types/api'

/** Everything the UI needs from the backend. Implemented by the fixture mock and the HTTP client. */
export interface GhostApi {
  getStatus(): Promise<SystemStatus>
  startScan(root: string): Promise<ScanProgress>
  getScanProgress(scanId: string): Promise<ScanProgress>
  getScan(scanId: string): Promise<ScanResult>
  correctDocument(fileId: string, correction: DocumentCorrection): Promise<DocumentRecord>
  getPlan(scanId: string, mode?: SortMode): Promise<PlanPreview>
  approvePlan(planId: string, mode?: SortMode): Promise<BatchResult>
  undoBatch(batchId: string): Promise<UndoResult>
}
