import type { ReportRow } from '../types/api'

function csvCell(v: string | null | undefined): string {
  if (v == null) return ''
  // Neutralise spreadsheet formula injection, then quote when needed.
  const safe = /^[=+\-@\t\r]/.test(v) ? `'${v}` : v
  return /[",\n\r]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe
}

/** CSV of accepted rows only. Amounts stay decimal strings in their own currency. */
export function toCsv(rows: ReportRow[]): string {
  const header = ['source_file', 'merchant', 'date', 'category', 'amount', 'currency']
  const body = rows
    .filter((r) => r.status === 'accepted')
    .map((r) => [r.source_filename, r.merchant, r.date, r.category, r.amount, r.currency].map(csvCell).join(','))
  return [header.join(','), ...body].join('\r\n') + '\r\n'
}

export function downloadText(filename: string, text: string, mime = 'text/csv;charset=utf-8'): void {
  const blob = new Blob(['﻿', text], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
