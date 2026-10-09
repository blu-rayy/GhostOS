/**
 * UI-only types. Everything that comes from (or goes to) the backend lives in
 * ./api.ts — the shared contract. Nothing here is sent over the wire.
 */

export type View =
  | 'dashboard'
  | 'folder'
  | 'scanning'
  | 'files'
  | 'plan'
  | 'report'
  | 'completion'

/** Side panels opened from the header; they sit over the current step. */
export type Panel = 'history' | 'settings'

export type SessionPhase =
  | 'idle'
  | 'folder_selected'
  | 'scanning'
  | 'scan_failed'
  | 'reviewing'
  | 'organizing'
  | 'organized'
  | 'undoing'
  | 'undone'

export type ActivityType =
  | 'folder_selected'
  | 'scan_started'
  | 'document_analyzed'
  | 'scan_completed'
  | 'scan_failed'
  | 'record_corrected'
  | 'record_reviewed'
  | 'plan_approved'
  | 'file_moved'
  | 'report_generated'
  | 'report_exported'
  | 'undo_started'
  | 'undo_completed'
  | 'undo_conflict'
  | 'action_failed'
  | 'reviews_set_aside'

/** Session-local audit entry. There is no activity endpoint in the API contract yet. */
export interface ActivityEvent {
  id: string
  at: string
  type: ActivityType
  title: string
  detail?: string
  level: 'info' | 'success' | 'warning' | 'error'
  fileId?: string
}

/** Review state shown in the UI, derived from DocumentRecord.status + user_corrected. */
export type RowStatus = 'extracted' | 'needs_review' | 'reviewed' | 'failed' | 'skipped'
