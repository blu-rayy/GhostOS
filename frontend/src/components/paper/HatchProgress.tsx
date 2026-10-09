import { cx } from '../ui/cx'

const HATCH = 'repeating-linear-gradient(-45deg, #1a1a1a 0 3px, #ffffff 3px 9px)'

/**
 * 26px progress bar with ink hatching. `value` is 0–1; pass null when the total is
 * unknown (indeterminate: the bar is fully hatched and no value is announced).
 */
export function HatchProgress({ value, label, className }: { value: number | null; label: string; className?: string }) {
  const pct = value === null ? null : Math.max(0, Math.min(100, Math.round(value * 100)))
  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={pct === null ? undefined : 0}
      aria-valuemax={pct === null ? undefined : 100}
      aria-valuenow={pct ?? undefined}
      className={cx('h-[26px] overflow-hidden rounded-[14px] border-[2.5px] border-ink bg-paper', className)}
    >
      <div
        className={cx('h-full transition-[width] duration-300 ease-out', pct !== null && pct > 0 && pct < 100 && 'border-r-[2.5px] border-ink', pct === null && 'opacity-40')}
        style={{ width: `${pct ?? 100}%`, backgroundImage: HATCH }}
      />
    </div>
  )
}
