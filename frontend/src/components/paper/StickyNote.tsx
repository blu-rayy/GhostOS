import type { ReactNode } from 'react'
import { cx } from '../ui/cx'

/** Square-cornered sticky note, slightly rotated. Pink notes are for errors and can be alerts. */
export function StickyNote({ tone = 'yellow', alert = false, tilt = -1, className, children }: { tone?: 'yellow' | 'pink'; alert?: boolean; tilt?: number; className?: string; children: ReactNode }) {
  return (
    <div
      role={alert ? 'alert' : undefined}
      style={{ transform: `rotate(${tilt}deg)` }}
      className={cx('border-[2.5px] border-ink shadow-sticky', tone === 'yellow' ? 'bg-sticky' : 'bg-sticky-pink', className)}
    >
      {children}
    </div>
  )
}
