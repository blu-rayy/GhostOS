import { useRef, type ReactNode, type RefObject } from 'react'
import { cx } from '../ui/cx'
import { useFocusTrap } from './useFocusTrap'

/**
 * Paper modal: the page stays visible underneath, dimmed with white (rgba 255,255,255,.72).
 * Focus moves to `initialFocus` (the safe choice), Tab stays inside the dialog, Esc calls
 * `onCancel`, and focus returns to whatever was focused before it opened.
 */
export function PaperDialog({
  open,
  onCancel,
  labelledBy,
  describedBy,
  initialFocus,
  role = 'dialog',
  variant = 'a',
  width = 560,
  className,
  children,
}: {
  open: boolean
  onCancel: () => void
  labelledBy: string
  describedBy?: string
  initialFocus?: RefObject<HTMLElement | null>
  role?: 'dialog' | 'alertdialog'
  variant?: 'a' | 'b'
  width?: number
  className?: string
  children: ReactNode
}) {
  const ref = useRef<HTMLDivElement>(null)
  useFocusTrap(open, ref, onCancel, initialFocus)

  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[rgba(255,255,255,.72)] p-6">
      <div
        ref={ref}
        tabIndex={-1}
        role={role}
        aria-modal="true"
        aria-labelledby={labelledBy}
        aria-describedby={describedBy}
        style={{ width }}
        className={cx('flex max-h-full max-w-full flex-col border-[2.5px] border-ink bg-paper shadow-sheet outline-none', variant === 'a' ? 'sketch-a' : 'sketch-b', className)}
      >
        {children}
      </div>
    </div>
  )
}
