import { Search, X } from 'lucide-react';
import { cx } from './cx';

export function SearchInput({ value, onChange, placeholder = 'Search' }: { value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div className="relative w-56">
      <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-fg-subtle" aria-hidden />
      <input className="input pl-8 pr-7" type="search" value={value} placeholder={placeholder} onChange={(e) => onChange(e.target.value)} aria-label={placeholder} />
      {value && (
        <button type="button" onClick={() => onChange('')} className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-0.5 text-fg-subtle hover:text-fg" aria-label="Clear search">
          <X size={13} />
        </button>
      )}
    </div>
  );
}

export function Segmented<T extends string>({ options, value, onChange, label }: { options: { value: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void; label: string }) {
  return (
    <div role="radiogroup" aria-label={label} className="flex h-8 items-center rounded-md border border-line bg-surface-2 p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={value === o.value}
          onClick={() => onChange(o.value)}
          className={cx(
            'flex h-full items-center gap-1.5 rounded-sm px-2.5 text-xs transition-colors duration-[120ms]',
            value === o.value ? 'bg-surface-3 font-medium text-fg shadow-panel' : 'text-fg-muted hover:text-fg',
          )}
        >
          {o.label}
          {o.count !== undefined && <span className="tabular text-2xs text-fg-subtle">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function ToggleChip({ active, onClick, children, tone = 'warning' }: { active: boolean; onClick: () => void; children: React.ReactNode; tone?: 'warning' | 'accent' }) {
  const on = tone === 'warning' ? 'border-warning/50 bg-warning/12 text-warning' : 'border-accent/50 bg-accent/12 text-accent-hover';
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cx('flex h-8 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium transition-colors duration-[120ms]', active ? on : 'border-line bg-surface-2 text-fg-muted hover:text-fg')}
    >
      {children}
    </button>
  );
}
