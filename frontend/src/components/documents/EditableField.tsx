import { useEffect, useRef, useState, type ReactNode } from 'react'
import { AlertTriangle, Check, Pencil, X } from 'lucide-react'
import { cx } from '../ui/cx'

export type FieldInput =
  | { kind: 'text'; placeholder?: string }
  | { kind: 'date' }
  | { kind: 'amount' }
  | { kind: 'select'; options: { value: string; label: string }[] }

/** Where the shown value came from. The contract has no per-field confidence, so this is all we claim. */
export type FieldSource = 'extracted' | 'missing' | 'unresolved' | 'reviewed'

const SOURCE: Record<FieldSource, { label: string; dot: string }> = {
  extracted: { label: 'Extracted', dot: 'bg-fg-subtle' },
  missing: { label: 'Not found', dot: 'bg-danger' },
  unresolved: { label: 'Unresolved', dot: 'bg-warning' },
  reviewed: { label: 'Reviewed by you', dot: 'bg-accent' },
}

/**
 * Shows an extracted value and lets a person correct it.
 * Values are validated before saving; invalid input never reaches the API.
 */
export function EditableField({
  label,
  display,
  rawValue,
  source,
  issue,
  input,
  onSave,
  validate,
  disabled,
  compact = false,
}: {
  label: string
  display: ReactNode
  rawValue: string
  source: FieldSource
  /** Review flag message for this field, shown verbatim. */
  issue?: string
  input: FieldInput
  onSave: (value: string) => void
  validate?: (value: string) => string | null
  disabled?: boolean
  /** Narrow fields show the source dot without its label. */
  compact?: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState(rawValue)
  const [error, setError] = useState<string | null>(null)
  const ref = useRef<HTMLInputElement & HTMLSelectElement>(null)

  useEffect(() => {
    if (editing) ref.current?.focus()
  }, [editing])

  const missing = source === 'missing' || source === 'unresolved'
  const attention = Boolean(issue) || missing
  const src = SOURCE[source]

  function start() {
    setDraft(rawValue)
    setError(null)
    setEditing(true)
  }
  function save() {
    const v = draft.trim()
    const err = validate?.(v) ?? null
    if (err) {
      setError(err)
      return
    }
    setError(null)
    setEditing(false)
    if (v !== rawValue) onSave(v)
  }
  function cancel() {
    setError(null)
    setEditing(false)
  }

  return (
    <div className={cx('rounded-md border px-3 py-2', attention ? 'border-warning/35 bg-warning/5' : 'border-line bg-surface-2/50')}>
      <div className="flex items-center justify-between gap-2">
        <span className="label">{label}</span>
        <span className="inline-flex items-center gap-1.5 text-2xs text-fg-muted" title={src.label}>
          <span className={cx('h-1.5 w-1.5 rounded-full', src.dot)} aria-hidden />
          {compact ? <span className="sr-only">{src.label}</span> : src.label}
        </span>
      </div>

      {editing ? (
        <div className="mt-1.5">
          <div className="flex items-center gap-1.5">
            {input.kind === 'select' ? (
              <select ref={ref} className="input" value={draft} onChange={(e) => setDraft(e.target.value)} aria-label={label}>
                <option value="">—</option>
                {input.options.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                ref={ref}
                className={cx('input', input.kind !== 'text' && 'tabular font-mono')}
                value={draft}
                inputMode={input.kind === 'amount' ? 'decimal' : undefined}
                placeholder={input.kind === 'date' ? 'YYYY-MM-DD' : input.kind === 'amount' ? '0.00' : input.placeholder}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') save()
                  if (e.key === 'Escape') {
                    e.stopPropagation()
                    cancel()
                  }
                }}
                aria-label={label}
                aria-invalid={Boolean(error)}
              />
            )}
            <button type="button" onClick={save} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-accent text-accent-fg hover:bg-accent-hover" aria-label={`Save ${label}`}>
              <Check size={15} />
            </button>
            <button type="button" onClick={cancel} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-line text-fg-muted hover:bg-surface-3" aria-label="Cancel">
              <X size={15} />
            </button>
          </div>
          {error && <p className="mt-1 text-xs text-danger">{error}</p>}
        </div>
      ) : (
        <div className="group mt-0.5 flex min-h-[28px] items-center justify-between gap-2">
          <div className={cx('min-w-0 truncate text-sm', missing ? 'italic text-fg-subtle' : 'text-fg')}>{source === 'unresolved' ? 'Unresolved, needs your input' : missing ? 'Not found in document' : display}</div>
          <button
            type="button"
            onClick={start}
            disabled={disabled}
            className="flex h-6 shrink-0 items-center gap-1 rounded-md px-1.5 text-2xs text-fg-subtle hover:bg-surface-3 hover:text-fg disabled:opacity-50"
            aria-label={`Edit ${label}`}
          >
            <Pencil size={12} aria-hidden />
            {missing ? 'Add' : 'Edit'}
          </button>
        </div>
      )}
      {issue && !editing && (
        <p className="mt-1 flex items-start gap-1.5 text-xs text-warning">
          <AlertTriangle size={12} className="mt-0.5 shrink-0" aria-hidden />
          {issue}
        </p>
      )}
    </div>
  )
}
