import { useEffect, useRef, type ReactNode, type RefObject } from 'react'
import { cx } from '../ui/cx'

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

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
  const cancelRef = useRef(onCancel)
  useEffect(() => {
    cancelRef.current = onCancel
  })

  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    ;(initialFocus?.current ?? ref.current)?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault()
        cancelRef.current()
        return
      }
      if (e.key !== 'Tab' || !ref.current) return
      const items = [...ref.current.querySelectorAll<HTMLElement>(FOCUSABLE)]
      if (items.length === 0) {
        e.preventDefault()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      const active = document.activeElement
      if (e.shiftKey && (active === first || !ref.current.contains(active))) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && (active === last || !ref.current.contains(active))) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      prev?.focus()
    }
  }, [open, initialFocus])

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
