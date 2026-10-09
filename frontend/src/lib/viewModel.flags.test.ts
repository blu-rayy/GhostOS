import { describe, expect, it } from 'vitest'
import scanFixture from '../fixtures/scan.json'
import type { DocumentRecord, ReviewFlag, ScanResult } from '../types/api'
import { flagTarget, flagsFor } from './viewModel'

const scan = scanFixture as unknown as ScanResult
const base = scan.documents.find((d) => d.file_id === 'f01')!

function withFlags(flags: ReviewFlag[]): DocumentRecord {
  return { ...base, status: 'needs_review', user_corrected: false, review_flags: flags }
}

describe('validator flag codes', () => {
  it('places missing_merchant and missing_currency next to their fields', () => {
    const doc = withFlags([
      { code: 'missing_merchant', message: 'No shop name found.' },
      { code: 'missing_currency', message: 'No currency found.' },
    ])
    expect(flagsFor(doc, 'merchant').map((f) => f.code)).toEqual(['missing_merchant'])
    expect(flagsFor(doc, 'amount').map((f) => f.code)).toEqual(['missing_currency'])
  })

  it('places the other validator codes next to their fields', () => {
    const doc = withFlags([
      { code: 'invalid_currency', message: 'Currency code is not valid.' },
      { code: 'currency_mismatch', message: 'Currency symbol and code disagree.' },
      { code: 'missing_evidence_quote', message: 'No quote was given for the amount.' },
      { code: 'uncertain_classification', message: 'Not sure what kind of document this is.' },
    ])
    expect(flagsFor(doc, 'amount').map((f) => f.code)).toEqual(['invalid_currency', 'currency_mismatch'])
    expect(flagsFor(doc, 'evidence').map((f) => f.code)).toEqual(['missing_evidence_quote'])
    expect(flagsFor(doc, 'category').map((f) => f.code)).toEqual(['uncertain_classification'])
  })

  it('shows unknown codes under document instead of dropping them', () => {
    const unknown = { code: 'brand_new_check', message: 'Something new to check.' } as unknown as ReviewFlag
    expect(flagTarget('brand_new_check')).toBe('document')
    expect(flagTarget('toString')).toBe('document')
    expect(flagsFor(withFlags([unknown]), 'document')).toEqual([unknown])
  })
})
