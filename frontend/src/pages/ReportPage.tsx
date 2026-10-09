import { useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, Coins, Download, FileSpreadsheet, FolderOpen, Info } from 'lucide-react'
import { ExpenseReportTable } from '../components/report/ExpenseReportTable'
import { FixtureTag } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Dialog } from '../components/ui/Dialog'
import { Banner, EmptyState, PageHeader } from '../components/ui/Layout'
import { SearchInput, Segmented } from '../components/ui/Toolbar'
import { money } from '../lib/format'
import { downloadText, toCsv } from '../lib/report'
import { useApp } from '../state/AppState'
import type { ReportRowStatus } from '../types/api'

type Filter = 'all' | ReportRowStatus

export function ReportPage() {
  const { state, navigate, selectDoc, logExport, usingFixtures } = useApp()
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState<Filter>('all')
  const [confirm, setConfirm] = useState(false)
  const [exported, setExported] = useState<string | null>(null)

  // After approval, show the report exactly as approved.
  const plan = state.approvedPlan ?? state.plan
  const rows = useMemo(() => plan?.report_rows ?? [], [plan])
  const totals = plan?.totals ?? []
  const accepted = rows.filter((r) => r.status === 'accepted').length
  const unresolved = rows.length - accepted
  const locked = state.batch !== null && state.phase !== 'undone'

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase()
    return rows.filter((r) => (filter === 'all' || r.status === filter) && (!q || [r.source_filename, r.merchant ?? ''].some((s) => s.toLowerCase().includes(q))))
  }, [rows, query, filter])

  if (!plan) {
    return (
      <div className="flex flex-1 flex-col">
        <PageHeader title="Expense report" description="A draft expense report is prepared from invoices and receipts after a scan." />
        <EmptyState
          icon={FileSpreadsheet}
          title="No report yet"
          className="flex-1"
          actions={
            <Button variant="primary" icon={FolderOpen} onClick={() => navigate('folder')}>
              Select Folder
            </Button>
          }
        >
          Scan a folder to draft an expense report.
        </EmptyState>
      </div>
    )
  }

  const filename = `ghostos_expenses_${(state.folder?.name ?? 'report').replace(/\W+/g, '_')}.csv`
  function doExport() {
    downloadText(filename, toCsv(rows))
    logExport(filename, accepted)
    setExported(new Date().toISOString())
    setConfirm(false)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader
        title="Expense report"
        meta={usingFixtures && <FixtureTag />}
        breadcrumbs={[state.folder?.name ?? 'Folder', 'Expense report']}
        description="Draft rows from invoices and receipts. Click a cell to correct it. Only accepted rows count toward totals and export."
        actions={
          <Button variant="primary" icon={Download} disabled={accepted === 0} onClick={() => (unresolved > 0 ? setConfirm(true) : doExport())}>
            Export CSV
          </Button>
        }
      />

      <div className="flex shrink-0 flex-col gap-3 px-6 pt-4">
        <div className="flex flex-wrap items-center gap-2">
          <SearchInput value={query} onChange={setQuery} placeholder="Search rows" />
          <Segmented<Filter>
            label="Row status"
            value={filter}
            onChange={setFilter}
            options={[
              { value: 'all', label: 'All', count: rows.length },
              { value: 'accepted', label: 'Accepted', count: accepted },
              { value: 'needs_review', label: 'Needs review', count: unresolved },
            ]}
          />
          <div className="ml-auto flex items-center gap-2 text-xs text-fg-muted">
            {state.batch ? (
              <>
                <CheckCircle2 size={13} className="text-success" aria-hidden />
                Written to <span className="font-mono">{state.batch.report_relative_path}</span>
                {usingFixtures && ' (simulated)'}
              </>
            ) : (
              <>
                <Info size={13} aria-hidden />
                Draft. The backend writes the CSV into the folder when you approve the plan.
              </>
            )}
          </div>
        </div>
        {exported && (
          <Banner tone="success" icon={CheckCircle2} title={`Exported ${accepted} accepted rows`}>
            {filename} was handed to your download/save dialog. Rows needing review were not included.
          </Banner>
        )}
        {state.actionError && !locked && (
          <Banner tone="danger" icon={AlertTriangle} title="Change not saved">
            {state.actionError}
          </Banner>
        )}
      </div>

      <div className="scroll-area mx-6 my-3 min-h-0 flex-1 rounded-lg border border-line bg-surface-1">
        {visible.length === 0 ? (
          <EmptyState icon={FileSpreadsheet} title="No rows in this view" />
        ) : (
          <ExpenseReportTable
            rows={visible}
            locked={locked}
            onOpen={(id) => {
              selectDoc(id)
              navigate('files')
            }}
          />
        )}
      </div>

      <div className="flex shrink-0 items-center gap-6 border-t border-line bg-surface-1 px-6 py-3">
        <div className="flex items-center gap-2 text-xs text-fg-muted">
          <Coins size={15} aria-hidden />
          <span>
            Totals from <strong className="text-fg">{accepted}</strong> accepted rows
          </span>
        </div>
        <div className="flex flex-1 flex-wrap items-center gap-x-6 gap-y-1">
          {totals.length === 0 ? (
            <span className="text-sm text-fg-subtle">No accepted rows yet</span>
          ) : (
            totals.map((t) => (
              <div key={t.currency} className="flex items-baseline gap-2">
                <span className="text-2xs font-semibold text-fg-subtle">{t.currency}</span>
                <span className="tabular text-lg font-semibold">{money(t.amount, t.currency)}</span>
                <span className="text-2xs text-fg-subtle">{t.row_count} rows</span>
              </div>
            ))
          )}
        </div>
        <div className="flex flex-col items-end text-2xs text-fg-subtle">
          {totals.length > 1 && <span>Currencies are totalled separately, never combined.</span>}
          {unresolved > 0 && (
            <span className="flex items-center gap-1 text-warning">
              <AlertTriangle size={11} aria-hidden /> {unresolved} rows not counted (need review, incomplete or duplicate)
            </span>
          )}
        </div>
      </div>

      <Dialog
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Export with rows that need review?"
        icon={AlertTriangle}
        tone="warning"
        footer={
          <>
            <Button
              variant="ghost"
              onClick={() => {
                setConfirm(false)
                setFilter('needs_review')
              }}
            >
              Show those rows
            </Button>
            <Button variant="primary" icon={Download} onClick={doExport}>
              Export {accepted} accepted rows
            </Button>
          </>
        }
      >
        <p>
          {unresolved} {unresolved === 1 ? 'row needs' : 'rows need'} review and will <strong>not</strong> be included. Their amounts are not guessed or filled in.
        </p>
        <p className="mt-2 text-fg-muted">The CSV is generated in the app from the current rows, with amounts in their original currency.</p>
      </Dialog>
    </div>
  )
}
