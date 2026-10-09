import { describe, expect, it } from 'vitest'
import scanFixture from '../fixtures/scan.json'
import type { PlanPreview, ScanResult } from '../types/api'
import { buildFileRows, docStatus, flagsFor, isBlocking, isInsideRoot, reviewChipState, reviewReasonText } from './viewModel'

const scan = scanFixture as unknown as ScanResult
const emptyPlan: PlanPreview = {
  plan_id: 'plan_fixture',
  scan_id: scan.scan_id,
  operations: [],
  report_rows: [],
  totals: [],
  blocking_review_count: 0,
}

describe('view model logic', () => {
  it('maps document statuses and blocking state', () => {
    const review = scan.documents.find((document) => document.file_id === 'f07')!
    const failed = scan.documents.find((document) => document.file_id === 'f10')!
    const ok = scan.documents.find((document) => document.file_id === 'f01')!
    expect(docStatus(review)).toBe('needs_review')
    expect(docStatus(failed)).toBe('failed')
    expect(docStatus(ok)).toBe('extracted')
    expect(isBlocking(review)).toBe(true)
    expect(isBlocking(failed)).toBe(false)
  })

  it('maps flag codes to field targets and hides them after correction', () => {
    const injection = scan.documents.find((document) => document.file_id === 'f13')!
    expect(flagsFor(injection, 'document').map((flag) => flag.code)).toEqual(['possible_injection'])
    expect(flagsFor(injection, 'amount')).toEqual([])
    const conflict = scan.documents.find((document) => document.file_id === 'f07')!
    expect(flagsFor(conflict, 'amount').map((flag) => flag.code)).toEqual(['amount_conflict'])
    const evidence = scan.documents.find((document) => document.file_id === 'f18')!
    expect(flagsFor(evidence, 'evidence').map((flag) => flag.code)).toEqual(['evidence_not_found'])
    const corrected = { ...injection, user_corrected: true }
    expect(flagsFor(corrected, 'document')).toEqual([])
  })

  it('includes all documents and skipped files in file rows', () => {
    const rows = buildFileRows(scan, emptyPlan)
    expect(rows).toHaveLength(scan.documents.length + scan.skipped.length)
    expect(rows.filter((row) => row.skip)).toHaveLength(5)
    expect(scan.skipped.map((file) => file.reason)).toEqual([
      'unsupported_type',
      'unsupported_type',
      'no_extractable_text',
      'too_large',
      'symlink',
    ])
    expect(rows.find((row) => row.id === 'skip:photos/receipt_photo_0915.jpg')?.status).toBe('skipped')
    expect(rows.find((row) => row.id === 'f10')?.status).toBe('failed')
  })

  it('rejects absolute and parent-traversal destinations', () => {
    expect(isInsideRoot('Invoices/2026-09/file.pdf')).toBe(true)
    expect(isInsideRoot('../outside/file.pdf')).toBe(false)
    expect(isInsideRoot('/absolute/file.pdf')).toBe(false)
    expect(isInsideRoot('C:/Windows/System32/file.pdf')).toBe(false)
    expect(isInsideRoot('\\\\server\\share\\file.pdf')).toBe(false)
  })

  it('labels backend-accepted unflagged files as ready, not check-this', () => {
    const ok = scan.documents.find((document) => document.file_id === 'f01')!
    expect(ok.status).toBe('ok')
    expect(ok.user_corrected).toBe(false)
    expect(ok.review_flags).toEqual([])
    expect(reviewChipState(ok)).toMatchObject({ text: 'ready', tone: 'done' })
  })

  it('keeps review-needed files on the attention state', () => {
    const review = scan.documents.find((document) => document.file_id === 'f07')!
    expect(reviewChipState(review)).toMatchObject({ text: 'check this', tone: 'check' })
    const failed = scan.documents.find((document) => document.file_id === 'f10')!
    expect(reviewChipState(failed)).toMatchObject({ text: "couldn't read", tone: 'oops' })
  })

  it('names the actual decision on decided rows instead of checked', () => {
    const rows = buildFileRows(scan, emptyPlan)
    const byId = new Map(rows.map((row) => [row.id, row]))
    const filed = { ...byId.get('f20')!.doc!, user_corrected: true, classification: { ...byId.get('f20')!.doc!.classification!, category: 'other' as const } }
    expect(reviewChipState(filed)).toMatchObject({ text: 'filed under Other', tone: 'done' })
    expect(reviewReasonText({ ...byId.get('f20')!, doc: filed })).toContain('filed under Other/')
    const left = { ...byId.get('f20')!.doc!, user_corrected: true, classification: { ...byId.get('f20')!.doc!.classification!, category: 'uncertain' as const } }
    expect(reviewChipState(left)).toMatchObject({ text: 'left for review', tone: 'muted' })
    expect(reviewReasonText({ ...byId.get('f20')!, doc: left })).toContain('left for review → Uncategorized/')
    const leftFailed = { ...byId.get('f10')!.doc!, user_corrected: true }
    expect(reviewChipState(leftFailed)).toMatchObject({ text: 'left for later', tone: 'muted' })
    const verified = { ...byId.get('f07')!.doc!, user_corrected: true }
    expect(reviewChipState(verified)).toMatchObject({ text: '✓ checked', tone: 'done' })
  })
})
