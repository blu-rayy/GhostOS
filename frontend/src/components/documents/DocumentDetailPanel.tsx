import { ArrowRight, Ban, Copy, FileWarning, FolderTree, Lightbulb, Quote, ShieldAlert, UserCheck, X } from 'lucide-react'
import { formatBytes, formatDate, isValidIsoDate, money, normalizeAmountInput } from '../../lib/format'
import { reviewBlockers } from '../../lib/review'
import { basename, flagsFor, type FileRow } from '../../lib/viewModel'
import { useApp } from '../../state/AppState'
import type { Category, DocumentCorrection } from '../../types/api'
import { Badge, CategoryBadge, ReviewStatusBadge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Banner, PathText } from '../ui/Layout'
import { EditableField, type FieldSource } from './EditableField'
import { EvidenceBlock } from './EvidenceBlock'

const CATEGORY_OPTIONS = [
  { value: 'invoice', label: 'Invoice' },
  { value: 'receipt', label: 'Receipt' },
  { value: 'other', label: 'Other' },
  { value: 'uncertain', label: 'Uncertain' },
]
const CURRENCY_OPTIONS = ['PHP', 'USD', 'EUR'].map((c) => ({ value: c, label: c }))

export function DocumentDetailPanel({ row, onClose }: { row: FileRow; onClose: () => void }) {
  const { correct, state, selectDoc } = useApp()
  const doc = row.doc
  const c = doc?.classification ?? null
  const locked = state.batch !== null && state.phase !== 'undone'
  const busy = state.busy === 'correct'
  const original = doc?.duplicate_of ? state.scan?.documents.find((d) => d.file_id === doc.duplicate_of) : null
  const showMoney = !c || c.category !== 'other'

  const source = (v: unknown, flagged = false): FieldSource =>
    doc?.user_corrected ? 'reviewed' : v === null || v === undefined ? (flagged ? 'unresolved' : 'missing') : 'extracted'
  const issue = (target: Parameters<typeof flagsFor>[1]) => (doc ? flagsFor(doc, target).map((f) => f.message).join(' ') || undefined : undefined)
  const save = (correction: Omit<DocumentCorrection, 'accept'>, label: string) => doc && correct(doc.file_id, { ...correction, accept: false }, label)

  const blockers = doc ? reviewBlockers(doc) : []
  const documentFlags = doc ? flagsFor(doc, 'document') : []

  return (
    <aside className="flex w-[400px] shrink-0 flex-col border-l border-line bg-surface-1 animate-slide-in" aria-label="Document details">
      <div className="flex items-start gap-2 border-b border-line px-4 py-3">
        <div className="min-w-0 flex-1">
          <h2 className="truncate text-base font-semibold" title={row.filename}>
            {row.filename}
          </h2>
          <div className="mt-0.5 truncate text-2xs text-fg-subtle">
            <PathText>{row.relPath}</PathText>
            {doc && ` · ${doc.file_type.toUpperCase()} · ${formatBytes(doc.size_bytes)}`}
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {row.status !== 'skipped' && <CategoryBadge category={row.category} />}
            <ReviewStatusBadge status={row.status} />
            {doc?.duplicate_of && (
              <Badge tone="info" icon={Copy}>
                Duplicate
              </Badge>
            )}
          </div>
        </div>
        <Button size="sm" variant="ghost" icon={X} onClick={onClose} aria-label="Close details" />
      </div>

      <div className="scroll-area min-h-0 flex-1 space-y-4 overflow-x-hidden px-4 py-4">
        {row.skip && (
          <Banner tone="neutral" icon={Ban} title="Skipped">
            {row.skip.detail}
          </Banner>
        )}
        {doc?.status === 'failed' && !doc.user_corrected && (
          <Banner tone="danger" icon={FileWarning} title="Extraction failed">
            {doc.review_flags[0]?.message ?? 'No usable classification.'} You can enter the values from the original document. Nothing is guessed.
          </Banner>
        )}
        {documentFlags
          .filter((f) => f.code === 'possible_injection')
          .map((f) => (
            <Banner key={f.code} tone="warning" icon={ShieldAlert} title="Instructions found inside the document">
              {f.message}
            </Banner>
          ))}
        {original && (
          <Banner tone="info" icon={Copy} title="Same content as another file">
            Content hash matches{' '}
            <button type="button" className="text-accent-hover hover:underline" onClick={() => selectDoc(original.file_id)}>
              {basename(original.relative_path)}
            </button>
            . Informational only: GhostOS never deletes duplicates, and duplicates are not counted in report totals.
          </Banner>
        )}

        {c && (
          <section>
            <div className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-fg-muted">
              <Lightbulb size={13} aria-hidden /> Why this classification
            </div>
            <p className="text-sm text-fg-muted">{c.explanation}</p>
          </section>
        )}

        {doc && (
          <section className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold text-fg-muted">Extracted values</h3>
              {locked && <span className="text-2xs text-fg-subtle">Locked after approval</span>}
            </div>
            <EditableField
              label="Category"
              display={<CategoryBadge category={c?.category ?? null} />}
              rawValue={c?.category ?? ''}
              source={source(c?.category)}
              issue={issue('category')}
              input={{ kind: 'select', options: CATEGORY_OPTIONS }}
              validate={(v) => (v ? null : 'Choose a category.')}
              onSave={(v) => save({ category: v as Category }, 'category')}
              disabled={locked || busy}
            />
            {showMoney && (
              <>
                <EditableField
                  label="Merchant"
                  display={c?.merchant}
                  rawValue={c?.merchant ?? ''}
                  source={source(c?.merchant)}
                  issue={issue('merchant')}
                  input={{ kind: 'text', placeholder: 'Merchant name' }}
                  validate={(v) => (v.length < 2 ? 'Enter a merchant name.' : null)}
                  onSave={(v) => save({ merchant: v }, 'merchant')}
                  disabled={locked || busy}
                />
                <EditableField
                  label="Date"
                  display={<span className="tabular">{formatDate(c?.date ?? null)}</span>}
                  rawValue={c?.date ?? ''}
                  source={source(c?.date)}
                  issue={issue('date')}
                  input={{ kind: 'date' }}
                  validate={(v) => (isValidIsoDate(v) ? null : 'Use YYYY-MM-DD, e.g. 2026-09-30.')}
                  onSave={(v) => save({ date: v }, 'date')}
                  disabled={locked || busy}
                />
                <div className="grid grid-cols-[minmax(0,1fr)_120px] gap-2">
                  <EditableField
                    label="Amount"
                    display={<span className="tabular">{money(c?.amount ?? null, c?.currency ?? null)}</span>}
                    rawValue={c?.amount ?? ''}
                    source={source(c?.amount, Boolean(c?.amount_text) || Boolean(issue('amount')))}
                    issue={[issue('amount'), c?.amount_text && c.amount === null ? `Document text: “${c.amount_text}”` : undefined].filter(Boolean).join(' ') || undefined}
                    input={{ kind: 'amount' }}
                    validate={(v) => (normalizeAmountInput(v) ? null : 'Enter an amount like 1520.00')}
                    onSave={(v) => save({ amount: normalizeAmountInput(v) }, 'amount')}
                    disabled={locked || busy}
                  />
                  <EditableField
                    label="Currency"
                    display={c?.currency}
                    rawValue={c?.currency ?? ''}
                    source={source(c?.currency)}
                    input={{ kind: 'select', options: CURRENCY_OPTIONS }}
                    validate={(v) => (v ? null : 'Choose a currency.')}
                    onSave={(v) => save({ currency: v }, 'currency')}
                    compact
                    disabled={locked || busy}
                  />
                </div>
              </>
            )}
          </section>
        )}

        {doc && (
          <section>
            <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-fg-muted">
              <Quote size={13} aria-hidden /> Evidence from the document
            </h3>
            <EvidenceBlock doc={doc} />
            {issue('evidence') && <p className="mt-1.5 text-xs text-warning">{issue('evidence')}</p>}
          </section>
        )}

        <section>
          <h3 className="mb-1.5 flex items-center gap-1.5 text-xs font-semibold text-fg-muted">
            <FolderTree size={13} aria-hidden /> Proposed destination
          </h3>
          <div className="rounded-md border border-line bg-surface-2/50 px-3 py-2 text-xs">
            {row.destination ? (
              <div className="flex items-center gap-1.5">
                <ArrowRight size={12} className="shrink-0 text-fg-subtle" aria-hidden />
                <PathText className="truncate text-fg">{row.destination}</PathText>
              </div>
            ) : (
              <span className="text-fg-muted">Stays where it is</span>
            )}
          </div>
        </section>
      </div>

      {doc && (
        <div className="border-t border-line px-4 py-3">
          {doc.user_corrected ? (
            <span className="flex items-center gap-1.5 text-sm text-success">
              <UserCheck size={15} aria-hidden /> Reviewed by you
            </span>
          ) : (
            <>
              <Button
                variant="primary"
                icon={UserCheck}
                className="w-full"
                disabled={blockers.length > 0 || locked || busy}
                onClick={() => correct(doc.file_id, { accept: true }, 'review')}
              >
                Mark as reviewed
              </Button>
              {blockers.length > 0 && <p className="mt-1.5 text-center text-2xs text-warning">{blockers.join(' ')}</p>}
              {state.actionError && <p className="mt-1.5 text-center text-2xs text-danger">{state.actionError}</p>}
            </>
          )}
        </div>
      )}
    </aside>
  )
}
