import type {
  BatchResult,
  DocumentCorrection,
  DocumentRecord,
  PlanPreview,
  ScanProgress,
  ScanResult,
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
  getPlan(scanId: string): Promise<PlanPreview>
  approvePlan(planId: string): Promise<BatchResult>
  undoBatch(batchId: string): Promise<UndoResult>
}
