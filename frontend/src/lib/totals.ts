/**
 * Display helpers for Step 3 · Totals. Pure functions only. Amounts are never
 * added up here: totals come from PlanPreview.totals, which the backend computes.
 */
import type { ProposedOperation, ReportRow } from '../types/api'

const CURRENCY_NAMES: Record<string, string> = { PHP: 'pesos', USD: 'US dollars', EUR: 'euros', GBP: 'pounds', SGD: 'Singapore dollars', JPY: 'yen' }

/** "pesos", "US dollars"; unknown currencies show their ISO code. */
export function currencyName(code: string): string {
  return CURRENCY_NAMES[code] ?? code
}

/** Folder part of a relative path, with a trailing slash ("Receipts/2026-09/"). */
export function folderOf(path: string): string {
  const i = path.lastIndexOf('/')
  return i < 0 ? '' : `${path.slice(0, i)}/`
}

export const OTHER_FOLDER = 'Other/'
export const UNCATEGORIZED_FOLDER = 'Uncategorized/'

/** Plain note shown under a destination folder. */
export function folderNote(folder: string): string {
  if (folder === OTHER_FOLDER) return 'not counted'
  // Not just unreadable files: flagged files set aside land here too.
  if (folder === UNCATEGORIZED_FOLDER) return 'look later'
  return ''
}

export interface FolderGroup {
  folder: string
  count: number
}

/** Destination folders with their move counts. Dated folders first, then Other/, then Uncategorized/. */
export function groupByDestination(ops: ProposedOperation[]): FolderGroup[] {
  const counts = new Map<string, number>()
  for (const op of ops) {
    const folder = folderOf(op.destination_relative_path)
    counts.set(folder, (counts.get(folder) ?? 0) + 1)
  }
  const rank = (f: string) => (f === UNCATEGORIZED_FOLDER ? 2 : f === OTHER_FOLDER ? 1 : 0)
  return [...counts]
    .map(([folder, count]) => ({ folder, count }))
    .sort((a, b) => rank(a.folder) - rank(b.folder) || a.folder.localeCompare(b.folder))
}

/** Files that won't move: every scanned file (documents + unsupported) minus the planned moves. */
export function stayCount(documents: number, skipped: number, moves: number): number {
  return Math.max(0, documents + skipped - moves)
}

/** Accepted rows only, oldest first (rows without a date last). */
export function acceptedRowsByDate(rows: ReportRow[]): ReportRow[] {
  return rows
    .filter((r) => r.status === 'accepted')
    .sort((a, b) => (a.date ?? '9999').localeCompare(b.date ?? '9999') || a.source_filename.localeCompare(b.source_filename))
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** "2026-09-05" → "2026-09"; null when there's no usable date. */
export function monthKey(date: string | null): string | null {
  return date && /^\d{4}-\d{2}/.test(date) ? date.slice(0, 7) : null
}

/** "2026-09" → "Sep" (or "Sep 2026" with the year). */
export function monthLabel(key: string, withYear = false): string {
  const name = MONTHS[Number(key.slice(5, 7)) - 1] ?? key
  return withYear ? `${name} ${key.slice(0, 4)}` : name
}

export interface MonthFilter {
  key: string
  label: string
  count: number
}

/** Filter chips: one per month present in the rows, newest first. */
export function monthFilters(rows: ReportRow[]): MonthFilter[] {
  const counts = new Map<string, number>()
  for (const r of rows) {
    const k = monthKey(r.date)
    if (k) counts.set(k, (counts.get(k) ?? 0) + 1)
  }
  const years = new Set([...counts.keys()].map((k) => k.slice(0, 4)))
  return [...counts]
    .sort((a, b) => b[0].localeCompare(a[0]))
    .map(([key, count]) => ({ key, label: monthLabel(key, years.size > 1), count }))
}

/** "Aug–Sep 2026", "Dec 2025–Jan 2026", "Sep 2026"; null when no row has a date. */
export function monthRange(rows: ReportRow[]): string | null {
  const keys = rows.map((r) => monthKey(r.date)).filter((k): k is string => k !== null).sort()
  if (keys.length === 0) return null
  const first = keys[0]
  const last = keys[keys.length - 1]
  if (first === last) return monthLabel(first, true)
  if (first.slice(0, 4) === last.slice(0, 4)) return `${monthLabel(first)}–${monthLabel(last, true)}`
  return `${monthLabel(first, true)}–${monthLabel(last, true)}`
}

/** "1 file" / "2 files". */
export function files(n: number): string {
  return `${n} ${n === 1 ? 'file' : 'files'}`
}
