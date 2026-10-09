import type { ReactNode } from 'react';
import { ChevronRight, type LucideIcon } from 'lucide-react';
import { cx } from './cx';

export function PageHeader({
  title,
  description,
  breadcrumbs,
  actions,
  meta,
}: {
  title: string;
  description?: ReactNode;
  breadcrumbs?: string[];
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <header className="flex shrink-0 items-end justify-between gap-6 border-b border-line px-6 pb-4 pt-5">
      <div className="min-w-0">
        {breadcrumbs && breadcrumbs.length > 0 && (
          <nav aria-label="Breadcrumb" className="mb-1 flex items-center gap-1 text-xs text-fg-subtle">
            {breadcrumbs.map((b, i) => (
              <span key={b} className="flex items-center gap-1">
                {i > 0 && <ChevronRight size={12} aria-hidden />}
                {b}
              </span>
            ))}
          </nav>
        )}
        <div className="flex items-center gap-2">
          <h1 className="truncate text-xl font-semibold tracking-tight">{title}</h1>
          {meta}
        </div>
        {description && <p className="mt-0.5 max-w-3xl text-sm text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Panel({ title, actions, children, className, bodyClassName, icon: Icon }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string; bodyClassName?: string; icon?: LucideIcon }) {
  return (
    <section className={cx('flex flex-col rounded-lg border border-line bg-surface-1 shadow-panel', className)}>
      {title && (
        <div className="flex h-10 shrink-0 items-center justify-between gap-3 border-b border-line px-4">
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            {Icon && <Icon size={15} className="text-fg-subtle" aria-hidden />}
            {title}
          </h2>
          {actions}
        </div>
      )}
      <div className={cx('p-4', bodyClassName)}>{children}</div>
    </section>
  );
}

export function StatCard({ label, value, hint, tone = 'neutral', icon: Icon }: { label: string; value: ReactNode; hint?: ReactNode; tone?: 'neutral' | 'warning' | 'success' | 'accent'; icon: LucideIcon }) {
  const toneCls = { neutral: 'text-fg-muted', warning: 'text-warning', success: 'text-success', accent: 'text-accent-hover' }[tone];
  return (
    <div className="rounded-lg border border-line bg-surface-1 px-4 py-3 shadow-panel">
      <div className="flex items-center justify-between">
        <span className="text-xs text-fg-muted">{label}</span>
        <Icon size={15} className={toneCls} aria-hidden />
      </div>
      <div className="tabular mt-1 text-2xl font-semibold">{value}</div>
      {hint && <div className="mt-0.5 text-xs text-fg-subtle">{hint}</div>}
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, actions, className }: { icon: LucideIcon; title: string; children?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div className={cx('flex flex-col items-center justify-center px-6 py-10 text-center', className)}>
      <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg border border-line bg-surface-2 text-fg-subtle">
        <Icon size={20} aria-hidden />
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-1 max-w-md text-sm text-fg-muted">{children}</div>}
      {actions && <div className="mt-4 flex items-center gap-2">{actions}</div>}
    </div>
  );
}

const BANNER = {
  info: 'border-info/30 bg-info/8 text-info',
  warning: 'border-warning/35 bg-warning/8 text-warning',
  danger: 'border-danger/35 bg-danger/8 text-danger',
  success: 'border-success/30 bg-success/8 text-success',
  neutral: 'border-line bg-surface-2 text-fg-muted',
};

export function Banner({ tone = 'info', icon: Icon, title, children, actions, className }: { tone?: keyof typeof BANNER; icon: LucideIcon; title?: ReactNode; children?: ReactNode; actions?: ReactNode; className?: string }) {
  return (
    <div role={tone === 'danger' ? 'alert' : 'status'} className={cx('flex items-start gap-3 rounded-md border px-3 py-2.5', BANNER[tone], className)}>
      <Icon size={16} className="mt-0.5 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1 text-sm">
        {title && <div className="font-semibold">{title}</div>}
        {children && <div className="text-fg-muted">{children}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function ProgressBar({ value, tone = 'accent', label }: { value: number; tone?: 'accent' | 'success' | 'danger' | 'warning'; label?: string }) {
  const pct = Math.max(0, Math.min(100, Math.round(value * 100)));
  const toneCls = { accent: 'bg-accent', success: 'bg-success', danger: 'bg-danger', warning: 'bg-warning' }[tone];
  return (
    <div role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={label} className="h-1.5 w-full overflow-hidden rounded-full bg-surface-3">
      <div className={cx('h-full rounded-full transition-[width] duration-200 ease-out', toneCls)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function KeyValue({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-1.5 text-sm">
      <span className="text-fg-muted">{label}</span>
      <span className="min-w-0 truncate text-right">{children}</span>
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <code className="rounded-sm border border-line bg-surface-2 px-1 py-px font-mono text-2xs text-fg-muted">{children}</code>;
}

export function PathText({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('font-mono text-xs', className)}>{children}</span>;
}
