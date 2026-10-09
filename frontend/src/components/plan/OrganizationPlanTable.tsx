import { AlertTriangle, ArrowRight, Copy, Minus, PauseCircle, XCircle, type LucideIcon } from 'lucide-react'
import type { PlanRow, PlanWarning } from '../../lib/viewModel'
import { Badge, CategoryBadge, type Tone } from '../ui/Badge'
import { cx } from '../ui/cx'

const WARN: Record<PlanWarning['kind'], { tone: Tone; icon: LucideIcon; label: string }> = {
  collision: { tone: 'warning', icon: AlertTriangle, label: 'Name collision' },
  duplicate: { tone: 'info', icon: Copy, label: 'Duplicate' },
  review: { tone: 'warning', icon: PauseCircle, label: 'Blocks approval' },
  failed: { tone: 'danger', icon: XCircle, label: 'Extraction failed' },
  skipped: { tone: 'neutral', icon: Minus, label: 'Skipped' },
}

export function OrganizationPlanTable({ rows, onOpenDoc }: { rows: PlanRow[]; onOpenDoc: (id: string) => void }) {
  return (
    <table className="w-full table-fixed border-separate border-spacing-0 text-sm">
      <colgroup>
        <col className="w-[24%]" />
        <col className="w-[3%]" />
        <col className="w-[33%]" />
        <col className="w-[11%]" />
        <col className="w-[29%]" />
      </colgroup>
      <thead className="sticky top-0 z-10">
        <tr className="text-left text-2xs font-semibold uppercase tracking-wide text-fg-subtle">
          <th className="h-8 border-b border-line bg-surface-1 px-3">Original path</th>
          <th className="border-b border-line bg-surface-1" aria-label="to" />
          <th className="border-b border-line bg-surface-1 px-3">Proposed destination</th>
          <th className="border-b border-line bg-surface-1 px-3">Category</th>
          <th className="border-b border-line bg-surface-1 px-3">Reason &amp; warnings</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((p) => (
          <tr key={p.fileId} className={cx('align-top hover:bg-surface-2', p.action === 'leave' && 'text-fg-muted', p.blocking && 'bg-warning/5')}>
            <td className="border-b border-line px-3 py-2.5">
              {p.fileId.startsWith('skip:') ? (
                <span className="block truncate font-mono text-xs" title={p.from}>
                  {p.from}
                </span>
              ) : (
                <button type="button" onClick={() => onOpenDoc(p.fileId)} className="block max-w-full truncate text-left font-mono text-xs hover:text-accent-hover hover:underline" title={p.from}>
                  {p.from}
                </button>
              )}
            </td>
            <td className="border-b border-line py-2.5 text-center">
              <ArrowRight size={13} className={p.action === 'leave' ? 'text-fg-subtle' : p.action === 'review_folder' ? 'text-warning' : 'text-accent-hover'} aria-hidden />
            </td>
            <td className="border-b border-line px-3 py-2.5">
              {p.to ? (
                <span className={cx('block truncate font-mono text-xs', p.action === 'review_folder' ? 'text-warning' : 'text-fg')} title={p.to}>
                  {p.to}
                </span>
              ) : (
                <span className="text-xs text-fg-subtle">Stays in place</span>
              )}
            </td>
            <td className="border-b border-line px-3 py-2.5">{p.fileId.startsWith('skip:') ? <span className="text-fg-subtle">—</span> : <CategoryBadge category={p.category} />}</td>
            <td className="border-b border-line px-3 py-2.5">
              <div className="line-clamp-2 text-xs text-fg-muted" title={p.reason}>
                {p.reason}
              </div>
              {p.warnings.length > 0 && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {p.warnings
                    .filter((w) => w.kind !== 'skipped')
                    .map((w, i) => {
                      const m = WARN[w.kind]
                      return (
                        <Badge key={i} tone={m.tone} icon={m.icon} title={w.message}>
                          {m.label}
                        </Badge>
                      )
                    })}
                </div>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}
