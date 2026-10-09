import { AlertTriangle, ArrowRight, Copy } from 'lucide-react'
import { formatDate, money } from '../../lib/format'
import type { FileRow } from '../../lib/viewModel'
import { CategoryBadge, ReviewStatusBadge } from '../ui/Badge'
import { cx } from '../ui/cx'

function Missing({ flagged }: { flagged: boolean }) {
  return flagged ? <span className="text-warning">Missing</span> : <span className="text-fg-subtle">—</span>
}

export function DocumentTable({ rows, selectedId, onSelect, compact }: { rows: FileRow[]; selectedId: string | null; onSelect: (id: string) => void; compact: boolean }) {
  return (
    <table className="w-full table-fixed border-separate border-spacing-0 text-sm">
      <colgroup>
        <col className={compact ? 'w-[29%]' : 'w-[19%]'} />
        {!compact && <col className="w-[5%]" />}
        <col className={compact ? 'w-[16%]' : 'w-[10%]'} />
        <col className={compact ? 'w-[20%]' : 'w-[14%]'} />
        {!compact && <col className="w-[9%]" />}
        <col className={compact ? 'w-[15%]' : 'w-[10%]'} />
        <col className={compact ? 'w-[20%]' : 'w-[11%]'} />
        {!compact && <col className="w-[22%]" />}
      </colgroup>
      <thead className="sticky top-0 z-10">
        <tr className="text-left text-2xs font-semibold uppercase tracking-wide text-fg-subtle">
          {['File', !compact && 'Type', 'Category', 'Merchant', !compact && 'Date', 'Amount', 'Status', !compact && 'Proposed destination']
            .filter(Boolean)
            .map((h) => (
              <th key={h as string} className={cx('h-8 border-b border-line bg-surface-1 px-3 font-semibold', h === 'Amount' && 'text-right')}>
                {h}
              </th>
            ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const selected = r.id === selectedId
          const skipped = r.status === 'skipped'
          const flagCodes = new Set(r.flags.map((f) => f.code))
          const amountFlag = flagCodes.has('amount_conflict') || flagCodes.has('amount_unparseable') || flagCodes.has('missing_amount')
          return (
            <tr
              key={r.id}
              onClick={() => onSelect(r.id)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault()
                  onSelect(r.id)
                }
              }}
              tabIndex={0}
              aria-selected={selected}
              className={cx(
                'group h-11 cursor-pointer outline-none transition-colors duration-[120ms] focus-visible:bg-surface-3',
                selected ? 'bg-accent/10' : 'hover:bg-surface-2',
                skipped && 'text-fg-subtle',
              )}
            >
              <td className={cx('border-b border-line px-3', selected && 'shadow-[inset_2px_0_0_rgb(var(--accent))]')}>
                <div className="flex min-w-0 items-center gap-1.5">
                  <span className={cx('truncate', !skipped && 'font-medium')} title={r.relPath}>
                    {r.filename}
                  </span>
                  {r.duplicateOf && <Copy size={12} className="shrink-0 text-info" aria-label="Duplicate" />}
                  {flagCodes.has('possible_injection') && <AlertTriangle size={12} className="shrink-0 text-warning" aria-label="Possible prompt injection" />}
                </div>
                {r.dir && <div className="truncate font-mono text-2xs text-fg-subtle">{r.dir}</div>}
              </td>
              {!compact && <td className="border-b border-line px-3 font-mono text-2xs uppercase text-fg-muted">{r.fileType}</td>}
              <td className="border-b border-line px-3">{skipped ? <span>—</span> : <CategoryBadge category={r.category} />}</td>
              <td className="border-b border-line px-3">
                {r.merchant ? <span className="block truncate">{r.merchant}</span> : <span className="text-fg-subtle">—</span>}
              </td>
              {!compact && (
                <td className="tabular border-b border-line px-3">{r.date ? formatDate(r.date) : <Missing flagged={flagCodes.has('missing_date')} />}</td>
              )}
              <td className={cx('tabular border-b border-line px-3 text-right', amountFlag && 'text-warning')}>
                {r.amount !== null ? money(r.amount, r.currency) : amountFlag ? 'Unresolved' : <span className="text-fg-subtle">—</span>}
              </td>
              <td className="border-b border-line px-3">
                <ReviewStatusBadge status={r.status} />
              </td>
              {!compact && (
                <td className="border-b border-line px-3 text-xs">
                  {r.destination ? (
                    <span className={cx('flex min-w-0 items-center gap-1 font-mono', r.destination.startsWith('Needs Review/') ? 'text-warning' : 'text-fg-muted')} title={r.destination}>
                      <ArrowRight size={11} className="shrink-0 text-fg-subtle" aria-hidden />
                      <span className="truncate">{r.destination}</span>
                    </span>
                  ) : (
                    <span className="text-fg-subtle">Stays in place</span>
                  )}
                </td>
              )}
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
