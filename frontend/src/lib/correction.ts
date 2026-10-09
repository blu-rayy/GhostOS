import type { DocumentCorrection } from '../types/api'
import { normalizeAmountInput } from './money'

/** The shop/date/amount fields as the Check panel shows them (strings; '' for empty). */
export interface TransactionFields {
  merchant: string
  date: string
  amount: string
}

export type TransactionCorrection =
  | { ok: true; correction: Pick<DocumentCorrection, 'merchant' | 'date' | 'amount'> }
  | { ok: false; error: string }

/**
 * Builds the shop/date/amount part of a correction from what the person actually changed.
 *
 * Request semantics (matching PATCH /api/documents/{id}, backend e5a7a06):
 * - A field the person did not change is **omitted**, so an untouched empty box never becomes an
 *   explicit `null` (the backend answers 422 to `amount: null`).
 * - `amount` changed to a value: sent normalised ("₱1,520" -> "1520.00"); the backend still
 *   checks it against the document's own text.
 * - `amount` cleared when it had a value: **not supported** by the backend (amount must be a
 *   parseable value), so nothing is sent and the panel says why.
 * - `merchant` / `date` cleared: sent as an explicit `null`, which the backend accepts.
 * - `date` must look like YYYY-MM-DD before it is sent.
 */
export function buildTransactionCorrection(initial: TransactionFields, edited: TransactionFields): TransactionCorrection {
  const correction: Pick<DocumentCorrection, 'merchant' | 'date' | 'amount'> = {}

  const merchant = edited.merchant.trim()
  if (merchant !== initial.merchant.trim()) correction.merchant = merchant || null

  const date = edited.date.trim()
  if (date !== initial.date.trim()) {
    if (date && !/^\d{4}-\d{2}-\d{2}$/.test(date)) return { ok: false, error: 'Write the date as YYYY-MM-DD, for example 2026-09-21.' }
    correction.date = date || null
  }

  const amount = edited.amount.trim()
  // Same value written differently ("1,250.00" for "1250.00") is not a change.
  const sameValue = amount !== '' && normalizeAmountInput(amount) !== null && normalizeAmountInput(amount) === normalizeAmountInput(initial.amount)
  if (amount !== initial.amount.trim() && !sameValue) {
    if (!amount) {
      if (initial.amount.trim()) return { ok: false, error: "The amount can't be cleared. Put back the amount you paid, or leave the file for review." }
    } else {
      const normalised = normalizeAmountInput(amount)
      if (normalised === null) return { ok: false, error: 'Write the amount as a number, for example 1,520.00.' }
      correction.amount = normalised
    }
  }

  return { ok: true, correction }
}
