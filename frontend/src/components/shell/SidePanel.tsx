import { useEffect, useRef, useState, type ReactNode } from 'react'
import { useFocusTrap } from '../paper/useFocusTrap'
import { CloseIcon } from '../paper/icons'

/** Matches --animate-panel-out; the panel stays mounted this long so it can slide away. */
const CLOSE_MS = 190

/**
 * History / Settings side panel: a 440px paper sheet over the full height of the app (below the
 * desktop title bar, which keeps its window buttons). It slides in from the right and the current
 * step stays visible behind it, faded; clicking the faded area, ×, or Esc closes it.
 */
export function SidePanel({ open, title, onClose, children }: { open: boolean; title: string; onClose: () => void; children: ReactNode }) {
  const ref = useRef<HTMLElement>(null)
  const close = useRef<HTMLButtonElement>(null)
  // Stay mounted briefly after `open` turns false so the slide-out can play.
  const [shown, setShown] = useState(open)
  const [wasOpen, setWasOpen] = useState(open)
  if (open !== wasOpen) {
    setWasOpen(open)
    if (open) setShown(true)
  }
  useEffect(() => {
    if (open || !shown) return
    const t = window.setTimeout(() => setShown(false), CLOSE_MS)
    return () => window.clearTimeout(t)
  }, [open, shown])
  useFocusTrap(open, ref, onClose, close)

  if (!shown) return null
  const closing = !open
  const titleId = `panel-${title.toLowerCase()}-title`
  return (
    <div className={`fixed inset-x-0 bottom-0 top-[var(--window-bar-h,0px)] z-40 flex justify-end ${closing ? 'pointer-events-none' : ''}`}>
      <div className={`absolute inset-0 bg-[rgba(255,255,255,.72)] ${closing ? 'animate-backdrop-out' : 'animate-backdrop-in'}`} onMouseDown={onClose} aria-hidden />
      <aside
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className={`relative flex h-full w-[440px] max-w-full flex-col border-l-[2.5px] border-ink bg-paper shadow-[-6px_0_0_rgb(26_26_26)] outline-none ${closing ? 'animate-panel-out' : 'animate-panel-in'}`}
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
