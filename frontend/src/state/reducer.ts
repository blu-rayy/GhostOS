import type {
  BatchResult,
  DocumentRecord,
  PlanPreview,
  ScanProgress,
  ScanResult,
  SystemStatus,
  UndoResult,
} from '../types/api'
import type { FolderSelection } from '../platform/types'
import type { ActivityEvent, SessionPhase, View } from '../types/ui'

export interface AppState {
  view: View
  phase: SessionPhase
  selectedDocId: string | null
  folder: FolderSelection | null
  /** Path typed by the user in browser mode when talking to the real backend. */
  typedRoot: string

  status: SystemStatus | null
  statusError: string | null

  progress: ScanProgress | null
  scanError: string | null
  scan: ScanResult | null

  plan: PlanPreview | null
  planLoading: boolean
  planError: string | null

  /** Snapshot of the plan the user approved, so results stay stable after later edits. */
  approvedPlan: PlanPreview | null
  batch: BatchResult | null
  undo: UndoResult | null
  /** Set while a request that changes something is in flight. */
  busy: 'approve' | 'undo' | 'correct' | null
  actionError: string | null

  activity: ActivityEvent[]
  /** UI-only demo switch (the activity log has no backend endpoint yet). */
  simulateActivityError: boolean
}

export const initialState: AppState = {
  view: 'dashboard',
  phase: 'idle',
  selectedDocId: null,
  folder: null,
  typedRoot: '',
  status: null,
  statusError: null,
  progress: null,
  scanError: null,
  scan: null,
  plan: null,
  planLoading: false,
  planError: null,
  approvedPlan: null,
  batch: null,
  undo: null,
  busy: null,
  actionError: null,
  activity: [],
  simulateActivityError: false,
}

export type Action =
  | { type: 'patch'; patch: Partial<AppState> }
  | { type: 'replaceDoc'; doc: DocumentRecord }
  | { type: 'log'; event: ActivityEvent }
  | { type: 'resetSession' }

export function reducer(state: AppState, action: Action): AppState {
  switch (action.type) {
    case 'patch':
      return { ...state, ...action.patch }
    case 'replaceDoc':
      if (!state.scan) return state
      return {
        ...state,
        scan: { ...state.scan, documents: state.scan.documents.map((d) => (d.file_id === action.doc.file_id ? action.doc : d)) },
      }
    case 'log':
      return { ...state, activity: [action.event, ...state.activity] }
    case 'resetSession':
      return { ...initialState, activity: state.activity, status: state.status, statusError: state.statusError, simulateActivityError: state.simulateActivityError }
  }
}
