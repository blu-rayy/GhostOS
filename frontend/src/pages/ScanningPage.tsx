import { ArrowRight, Check, CheckCircle2, FileText, FolderOpen, Loader2, RotateCcw, ScanSearch, XCircle } from 'lucide-react'
import { FixtureTag } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { cx } from '../components/ui/cx'
import { Banner, EmptyState, PageHeader, Panel, ProgressBar } from '../components/ui/Layout'
import { basename } from '../lib/viewModel'
import { useApp } from '../state/AppState'

const STAGES = [
  { label: 'Discovering files', desc: 'Listing files and checking types, sizes and links against the limits.' },
  { label: 'Extracting and classifying', desc: 'The local model proposes category, merchant, date and amount with evidence.' },
  { label: 'Drafting organization plan', desc: 'Destination paths are built by rules inside the folder. Nothing moves.' },
]

export function ScanningPage() {
  const { state, navigate, startScan, counts, usingFixtures } = useApp()
  const p = state.progress
  const failed = state.phase === 'scan_failed'
  const done = state.scan !== null
  const scanning = state.phase === 'scanning'

  if (!p && !failed && !done) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="Scan" breadcrumbs={['Dashboard', 'Scan']} />
        <EmptyState
          icon={ScanSearch}
          title="No scan running"
          className="flex-1"
          actions={
            <Button variant="primary" icon={FolderOpen} onClick={() => navigate('folder')}>
              Select Folder
            </Button>
          }
        >
          Select a folder to start a scan.
        </EmptyState>
      </div>
    )
  }

  const total = p?.files_total ?? 0
  const processed = p?.files_processed ?? 0
  const pct = done ? 1 : total ? (processed / total) * 0.95 : 0
  const stageIdx = done ? 3 : !p ? 0 : processed >= total && total > 0 ? 2 : 1

  return (
    <div className="scroll-area flex-1">
      <PageHeader
        title={done ? 'Scan complete' : failed ? 'Scan stopped' : 'Scanning…'}
        meta={usingFixtures && <FixtureTag />}
        breadcrumbs={['Dashboard', state.folder?.name ?? 'Folder', 'Scan']}
        description={done ? 'Every supported file was analyzed. Review the results before anything is organized.' : 'Files are read on this device. Nothing is moved during a scan.'}
        actions={
          done && (
            <>
              <Button onClick={() => navigate('plan')}>View plan</Button>
              <Button variant="primary" iconRight={ArrowRight} onClick={() => navigate('files')}>
                Review files
              </Button>
            </>
          )
        }
      />
      <div className="grid grid-cols-[minmax(0,1fr)_320px] gap-4 p-6">
        <div className="space-y-4">
          {failed && (
            <Banner
              tone="danger"
              icon={XCircle}
              title="The scan could not finish"
              actions={
                <>
                  <Button size="sm" onClick={() => navigate('folder')}>
                    Back to folder
                  </Button>
                  <Button size="sm" variant="primary" icon={RotateCcw} onClick={startScan}>
                    Retry scan
                  </Button>
                </>
              }
            >
              {state.scanError} No files were changed and no plan was made.
            </Banner>
          )}
          {done && (
            <Banner tone="success" icon={CheckCircle2} title={`${counts.documents} documents analyzed`}>
              {counts.needsReview} need review · {counts.skipped} skipped. No files have been moved.
            </Banner>
          )}

          <Panel>
            <div className="flex items-end justify-between">
              <div>
                <div className="label">Overall progress</div>
                <div className="tabular mt-1 text-2xl font-semibold">{Math.round(pct * 100)}%</div>
              </div>
              <div className="tabular grid grid-cols-3 gap-6 text-right text-sm">
                <div>
                  <div className="text-xs text-fg-subtle">Processed</div>
                  <div className="font-semibold">{processed}</div>
                </div>
                <div>
                  <div className="text-xs text-fg-subtle">Skipped</div>
                  <div className="font-semibold">{done ? counts.skipped : '—'}</div>
                </div>
                <div>
                  <div className="text-xs text-fg-subtle">Remaining</div>
                  <div className="font-semibold">{Math.max(0, total - processed)}</div>
                </div>
              </div>
            </div>
            <div className="mt-3">
              <ProgressBar value={pct} tone={failed ? 'danger' : done ? 'success' : 'accent'} label="Scan progress" />
            </div>
            <div className="mt-2 flex h-5 items-center gap-2 text-xs text-fg-muted">
              {scanning && p?.current_file && (
                <>
                  <Loader2 size={13} className="animate-spin" aria-hidden />
                  <span className="truncate font-mono">{p.current_file}</span>
                </>
              )}
            </div>
          </Panel>

          <Panel title="Activity" icon={FileText} bodyClassName="p-0">
            {state.activity.filter((e) => e.type === 'document_analyzed').length === 0 ? (
              <p className="px-4 py-6 text-center text-sm text-fg-subtle">{scanning ? 'Waiting for the first file…' : 'No files analyzed in this scan.'}</p>
            ) : (
              <ul className="scroll-area max-h-80 divide-y divide-line">
                {state.activity
                  .filter((e) => e.type === 'document_analyzed')
                  .slice(0, 30)
                  .map((e) => (
                    <li key={e.id} className="flex h-9 items-center gap-3 px-4 text-xs animate-fade-in">
                      <Check size={13} className="shrink-0 text-success" aria-hidden />
                      <span className="min-w-0 flex-1 truncate font-mono">{basename(e.title.replace(/^Analyzed /, ''))}</span>
                    </li>
                  ))}
              </ul>
            )}
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel title="Stages">
            <ol className="space-y-3">
              {STAGES.map((s, i) => {
                const isDone = i < stageIdx
                const isActive = i === stageIdx && !done
                const isFailed = failed && isActive
                return (
                  <li key={s.label} className="flex gap-3">
                    <span
                      className={cx(
                        'mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border',
                        isDone && 'border-success bg-success/15 text-success',
                        isActive && !isFailed && 'border-accent text-accent-hover',
                        isFailed && 'border-danger bg-danger/15 text-danger',
                        !isDone && !isActive && 'border-line-strong text-fg-subtle',
                      )}
                    >
                      {isDone ? <Check size={12} strokeWidth={3} /> : isFailed ? <XCircle size={12} /> : isActive ? <Loader2 size={12} className="animate-spin" /> : null}
                    </span>
                    <div>
                      <div className={cx('text-sm', isActive || isDone ? 'text-fg' : 'text-fg-subtle')}>{s.label}</div>
                      <div className="text-xs text-fg-subtle">{s.desc}</div>
                    </div>
                  </li>
                )
              })}
            </ol>
          </Panel>
          <Panel title="File handling">
            <dl className="space-y-2 text-xs">
              <div>
                <dt className="font-medium text-fg">Supported</dt>
                <dd className="text-fg-muted">Text-based PDF, TXT and CSV, up to {state.scan?.max_files ?? 100} files.</dd>
              </div>
              <div>
                <dt className="font-medium text-fg">Skipped</dt>
                <dd className="text-fg-muted">Images, DOCX, scanned PDFs, oversized files and symbolic links are listed but never processed.</dd>
              </div>
              <div>
                <dt className="font-medium text-fg">Failed</dt>
                <dd className="text-fg-muted">Supported files without a usable result stay visible for manual review.</dd>
              </div>
            </dl>
          </Panel>
        </div>
      </div>
    </div>
  )
}
