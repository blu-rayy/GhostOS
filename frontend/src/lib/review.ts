import type { DocumentRecord } from '../types/api'

/** Reasons a record cannot be accepted yet (empty = allowed). Mirrors the report's "accepted" rule. */
export function reviewBlockers(d: DocumentRecord): string[] {
  const out: string[] = []
  const c = d.classification
  if (!c) return ['Enter the values from the original document first.']
  if (c.category === 'uncertain') out.push('Choose Invoice, Receipt or Other.')
  if (c.category === 'invoice' || c.category === 'receipt') {
    if (!c.merchant) out.push('Add a merchant.')
    if (!c.date) out.push('Add a date.')
    if (c.amount === null) out.push('Add an amount.')
    if (!c.currency) out.push('Add a currency.')
  }
  return out
}
