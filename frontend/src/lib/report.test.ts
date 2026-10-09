import { describe, expect, it } from 'vitest'
import type { ReportRow } from '../types/api'
import { toCsv } from './report'

describe('report CSV', () => {
  it('exports accepted rows only and quotes comma/newline content', () => {
    const rows: ReportRow[] = [
      {
        file_id: 'accepted',
        source_filename: 'receipt, one.txt',
        merchant: 'Shop\nBranch',
        date: '2026-09-01',
        category: 'receipt',
        amount: '12.00',
        currency: 'PHP',
        status: 'accepted',
      },
      {
        file_id: 'review',
        source_filename: 'needs-review.txt',
        merchant: 'No export',
        date: null,
        category: 'invoice',
        amount: null,
        currency: null,
        status: 'needs_review',
      },
    ]
    expect(toCsv(rows)).toBe([
      'source_file,merchant,date,category,amount,currency',
      '"receipt, one.txt","Shop\nBranch",2026-09-01,receipt,12.00,PHP',
      '',
    ].join('\r\n'))
  })

  it('guards spreadsheet formula injection while preserving ordinary text', () => {
    const row: ReportRow = {
      file_id: 'formula',
      source_filename: '=CMD|\"/C calc\"!A0',
      merchant: '+SUM(1,2)',
      date: '2026-09-01',
      category: 'invoice',
      amount: '-10.00',
      currency: 'PHP',
      status: 'accepted',
    }
    const csv = toCsv([row])
    expect(csv).toContain("\"'=CMD|\"\"/C calc\"\"!A0\"")
    expect(csv).toContain("'+SUM(1,2)")
    expect(csv).toContain("'-10.00")
  })
})
