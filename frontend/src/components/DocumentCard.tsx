import { useState } from 'react'
import type { Category, DocumentCorrection, DocumentRecord } from '../types/api'
import { CATEGORY_LABEL } from '../lib/labels'
import { formatMoney, normalizeAmountInput } from '../lib/money'

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

/** Show the excerpt with the evidence quote highlighted where it actually occurs. */
function Excerpt({ text, quote }: { text: string; quote: string | null }) {
  const idx = quote ? text.indexOf(quote) : -1
  if (!quote || idx < 0) return <pre className="excerpt">{text}</pre>
  return (
    <pre className="excerpt">
      {text.slice(0, idx)}
      <mark>{quote}</mark>
      {text.slice(idx + quote.length)}
    </pre>
  )
}

interface Props {
  doc: DocumentRecord
  duplicateOfPath: string | null
  onCorrect: (fileId: string, correction: DocumentCorrection) => Promise<void>
}

export function DocumentCard({ doc, duplicateOfPath, onCorrect }: Props) {
  const c = doc.classification
  const [showExcerpt, setShowExcerpt] = useState(doc.status !== 'ok')
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [draft, setDraft] = useState({
    category: c?.category ?? 'uncertain',
    merchant: c?.merchant ?? '',
    date: c?.date ?? '',
    amount: c?.amount ?? '',
    currency: c?.currency ?? 'PHP',
  })

  const pendingReview = doc.status === 'needs_review' && !doc.user_corrected
  const amountValue = draft.amount.trim() === '' ? null : normalizeAmountInput(draft.amount)
  const amountInvalid = draft.amount.trim() !== '' && amountValue === null
  const dateInvalid = draft.date !== '' && !/^\d{4}-\d{2}-\d{2}$/.test(draft.date)

  const save = async () => {
    setSaving(true)
    try {
      await onCorrect(doc.file_id, {
        category: draft.category,
        merchant: draft.merchant.trim() || null,
        date: draft.date || null,
        amount: amountValue,
        currency: draft.currency.trim().toUpperCase() || null,
        accept: true,
      })
      setEditing(false)
    } finally {
      setSaving(false)
    }
  }

  const markReviewed = async () => {
    setSaving(true)
    try {
      await onCorrect(doc.file_id, { accept: true })
    } finally {
      setSaving(false)
    }
  }

  const statusChip = doc.user_corrected
    ? { cls: 'chip-ok', text: 'Reviewed' }
    : doc.status === 'failed'
      ? { cls: 'chip-bad', text: 'Failed' }
      : doc.status === 'needs_review'
        ? { cls: 'chip-warn', text: 'Needs review' }
        : { cls: 'chip-ok', text: 'OK' }

  return (
    <article className={`doc-card ${pendingReview ? 'doc-card-attention' : ''}`}>
      <header className="doc-head">
        <div className="doc-title">
          <span className={`cat cat-${c?.category ?? 'none'}`}>{c ? CATEGORY_LABEL[c.category] : 'Unclassified'}</span>
          <h3 title={doc.relative_path}>{doc.relative_path}</h3>
        </div>
        <span className={`chip ${statusChip.cls}`}>{statusChip.text}</span>
      </header>
      <p className="doc-meta muted">
        {doc.file_type.toUpperCase()} · {formatBytes(doc.size_bytes)} · sha256 {doc.sha256.slice(0, 10)}…
      </p>

      {doc.review_flags.length > 0 && (
        <ul className="flags">
          {doc.review_flags.map((f) => (
            <li key={f.code} className={`flag flag-${f.code}`}>
              {f.message}
            </li>
          ))}
        </ul>
      )}

      {duplicateOfPath && (
        <p className="note">
          Exact duplicate of <code>{duplicateOfPath}</code>. Both files are kept, and this one is left out of the
          report total.
        </p>
      )}

      {c && !editing && (
        <dl className="fields">
          <div>
            <dt>Merchant</dt>
            <dd>{c.merchant ?? <span className="missing">not found</span>}</dd>
          </div>
          <div>
            <dt>Date</dt>
            <dd>{c.date ?? <span className="missing">not found</span>}</dd>
          </div>
          <div>
            <dt>Amount</dt>
            <dd>
              {c.amount !== null ? (
                formatMoney(c.amount, c.currency)
              ) : c.amount_text ? (
                <span className="missing">unclear: “{c.amount_text}”</span>
              ) : (
                <span className="missing">none</span>
              )}
            </dd>
          </div>
        </dl>
      )}

      {editing && (
        <div className="edit-form">
          <label>
            Category
            <select value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value as Category })}>
              {(Object.keys(CATEGORY_LABEL) as Category[]).map((k) => (
                <option key={k} value={k}>
                  {CATEGORY_LABEL[k]}
                </option>
              ))}
            </select>
          </label>
          <label>
            Merchant
            <input value={draft.merchant} onChange={(e) => setDraft({ ...draft, merchant: e.target.value })} />
          </label>
          <label>
            Date
            <input
              type="date"
              value={draft.date}
              onChange={(e) => setDraft({ ...draft, date: e.target.value })}
              aria-invalid={dateInvalid}
            />
          </label>
          <label>
            Amount
            <input
              value={draft.amount}
              inputMode="decimal"
              placeholder="0.00"
              onChange={(e) => setDraft({ ...draft, amount: e.target.value })}
              aria-invalid={amountInvalid}
            />
          </label>
          <label>
            Currency
            <input
              value={draft.currency}
              maxLength={3}
              onChange={(e) => setDraft({ ...draft, currency: e.target.value })}
            />
          </label>
          {amountInvalid && <p className="field-error">Amount must be a number such as 1520.00.</p>}
          <div className="edit-actions">
            <button className="btn" onClick={() => setEditing(false)} disabled={saving}>
              Cancel
            </button>
            <button className="btn btn-primary" onClick={save} disabled={saving || amountInvalid || dateInvalid}>
              {saving ? 'Saving…' : 'Save and mark reviewed'}
            </button>
          </div>
        </div>
      )}

      {c && (
        <div className="evidence">
          <div className="evidence-head">
            <span className="evidence-label">Evidence</span>
            {c.evidence_verified ? (
              <span className="chip chip-ok">Found in document</span>
            ) : (
              <span className="chip chip-bad">Not found in document</span>
            )}
          </div>
          {c.evidence_quote && <blockquote>“{c.evidence_quote}”</blockquote>}
          <p className="explanation">{c.explanation}</p>
        </div>
      )}

      <div className="doc-actions">
        <button className="btn btn-ghost" onClick={() => setShowExcerpt((s) => !s)}>
          {showExcerpt ? 'Hide text' : 'Show extracted text'}
        </button>
        {c && !editing && (
          <button className="btn btn-ghost" onClick={() => setEditing(true)}>
            Edit fields
          </button>
        )}
        {pendingReview && !editing && (
          <button className="btn" onClick={markReviewed} disabled={saving}>
            Mark reviewed
          </button>
        )}
      </div>

      {showExcerpt && <Excerpt text={doc.excerpt} quote={c?.evidence_verified ? c.evidence_quote : null} />}
    </article>
  )
}
