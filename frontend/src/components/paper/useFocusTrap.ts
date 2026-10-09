import { useEffect, useRef, type RefObject } from 'react'

/** Open traps, innermost last: only the top one handles keys (e.g. a dialog opened from a panel). */
const stack: symbol[] = []

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

/**
 * Modal focus handling shared by PaperDialog and SidePanel: while `open`, focus moves to
 * `initialFocus` (or the container), Tab / Shift+Tab stay inside, Esc calls `onCancel`, and
 * focus returns to whatever was focused before it opened.
 */
export function useFocusTrap(open: boolean, container: RefObject<HTMLElement | null>, onCancel: () => void, initialFocus?: RefObject<HTMLElement | null>) {
  const cancelRef = useRef(onCancel)
  useEffect(() => {
    cancelRef.current = onCancel
  })

  useEffect(() => {
    if (!open) return
    const me = Symbol('focus-trap')
    stack.push(me)
    const prev = document.activeElement as HTMLElement | null
    ;(initialFocus?.current ?? container.current)?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (stack[stack.length - 1] !== me) return
      if (e.key === 'Escape') {
        e.preventDefault()
        cancelRef.current()
        return
      }
      const root = container.current
      if (e.key !== 'Tab' || !root) return
      const items = [...root.querySelectorAll<HTMLElement>(FOCUSABLE)]
      if (items.length === 0) {
        e.preventDefault()
        return
      }
      const first = items[0]
      const last = items[items.length - 1]
      const active = document.activeElement
      if (e.shiftKey && (active === first || !root.contains(active))) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && (active === last || !root.contains(active))) {
        e.preventDefault()
        first.focus()
      }
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      stack.splice(stack.indexOf(me), 1)
      prev?.focus()
    }
  }, [open, container, initialFocus])
}
