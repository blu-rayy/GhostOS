import { Search, X, Folder } from 'lucide-react'
import type { ReactNode } from 'react'
import type { DocumentRecord } from '../../types/api'
import type { FileRow } from '../../lib/viewModel'
import { basename, documentKindLabel, reviewChipState, reviewReasonText } from '../../lib/viewModel'
import { formatBytes, money } from '../../lib/format'
import { Chip } from './Chip'
import { PaperButton } from './Button'

export type CheckFilter = 'all' | 'needs' | 'failed' | 'ready' | 'unsupported'

export function SegmentedFilter({ value, counts, onChange }: { value: CheckFilter; counts: Record<CheckFilter, number>; onChange: (value: CheckFilter) => void }) {
  const options: [CheckFilter, string][] = [['all', 'all'], ['needs', 'needs you'], ['failed', "couldn't read"], ['ready', 'ready'], ['unsupported', 'not supported']]
  return <div className="flex flex-wrap" role="tablist" aria-label="Filter files">
    {options.map(([id, label]) => <button key={id} type="button" role="tab" aria-selected={value === id} onClick={() => onChange(id)} className={`border-[2.5px] border-ink px-3 py-1.5 text-[17px] first:rounded-l-[12px] last:rounded-r-[12px] ${value === id ? 'bg-ink text-paper' : 'bg-paper'}`}>
      {label} <span className="font-mono text-[13px]">{counts[id]}</span>
    </button>)}
  </div>
}

export function SearchPill({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return <label className="flex h-11 min-w-[230px] items-center gap-2 rounded-full border-[2.5px] border-ink bg-paper px-3">
    <Search size={19} aria-hidden />
    <span className="sr-only">Search files or shops</span>
    <input value={value} onChange={(event) => onChange(event.target.value)} className="min-w-0 flex-1 bg-transparent outline-none" placeholder="search files or shops…" />
  </label>
}

export function ReviewRow({ row, selected, onClick, onKeyDown, buttonRef }: { row: FileRow; selected: boolean; onClick: () => void; onKeyDown: (event: React.KeyboardEvent<HTMLButtonElement>) => void; buttonRef?: (element: HTMLButtonElement | null) => void }) {
  const doc = row.doc
  const chip = reviewChipState(doc)
  const reason = reviewReasonText(row)
  const transactional = row.fieldProfile === 'transaction'
  const amount = !transactional ? '' : doc?.review_flags.some((flag) => flag.code === 'amount_conflict') ? '₱?,???.??' : money(row.amount, row.currency)
  // Non-transaction papers say what they are instead of naming a shop.
  const what = transactional || !doc ? `${row.category ?? 'other'} · ${row.merchant ?? 'unknown shop'}` : documentKindLabel(doc)
  return <button ref={buttonRef} type="button" role="option" aria-selected={selected} onClick={onClick} onKeyDown={onKeyDown} style={{ boxShadow: selected ? '4px 4px 0 #1a1a1a' : `inset 8px 0 0 ${chip.stripe}` }} className={`group relative flex w-full items-center gap-4 border-[2.5px] border-transparent bg-paper px-4 py-3 text-left ${selected ? 'border-ink bg-row-selected' : ''}`}>
    <span className="min-w-0 flex-1 pl-2">
      <span className="block truncate text-[19px] leading-6">{row.relPath}</span>
      <span className="block truncate text-[16px] text-graphite">{what} · {reason}</span>
    </span>
    <span className="font-mono text-[13px]">{amount}</span>
    <Chip tone={chip.tone === 'muted' ? 'muted' : chip.tone} size="sm">{chip.text}</Chip>
  </button>
}

export function EvidenceExcerpt({ text, quote, tone = 'yellow' }: { text: string; quote?: string | null; tone?: 'yellow' | 'pink' }) {
  const index = quote ? text.indexOf(quote) : -1
  if (index < 0) return <pre className="m-0 whitespace-pre-wrap border-l-[7px] border-ink pl-3 font-mono text-[13px] leading-5">{text}</pre>
  const safeQuote = quote ?? ''
  return <pre className="m-0 whitespace-pre-wrap border-l-[7px] border-ink pl-3 font-mono text-[13px] leading-5">{text.slice(0, index)}<mark className={tone === 'pink' ? 'bg-hl-oops' : 'bg-hl-check'}>{text.slice(index, index + safeQuote.length)}</mark>{text.slice(index + safeQuote.length)}</pre>
}

export function ChoiceButtons({ candidates, value, onChange }: { candidates?: { amount: string; label: string }[]; value: string; onChange: (value: string) => void }) {
  if (!candidates?.length) return null
  return <div className="grid gap-2">{candidates.map((candidate) => <button key={candidate.amount} type="button" aria-pressed={value === candidate.amount} onClick={() => onChange(candidate.amount)} className={`rounded-[12px] border-[2.5px] border-ink p-3 text-left ${value === candidate.amount ? 'bg-hl-check' : 'bg-paper'}`}><span className="block font-mono">{candidate.amount}</span><span>{candidate.label}</span></button>)}</div>
}

export function RadioCard({ checked, onChange, children }: { checked: boolean; onChange: () => void; children: ReactNode }) {
  return <button type="button" role="radio" aria-checked={checked} onClick={onChange} className={`flex w-full items-start gap-3 rounded-[12px] border-[2.5px] border-ink p-3 text-left ${checked ? 'bg-hl-check' : 'bg-paper'}`}><span aria-hidden>{checked ? '◉' : '○'}</span><span>{children}</span></button>
}

export function ProgressDots({ checked, total }: { checked: number; total: number }) {
  return <div className="flex gap-1.5" aria-label={`${checked} of ${total} decided`}>{Array.from({ length: Math.max(5, Math.min(5, total)) }, (_, index) => <span key={index} className={`h-3 w-3 rounded-full border-2 border-ink ${index < Math.min(checked, 5) ? 'bg-ink' : 'bg-paper'}`} />)}</div>
}

export function FolderRow({ path, note, count }: { path: string; note: string; count: number }) {
  return <div className="flex items-center gap-3 border-b-[1.5px] border-dashed border-graphite py-2"><Folder size={22} aria-hidden /><span className="min-w-0 flex-1"><span className="block truncate font-mono text-[13px]">{path}</span><span className="block text-[16px] text-graphite">{note}</span></span><span className="font-mono text-[13px]">{count}</span></div>
}

export function CheckDetailHeader({ doc, status, onClose }: { doc: DocumentRecord; status: string; onClose: () => void }) {
  return <div className="flex items-start gap-3 border-b-[2.5px] border-ink px-5 py-4"><div className="min-w-0 flex-1"><h2 className="truncate font-display text-[26px] font-normal">{basename(doc.relative_path)}</h2><p className="m-0 truncate text-[16px] text-graphite">{doc.file_type.toUpperCase()} · {formatBytes(doc.size_bytes)}</p></div><Chip tone={status === 'failed' ? 'oops' : doc.user_corrected ? 'done' : 'check'} size="sm">{status}</Chip><button type="button" onClick={onClose} aria-label="Close file details" className="flex h-10 w-10 items-center justify-center rounded-[10px] border-[2.5px] border-ink bg-paper"><X size={20} aria-hidden /></button></div>
}

export function PanelAction({ children, onClick, disabled = false, secondary = false }: { children: ReactNode; onClick: () => void; disabled?: boolean; secondary?: boolean }) {
  return <PaperButton variant={secondary ? 'secondary' : 'primary'} className="w-full" onClick={onClick} disabled={disabled}>{children}</PaperButton>
}
