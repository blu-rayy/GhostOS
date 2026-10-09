import { ShieldAlert, ShieldCheck } from 'lucide-react'
import { useServiceStates } from './useServiceStates'
import { cx } from '../ui/cx'

export type ServiceState = 'unknown' | 'fixture' | 'ok' | 'down'

const STATE: Record<ServiceState, { dot: string }> = {
  unknown: { dot: 'bg-fg-subtle' },
  fixture: { dot: 'bg-info' },
  ok: { dot: 'bg-success' },
  down: { dot: 'bg-danger' },
}

export function ServiceRow({ name, state, label }: { name: string; state: ServiceState; label: string }) {
  return (
    <div className="flex items-center justify-between gap-2 text-2xs">
      <span className="text-fg-muted">{name}</span>
      <span className="flex items-center gap-1.5 text-fg-subtle">
        <span className={cx('h-1.5 w-1.5 rounded-full', STATE[state].dot)} aria-hidden />
        {label}
      </span>
    </div>
  )
}

/** Compact sidebar block. */
export function LocalStatusIndicator({ onOpen }: { onOpen: () => void }) {
  const svc = useServiceStates()
  const leaked = svc.external > 0
  return (
    <button
      type="button"
      onClick={onOpen}
      className="w-full rounded-md border border-line bg-surface-2/60 p-2.5 text-left transition-colors duration-[120ms] hover:border-line-strong"
    >
      <div className={cx('mb-2 flex items-center gap-1.5 text-xs font-medium', leaked ? 'text-danger' : 'text-success')}>
        {leaked ? <ShieldAlert size={14} aria-hidden /> : <ShieldCheck size={14} aria-hidden />}
        {leaked ? `${svc.external} external requests` : 'Local-only mode'}
      </div>
      <div className="space-y-1">
        <ServiceRow name="Backend" {...svc.backend} />
        <ServiceRow name="Ollama" {...svc.model} />
      </div>
    </button>
  )
}
