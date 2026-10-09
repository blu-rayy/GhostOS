// Money is carried as decimal strings ("1250.00") end to end, matching the
// backend's Decimal. We sum in integer cents via BigInt so the UI never
// introduces float rounding into report totals.

const DECIMAL_RE = /^(-?)(\d+)(?:\.(\d{1,2}))?$/

export function toCents(amount: string): bigint | null {
  const m = DECIMAL_RE.exec(amount.trim())
  if (!m) return null
  const [, sign, whole, frac = ''] = m
  const cents = BigInt(whole) * 100n + BigInt(frac.padEnd(2, '0'))
  return sign ? -cents : cents
}

export function fromCents(cents: bigint): string {
  const neg = cents < 0n
  const abs = neg ? -cents : cents
  const whole = abs / 100n
  const frac = (abs % 100n).toString().padStart(2, '0')
  return `${neg ? '-' : ''}${whole}.${frac}`
}

export function sumAmounts(amounts: string[]): string {
  let total = 0n
  for (const a of amounts) total += toCents(a) ?? 0n
  return fromCents(total)
}

/**
 * Parse what a user types in a correction field ("₱1,520", "1520.5")
 * into a canonical decimal string, or null if it isn't a plain amount.
 */
export function normalizeAmountInput(input: string): string | null {
  const stripped = input.replace(/S\$|[₱$€£¥,\s]|PHP|USD|EUR|GBP|SGD|JPY/gi, '')
  if (stripped === '') return null
  const cents = toCents(stripped)
  return cents === null ? null : fromCents(cents)
}

/** Display only: "18500.00" -> "18,500.00" */
export function formatAmount(amount: string): string {
  const [whole, frac = '00'] = amount.split('.')
  const neg = whole.startsWith('-')
  const digits = neg ? whole.slice(1) : whole
  return `${neg ? '-' : ''}${digits.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}.${frac}`
}

export function formatMoney(amount: string | null, currency: string | null): string {
  if (amount === null) return '—'
  return currency ? `${currency} ${formatAmount(amount)}` : formatAmount(amount)
}
