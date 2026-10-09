import { useRef, type ReactNode } from 'react'
import { useFocusTrap } from '../paper/useFocusTrap'
import { CloseIcon } from '../paper/icons'

/**
 * History / Settings side panel: a 440px paper sheet under the header. The current step
 * stays visible behind it, dimmed; clicking the dimmed area, ×, or Esc closes it.
 */
export function SidePanel({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLElement>(null)
  const close = useRef<HTMLButtonElement>(null)
  useFocusTrap(open, ref, onClose, close)

  if (!open) return null
  const titleId = `panel-${title.toLowerCase()}-title`
  return (
    <div className="fixed inset-x-0 bottom-0 top-16 z-40 flex justify-end">
      <div className="absolute inset-0 bg-[rgba(255,255,255,.72)]" onMouseDown={onClose} aria-hidden />
      <aside
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="relative flex h-full w-[440px] max-w-full flex-col border-l-[2.5px] border-ink bg-paper shadow-[-6px_0_0_rgb(26_26_26)] outline-none"
      >
        <div className="flex shrink-0 items-center justify-between gap-3 border-b-[2.5px] border-ink px-6 py-3">
          <h2 id={titleId} className="m-0 font-display text-[30px] font-normal leading-tight">
            {title}
          </h2>
          <button
            ref={close}
            type="button"
            onClick={onClose}
            aria-label={`Close ${title}`}
            className="inline-flex h-10 w-10 items-center justify-center rounded-[12px] border-[2.5px] border-ink bg-paper hover:bg-pencil"
          >
            <CloseIcon size={20} crisp />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-4">{children}</div>
      </aside>
    </div>
  )
}
