import { describe, expect, it } from 'vitest'
import type { ProposedOperation, ReportRow } from '../types/api'
import { acceptedRowsByDate, currencyName, folderNote, groupByDestination, monthFilters, monthRange, stayCount } from './totals'

const row = (file_id: string, date: string | null, status: ReportRow['status'] = 'accepted'): ReportRow => ({
  file_id,
  source_filename: `${file_id}.pdf`,
  category: 'receipt',
  date,
  merchant: 'Shop',
  amount: '1.00',
  currency: 'PHP',
  status,
})

const op = (file_id: string, destination_relative_path: string): ProposedOperation => ({
  file_id,
  original_relative_path: `${file_id}.pdf`,
  destination_relative_path,
  reason: '',
  collision_suffixed: false,
})

describe('totals display helpers', () => {
  it('keeps accepted rows only, oldest first', () => {
    const rows = acceptedRowsByDate([row('b', '2026-09-03'), row('x', '2026-08-01', 'needs_review'), row('a', '2026-08-25')])
    expect(rows.map((r) => r.file_id)).toEqual(['a', 'b'])
  })

  it('builds month chips and the month range from row dates', () => {
    const rows = [row('a', '2026-08-25'), row('b', '2026-09-03'), row('c', '2026-09-10')]
    expect(monthFilters(rows)).toEqual([
      { key: '2026-09', label: 'Sep', count: 2 },
      { key: '2026-08', label: 'Aug', count: 1 },
    ])
    expect(monthRange(rows)).toBe('Aug–Sep 2026')
    expect(monthRange([row('a', '2025-12-30'), row('b', '2026-01-02')])).toBe('Dec 2025–Jan 2026')
    expect(monthRange([row('a', null)])).toBeNull()
  })

  it('groups destinations with Other/ and Uncategorized/ last', () => {
    const groups = groupByDestination([op('1', 'Other/a.txt'), op('2', 'Receipts/2026-09/b.pdf'), op('3', 'Uncategorized/c.pdf'), op('4', 'Invoices/2026-09/d.pdf'), op('5', 'Receipts/2026-09/e.pdf')])
    expect(groups).toEqual([
      { folder: 'Invoices/2026-09/', count: 1 },
      { folder: 'Receipts/2026-09/', count: 2 },
      { folder: 'Other/', count: 1 },
      { folder: 'Uncategorized/', count: 1 },
    ])
    expect(folderNote('Other/')).toBe('not counted')
    expect(folderNote('Uncategorized/')).toBe("couldn't read")
  })

  it('counts files that stay, including unsupported ones', () => {
    expect(stayCount(18, 5, 17)).toBe(6)
    expect(currencyName('PHP')).toBe('pesos')
    expect(currencyName('JPY')).toBe('yen')
    expect(currencyName('CHF')).toBe('CHF')
  })
})
