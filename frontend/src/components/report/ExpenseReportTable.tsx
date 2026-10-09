import { Copy, Eye } from 'lucide-react'
import { formatAmount } from '../../lib/money'
import { formatDate, isValidIsoDate, normalizeAmountInput } from '../../lib/format'
import { basename } from '../../lib/viewModel'
import { useApp } from '../../state/AppState'
import type { ReportRow } from '../../types/api'
import { Badge, CategoryBadge, ReportStatusBadge } from '../ui/Badge'
import { cx } from '../ui/cx'
import { InlineEdit } from './InlineEdit'

/** Spreadsheet-style view of PlanPreview.report_rows. Each edit is a PATCH to the document. */
export function ExpenseReportTable({ rows, onOpen, locked }: { rows: ReportRow[]; onOpen: (fileId: string) => void; locked: boolean }) {
  const { correct, state } = useApp()
  const duplicates = new Set((state.scan?.documents ?? []).filter((d) => d.duplicate_of).map((d) => d.file_id))
  const save = (r: ReportRow, field: 'merchant' | 'date' | 'amount' | 'currency', value: string | null) =>
    correct(r.file_id, { [field]: value, accept: false }, field)

  return (
    <table className="w-full table-fixed border-separate border-spacing-0 text-xs">
      <colgroup>
        <col className="w-[27%]" />
        <col className="w-[21%]" />
        <col className="w-[12%]" />
        <col className="w-[11%]" />
        <col className="w-[11%]" />
        <col className="w-[7%]" />
        <col className="w-[11%]" />
      </colgroup>
      <thead className="sticky top-0 z-10">
        <tr className="text-left text-2xs font-semibold uppercase tracking-wide text-fg-subtle">
          {['Source file', 'Merchant', 'Date', 'Type', 'Amount', 'Cur.', 'Status'].map((h) => (
            <th key={h} className={cx('h-8 border-b border-r border-line bg-surface-2 px-2.5 last:border-r-0', h === 'Amount' && 'text-right')}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const cell = 'border-b border-r border-line px-1 last:border-r-0'
          return (
            <tr key={r.file_id} className={cx('group h-9 hover:bg-surface-2/60', r.status === 'needs_review' && 'bg-warning/5')}>
              <td className={cx(cell, 'px-2.5')}>
                <div className="flex items-center gap-1">
                  <span className="min-w-0 flex-1 truncate" title={r.source_filename}>
                    {basename(r.source_filename)}
                  </span>
                  <button
                    type="button"
                    onClick={() => onOpen(r.file_id)}
                    className="shrink-0 rounded-md p-0.5 text-fg-subtle opacity-0 hover:text-fg group-hover:opacity-100 focus:opacity-100"
                    aria-label={`Open ${basename(r.source_filename)} details`}
                  >
                    <Eye size={13} />
                  </button>
                </div>
              </td>
              <td className={cell}>
                <InlineEdit
                  label="merchant"
                  raw={r.merchant ?? ''}
                  display={r.merchant ?? <span className="text-fg-subtle">—</span>}
                  validate={(v) => (v.length < 2 ? 'Enter a merchant' : null)}
                  onSave={(v) => save(r, 'merchant', v)}
                  disabled={locked}
                />
              </td>
              <td className={cell}>
                <InlineEdit
                  label="date"
                  mono
                  raw={r.date ?? ''}
                  display={r.date ? formatDate(r.date) : <span className="text-warning">Missing</span>}
                  validate={(v) => (isValidIsoDate(v) ? null : 'Use YYYY-MM-DD')}
                  onSave={(v) => save(r, 'date', v)}
                  disabled={locked}
                />
              </td>
              <td className={cx(cell, 'px-2.5')}>
                <CategoryBadge category={r.category} />
              </td>
              <td className={cell}>
                <InlineEdit
                  label="amount"
                  mono
                  align="right"
                  raw={r.amount ?? ''}
                  display={r.amount !== null ? formatAmount(r.amount) : <span className="text-warning">Unresolved</span>}
                  validate={(v) => (normalizeAmountInput(v) ? null : 'Amount like 1520.00')}
                  onSave={(v) => save(r, 'amount', normalizeAmountInput(v))}
                  disabled={locked}
                />
              </td>
              <td className={cell}>
                <InlineEdit
                  label="currency"
                  raw={r.currency ?? ''}
                  options={['PHP', 'USD', 'EUR']}
                  display={r.currency ?? <span className="text-fg-subtle">—</span>}
                  onSave={(v) => save(r, 'currency', v || null)}
                  disabled={locked}
                />
              </td>
              <td className={cx(cell, 'px-2')}>
                {duplicates.has(r.file_id) ? (
                  <Badge tone="info" icon={Copy} title="Exact duplicate of another file. Never counted in totals.">
                    Duplicate
                  </Badge>
                ) : (
                  <ReportStatusBadge status={r.status} title={r.status === 'accepted' ? 'Counted in totals' : 'Not counted until the document is reviewed and complete'} />
                )}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
