import { useMemo, useState } from 'react'
import { AlertTriangle, ArrowRight, CheckCircle2, FolderOpen, FolderTree, Loader2, PauseCircle, RotateCcw, ShieldCheck, XCircle } from 'lucide-react'
import { ApprovalDialogBody, BackToReviewButton } from '../components/plan/ApprovalDialog'
import { useApprovalState } from '../components/plan/useApprovalState'
import { OrganizationPlanTable } from '../components/plan/OrganizationPlanTable'
import { FixtureTag } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { Banner, EmptyState, PageHeader } from '../components/ui/Layout'
import { Segmented } from '../components/ui/Toolbar'
import { isInsideRoot } from '../lib/viewModel'
import { useApp } from '../state/AppState'

type Filter = 'all' | 'move' | 'review_folder' | 'leave' | 'warnings'

export function PlanPage() {
  const { state, planRows, navigate, selectDoc, approve, reloadPlan, usingFixtures } = useApp()
  const [filter, setFilter] = useState<Filter>('all')
  const approval = useApprovalState()
  const plan = state.plan

  const moves = planRows.filter((p) => p.action === 'move')
  const toReview = planRows.filter((p) => p.action === 'review_folder')
  const left = planRows.filter((p) => p.action === 'leave')
  const withWarnings = planRows.filter((p) => p.warnings.length > 0)
  const collisions = plan?.operations.filter((o) => o.collision_suffixed).length ?? 0
  const blocking = plan?.blocking_review_count ?? 0
  const allInside = plan?.operations.every((o) => isInsideRoot(o.destination_relative_path)) ?? true
  const approved = state.batch !== null
  const canApprove = !!plan && !approved && blocking === 0 && allInside && plan.operations.length > 0 && !state.planLoading

  const visible = useMemo(() => {
    if (filter === 'all') return planRows
    if (filter === 'warnings') return withWarnings
    return planRows.filter((p) => p.action === filter)
  }, [planRows, filter, withWarnings])

  if (!state.scan) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="Organization plan" description="Proposed moves appear here after a scan." />
        <EmptyState
          icon={FolderTree}
          title="No plan yet"
          className="flex-1"
          actions={
            <Button variant="primary" icon={FolderOpen} onClick={() => navigate('folder')}>
              Select Folder
            </Button>
          }
        >
          GhostOS drafts a plan from scanned documents. Nothing is moved until you approve it.
        </EmptyState>
      </div>
    )
  }

  const openDoc = (id: string) => {
    selectDoc(id)
    navigate('files')
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader
        title="Organization plan"
        meta={usingFixtures && <FixtureTag />}
        breadcrumbs={[state.folder?.name ?? 'Folder', 'Organize']}
        description="Every proposed move, with the reason the backend gave. Review the plan, then approve it explicitly."
        actions={
          approved ? (
            <Button variant="primary" iconRight={ArrowRight} onClick={() => navigate('completion')}>
              View batch results
            </Button>
          ) : (
            <Button variant="primary" iconRight={ArrowRight} disabled={!canApprove} onClick={approval.show}>
              Continue to approval
            </Button>
          )
        }
      />

      <div className="flex shrink-0 flex-col gap-3 px-6 pt-4">
        {state.planError && (
          <Banner tone="danger" icon={XCircle} title="Could not load the plan" actions={<Button size="sm" icon={RotateCcw} onClick={reloadPlan}>Retry</Button>}>
            {state.planError}
          </Banner>
        )}
        {state.actionError && !approved && (
          <Banner tone="danger" icon={XCircle} title="Approval failed. Nothing was moved.">
            {state.actionError}
          </Banner>
        )}
        {approved ? (
          <Banner tone="success" icon={CheckCircle2} title="This plan was approved">
            Batch {state.batch?.batch_id}. Results and undo are on the batch results screen.
          </Banner>
        ) : blocking > 0 ? (
          <Banner
            tone="warning"
            icon={PauseCircle}
            title={`${blocking} ${blocking === 1 ? 'document needs' : 'documents need'} review before you can approve`}
            actions={
              <Button size="sm" onClick={() => navigate('files')}>
                Review files
              </Button>
            }
          >
            Approval stays disabled until every flagged document is reviewed. Failed extractions don't block; they go to Needs Review/.
          </Banner>
        ) : null}

        <div className="grid grid-cols-4 gap-3">
          {[
            { label: 'Will move', n: moves.length, cls: 'text-accent-hover' },
            { label: 'To Needs Review/', n: toReview.length, cls: 'text-warning' },
            { label: 'Stay in place', n: left.length, cls: 'text-fg-muted' },
            { label: 'Blocking approval', n: blocking, cls: blocking ? 'text-warning' : 'text-fg-muted' },
          ].map((s) => (
            <div key={s.label} className="flex items-baseline justify-between rounded-lg border border-line bg-surface-1 px-4 py-2.5">
              <span className="text-xs text-fg-muted">{s.label}</span>
              <span className={`tabular text-xl font-semibold ${s.cls}`}>{s.n}</span>
            </div>
          ))}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3">
          <Segmented<Filter>
            label="Plan filter"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'all', label: 'All', count: planRows.length },
              { value: 'move', label: 'Moves', count: moves.length },
              { value: 'review_folder', label: 'Needs Review/', count: toReview.length },
              { value: 'leave', label: 'In place', count: left.length },
              { value: 'warnings', label: 'Warnings', count: withWarnings.length },
            ]}
          />
          <ul className="flex flex-wrap items-center gap-x-4 gap-y-1 text-2xs text-fg-muted">
            {[
              [allInside, 'Destinations inside selected folder'],
              [true, 'Paths built by rules, not the model'],
              [true, 'No deletions'],
              [true, 'No overwrites'],
            ].map(([ok, t]) => (
              <li key={t as string} className="flex items-center gap-1">
                {ok ? <ShieldCheck size={12} className="text-success" aria-hidden /> : <AlertTriangle size={12} className="text-danger" aria-hidden />}
                {t as string}
              </li>
            ))}
          </ul>
        </div>
      </div>

      <div className="scroll-area mx-6 my-3 min-h-0 flex-1 rounded-lg border border-line bg-surface-1">
        {state.planLoading && !plan ? (
          <EmptyState icon={Loader2} title="Building the plan…" />
        ) : visible.length === 0 ? (
          <EmptyState icon={FolderTree} title="Nothing in this view" />
        ) : (
          <OrganizationPlanTable rows={visible} onOpenDoc={openDoc} />
        )}
      </div>

      {!approved && (
        <div className="flex shrink-0 items-center justify-between gap-4 border-t border-line bg-surface-1 px-6 py-3">
          <div className="flex items-center gap-2 text-xs text-fg-muted">
            <span className="rounded-full bg-accent/15 px-2 py-0.5 text-2xs font-semibold text-accent-hover">Step 1 of 2</span>
            Review the plan. Nothing has been moved.
            {collisions > 0 && (
              <span className="flex items-center gap-1 text-warning">
                <AlertTriangle size={12} aria-hidden /> {collisions} name {collisions === 1 ? 'collision' : 'collisions'} resolved
              </span>
            )}
          </div>
          <Button variant="primary" iconRight={ArrowRight} disabled={!canApprove} onClick={approval.show}>
            Continue to approval
          </Button>
        </div>
      )}

      {plan && (
        <Dialog
          open={approval.open}
          onClose={approval.hide}
          title="Step 2 of 2 · Approve organization plan"
          icon={ShieldCheck}
          footer={
            <>
              <BackToReviewButton onClick={approval.hide} />
              <Button
                variant="primary"
                icon={ShieldCheck}
                disabled={!approval.ack || state.busy === 'approve'}
                onClick={() => {
                  approval.hide()
                  approve()
                }}
              >
                Approve and Organize {plan.operations.length} files
              </Button>
            </>
          }
        >
          <ApprovalDialogBody
            operations={plan.operations}
            reviewFolderCount={toReview.length}
            leftCount={left.length}
            collisions={collisions}
            rootName={state.folder?.name ?? 'the selected folder'}
            usingFixtures={usingFixtures}
            acknowledged={approval.ack}
            onAcknowledge={approval.setAck}
          />
        </Dialog>
      )}
    </div>
  )
}
