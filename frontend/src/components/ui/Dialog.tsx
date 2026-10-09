import { useEffect, useRef, type ReactNode } from 'react';
import { X, type LucideIcon } from 'lucide-react';
import { cx } from './cx';

/** Modal dialog. Escape and the close button dismiss; focus moves into the dialog. */
export function Dialog({
  open,
  onClose,
  title,
  icon: Icon,
  tone = 'accent',
  children,
  footer,
  width = 'max-w-xl',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  icon?: LucideIcon;
  tone?: 'accent' | 'warning' | 'danger';
  children: ReactNode;
  footer?: ReactNode;
  width?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      prev?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  const toneCls = { accent: 'text-accent-hover bg-accent/15', warning: 'text-warning bg-warning/15', danger: 'text-danger bg-danger/15' }[tone];
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6 animate-fade-in" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" aria-label={title} className={cx('flex max-h-full w-full flex-col rounded-lg bg-surface-1 shadow-overlay outline-none', width)}>
        <div className="flex items-center gap-3 border-b border-line px-5 py-3.5">
          {Icon && (
            <span className={cx('flex h-7 w-7 items-center justify-center rounded-md', toneCls)}>
              <Icon size={16} aria-hidden />
            </span>
          )}
          <h2 className="flex-1 text-base font-semibold">{title}</h2>
          <button type="button" onClick={onClose} aria-label="Close dialog" className="rounded-md p-1 text-fg-subtle hover:bg-surface-3 hover:text-fg">
            <X size={16} />
          </button>
        </div>
        <div className="scroll-area min-h-0 flex-1 px-5 py-4 text-sm">{children}</div>
        {footer && <div className="flex items-center justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}
