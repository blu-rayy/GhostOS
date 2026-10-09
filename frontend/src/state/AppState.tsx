import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react'
import { api, USING_FIXTURES } from '../api'
import { mockTiming } from '../api/mock'
import { DEMO_FOLDER_NAME } from '../lib/copy'
import { errorText } from '../lib/format'
import { basename, buildFileRows, buildPlanRows, docStatus, type FileRow, type PlanRow } from '../lib/viewModel'
import { resolvePlatform } from '../platform/electron'
import type { GhostOSPlatform } from '../platform/types'
import type { DocumentCorrection, DocumentRecord } from '../types/api'
import type { ActivityEvent, View } from '../types/ui'
import { initialState, loadDesktopPip, reducer, saveDesktopPip, type Action, type AppState } from './reducer'

/**
 * Session state + actions. All data comes from `api` (src/api): the fixture
 * mock by default, or FastAPI when VITE_USE_FIXTURES=false. Nothing here
 * touches the filesystem; desktop capabilities come from src/platform.
 */

const POLL_MS = 500
const STATUS_POLL_MS = 10_000
const FIXTURE_ROOT = 'fixtures://sample'

let eventSeq = 0
function makeEvent(e: Omit<ActivityEvent, 'id' | 'at'>): ActivityEvent {
  eventSeq += 1
  return { id: `ev${Date.now()}_${eventSeq}`, at: new Date().toISOString(), ...e }
}

/** First path segment that most destinations share ("Receipts/2026-09/a.pdf" -> "Receipts"). */
function busiestTopFolder(paths: string[]): string | null {
  const counts = new Map<string, number>()
  for (const p of paths) {
    const top = p.split('/')[0]
    if (top && top !== p) counts.set(top, (counts.get(top) ?? 0) + 1)
  }
  let best: string | null = null
  for (const [name, n] of counts) if (best === null || n > (counts.get(best) ?? 0)) best = name
  return best
}

export interface Counts {
  documents: number
  skipped: number
  needsReview: number
  blocking: number
  failed: number
}

interface AppApi {
  state: AppState
  dispatch: React.Dispatch<Action>
  platform: GhostOSPlatform
  usingFixtures: boolean
  rows: FileRow[]
  planRows: PlanRow[]
  selectedDoc: DocumentRecord | null
  counts: Counts
  navigate(view: View): void
  selectDoc(id: string | null): void
  chooseFolder(): Promise<void>
  chooseSampleFolder(): void
  setTypedRoot(path: string): void
  startScan(): Promise<void>
  reloadPlan(): Promise<void>
  correct(fileId: string, correction: DocumentCorrection, label: string): Promise<boolean>
  approve(): Promise<void>
  undoBatch(): Promise<void>
  logExport(filename: string, rows: number): void
  resetSession(): void
  setDesktopPip(on: boolean): void
}

const Ctx = createContext<AppApi | null>(null)

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reducer, initialState, (init) => ({ ...init, desktopPip: loadDesktopPip() }))
  const stateRef = useRef(state)
  useEffect(() => {
    stateRef.current = state
  })
  const platform = useMemo(() => resolvePlatform(), [])
  const pollTimer = useRef<number | null>(null)

  const patch = useCallback((p: Partial<AppState>) => dispatch({ type: 'patch', patch: p }), [])
  const log = useCallback((e: Omit<ActivityEvent, 'id' | 'at'>) => dispatch({ type: 'log', event: makeEvent(e) }), [])
  const stopPolling = () => {
    if (pollTimer.current !== null) window.clearTimeout(pollTimer.current)
    pollTimer.current = null
  }

  // System status: polled so the "local only" claims reflect what the backend reports.
  useEffect(() => {
    let alive = true
    let timer: number
    const tick = async () => {
      try {
        const status = await api.getStatus()
        if (alive) patch({ status, statusError: null })
      } catch (e) {
        if (alive) patch({ statusError: errorText(e) })
      }
      if (alive) timer = window.setTimeout(tick, STATUS_POLL_MS)
    }
    tick()
    return () => {
      alive = false
      window.clearTimeout(timer)
    }
  }, [patch])
  useEffect(() => stopPolling, [])

  const rows = useMemo(() => buildFileRows(state.scan, state.plan), [state.scan, state.plan])
  const planRows = useMemo(() => buildPlanRows(state.scan, state.plan), [state.scan, state.plan])
  const selectedDoc = state.scan?.documents.find((d) => d.file_id === state.selectedDocId) ?? null
  const counts = useMemo<Counts>(() => {
    const docs = state.scan?.documents ?? []
    const statuses = docs.map(docStatus)
    return {
      documents: docs.length,
      skipped: state.scan?.skipped.length ?? 0,
      needsReview: statuses.filter((s) => s === 'needs_review' || s === 'failed').length,
      blocking: state.plan?.blocking_review_count ?? statuses.filter((s) => s === 'needs_review').length,
      failed: statuses.filter((s) => s === 'failed').length,
    }
  }, [state.scan, state.plan])

  const loadPlan = useCallback(
    async (scanId: string) => {
      patch({ planLoading: true, planError: null })
      try {
        const plan = await api.getPlan(scanId)
        patch({ plan, planLoading: false })
      } catch (e) {
        patch({ planLoading: false, planError: errorText(e) })
      }
    },
    [patch],
  )

  const value: AppApi = {
    state,
    dispatch,
    platform,
    usingFixtures: USING_FIXTURES,
    rows,
    planRows,
    selectedDoc,
    counts,
    // Opening a step closes any History/Settings panel.
    navigate: (view) => patch({ view, panel: null }),
    selectDoc: (id) => patch({ selectedDocId: id }),

    async chooseFolder() {
      const selection = await platform.selectFolder()
      if (!selection) return
      stopPolling()
      dispatch({ type: 'resetSession' })
      patch({ folder: selection, phase: 'folder_selected', view: 'folder' })
      log({
        type: 'folder_selected',
        level: 'info',
        title: `Folder selected: ${selection.name}`,
        detail: 'Selection only. Nothing has been read or moved yet.',
      })
    },

    chooseSampleFolder() {
      stopPolling()
      dispatch({ type: 'resetSession' })
      patch({ folder: { kind: 'mock', name: DEMO_FOLDER_NAME, documentCount: null }, phase: 'folder_selected', view: 'folder' })
      log({ type: 'folder_selected', level: 'info', title: 'Demo files selected', detail: 'Demo data bundled with the app. No files on this computer are read.' })
    },

    setTypedRoot: (typedRoot) => patch({ typedRoot }),

    async reloadPlan() {
      const scan = stateRef.current.scan
      if (scan) await loadPlan(scan.scan_id)
    },

    async startScan() {
      const s = stateRef.current
      if (!s.folder) return
      const root = s.folder.path ?? (s.typedRoot.trim() || (USING_FIXTURES ? FIXTURE_ROOT : ''))
      if (!root) {
        patch({ scanError: 'Enter the folder path, or open GhostOS in the desktop app to use the folder picker.' })
        return
      }
      stopPolling()
      patch({ phase: 'scanning', view: 'scanning', scan: null, plan: null, progress: null, scanError: null, batch: null, undo: null, approvedPlan: null, selectedDocId: null })
      log({ type: 'scan_started', level: 'info', title: `Scan started: ${s.folder.name}`, detail: USING_FIXTURES ? 'Fixture mock. Processed in this app only.' : 'Sent to the local backend at 127.0.0.1.' })

      let lastProcessed = 0
      let lastFile: string | null = null
      // Desktop Pip (Settings toggle): only for a real folder picked in the desktop app.
      const pip = s.desktopPip && s.folder.path ? platform.desktopPip : undefined
      const fail = (message: string) => {
        stopPolling()
        pip?.stop()
        patch({ phase: 'scan_failed', scanError: message })
        log({ type: 'scan_failed', level: 'error', title: 'Scan stopped', detail: message })
      }
      const poll = async (scanId: string) => {
        try {
          const progress = await api.getScanProgress(scanId)
          patch({ progress })
          if (progress.files_processed > lastProcessed && lastFile) {
            log({ type: 'document_analyzed', level: 'info', title: `Analyzed ${basename(lastFile)}` })
          }
          lastProcessed = progress.files_processed
          if (pip && progress.current_file && progress.current_file !== lastFile) pip.target(progress.current_file)
          lastFile = progress.current_file
          if (progress.state === 'error') return fail(progress.error ?? 'The scan failed.')
          if (progress.state === 'done') {
            pip?.stop()
            const scan = await api.getScan(scanId)
            // Go straight to Check. An open History/Settings panel stays on top.
            patch({ scan, phase: 'reviewing', ...(stateRef.current.view === 'scanning' ? { view: 'files' as const } : {}) })
            log({
              type: 'scan_completed',
              level: 'success',
              title: `Scan complete: ${scan.documents.length} documents, ${scan.skipped.length} skipped`,
              detail: 'Plan drafted. No files have been moved.',
            })
            await loadPlan(scanId)
            return
          }
          pollTimer.current = window.setTimeout(() => poll(scanId), POLL_MS)
        } catch (e) {
          fail(errorText(e))
        }
      }
      try {
        // Demo data with desktop Pip: slow the fake scan down so the animation can play, and let
        // Pip haunt random files in the picked folder (the demo file names aren't in it).
        mockTiming.scanDurationMs = USING_FIXTURES && pip ? 32_000 : 4000
        const first = await api.startScan(root)
        patch({ progress: first })
        if (pip && s.folder.path) pip.start(s.folder.path, { randomFiles: USING_FIXTURES })
        poll(first.scan_id)
      } catch (e) {
        fail(errorText(e))
      }
    },

    async correct(fileId, correction, label) {
      const s = stateRef.current
      const doc = s.scan?.documents.find((d) => d.file_id === fileId)
      patch({ busy: 'correct', actionError: null })
      try {
        const updated = await api.correctDocument(fileId, correction)
        dispatch({ type: 'replaceDoc', doc: updated })
        const name = basename(doc?.relative_path ?? fileId)
        log(
          correction.accept
            ? { type: 'record_reviewed', level: 'success', title: `Marked reviewed: ${name}`, fileId }
            : { type: 'record_corrected', level: 'info', title: `Corrected ${label} on ${name}`, fileId },
        )
        patch({ busy: null })
        if (s.scan) await loadPlan(s.scan.scan_id)
        return true
      } catch (e) {
        patch({ busy: null, actionError: errorText(e) })
        log({ type: 'action_failed', level: 'error', title: 'Correction not saved', detail: errorText(e), fileId })
        return false
      }
    },

    async approve() {
      const s = stateRef.current
      if (!s.plan) return
      // Totals shows "moving" (3c) while this runs; failures stay on Totals (3d), success opens Done.
      patch({ busy: 'approve', actionError: null, phase: 'organizing', view: 'report', approvedPlan: s.plan })
      try {
        const batch = await api.approvePlan(s.plan.plan_id)
        const onTotals = stateRef.current.view === 'report'
        patch({ batch, busy: null, phase: 'organized', ...(onTotals && batch.failed.length === 0 ? { view: 'completion' as const } : {}) })
        log({ type: 'plan_approved', level: 'info', title: `Move approved (${s.plan.operations.length} files)`, detail: `Batch ${batch.batch_id}` })
        for (const op of s.plan.operations) {
          const failed = batch.failed.find((f) => f.file_id === op.file_id)
          log(
            failed
              ? { type: 'action_failed', level: 'error', title: `Not moved: ${op.original_relative_path}`, detail: failed.error, fileId: op.file_id }
              : { type: 'file_moved', level: 'success', title: `Moved ${op.original_relative_path}`, detail: `→ ${op.destination_relative_path}`, fileId: op.file_id },
          )
        }
        log({ type: 'report_generated', level: 'success', title: 'Totals list written', detail: batch.report_relative_path })
        // Desktop Pip (Settings toggle): Pip flies into the real folder that received the most
        // files. Cosmetic; never affects the result.
        const root = s.folder?.path
        if (s.desktopPip && root && batch.failed.length === 0 && batch.moved > 0 && platform.desktopPip) {
          const top = busiestTopFolder(s.plan.operations.map((op) => op.destination_relative_path))
          if (top) platform.desktopPip.intoFolder(root, top)
        }
      } catch (e) {
        patch({ busy: null, phase: 'reviewing', actionError: errorText(e), view: 'report', approvedPlan: null })
        log({ type: 'action_failed', level: 'error', title: 'Approval failed. Nothing was moved.', detail: errorText(e) })
      }
    },

    async undoBatch() {
      const s = stateRef.current
      if (!s.batch) return
      patch({ busy: 'undo', actionError: null, phase: 'undoing' })
      log({ type: 'undo_started', level: 'info', title: 'Putting files back', detail: `Batch ${s.batch.batch_id}` })
      try {
        const undo = await api.undoBatch(s.batch.batch_id)
        patch({ undo, busy: null, phase: 'undone' })
        for (const c of undo.conflicts) {
          log({ type: 'undo_conflict', level: 'warning', title: `Not restored: ${c.relative_path}`, detail: c.reason, fileId: c.file_id })
        }
        log({
          type: 'undo_completed',
          level: undo.conflicts.length ? 'warning' : 'success',
          title: undo.conflicts.length ? 'Put back (some files stayed)' : 'Put back',
          detail: `${undo.restored} restored, ${undo.conflicts.length} left in organized location.`,
        })
      } catch (e) {
        patch({ busy: null, phase: 'organized', actionError: errorText(e) })
        log({ type: 'action_failed', level: 'error', title: 'Undo failed', detail: errorText(e) })
      }
    },

    logExport(filename, n) {
      log({ type: 'report_exported', level: 'success', title: `Exported ${filename}`, detail: `${n} accepted rows, generated in the app.` })
    },

    resetSession() {
      stopPolling()
      if (stateRef.current.phase === 'scanning') platform.desktopPip?.stop()
      dispatch({ type: 'resetSession' })
    },

    setDesktopPip(on) {
      saveDesktopPip(on)
      patch({ desktopPip: on })
    },
  }

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// oxlint-disable-next-line react/only-export-components
export function useApp(): AppApi {
  const v = useContext(Ctx)
  if (!v) throw new Error('useApp must be used inside AppStateProvider')
  return v
}
