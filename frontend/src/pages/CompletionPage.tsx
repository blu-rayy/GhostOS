import { useState } from 'react'
import { AlertTriangle, ArrowRight, Check, CheckCircle2, FileSpreadsheet, FolderTree, Info, Loader2, RotateCcw, ShieldCheck, Undo2, XCircle } from 'lucide-react'
import { FixtureTag } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { cx } from '../components/ui/cx'
import { Dialog } from '../components/ui/Dialog'
import { Banner, EmptyState, PageHeader, Panel, PathText, StatCard } from '../components/ui/Layout'
import { formatDateTime } from '../lib/format'
import { useApp } from '../state/AppState'

type OpState = 'pending' | 'moved' | 'failed' | 'restored' | 'conflict'

const OP: Record<OpState, { icon: typeof Check; cls: string; label: string }> = {
  pending: { icon: Loader2, cls: 'text-fg-subtle animate-spin', label: 'Pending' },
  moved: { icon: Check, cls: 'text-success', label: 'Moved' },
  failed: { icon: XCircle, cls: 'text-danger', label: 'Not moved' },
  restored: { icon: RotateCcw, cls: 'text-info', label: 'Restored' },
  conflict: { icon: AlertTriangle, cls: 'text-warning', label: 'Not restored' },
}

export function CompletionPage() {
  const { state, navigate, undoBatch, usingFixtures } = useApp()
  const [confirmUndo, setConfirmUndo] = useState(false)
  const { batch, undo, approvedPlan } = state

  if (!approvedPlan) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="Batch results" description="Results of an approved organization plan appear here." />
        <EmptyState
          icon={FolderTree}
          title="No approved batch"
          className="flex-1"
          actions={
            state.scan && (
              <Button variant="primary" onClick={() => navigate('plan')}>
                Review organization plan
              </Button>
            )
          }
        >
          Nothing has been organized in this session. Files only move after you approve a plan.
        </EmptyState>
      </div>
    )
  }

  const ops = approvedPlan.operations
  const running = state.busy === 'approve'
  const undoing = state.busy === 'undo'
  const conflicts = new Map((undo?.conflicts ?? []).map((c) => [c.file_id, c]))
  const failed = new Map((batch?.failed ?? []).map((f) => [f.file_id, f]))
  const opState = (fileId: string): OpState => {
    if (!batch) return 'pending'
    if (failed.has(fileId)) return 'failed'
    if (undo) return conflicts.has(fileId) ? 'conflict' : 'restored'
    return 'moved'
  }
  const reviewFolder = ops.filter((o) => o.destination_relative_path.startsWith('Needs Review/')).length

  const title = running
    ? 'Organizing…'
    : undoing
      ? 'Undoing batch…'
      : undo
        ? undo.conflicts.length
          ? 'Batch partially undone'
          : 'Batch undone'
        : batch
          ? 'Organization complete'
          : 'Batch results'

  return (
    <div className="scroll-area flex-1">
      <PageHeader
        title={title}
        meta={usingFixtures && <FixtureTag />}
        breadcrumbs={[state.folder?.name ?? 'Folder', 'Organize', 'Batch results']}
        description={batch ? `Batch ${batch.batch_id} · committed ${formatDateTime(batch.committed_at)}` : 'Waiting for the backend to confirm the batch.'}
        actions={
          batch &&
          !undo && (
            <Button variant="danger" icon={Undo2} disabled={undoing} onClick={() => setConfirmUndo(true)}>
              Undo Batch
            </Button>
          )
        }
      />
      <div className="space-y-4 p-6">
        {(running || undoing) && (
          <Banner tone="info" icon={Loader2} title={running ? 'Moving files…' : 'Restoring original locations…'}>
            {usingFixtures ? 'Fixture mode: the mock backend simulates this step.' : 'The local backend is applying the batch.'}
          </Banner>
        )}
        {state.actionError && (
          <Banner tone="danger" icon={XCircle} title="Request failed">
            {state.actionError}
          </Banner>
        )}
        {batch && !undo && (
          <Banner tone={batch.failed.length ? 'warning' : 'success'} icon={batch.failed.length ? AlertTriangle : CheckCircle2} title={`${batch.moved} files organized`}>
            {batch.failed.length ? `${batch.failed.length} could not be moved and stayed where they were. ` : ''}
            All moves stayed inside {state.folder?.name}. Nothing was deleted or overwritten.
          </Banner>
        )}
        {undo && undo.conflicts.length === 0 && (
          <Banner tone="success" icon={RotateCcw} title={`All ${undo.restored} files restored`}>
            Every file is back at its original path.
          </Banner>
        )}
        {undo && undo.conflicts.length > 0 && (
          <Banner tone="warning" icon={AlertTriangle} title={`${undo.restored} restored · ${undo.conflicts.length} could not be restored`}>
            GhostOS skipped files whose original location is no longer safe to write to. Those files remain in their organized location. Move or rename the
            conflicting file, then restore it manually.
          </Banner>
        )}

        <div className="grid grid-cols-4 gap-4">
          <StatCard icon={FolderTree} tone="success" label={undo ? 'Restored' : 'Files organized'} value={undo ? undo.restored : (batch?.moved ?? '—')} hint={`of ${ops.length} in batch`} />
          <StatCard icon={AlertTriangle} tone={reviewFolder ? 'warning' : 'neutral'} label="Filed in Needs Review/" value={reviewFolder} hint="Failed or incomplete records" />
          <StatCard icon={ShieldCheck} label="Not moved" value={batch ? batch.failed.length : '—'} hint="Errors during the batch" />
          <StatCard
            icon={FileSpreadsheet}
            tone={batch ? 'success' : 'neutral'}
            label="Expense report"
            value={batch ? 'Written' : '—'}
            hint={batch ? `${batch.report_relative_path}${usingFixtures ? ' (simulated)' : ''}` : 'Written when the batch commits'}
          />
        </div>

        <Panel
          title="Operations"
          icon={FolderTree}
          bodyClassName="p-0"
          actions={
            <Button size="sm" variant="ghost" iconRight={ArrowRight} onClick={() => navigate('report')}>
              Open expense report
            </Button>
          }
        >
          <ul className="divide-y divide-line">
            {ops.map((op) => {
              const st = opState(op.file_id)
              const s = OP[st]
              const note = conflicts.get(op.file_id)?.reason ?? failed.get(op.file_id)?.error
              return (
                <li key={op.file_id} className={cx('px-4 py-2', (st === 'conflict' || st === 'failed') && 'bg-warning/5')}>
                  <div className="flex items-center gap-3 text-xs">
                    <s.icon size={14} className={cx('shrink-0', s.cls)} aria-hidden />
                    <PathText className="w-[38%] truncate text-fg-muted">{op.original_relative_path}</PathText>
                    <ArrowRight size={12} className="shrink-0 text-fg-subtle" aria-hidden />
                    <PathText className="min-w-0 flex-1 truncate">{op.destination_relative_path}</PathText>
                    <span className="w-20 shrink-0 text-right text-2xs text-fg-subtle">{s.label}</span>
                  </div>
                  {note && <p className="ml-[26px] mt-1 text-2xs text-warning">{note}</p>}
                </li>
              )
            })}
          </ul>
        </Panel>

        <div className="flex items-center gap-2 text-xs text-fg-subtle">
          <Info size={13} aria-hidden />
          Undo checks each file's identity and confirms its original path is free before restoring. Conflicting files are never overwritten.
        </div>
      </div>

      <Dialog
        open={confirmUndo}
        onClose={() => setConfirmUndo(false)}
        title="Undo this batch?"
        icon={Undo2}
        tone="warning"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmUndo(false)}>
              Keep organized
            </Button>
            <Button
              variant="danger"
              icon={Undo2}
              onClick={() => {
                setConfirmUndo(false)
                undoBatch()
              }}
            >
              Restore {ops.length} files
            </Button>
          </>
        }
      >
        <div className="space-y-3">
          <p>
            GhostOS will move the {ops.length} files in this batch back to their original paths. Before each restore it checks that the file is unchanged and that
            the original path is still free.
          </p>
          <ul className="space-y-1.5 text-xs text-fg-muted">
            <li className="flex gap-2">
              <ShieldCheck size={14} className="shrink-0 text-success" />
              A file whose original path is now taken is left where it is and reported as a conflict.
            </li>
            <li className="flex gap-2">
              <ShieldCheck size={14} className="shrink-0 text-success" />
              Nothing is overwritten or deleted. The written expense report stays in place.
            </li>
          </ul>
          {usingFixtures && <p className="text-xs text-fg-muted">Fixture mode: restores are simulated. Settings → Demo scenarios can force a conflict.</p>}
        </div>
      </Dialog>
    </div>
  )
}
