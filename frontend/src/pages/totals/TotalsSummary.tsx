import { useMemo, useRef, useState } from 'react'
import { useApp } from '../../state/AppState'
import type { PlanPreview } from '../../types/api'
import { money } from '../../lib/format'
import { downloadText, toCsv } from '../../lib/report'
import { acceptedRowsByDate, currencyName, files, folderNote, folderOf, groupByDestination, monthFilters, monthKey, monthRange, stayCount } from '../../lib/totals'
import { PaperButton } from '../../components/paper/Button'
import { Chip } from '../../components/paper/Chip'
import { FolderRow } from '../../components/paper/CheckComponents'
import { PageFooter } from '../../components/paper/PageFooter'
import { CardTitle, PaperCard } from '../../components/paper/PaperCard'
import { PaperDialog } from '../../components/paper/PaperDialog'
import { StickyNote } from '../../components/paper/StickyNote'
import { UndoIcon } from '../../components/paper/icons'
import { cx } from '../../components/ui/cx'

/** Green highlighter stroke behind the total (the shared `.marker` is yellow). */
const GREEN_MARKER = { background: 'linear-gradient(transparent 45%, rgb(var(--hl-done)) 45%, rgb(var(--hl-done)) 92%, transparent 92%)' }
const LIST_COLS = 'grid grid-cols-[110px_minmax(0,1fr)_80px_130px_170px] items-center gap-3'

/** 3a · Totals. Every number comes from the PlanPreview; nothing is summed here. */
export function TotalsSummary({ plan }: { plan: PlanPreview }) {
  const { state, navigate, approve, logExport } = useApp()
  const [month, setMonth] = useState<string | null>(null)
  const [confirmOpen, setConfirmOpen] = useState(false)
  const [movesOpen, setMovesOpen] = useState(false)

  const rows = useMemo(() => acceptedRowsByDate(plan.report_rows), [plan])
  const months = useMemo(() => monthFilters(rows), [rows])
  const range = monthRange(rows)
  const visible = month ? rows.filter((r) => monthKey(r.date) === month) : rows
  const destination = useMemo(() => new Map(plan.operations.map((op) => [op.file_id, folderOf(op.destination_relative_path)])), [plan])
  const corrected = useMemo(() => new Set((state.scan?.documents ?? []).filter((d) => d.user_corrected).map((d) => d.file_id)), [state.scan])
  const groups = useMemo(() => groupByDestination(plan.operations), [plan])

  const folderName = state.folder?.name ?? 'your folder'
  const moves = plan.operations.length
  const stay = stayCount(state.scan?.documents.length ?? 0, state.scan?.skipped.length ?? 0, moves)
  const moved = state.batch !== null
  const blocking = plan.blocking_review_count

  const exportCsv = () => {
    const filename = `ghostos_totals_${folderName.replace(/\W+/g, '_')}.csv`
    downloadText(filename, toCsv(plan.report_rows))
    logExport(filename, rows.length)
  }

  return (
    <>
      <div className="mx-auto grid min-h-0 w-full max-w-[1366px] flex-1 grid-cols-[minmax(0,1fr)_360px] gap-[26px] px-8 pb-[14px] pt-[18px]">
        {/* Left column: totals per currency and the list */}
        <section className="flex min-h-0 min-w-0 flex-col" aria-labelledby="totals-title">
          <div className="flex shrink-0 items-end justify-between gap-4">
            <h1 id="totals-title" className="m-0 font-display text-[42px] font-normal leading-none">
              Your totals
            </h1>
            <p className="m-0 truncate text-[17px]">
              {[files(rows.length), range, folderName].filter(Boolean).join(' · ')}
            </p>
          </div>

          <div className="mt-4 flex shrink-0 flex-wrap items-start gap-4">
            {plan.totals.length === 0 ? (
              <PaperCard shadow="sm" className="px-5 py-3">
                <p className="m-0 text-[17px]">Nothing counted yet: no invoice or receipt has an amount, a date and a currency.</p>
              </PaperCard>
            ) : (
              plan.totals.map((t, i) => (
                <PaperCard key={t.currency} variant={i % 2 === 0 ? 'a' : 'b'} shadow="sm" className="min-w-[220px] px-5 py-3">
                  <p className="m-0 text-[17px] text-graphite">
                    {currencyName(t.currency)} · {files(t.row_count)}
                  </p>
                  <p className="m-0 mt-1 font-mono text-[26px] font-bold leading-tight">
                    <span style={GREEN_MARKER} className="px-1">
                      {money(t.amount, t.currency)}
                    </span>
                  </p>
                </PaperCard>
              ))
            )}
            {plan.totals.length >= 2 && (
              <StickyNote tilt={1.2} className="max-w-[260px] px-4 py-3">
                <p className="m-0 text-[17px] leading-6">
                  <strong>Kept separate.</strong> Pip doesn't convert currencies, so nothing gets guessed.
                </p>
              </StickyNote>
            )}
          </div>

          <PaperCard as="section" aria-labelledby="list-title" className="mt-5 flex min-h-0 flex-1 flex-col overflow-hidden px-5 pb-2 pt-3">
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <CardTitle size="sm" className="mr-2">
                <span id="list-title">the list</span>
              </CardTitle>
              <div role="group" aria-label="Show month" className="flex flex-wrap gap-1.5">
                <FilterChip pressed={month === null} onClick={() => setMonth(null)}>
                  all <span className="font-mono text-[13px]">{rows.length}</span>
                </FilterChip>
                {months.map((m) => (
                  <FilterChip key={m.key} pressed={month === m.key} onClick={() => setMonth(m.key)}>
                    {m.label} <span className="font-mono text-[13px]">{m.count}</span>
                  </FilterChip>
                ))}
              </div>
              <span className="ml-auto text-[16px] text-graphite">sorted by date</span>
            </div>
            <div role="table" aria-label="Counted files" className="mt-2 flex min-h-0 flex-1 flex-col">
              <div role="rowgroup" className="shrink-0 border-b-[2.5px] border-ink pb-1 text-[16px] text-graphite">
                <div role="row" className={LIST_COLS}>
                  <span role="columnheader">date</span>
                  <span role="columnheader">shop</span>
                  <span role="columnheader">kind</span>
                  <span role="columnheader" className="text-right">
                    amount
                  </span>
                  <span role="columnheader">goes to</span>
                </div>
              </div>
              <div role="rowgroup" className="min-h-0 flex-1 overflow-y-auto" tabIndex={0} aria-label="Counted files, scrollable">
                {visible.length === 0 && <p className="m-0 py-3 text-[17px] text-graphite">No counted files{month ? ' in this month' : ''}.</p>}
                {visible.map((r) => (
                  <div key={r.file_id} role="row" className={cx(LIST_COLS, 'border-b-[1.5px] border-dashed border-pencil py-1.5')}>
                    <span role="cell" className="font-mono text-[15px]">
                      {r.date ?? '—'}
                    </span>
                    <span role="cell" className="flex min-w-0 items-center gap-2 text-[17px]">
                      <span className="truncate" title={r.source_filename}>
                        {r.merchant ?? 'unknown shop'}
                      </span>
                      {corrected.has(r.file_id) && (
                        <Chip tone="done" size="sm">
                          ✓ you checked
                        </Chip>
                      )}
                    </span>
                    <span role="cell" className="text-[17px]">
                      {r.category}
                    </span>
                    <span role="cell" className="text-right font-mono text-[15px]">
                      {money(r.amount, r.currency)}
                    </span>
                    <span role="cell" className="truncate font-mono text-[14px]">
                      {destination.get(r.file_id) ?? 'stays put'}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </PaperCard>
        </section>

        {/* Right column: where files go */}
        <aside className="flex min-h-0 flex-col gap-3 overflow-y-auto pb-2 pr-2" aria-label="Ready to move">
          <PaperCard variant="b" className="px-5 pb-3 pt-3">
            <CardTitle size="sm">ready to move</CardTitle>
            <div className="mt-1">
              {groups.map((g) => (
                <FolderRow key={g.folder} path={g.folder} note={folderNote(g.folder)} count={g.count} />
              ))}
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-x-3 border-t-[2px] border-dashed border-ink pt-2">
              <span className="text-[17px]">
                {moves} move · {stay} stay where they are
              </span>
              <PaperButton variant="link" className="!h-9 !text-[17px]" onClick={() => setMovesOpen(true)} disabled={moves === 0}>
                see every move
              </PaperButton>
            </div>
          </PaperCard>

          <div>
            <PaperButton variant="secondary" size="sm" className="w-full" onClick={exportCsv} disabled={rows.length === 0}>
              Save list as CSV
            </PaperButton>
            <p className="m-0 mt-1.5 text-center text-[16px] text-graphite">saved on this computer · works in Excel or Sheets</p>
          </div>

          <StickyNote tilt={-1} className="mt-auto px-4 py-3">
            <p className="m-0 text-[17px] leading-6">
              Moving is the only step that changes your folder. You can put everything back from <strong>History</strong>.
            </p>
          </StickyNote>
        </aside>
      </div>

      {state.actionError && !moved && (
        <div className="mx-auto w-full max-w-[1366px] shrink-0 px-8 pb-2">
          <StickyNote tone="pink" alert tilt={0} className="px-4 py-2">
            <p className="m-0 text-[17px]">The move didn't go through: {state.actionError}</p>
          </StickyNote>
        </div>
      )}

      <PageFooter
        className="!h-[72px]"
        left={
          <>
            {!moved && (
              <PaperButton variant="link" onClick={() => navigate('files')}>
                ← back to check
              </PaperButton>
            )}
            <span className="ml-3 text-[17px] text-graphite">{moved ? (state.phase === 'undone' ? 'files were put back' : 'files already moved') : 'nothing has moved yet'}</span>
          </>
        }
        right={
          moved ? (
            <PaperButton variant="primary" onClick={() => navigate('completion')}>
              Done →
            </PaperButton>
          ) : (
            <PaperButton
              variant="primary"
              disabled={blocking > 0 || moves === 0}
              disabledReason={blocking > 0 ? `check ${blocking} more ${blocking === 1 ? 'file' : 'files'} first` : 'nothing to move'}
              reasonId="move-reason"
              onClick={() => setConfirmOpen(true)}
            >
              Move {files(moves)} →
            </PaperButton>
          )
        }
      />

      <ConfirmMove
        open={confirmOpen}
        plan={plan}
        folderName={folderName}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false)
          void approve()
        }}
      />
      <MovesSheet open={movesOpen} plan={plan} onClose={() => setMovesOpen(false)} />
    </>
  )
}

function FilterChip({ pressed, onClick, children }: { pressed: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cx('rounded-full border-[2.5px] border-ink px-3 text-[16px] leading-7', pressed ? 'bg-ink text-paper' : 'bg-paper')}
    >
      {children}
    </button>
  )
}

/** 3b · Confirm the move. "Not yet" has initial focus; Esc cancels. */
function ConfirmMove({ open, plan, folderName, onCancel, onConfirm }: { open: boolean; plan: PlanPreview; folderName: string; onCancel: () => void; onConfirm: () => void }) {
  const notYet = useRef<HTMLButtonElement>(null)
  const n = plan.operations.length
  const suffixed = plan.operations.some((op) => op.collision_suffixed)
  return (
    <PaperDialog open={open} onCancel={onCancel} labelledBy="confirm-move-title" describedBy="confirm-move-desc" initialFocus={notYet}>
      <div className="px-8 pb-6 pt-6">
        <h2 id="confirm-move-title" className="m-0 font-display text-[36px] font-normal leading-tight">
          Move {files(n)}?
        </h2>
        <p id="confirm-move-desc" className="m-0 mt-2 text-[18px] leading-7">
          They'll go into new folders inside <span className="rounded-[6px] bg-path-box px-1.5 font-mono text-[15px]">{folderName}/</span>. Nothing is deleted or renamed
          {suffixed ? <>, except <span className="font-mono text-[15px]">(2)</span> added if a name is already taken</> : null}.
        </p>
        <div className="mt-4 max-h-[320px] overflow-y-auto rounded-[12px] border-[2px] border-dashed border-ink px-4 py-1">
          {groupByDestination(plan.operations).map((g) => (
            <FolderRow key={g.folder} path={g.folder} note={folderNote(g.folder)} count={g.count} />
          ))}
        </div>
        <p className="m-0 mt-4 flex items-start gap-2 text-[17px] leading-6">
          <UndoIcon size={22} className="mt-0.5 shrink-0" />
          <span>
            Changed your mind later? <strong>History → Put files back</strong> returns all {n} to where they were.
          </span>
        </p>
        <div className="mt-6 flex items-center justify-end gap-4">
          <PaperButton ref={notYet} variant="secondary" size="sm" onClick={onCancel}>
            Not yet
          </PaperButton>
          <PaperButton variant="primary" size="sm" onClick={onConfirm}>
            Move {files(n)}
          </PaperButton>
        </div>
      </div>
    </PaperDialog>
  )
}

/** "see every move": every original → destination, with "(2) added" on renamed ones. */
function MovesSheet({ open, plan, onClose }: { open: boolean; plan: PlanPreview; onClose: () => void }) {
  const close = useRef<HTMLButtonElement>(null)
  return (
    <PaperDialog open={open} onCancel={onClose} labelledBy="moves-title" initialFocus={close} variant="b" width={760}>
      <div className="flex min-h-0 flex-col px-7 pb-5 pt-5">
        <div className="flex items-center justify-between gap-4">
          <h2 id="moves-title" className="m-0 font-display text-[30px] font-normal">
            Every move · {plan.operations.length}
          </h2>
          <PaperButton ref={close} variant="secondary" size="sm" onClick={onClose}>
            Close
          </PaperButton>
        </div>
        <p className="m-0 text-[17px] text-graphite">Nothing has moved yet. This is the plan.</p>
        <ul className="m-0 mt-3 max-h-[60vh] list-none overflow-y-auto p-0 pr-2">
          {plan.operations.map((op) => (
            <li key={op.file_id} className="flex flex-wrap items-center gap-x-2 gap-y-1 border-b-[1.5px] border-dashed border-pencil py-2 font-mono text-[14px]" title={op.reason}>
              <span className="break-all">{op.original_relative_path}</span>
              <span aria-label="goes to">→</span>
              <span className="break-all">{op.destination_relative_path}</span>
              {op.collision_suffixed && (
                <Chip tone="info" size="sm" className="font-sans">
                  (2) added
                </Chip>
              )}
            </li>
          ))}
        </ul>
      </div>
    </PaperDialog>
  )
}
