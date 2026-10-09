import { useEffect, useRef, useState, type ReactNode } from 'react';
import { cx } from '../ui/cx';

/** Spreadsheet-style cell: click or Enter to edit, Enter to save, Escape to cancel. */
export function InlineEdit({
  display,
  raw,
  onSave,
  validate,
  options,
  align = 'left',
  mono,
  label,
  disabled,
}: {
  display: ReactNode;
  raw: string;
  onSave: (v: string) => void;
  validate?: (v: string) => string | null;
  options?: string[];
  align?: 'left' | 'right';
  mono?: boolean;
  label: string;
  disabled?: boolean;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(raw);
  const [error, setError] = useState<string | null>(null);
  const ref = useRef<HTMLInputElement & HTMLSelectElement>(null);

  useEffect(() => {
    if (editing) {
      ref.current?.focus();
      if (ref.current instanceof HTMLInputElement) ref.current.select();
    }
  }, [editing]);

  const commit = () => {
    const v = draft.trim();
    const err = validate?.(v) ?? null;
    if (err) {
      setError(err);
      return;
    }
    setEditing(false);
    setError(null);
    if (v !== raw) onSave(v);
  };
  const cancel = () => {
    setEditing(false);
    setError(null);
    setDraft(raw);
  };

  if (editing) {
    const common = {
      'aria-label': label,
      'aria-invalid': Boolean(error),
      title: error ?? undefined,
      className: cx('input h-7 px-1.5 text-xs', align === 'right' && 'text-right', mono && 'tabular font-mono', error && 'border-danger focus:border-danger'),
      onBlur: commit,
      onKeyDown: (e: React.KeyboardEvent) => {
        if (e.key === 'Enter') commit();
        if (e.key === 'Escape') cancel();
      },
    };
    return options ? (
      <select ref={ref} {...common} value={draft} onChange={(e) => setDraft(e.target.value)}>
        <option value="">—</option>
        {options.map((o) => (
          <option key={o}>{o}</option>
        ))}
      </select>
    ) : (
      <input ref={ref} {...common} value={draft} onChange={(e) => setDraft(e.target.value)} />
    );
  }

  return (
    <button
      type="button"
      disabled={disabled}
      aria-label={`Edit ${label}`}
      onClick={() => {
        setDraft(raw);
        setEditing(true);
      }}
      className={cx(
        'block h-7 w-full truncate rounded-sm border border-transparent px-1.5 text-xs transition-colors duration-[120ms]',
        align === 'right' ? 'text-right' : 'text-left',
        mono && 'tabular',
        !disabled && 'hover:border-line-strong hover:bg-surface-2',
      )}
    >
      {display}
    </button>
  );
}
