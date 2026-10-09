import { ArrowRight, CheckCircle2, Cpu, Eye, FileSearch, FileSpreadsheet, FolderOpen, FolderTree, History, ListChecks, ShieldAlert, ShieldCheck, TriangleAlert, Undo2 } from 'lucide-react'
import { ActivityTimeline } from '../components/activity/ActivityTimeline'
import { ServiceRow } from '../components/shell/LocalStatusIndicator'
import { useServiceStates } from '../components/shell/useServiceStates'
import { FixtureTag } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { EmptyState, PageHeader, Panel, StatCard } from '../components/ui/Layout'
import { useApp } from '../state/AppState'

const PROMISES = [
  { icon: ShieldCheck, text: 'Documents are read on this device. No cloud model, no upload.' },
  { icon: Eye, text: 'Scanning only proposes changes. Nothing moves until you approve.' },
  { icon: ListChecks, text: 'Uncertain amounts and dates stay flagged until you review them.' },
  { icon: Undo2, text: 'Every approved batch is logged and can be undone when it is safe.' },
]

export function DashboardPage() {
  const { state, navigate, chooseSampleFolder, counts, usingFixtures } = useApp()
  const svc = useServiceStates()
  const hasSession = state.scan !== null
  const moves = state.plan?.operations.length ?? 0

  const next = (() => {
    if (state.phase === 'folder_selected') return { label: 'Start scan', text: `${state.folder?.name} is selected but not scanned yet.`, view: 'folder' as const }
    if (state.phase === 'scanning') return { label: 'View progress', text: 'A scan is in progress.', view: 'scanning' as const }
    if (state.phase === 'scan_failed') return { label: 'View scan', text: 'The last scan stopped before finishing.', view: 'scanning' as const }
    if (state.phase === 'reviewing' && counts.blocking > 0)
      return { label: 'Review files', text: `${counts.blocking} documents need your review before the plan can be approved.`, view: 'files' as const }
    if (state.phase === 'reviewing') return { label: 'Review plan', text: 'Nothing is blocking approval. Review the organization plan.', view: 'plan' as const }
    if (state.approvedPlan) return { label: 'View results', text: 'The last batch finished. You can review or undo it.', view: 'completion' as const }
    return null
  })()

  const startSample = () => {
    chooseSampleFolder()
  }

  return (
    <div className="scroll-area flex-1">
      <PageHeader
        title="Dashboard"
        meta={usingFixtures && <FixtureTag />}
        description="GhostOS organizes invoices, receipts and business documents in a folder you choose, using a local AI model."
        actions={
          <>
            {usingFixtures && (
              <Button icon={FileSearch} onClick={startSample}>
                Use sample folder
              </Button>
            )}
            <Button variant="primary" icon={FolderOpen} onClick={() => navigate('folder')}>
              Select Folder
            </Button>
          </>
        }
      />

      <div className="space-y-4 p-6">
        {next && (
          <div className="flex items-center gap-3 rounded-lg border border-accent/30 bg-accent/8 px-4 py-3">
            <ArrowRight size={16} className="text-accent-hover" aria-hidden />
            <div className="flex-1 text-sm">
              <span className="font-medium">Continue where you left off.</span> <span className="text-fg-muted">{next.text}</span>
            </div>
            <Button size="sm" variant="primary" onClick={() => navigate(next.view)}>
              {next.label}
            </Button>
          </div>
        )}

        <div className="grid grid-cols-4 gap-4">
          <StatCard icon={FileSearch} label="Files scanned" value={hasSession ? counts.documents : '—'} hint={hasSession ? `${counts.skipped} skipped · ${counts.failed} failed` : 'No scan yet'} />
          <StatCard icon={TriangleAlert} tone={counts.blocking ? 'warning' : 'neutral'} label="Needs review" value={hasSession ? counts.blocking : '—'} hint={hasSession ? 'Blocking approval' : 'Nothing to review'} />
          <StatCard icon={FolderTree} tone="accent" label="Proposed moves" value={hasSession ? moves : '—'} hint={state.batch ? 'Batch already approved' : 'Awaiting your approval'} />
          <StatCard icon={FileSpreadsheet} tone={state.batch ? 'success' : 'neutral'} label="Reports written" value={state.batch ? 1 : 0} hint={state.batch ? state.batch.report_relative_path : 'Written after approval'} />
        </div>

        <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-4">
          <div className="space-y-4">
            {!hasSession && (
              <Panel>
                <div className="grid grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-8 p-2">
                  <div>
                    <h2 className="text-lg font-semibold">Start with a folder</h2>
                    <p className="mt-1 text-sm text-fg-muted">
                      Point GhostOS at a messy folder of PDFs, text files and CSVs. It classifies each document, pulls out merchant, date and amount with
                      supporting evidence, and drafts a tidy folder structure and expense CSV for you to check.
                    </p>
                    <div className="mt-4 flex gap-2">
                      <Button variant="primary" icon={FolderOpen} onClick={() => navigate('folder')}>
                        Select Folder
                      </Button>
                      {usingFixtures && (
                        <Button icon={FileSearch} onClick={startSample}>
                          Try with fixtures
                        </Button>
                      )}
                    </div>
                    {usingFixtures && <p className="mt-2 text-xs text-fg-subtle">Fixture mode: data comes from bundled JSON, not from files on this computer.</p>}
                  </div>
                  <ul className="space-y-3">
                    {PROMISES.map((p) => (
                      <li key={p.text} className="flex gap-3 text-sm">
                        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-line bg-surface-2 text-success">
                          <p.icon size={15} aria-hidden />
                        </span>
                        <span className="pt-1 text-fg-muted">{p.text}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </Panel>
            )}

            <Panel
              title="Recent activity"
              icon={History}
              actions={
                state.activity.length > 0 && (
                  <Button size="sm" variant="ghost" iconRight={ArrowRight} onClick={() => navigate('activity')}>
                    View all
                  </Button>
                )
              }
              bodyClassName="p-0"
            >
              {state.activity.length === 0 ? (
                <EmptyState icon={History} title="No activity yet">
                  Folder selections, scans, corrections, approvals and undo operations will be recorded here.
                </EmptyState>
              ) : (
                <div className="px-4 py-3">
                  <ActivityTimeline events={state.activity.slice(0, 6)} compact />
                </div>
              )}
            </Panel>
          </div>

          <Panel title="System status" icon={Cpu} className="self-start">
            {svc.external > 0 ? (
              <div className="mb-3 flex items-center gap-2 rounded-md border border-danger/35 bg-danger/8 px-2.5 py-2 text-xs text-danger">
                <ShieldAlert size={14} aria-hidden />
                {svc.external} requests left this device
              </div>
            ) : (
              <div className="mb-3 flex items-center gap-2 rounded-md border border-success/30 bg-success/8 px-2.5 py-2 text-xs text-success">
                <CheckCircle2 size={14} aria-hidden />
                Local-only. No cloud fallback.
              </div>
            )}
            <div className="space-y-2">
              <ServiceRow name="FastAPI · 127.0.0.1:8000" {...svc.backend} />
              <ServiceRow name="Ollama · 127.0.0.1:11434" {...svc.model} />
            </div>
            <div className="mt-3 border-t border-line pt-3 text-2xs text-fg-subtle">
              {usingFixtures
                ? 'Fixture mode: statuses come from src/fixtures/status.json, not a live check. Set VITE_USE_FIXTURES=false to use the backend.'
                : 'Polled from GET /api/status every 10 seconds.'}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  )
}
