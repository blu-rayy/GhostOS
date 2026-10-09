import type {
  BatchResult,
  DocumentRecord,
  PlanPreview,
  ScanProgress,
  ScanResult,
  SortMode,
  SystemStatus,
  UndoResult,
} from '../types/api'
import type { FolderSelection } from '../platform/types'
import type { ActivityEvent, Panel, SessionPhase, View } from '../types/ui'

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
  /** History or Settings side panel, open over the current step. */
  panel: Panel | null
  /** Settings toggle: Pip appears in File Explorer while reading and after moving (desktop only). */
  desktopPip: boolean
  /**
   * Review choice for this scan (docs/design/review-choice-popup.md). 'blocking': every flagged
   * file must be decided before Move. 'partial': unchecked files are set aside in Uncategorized/.
   */
  sortMode: SortMode
  /** True right after reading when files are blocking and the user hasn't chosen yet. */
  reviewChoicePending: boolean
  /** The short "All moved." beat on Totals between a successful move and the Done screen. */
  moveFinished: boolean
}

const DESKTOP_PIP_KEY = 'ghostos.desktopPip'

export function loadDesktopPip(): boolean {
  try {
    return localStorage.getItem(DESKTOP_PIP_KEY) === '1'
  } catch {
    return false
  }
}

export function saveDesktopPip(on: boolean): void {
  try {
    localStorage.setItem(DESKTOP_PIP_KEY, on ? '1' : '0')
  } catch {
    // Storage blocked: the toggle still works for this session.
  }
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
  panel: null,
  desktopPip: false,
  sortMode: 'blocking',
  reviewChoicePending: false,
  moveFinished: false,
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
      return { ...initialState, activity: state.activity, status: state.status, statusError: state.statusError, desktopPip: state.desktopPip }
  }
}
