import { useMemo, useRef, useState, type ReactNode } from 'react'
import { useApp } from '../../state/AppState'
import type { BatchResult, PlanPreview, UndoResult } from '../../types/api'
import { PIP_LINES } from '../../lib/copy'
import { money } from '../../lib/format'
import { downloadText, toCsv } from '../../lib/report'
import { NEEDS_REVIEW_FOLDER, OTHER_FOLDER, currencyName, files, folderOf, groupByDestination, stayCount } from '../../lib/totals'
import { basename } from '../../lib/viewModel'
import { PaperButton } from '../../components/paper/Button'
import { FolderRow } from '../../components/paper/CheckComponents'
import { PageFooter } from '../../components/paper/PageFooter'
import { CardTitle, PaperCard } from '../../components/paper/PaperCard'
import { PaperDialog } from '../../components/paper/PaperDialog'
import { StickyNote } from '../../components/paper/StickyNote'
import { HistoryIcon } from '../../components/paper/icons'
import { PipWithBubble, type PipMood } from '../../components/pip/Pip'

/**
 * Step 4 · Done (docs/design/step4-done.md). 4a after a move (also while putting back),
 * 4c when the undo fully succeeded, 4d when some files stayed (UndoResult.conflicts).
 * Counts, folders and totals come from BatchResult / UndoResult / the approved PlanPreview.
 */
export function DonePage() {
  const { state, navigate, resetSession } = useApp()
  const { batch, approvedPlan: plan, undo } = state
  const folderName = state.folder?.name ?? 'your folder'
  // The CSV the user saved from Totals/Done is a file the browser wrote, so undo can't touch it.
  const savedCsv = state.activity.some((e) => e.type === 'report_exported')
  const startOver = () => {
    resetSession()
    navigate('dashboard')
  }

  if (!batch || !plan) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-4 p-8 text-center">
        <h1 className="m-0 font-display text-[42px] font-normal">Nothing has moved yet</h1>
        <p className="m-0 text-[19px]">Files only move after you say yes on Totals.</p>
        <PaperButton variant="primary" onClick={() => navigate(state.scan ? 'report' : 'dashboard')}>
          {state.scan ? 'Go to Totals' : 'Go to Start'}
        </PaperButton>
      </div>
    )
  }

  if (undo && state.phase === 'undone') {
    return undo.conflicts.length === 0 ? (
      <PutBack undo={undo} folderName={folderName} savedCsv={savedCsv} onDone={startOver} />
    ) : (
      <SomeStayed undo={undo} plan={plan} folderName={folderName} onDone={startOver} />
    )
  }
  return <AllTidy batch={batch} plan={plan} folderName={folderName} savedCsv={savedCsv} onDone={startOver} />
}

function DoneLayout({ mood, line, children, footer }: { mood: PipMood; line: string; children: ReactNode; footer: ReactNode }) {
  return (
    <>
      <div className="mx-auto grid min-h-0 w-full max-w-[1366px] flex-1 grid-cols-[340px_minmax(0,1fr)] items-center gap-10 px-16 pb-[18px] pt-6">
        <PipWithBubble mood={mood} line={line} size={240} tailOffset={100} />
        <div className="flex max-h-full min-h-0 min-w-0 flex-col overflow-y-auto py-1 pr-2">{children}</div>
      </div>
      {footer}
    </>
  )
}

/** Back to Step 3 · Totals, which shows the moved (or put back) state read-only. */
function BackToTotals({ disabled }: { disabled?: boolean }) {
  const { navigate } = useApp()
  return (
    <PaperButton variant="link" onClick={() => navigate('report')} disabled={disabled}>
      ← back to totals
    </PaperButton>
  )
}

function Title({ folderName, children }: { folderName: string; children: ReactNode }) {
  return (
    <>
      <p className="m-0 text-[20px] text-graphite">{folderName}</p>
      <h1 className="m-0 font-display text-[56px] font-normal leading-[1.05]">{children}</h1>
    </>
  )
}

function doneNote(folder: string): string {
  if (folder === NEEDS_REVIEW_FOLDER) return 'look later'
  if (folder === OTHER_FOLDER) return 'not counted'
  return ''
}

/** "09 Oct 2026, 14:32" */
function savedAt(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return `${d.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' })}, ${d.toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })}`
}

/** 4a · All tidy, plus the 4b confirmation. */
function AllTidy({ batch, plan, folderName, savedCsv, onDone }: { batch: BatchResult; plan: PlanPreview; folderName: string; savedCsv: boolean; onDone: () => void }) {
  const { state, undoBatch, logExport } = useApp()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const failedIds = useMemo(() => new Set(batch.failed.map((f) => f.file_id)), [batch])
  const groups = useMemo(() => groupByDestination(plan.operations.filter((op) => !failedIds.has(op.file_id))), [plan, failedIds])
  const moved = batch.moved
  const stayed = stayCount(state.scan?.documents.length ?? 0, state.scan?.skipped.length ?? 0, moved)
  const undoing = state.busy === 'undo'

  const exportCsv = () => {
    const filename = `ghostos_totals_${folderName.replace(/\W+/g, '_')}.csv`
    downloadText(filename, toCsv(plan.report_rows))
    logExport(filename, plan.report_rows.filter((r) => r.status === 'accepted').length)
  }

  return (
    <DoneLayout
      mood="done"
      line={PIP_LINES.sorted(moved)}
      footer={
        <PageFooter
          className="!h-[72px]"
          left={
            <>
              <BackToTotals disabled={undoing} />
              <span className="ml-3 flex items-center gap-2 text-[17px]">
                <HistoryIcon size={22} />
                Saved in History · {savedAt(batch.committed_at)}
              </span>
            </>
          }
          right={
            <PaperButton variant="primary" onClick={onDone} disabled={undoing}>
              Tidy another folder
            </PaperButton>
          }
        />
      }
    >
      <Title folderName={folderName}>All tidy.</Title>
      <p className="m-0 mt-2 text-[20px]">
        {files(moved)} moved into {groups.length} {groups.length === 1 ? 'folder' : 'folders'}. {stayed} stayed where they were.
        {batch.failed.length > 0 && ` ${batch.failed.length} of them didn't move.`}
      </p>

      <div className="mt-5 grid grid-cols-[1.2fr_1fr] items-start gap-5">
        <PaperCard as="section" aria-labelledby="went-title" className="px-5 pb-3 pt-3">
          <CardTitle size="sm">
            <span id="went-title">where they went</span>
          </CardTitle>
          <div className="mt-1">
            {groups.map((g) => (
              <FolderRow key={g.folder} path={g.folder} note={doneNote(g.folder)} count={g.count} />
            ))}
          </div>
        </PaperCard>
        <PaperCard as="section" variant="b" aria-labelledby="done-totals-title" className="px-5 pb-4 pt-3">
          <CardTitle size="sm">
            <span id="done-totals-title">totals</span>
          </CardTitle>
          {plan.totals.length === 0 ? (
            <p className="m-0 mt-1 text-[17px] text-graphite">Nothing was counted.</p>
          ) : (
            <ul className="m-0 mt-1 list-none p-0">
              {plan.totals.map((t) => (
                <li key={t.currency} className="flex items-baseline justify-between gap-3 border-b-[1.5px] border-dashed border-pencil py-1.5">
                  <span className="text-[17px]">
                    {currencyName(t.currency)} · {t.row_count}
                  </span>
                  <span className="font-mono text-[18px] font-bold">{money(t.amount, t.currency)}</span>
                </li>
              ))}
            </ul>
          )}
          <PaperButton variant="secondary" size="sm" className="mt-4 w-full" onClick={exportCsv}>
            Save list as CSV
          </PaperButton>
        </PaperCard>
      </div>

      {state.actionError && !undoing && (
        <StickyNote tone="pink" alert tilt={0} className="mt-4 px-4 py-2">
          <p className="m-0 text-[17px]">Putting files back didn't work: {state.actionError}</p>
        </StickyNote>
      )}

      <div className="mt-5 flex items-center justify-end gap-4 border-t-[2px] border-dashed border-ink pt-4">
        <span className="text-[18px]">Moved the wrong way? You can undo it all.</span>
        <PaperButton variant="careful" size="sm" className="!bg-sticky-pink" onClick={() => setConfirmOpen(true)} disabled={undoing || moved === 0}>
          {undoing ? 'Putting back…' : 'Put files back…'}
        </PaperButton>
      </div>

      <PutBackConfirm
        open={confirmOpen}
        n={moved}
        savedCsv={savedCsv}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false)
          void undoBatch()
        }}
      />
    </DoneLayout>
  )
}

/** 4b · Confirm putting files back. "Keep them" has initial focus; Esc keeps. */
export function PutBackConfirm({ open, n, savedCsv, onCancel, onConfirm }: { open: boolean; n: number; savedCsv: boolean; onCancel: () => void; onConfirm: () => void }) {
  const keep = useRef<HTMLButtonElement>(null)
  return (
    <PaperDialog open={open} onCancel={onCancel} role="alertdialog" variant="b" labelledBy="put-back-title" describedBy="put-back-desc" initialFocus={keep}>
      <div className="px-8 pb-6 pt-6">
        <h2 id="put-back-title" className="m-0 font-display text-[36px] font-normal leading-tight">
          Put {files(n)} back?
        </h2>
        {/* Nothing about the folders Pip made: what undo does with them isn't confirmed yet (R5). */}
        <p id="put-back-desc" className="m-0 mt-2 text-[18px] leading-7">
          Each file goes back to <strong>exactly where it was</strong> before you pressed Move.
        </p>
        <StickyNote tilt={-0.8} className="mt-4 px-4 py-3">
          <p className="m-0 text-[17px] leading-6">
            {savedCsv && 'Your saved CSV stays. '}If you changed a moved file since, Pip leaves that one alone and tells you.
          </p>
        </StickyNote>
        <div className="mt-6 flex items-center justify-end gap-4">
          <PaperButton ref={keep} variant="secondary" size="sm" onClick={onCancel}>
            Keep them where they are
          </PaperButton>
          <PaperButton variant="primary" size="sm" className="!shadow-[5px_5px_0_#ffb3b3]" onClick={onConfirm}>
            Put {files(n)} back
          </PaperButton>
        </div>
      </div>
    </PaperDialog>
  )
}

/** 4c · Back how it was. Only claims the undo result confirms. */
function PutBack({ undo, folderName, savedCsv, onDone }: { undo: UndoResult; folderName: string; savedCsv: boolean; onDone: () => void }) {
  const n = undo.restored
  return (
    <DoneLayout mood="shrug" line={PIP_LINES.undone} footer={<PageFooter className="!h-[72px]" left={<BackToTotals />} right={<PaperButton variant="primary" onClick={onDone}>Tidy a folder</PaperButton>} />}>
      <Title folderName={folderName}>Back how it was.</Title>
      <p className="m-0 mt-2 text-[20px]">{n === 1 ? 'The file is in its original place.' : `All ${n} files are in their original places.`}</p>
      <ul className="m-0 mt-5 list-none space-y-2 p-0 text-[20px]">
        <Tick>
          {n} of {n} files put back
        </Tick>
        {savedCsv && <Tick>your CSV is still saved</Tick>}
      </ul>
      <p className="m-0 mt-5 text-[18px] text-graphite">This shows up in History as "put back".</p>
    </DoneLayout>
  )
}

function Tick({ children }: { children: ReactNode }) {
  return (
    <li className="flex items-center gap-3">
      <span aria-hidden className="inline-flex h-7 w-7 items-center justify-center rounded-full border-[2.5px] border-ink bg-hl-done text-[16px] leading-none">
        ✓
      </span>
      <span>{children}</span>
    </li>
  )
}

/** 4d · Some files stayed (UndoResult.conflicts). A result screen: undo has no pre-check. */
function SomeStayed({ undo, plan, folderName, onDone }: { undo: UndoResult; plan: PlanPreview; folderName: string; onDone: () => void }) {
  const stuck = undo.conflicts.length
  const destination = new Map(plan.operations.map((op) => [op.file_id, op]))
  return (
    <DoneLayout mood="sigh" line={PIP_LINES.comfy(stuck)} footer={<PageFooter className="!h-[72px]" left={<BackToTotals />} right={<PaperButton variant="primary" onClick={onDone}>OK, leave them</PaperButton>} />}>
      <Title folderName={folderName}>
        {undo.restored} back, {stuck} stayed.
      </Title>
      <StickyNote tone="pink" alert tilt={-0.8} className="mt-4 max-w-[680px] px-4 py-3">
        <p className="m-0 text-[19px] leading-6">
          Pip didn't overwrite anything. {stuck === 1 ? 'This one stays in its new folder' : `These ${stuck} stay in their new folder`} until you decide.
        </p>
      </StickyNote>
      <PaperCard as="section" aria-label="Files that stayed" className="mt-5 max-w-[820px] px-5 py-2">
        <ul className="m-0 list-none p-0">
          {undo.conflicts.map((c) => {
            const op = destination.get(c.file_id)
            return (
              <li key={c.file_id} className="flex items-center gap-4 border-b-[1.5px] border-dashed border-pencil py-2.5 last:border-b-0">
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[19px]">{basename(op?.original_relative_path ?? c.relative_path)}</span>
                  <span className="block text-[17px] text-graphite">{c.reason.trim() || "couldn't go back safely"}</span>
                </span>
                {op && <span className="shrink-0 font-mono text-[14px]">{folderOf(op.destination_relative_path)}</span>}
              </li>
            )
          })}
        </ul>
      </PaperCard>
      <p className="m-0 mt-4 text-[18px]">You can move these yourself, or leave them. Pip won't touch them again.</p>
    </DoneLayout>
  )
}
