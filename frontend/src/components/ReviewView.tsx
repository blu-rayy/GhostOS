import { useMemo, useState } from 'react'
import type { DocumentCorrection, DocumentRecord, ScanResult, SkipReason } from '../types/api'
import { CATEGORY_LABEL } from '../lib/labels'
import { DocumentCard } from './DocumentCard'

type Filter = 'all' | 'attention' | 'invoice' | 'receipt' | 'other'

const SKIP_LABEL: Record<SkipReason, string> = {
  unsupported_type: 'Unsupported type',
  too_large: 'Too large',
  unreadable: 'Unreadable',
  symlink: 'Symbolic link',
  no_extractable_text: 'No text layer',
  file_limit_reached: 'Over 100-file limit',
}

const needsAttention = (d: DocumentRecord) => d.status !== 'ok' && !d.user_corrected

interface Props {
  scan: ScanResult
  onCorrect: (fileId: string, correction: DocumentCorrection) => Promise<void>
  onContinue: () => void
}

export function ReviewView({ scan, onCorrect, onContinue }: Props) {
  const docs = scan.documents
  const [filter, setFilter] = useState<Filter>(() => (docs.some(needsAttention) ? 'attention' : 'all'))

  const counts = useMemo(
    () => ({
      all: docs.length,
      attention: docs.filter(needsAttention).length,
      invoice: docs.filter((d) => d.classification?.category === 'invoice').length,
      receipt: docs.filter((d) => d.classification?.category === 'receipt').length,
      other: docs.filter((d) => d.classification?.category === 'other').length,
    }),
    [docs],
  )

  const pathById = useMemo(() => new Map(docs.map((d) => [d.file_id, d.relative_path])), [docs])

  const visible = docs.filter((d) => {
    if (filter === 'all') return true
    if (filter === 'attention') return needsAttention(d)
    return d.classification?.category === filter
  })

  const filters: { id: Filter; label: string }[] = [
    { id: 'attention', label: 'Needs review' },
    { id: 'all', label: 'All' },
    { id: 'invoice', label: CATEGORY_LABEL.invoice + 's' },
    { id: 'receipt', label: CATEGORY_LABEL.receipt + 's' },
    { id: 'other', label: CATEGORY_LABEL.other },
  ]

  return (
    <section className="panel">
      <header className="view-head">
        <div>
          <h1>Review documents</h1>
          <p className="muted">
            <code>{scan.root}</code> · {docs.length} read · {scan.skipped.length} skipped · scanned{' '}
            {new Date(scan.scanned_at).toLocaleString()}
          </p>
        </div>
        <button className="btn btn-primary" onClick={onContinue}>
          Preview plan →
        </button>
      </header>

      <div className="summary-tiles">
        <div className="tile">
          <span className="tile-num">{counts.invoice}</span>
          <span className="tile-label">Invoices</span>
        </div>
        <div className="tile">
          <span className="tile-num">{counts.receipt}</span>
          <span className="tile-label">Receipts</span>
        </div>
        <div className="tile">
          <span className="tile-num">{counts.other}</span>
          <span className="tile-label">Other</span>
        </div>
        <div className={`tile ${counts.attention ? 'tile-warn' : ''}`}>
          <span className="tile-num">{counts.attention}</span>
          <span className="tile-label">Need review</span>
        </div>
      </div>

      <div className="filters" role="tablist" aria-label="Filter documents">
        {filters.map((f) => (
          <button
            key={f.id}
            role="tab"
            aria-selected={filter === f.id}
            className={`chip chip-filter ${filter === f.id ? 'chip-active' : ''}`}
            onClick={() => setFilter(f.id)}
          >
            {f.label} <span className="count">{counts[f.id]}</span>
          </button>
        ))}
      </div>

      {visible.length === 0 ? (
        <p className="empty">
          {filter === 'attention' ? 'Nothing left to review. Continue to the plan preview.' : 'No documents here.'}
        </p>
      ) : (
        <div className="card-grid">
          {visible.map((d) => (
            <DocumentCard
              key={d.file_id}
              doc={d}
              duplicateOfPath={d.duplicate_of ? (pathById.get(d.duplicate_of) ?? d.duplicate_of) : null}
              onCorrect={onCorrect}
            />
          ))}
        </div>
      )}

      {scan.skipped.length > 0 && (
        <details className="skipped">
          <summary>
            {scan.skipped.length} files skipped. They will not be moved.
          </summary>
          <table>
            <tbody>
              {scan.skipped.map((s) => (
                <tr key={s.relative_path}>
                  <td>
                    <code>{s.relative_path}</code>
                  </td>
                  <td>
                    <span className="chip">{SKIP_LABEL[s.reason]}</span>
                  </td>
                  <td className="muted">{s.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </section>
  )
}
