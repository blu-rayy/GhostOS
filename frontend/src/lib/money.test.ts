import { describe, expect, it } from 'vitest'
import { fromCents, normalizeAmountInput, sumAmounts, toCents } from './money'

describe('money helpers', () => {
  it('converts decimal strings to cents without floating point rounding', () => {
    expect(toCents('1520')).toBe(152000n)
    expect(toCents('1520.5')).toBe(152050n)
    expect(toCents('0.01')).toBe(1n)
    expect(toCents('-12.34')).toBe(-1234n)
    expect(toCents('12.345')).toBeNull()
    expect(toCents('1e3')).toBeNull()
  })

  it('formats cents canonically', () => {
    expect(fromCents(0n)).toBe('0.00')
    expect(fromCents(5n)).toBe('0.05')
    expect(fromCents(-123405n)).toBe('-1234.05')
  })

  it('sums valid decimal amounts and ignores invalid inputs', () => {
    expect(sumAmounts(['18500.00', '245.00', '0.45'])).toBe('18745.45')
    expect(sumAmounts(['bad', '1.10'])).toBe('1.10')
  })

  it('normalizes currency symbols, labels, commas, and whitespace', () => {
    expect(normalizeAmountInput('₱1,520')).toBe('1520.00')
    expect(normalizeAmountInput(' PHP 1,520.5 ')).toBe('1520.50')
    expect(normalizeAmountInput('$14.99')).toBe('14.99')
    expect(normalizeAmountInput('not an amount')).toBeNull()
    expect(normalizeAmountInput('')).toBeNull()
  })
})
