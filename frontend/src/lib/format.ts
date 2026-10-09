import { formatAmount, normalizeAmountInput } from './money'

const SYMBOL: Record<string, string> = { USD: '$', PHP: '₱', EUR: '€', GBP: '£', SGD: 'S$', JPY: '¥' }
/** Currencies with no minor unit: shown without ".00". Amounts stay 2-decimal strings internally. */
const NO_DECIMALS = new Set(['JPY'])

/** Display a decimal-string amount (never a float). Unknown currencies show their ISO code. */
export function money(amount: string | null, currency: string | null): string {
  if (amount === null) return '—'
  const n = currency && NO_DECIMALS.has(currency) ? formatAmount(amount).replace(/\.00$/, '') : formatAmount(amount)
  if (!currency) return n
  return SYMBOL[currency] ? `${SYMBOL[currency]}${n}` : `${currency} ${n}`
}

export { normalizeAmountInput }

export function formatDate(iso: string | null): string {
  if (!iso) return '—'
  const d = new Date(`${iso}T00:00:00`)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: '2-digit' })
}

export function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  return `${d.toLocaleDateString('en-US', { month: 'short', day: '2-digit' })}, ${formatTime(iso)}`
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

export function isValidIsoDate(s: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return false
  const [y, m, day] = s.split('-').map(Number)
  const d = new Date(Date.UTC(y, m - 1, day))
  return d.getUTCFullYear() === y && d.getUTCMonth() === m - 1 && d.getUTCDate() === day
}

export function errorText(e: unknown): string {
  return e instanceof Error ? e.message : String(e)
}

/** Plain words for the Check panel's correction errors; unknown errors keep their backend text. */
export function correctionErrorText(raw: string): string {
  if (raw.includes('Cannot accept transaction while source validation findings remain unresolved')) {
    return "Pip can't back up this total with the text in the file, so it can't be counted. Leave it for review instead: it goes to Uncategorized/ and isn't counted."
  }
  if (raw.includes('amount correction is not supported by validated source evidence')) {
    return "That amount isn't the total written in the file, so it can't be counted. Check the number, or leave it for review."
  }
  return `Couldn't save that (${raw}).`
}
