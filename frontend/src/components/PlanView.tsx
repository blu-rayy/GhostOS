import { useMemo } from 'react'
import type { BatchResult, PlanPreview, ProposedOperation, UndoResult } from '../types/api'
import { formatMoney } from '../lib/money'

function folderOf(path: string): string {
  const i = path.lastIndexOf('/')
  return i < 0 ? '' : path.slice(0, i)
}

function fileOf(path: string): string {
  return path.slice(path.lastIndexOf('/') + 1)
}

interface Props {
  root: string
  plan: PlanPreview | null
  loading: boolean
  batch: BatchResult | null
  undo: UndoResult | null
  busy: boolean
  actionError: string | null
  onBackToReview: () => void
  onApprove: () => void
  onUndo: () => void
}

export function PlanView({ root, plan, loading, batch, undo, busy, actionError, onBackToReview, onApprove, onUndo }: Props) {
  const groups = useMemo(() => {
    const m = new Map<string, ProposedOperation[]>()
    for (const op of plan?.operations ?? []) {
      const f = folderOf(op.destination_relative_path)
      m.set(f, [...(m.get(f) ?? []), op])
    }
    // Needs Review last so the tidy folders read first.
    return [...m].sort(([a], [b]) => (a === 'Needs Review' ? 1 : b === 'Needs Review' ? -1 : a.localeCompare(b)))
  }, [plan])

  if (loading || !plan) return <section className="panel"><p className="muted">Building plan…</p></section>

  const blocked = plan.blocking_review_count > 0
  const committed = batch !== null && undo === null

  return (
    <section className="panel">
      <header className="view-head">
        <div>
          <h1>Preview and approve</h1>
          <p className="muted">
            Nothing has moved yet. All paths are inside <code>{root}</code>.
          </p>
        </div>
      </header>

      {blocked && !batch && (
        <div className="banner banner-warn">
          <span>
            {plan.blocking_review_count} document{plan.blocking_review_count === 1 ? '' : 's'} still need review
            before you can approve.
          </span>
          <button className="btn" onClick={onBackToReview}>
            Go to review
          </button>
        </div>
      )}

      <div className="plan-grid">
        <div className="plan-col">
          <h2>
            Proposed moves <span className="count">{plan.operations.length}</span>
          </h2>
          <div className="tree">
            {groups.map(([folder, ops]) => (
              <div key={folder} className={`tree-folder ${folder === 'Needs Review' ? 'tree-folder-review' : ''}`}>
                <div className="tree-folder-name">📁 {folder || '(root)'}</div>
                <ul>
                  {ops.map((op) => (
                    <li key={op.file_id} title={op.reason}>
                      <span className="tree-file">{fileOf(op.destination_relative_path)}</span>
                      {op.collision_suffixed && <span className="chip chip-warn">renamed to avoid overwrite</span>}
                      <span className="tree-from muted">from {op.original_relative_path}</span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="plan-col">
          <h2>
            Draft expense report <span className="count">{plan.report_rows.length}</span>
          </h2>
          <table className="report">
            <thead>
              <tr>
                <th>Date</th>
                <th>Merchant</th>
                <th>Type</th>
                <th className="num">Amount</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {plan.report_rows.map((r) => (
                <tr key={r.file_id} className={r.status === 'needs_review' ? 'row-review' : ''} title={r.source_filename}>
                  <td>{r.date ?? '—'}</td>
                  <td>{r.merchant ?? '—'}</td>
                  <td>{r.category}</td>
                  <td className="num">{formatMoney(r.amount, r.currency)}</td>
                  <td>
                    <span className={`chip ${r.status === 'accepted' ? 'chip-ok' : 'chip-warn'}`}>
                      {r.status === 'accepted' ? 'Accepted' : 'Needs review'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              {plan.totals.map((t) => (
                <tr key={t.currency}>
                  <td colSpan={3}>
                    Total {t.currency} ({t.row_count} accepted rows)
                  </td>
                  <td className="num">{formatMoney(t.amount, t.currency)}</td>
                  <td />
                </tr>
              ))}
            </tfoot>
          </table>
          <p className="muted small">
            Totals include accepted rows only. Rows that need review and exact duplicates appear in the CSV with their
            status but are not added to the total.
          </p>
        </div>
      </div>

      <div className="approve-bar">
        {actionError && <p className="field-error">{actionError}</p>}
        {!batch && (
          <>
            <p className="muted">
              Approving moves {plan.operations.length} files and writes the report CSV. You can undo the whole batch
              afterwards.
            </p>
            <button className="btn btn-primary btn-lg" disabled={blocked || busy} onClick={onApprove}>
              {busy ? 'Applying…' : `Approve and move ${plan.operations.length} files`}
            </button>
          </>
        )}
        {committed && (
          <>
            <p>
              ✓ Moved {batch.moved} files
              {batch.failed.length > 0 && `, ${batch.failed.length} failed`}. Report written to{' '}
              <code>{batch.report_relative_path}</code>.
            </p>
            <button className="btn btn-lg" disabled={busy} onClick={onUndo}>
              {busy ? 'Restoring…' : 'Undo batch'}
            </button>
          </>
        )}
        {undo && (
          <p>
            ↺ Restored {undo.restored} files to their original locations
            {undo.conflicts.length > 0 && `; ${undo.conflicts.length} could not be restored`}.
          </p>
        )}
      </div>
    </section>
  )
}
