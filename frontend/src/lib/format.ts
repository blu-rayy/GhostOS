import { formatAmount, normalizeAmountInput } from './money'

const SYMBOL: Record<string, string> = { USD: '$', PHP: '₱', EUR: '€' }

/** Display a decimal-string amount (never a float). Unknown currencies show their ISO code. */
export function money(amount: string | null, currency: string | null): string {
  if (amount === null) return '—'
  const n = formatAmount(amount)
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
