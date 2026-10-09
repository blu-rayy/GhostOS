import { useState } from 'react'
import { useApp } from '../../state/AppState'
import type { ActivityEvent } from '../../types/ui'
import { files } from '../../lib/totals'
import { PutBackConfirm } from '../../pages/done/DonePage'
import { PaperButton } from '../paper/Button'
import { Chip } from '../paper/Chip'
import { CardTitle, PaperCard } from '../paper/PaperCard'
import { StickyNote } from '../paper/StickyNote'
import { cx } from '../ui/cx'

type Filter = 'all' | 'moves' | 'problems'

const MOVE_TYPES: ActivityEvent['type'][] = ['plan_approved', 'file_moved', 'report_generated', 'report_exported', 'undo_started', 'undo_completed', 'undo_conflict']

/** "22:54" */
const timeOf = (iso: string) => new Date(iso).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })

/**
 * History panel: the session log (there is no activity endpoint, so it resets when the app
 * closes) and the "Put files back" action that Totals and the move dialog point to.
 */
export function HistoryPanel() {
  const { state, navigate, undoBatch } = useApp()
  const [filter, setFilter] = useState<Filter>('all')
  const [confirmOpen, setConfirmOpen] = useState(false)
  const events = state.activity
  const visible = events.filter((e) => filter === 'all' || (filter === 'moves' ? MOVE_TYPES.includes(e.type) : e.level === 'error' || e.level === 'warning'))
  const batch = state.batch
  const canPutBack = batch !== null && batch.moved > 0 && state.phase === 'organized' && state.busy === null
  const savedCsv = events.some((e) => e.type === 'report_exported')

  return (
    <div className="space-y-4">
      <StickyNote tilt={-0.8} className="px-4 py-3">
        <p className="m-0 text-[17px] leading-6">This session only. History starts fresh each time GhostOS opens.</p>
      </StickyNote>

      {batch && (
        <PaperCard variant="b" shadow="sm" className="px-4 py-3">
          <CardTitle size="sm">last move</CardTitle>
          <p className="m-0 mt-1 text-[17px]">
            {files(batch.moved)} moved at {timeOf(batch.committed_at)}
            {batch.failed.length > 0 && ` · ${batch.failed.length} didn't move`}
          </p>
          {state.phase === 'undone' && state.undo ? (
            <p className="m-0 mt-1 text-[17px] text-graphite">
              Put back: {state.undo.restored} of {batch.moved}
              {state.undo.conflicts.length > 0 && ` · ${state.undo.conflicts.length} stayed`}
            </p>
          ) : (
            <PaperButton variant="careful" size="sm" className="mt-3 !bg-sticky-pink" disabled={!canPutBack} onClick={() => setConfirmOpen(true)}>
              {state.busy === 'undo' ? 'Putting back…' : 'Put files back…'}
            </PaperButton>
          )}
        </PaperCard>
      )}

      <div role="group" aria-label="Show" className="flex flex-wrap gap-1.5">
        {(
          [
            ['all', 'all'],
            ['moves', 'moves & put back'],
            ['problems', 'problems'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            type="button"
            aria-pressed={filter === id}
            onClick={() => setFilter(id)}
            className={cx('rounded-full border-[2.5px] border-ink px-3 text-[16px] leading-7', filter === id ? 'bg-ink text-paper' : 'bg-paper')}
          >
            {label}
          </button>
        ))}
      </div>

      {events.length === 0 ? (
        <p className="m-0 text-[17px] text-graphite">Nothing yet. Picking a folder, reading it, checking files, moving and putting back all show up here.</p>
      ) : visible.length === 0 ? (
        <p className="m-0 text-[17px] text-graphite">Nothing here yet.</p>
      ) : (
        <ol className="m-0 list-none p-0" aria-label="History, newest first">
          {visible.map((e) => (
            <li key={e.id} className="flex gap-3 border-b-[1.5px] border-dashed border-pencil py-2.5 last:border-b-0">
              <span className="w-[46px] shrink-0 pt-0.5 font-mono text-[13px] text-graphite">{timeOf(e.at)}</span>
              <span className="min-w-0 flex-1">
                <span className="flex items-start gap-2">
                  <span className="min-w-0 flex-1 break-words text-[17px] leading-6">{e.title}</span>
                  {e.level === 'error' && (
                    <Chip tone="oops" size="sm">
                      didn't work
                    </Chip>
                  )}
                  {e.level === 'warning' && (
                    <Chip tone="check" size="sm">
                      look
                    </Chip>
                  )}
                </span>
                {e.detail && <span className="block break-words text-[16px] leading-5 text-graphite">{e.detail}</span>}
              </span>
            </li>
          ))}
        </ol>
      )}

      <PutBackConfirm
        open={confirmOpen}
        n={batch?.moved ?? 0}
        savedCsv={savedCsv}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false)
          // Done shows the result (4c put back / 4d some stayed); navigate also closes this panel.
          navigate('completion')
          void undoBatch()
        }}
      />
    </div>
  )
}
