import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { ChevronDown } from 'lucide-react'
import { useApp } from '../state/AppState'
import type { DocumentCorrection } from '../types/api'
import { basename, documentKindLabel, fieldProfile, NON_TRANSACTION_DECISIONS, type FileRow } from '../lib/viewModel'
import { formatBytes } from '../lib/format'
import { Chip } from '../components/paper/Chip'
import { PageFooter } from '../components/paper/PageFooter'
import { PaperButton } from '../components/paper/Button'
import { EvidenceExcerpt, FolderRow, ProgressDots, RadioCard, ReviewRow, SearchPill, SegmentedFilter, type CheckFilter } from '../components/paper/CheckComponents'

function isNeeds(row: FileRow) { return row.doc?.status === 'needs_review' && !row.doc.user_corrected }
function isFailed(row: FileRow) { return row.doc?.status === 'failed' }
function isReady(row: FileRow) { return row.doc?.status === 'ok' || Boolean(row.doc?.user_corrected) }
function isUnsupported(row: FileRow) { return row.status === 'skipped' }

function PanelAction({ children, onClick, disabled }: { children: ReactNode; onClick: () => void; disabled?: boolean }) {
  return <PaperButton variant="primary" className="w-full" onClick={onClick} disabled={disabled}>{children}</PaperButton>
}

function DetailPanel({ row, onClose }: { row: FileRow; onClose: () => void }) {
  const { state, correct } = useApp()
  const doc = row.doc
  const [amount, setAmount] = useState(doc?.classification?.amount ?? '')
  const [date, setDate] = useState(doc?.classification?.date ?? '')
  const [merchant, setMerchant] = useState(doc?.classification?.merchant ?? '')
  const [manual, setManual] = useState(false)
  // Typing in an unreadable file: the person says what it is, so the backend can derive the profile.
  const [manualKind, setManualKind] = useState<'receipt' | 'invoice'>('receipt')
  const [saving, setSaving] = useState(false)
  if (!doc) return null
  const flag = doc.review_flags[0]?.code
  const isInjection = flag === 'possible_injection'
  const isConflict = flag === 'amount_conflict'
  const isMissingDate = flag === 'missing_date'
  const isFailedDoc = doc.status === 'failed'
  // Shop/date/amount inputs only for the backend's 'transaction' profile. Unreadable files keep
  // their own "type it yourself" flow, and suspicious files their own warning.
  const transactional = fieldProfile(doc) === 'transaction'
  if (!transactional && !isFailedDoc && !isInjection) return <NonTransactionalDetailPanel row={row} onClose={onClose} />
  const save = async (correction: Omit<DocumentCorrection, 'accept'> = {}) => {
    setSaving(true)
    await correct(doc.file_id, { ...correction, accept: true }, 'review')
    setSaving(false)
  }
  const details = { amount: amount || null, date: date || null, merchant: merchant || null }
  /**
   * Unreadable file. The backend only accepts a shop/date/amount on a 'transaction' record, so
   * typing them in is two steps: say it's a receipt/invoice (which makes it one), then the details.
   * "Leave it for later" sends no money fields at all.
   */
  const saveFailed = async () => {
    if (!manual) return save({ category: 'uncertain' })
    setSaving(true)
    const ok = await correct(doc.file_id, { category: manualKind, accept: false }, 'kind')
    if (ok) await correct(doc.file_id, { ...details, accept: true }, 'details')
    setSaving(false)
  }
  const sticky = isInjection ? '⚠ This file has text that tries to give Pip orders… Pip ignored it — files are only ever moved by you.' : isFailedDoc ? `${doc.review_flags[0]?.message ?? 'The local AI took too long on this file and gave up.'} Pip didn't guess anything, so there are no numbers to trust here.` : isMissingDate ? 'Pip found a shop and a total, but no date anywhere on the receipt. When did you buy this?' : isConflict ? "The subtotal and the amount due don't match, and there's no tax line explaining it. Which one did you pay?" : (doc.review_flags[0]?.message ?? 'Check the extracted details before this file is filed.')
  const failedLeft = isFailedDoc && doc.user_corrected && !doc.classification?.merchant && !doc.classification?.date && !doc.classification?.amount
  const status = doc.user_corrected ? (failedLeft ? 'left for later' : '✓ checked') : isFailedDoc ? "couldn't read" : 'check this'
  return <aside className="flex w-[500px] min-h-0 shrink-0 flex-col border-l-[2.5px] border-ink bg-paper" aria-label="File details">
    <div className="flex items-start gap-3 border-b-[2.5px] border-ink px-5 py-4"><div className="min-w-0 flex-1"><h2 className="truncate font-display text-[26px] font-normal">{basename(doc.relative_path)}</h2><p className="m-0 text-[16px] text-graphite">{doc.file_type.toUpperCase()} · {formatBytes(doc.size_bytes)}</p></div><Chip tone={doc.user_corrected ? (failedLeft ? 'muted' : 'done') : isFailedDoc ? 'oops' : 'check'} size="sm">{status}</Chip><button type="button" onClick={onClose} aria-label="Close file details" className="flex h-10 w-10 items-center justify-center rounded-[10px] border-[2.5px] border-ink bg-paper">×</button></div>
    <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
      <div role={isInjection ? 'alert' : 'note'} className={`rotate-[-0.6deg] border-[2.5px] border-ink p-4 shadow-sticky ${isInjection || isFailedDoc ? 'bg-note-oops' : 'bg-note-check'}`}><p className="m-0 text-[19px] leading-6">{sticky}</p></div>
      {isInjection && <><p className="m-0 text-[16px]">the text, shown as plain words only:</p><EvidenceExcerpt text={doc.excerpt} quote={doc.classification?.evidence_quote} tone="pink" /></>}
      {isFailedDoc && <div role="radiogroup" aria-label="What to do with this file" className="space-y-2"><RadioCard checked={!manual} onChange={() => setManual(false)}>Leave it for later<br /><span className="text-graphite">goes to Uncategorized/ and is not counted</span></RadioCard><RadioCard checked={manual} onChange={() => setManual(true)}>Type the details myself</RadioCard></div>}
      {!isInjection && (!isFailedDoc || manual) && <div className="space-y-3">
        {isFailedDoc && <div role="radiogroup" aria-label="What kind of paper is it" className="flex gap-2">{(['receipt', 'invoice'] as const).map((k) => <button key={k} type="button" role="radio" aria-checked={manualKind === k} onClick={() => setManualKind(k)} className={`flex-1 rounded-full border-[2.5px] border-ink px-3 py-1.5 text-[17px] ${manualKind === k ? 'bg-ink text-paper' : 'bg-paper'}`}>{k}</button>)}</div>}
        <label className="block">Shop<input value={merchant} onChange={(e) => setMerchant(e.target.value)} className="mt-1 block h-11 w-full rounded-[8px] border-[2.5px] border-ink bg-paper px-3" /></label>
        <label className="block">Amount<input value={amount} onChange={(e) => setAmount(e.target.value)} inputMode="decimal" className="mt-1 block h-11 w-full rounded-[8px] border-[2.5px] border-ink bg-paper px-3 font-mono text-[15px]" /></label>
        {(isMissingDate || !isConflict) && <label className={`block ${isMissingDate ? 'rounded-[8px] bg-hl-check p-2' : ''}`}>Date<input value={date} onChange={(e) => setDate(e.target.value)} placeholder="YYYY-MM-DD" className="mt-1 block h-11 w-full rounded-[8px] border-[2.5px] border-ink bg-paper px-3 font-mono text-[15px]" /></label>}
      </div>}
      {!isInjection && <><p className="m-0 text-[16px] text-graphite">what Pip read in the file:</p><EvidenceExcerpt text={doc.excerpt} quote={doc.classification?.evidence_quote} /></>}
      <p className="m-0 text-[16px] text-graphite">goes to <span className="font-mono">{row.destination ?? (isInjection ? 'Other/' : 'Uncategorized/')}</span> once checked</p>
    </div>
    <div className="border-t-[2.5px] border-ink p-4">{state.actionError && <p className="mb-2 text-center text-[16px] text-danger">{state.actionError}</p>}<PanelAction disabled={saving} onClick={() => isInjection ? save() : isFailedDoc ? saveFailed() : save(details)}>{isFailedDoc && !manual ? 'Leave it for later · mark checked' : isInjection ? 'Got it · file under Other' : isMissingDate ? 'Save date · mark checked' : 'Looks right · mark checked'}</PanelAction></div>
  </aside>
}

/** Statements, IDs, legal, medical and unclear papers: what it is, the evidence, and a decision. No money fields. */
function NonTransactionalDetailPanel({ row, onClose }: { row: FileRow; onClose: () => void }) {
  const { state, correct } = useApp()
  const [saving, setSaving] = useState<'file' | 'leave' | null>(null)
  const doc = row.doc
  if (!doc) return null
  const c = doc.classification
  const kind = documentKindLabel(doc)
  const unclear = (c?.document_kind ?? 'uncertain') === 'uncertain'
  const ignoredFields = doc.review_flags.some((f) => f.code === 'transaction_fields_on_non_transactional')
  const decided = doc.user_corrected ? (c?.category === 'other' ? 'file' : 'leave') : null
  const decide = async (choice: 'file' | 'leave') => {
    setSaving(choice)
    await correct(doc.file_id, NON_TRANSACTION_DECISIONS[choice], choice === 'file' ? 'filing' : 'review')
    setSaving(null)
  }
  return <aside className="flex w-[500px] min-h-0 shrink-0 flex-col border-l-[2.5px] border-ink bg-paper" aria-label="File details">
    <div className="flex items-start gap-3 border-b-[2.5px] border-ink px-5 py-4"><div className="min-w-0 flex-1"><h2 className="truncate font-display text-[26px] font-normal">{basename(doc.relative_path)}</h2><p className="m-0 text-[16px] text-graphite">{doc.file_type.toUpperCase()} · {formatBytes(doc.size_bytes)}</p></div><Chip tone={!decided ? 'check' : decided === 'file' ? 'done' : 'muted'} size="sm">{!decided ? 'check this' : decided === 'file' ? '✓ filed under Other' : 'left for review'}</Chip><button type="button" onClick={onClose} aria-label="Close file details" className="flex h-10 w-10 items-center justify-center rounded-[10px] border-[2.5px] border-ink bg-paper">×</button></div>
    <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4">
      <div role="note" className="rotate-[-0.6deg] border-[2.5px] border-ink bg-note-check p-4 shadow-sticky"><p className="m-0 text-[19px] leading-6">{unclear ? "Pip can't tell what kind of paper this is. It won't guess a shop, date or amount." : `This looks like ${kind === 'other document' ? 'a document' : `${/^[aeiou]/.test(kind) ? 'an' : 'a'} ${kind}`}, not a payment. There's no shop, date or amount to check.`}</p></div>
      <div className="rounded-[10px] border-[2.5px] border-ink bg-paper px-3 py-2" aria-label="What Pip thinks this is">
        <div className="text-[15px] text-graphite">what it is</div>
        <div className="text-[20px]">{kind}</div>
        {c?.explanation && <div className="mt-1 text-[16px] text-graphite">{c.explanation}</div>}
        {ignoredFields && <div className="mt-2 rounded-[6px] bg-hl-info px-2 py-1 text-[15px]">The AI also wrote down payment details for this file. GhostOS ignores them: they aren't shown, counted or filed.</div>}
      </div>
      <div><p className="m-0 mb-1 text-[16px] text-graphite">what Pip read in the file:</p><EvidenceExcerpt text={doc.excerpt} quote={c?.evidence_quote} /></div>
      <p className="m-0 text-[16px] text-graphite">{decided ? <>goes to <span className="font-mono">{row.destination ?? (decided === 'file' ? 'Other/' : 'Uncategorized/')}</span> · not counted in totals</> : 'Not counted in totals either way. Nothing moves until you press Move.'}</p>
    </div>
    <div className="space-y-2 border-t-[2.5px] border-ink p-4">
      {state.actionError && <p className="mb-2 text-center text-[16px] text-danger">{state.actionError}</p>}
      <PaperButton variant={decided === 'file' ? 'secondary' : 'primary'} className="w-full" disabled={saving !== null || decided === 'file'} onClick={() => decide('file')}>{decided === 'file' ? '✓ Filed under Other' : 'File it · no payment details'}</PaperButton>
      <PaperButton variant="secondary" className="w-full" disabled={saving !== null || decided === 'leave'} onClick={() => decide('leave')}>{decided === 'leave' ? '✓ Left for review' : 'Leave for review'}</PaperButton>
      <p className="m-0 text-center text-[15px] text-graphite">File it → Other/ · Leave for review → Uncategorized/</p>
    </div>
  </aside>
}

function ResolvedPanel({ plan, scanCount, unsupportedCount }: { plan: NonNullable<ReturnType<typeof useApp>['state']['plan']>; scanCount: number; unsupportedCount: number }) {
  const groups = useMemo(() => { const map = new Map<string, number>(); for (const op of plan.operations) { const path = op.destination_relative_path.split('/').slice(0, -1).join('/') || op.destination_relative_path; map.set(path, (map.get(path) ?? 0) + 1) } return [...map.entries()] }, [plan])
  return <aside className="flex w-[500px] min-h-0 shrink-0 flex-col border-l-[2.5px] border-ink bg-paper" aria-label="File details"><div className="border-b-[2.5px] border-ink px-5 py-4"><h2 className="font-display text-[28px] font-normal">Where files will go</h2><p className="m-0 text-[17px]">{plan.operations.length} files will move · {scanCount - plan.operations.length} stay where they are</p><Chip tone="done" size="sm">✓ all checked</Chip></div><div className="min-h-0 flex-1 overflow-y-auto px-5 py-4"><div className="rotate-[-0.6deg] border-[2.5px] border-ink bg-note-check p-4 shadow-sticky" role="note"><p className="m-0 text-[19px]">All {scanCount} checked. Here's where everything will go. <strong>Nothing has moved yet</strong> — you'll say yes one more time on the next step.</p></div><div className="mt-5">{groups.map(([path, count]) => <FolderRow key={path} path={path} note="from the plan" count={count} />)}</div><p className="mt-4 font-mono text-[13px]">{unsupportedCount} not supported stay put</p></div></aside>
}

export function FilesPage() {
  const { state, rows, selectDoc, navigate, counts, usingFixtures } = useApp()
  const [filter, setFilter] = useState<CheckFilter>('all')
  const [query, setQuery] = useState('')
  const [selected, setSelected] = useState<string | null>(state.selectedDocId)
  const rowRefs = useRef<Record<string, HTMLButtonElement | null>>({})
  const visibleRows = useMemo(() => rows.filter((row) => { const q = query.trim().toLowerCase(); const matches = !q || [row.relPath, row.filename, row.merchant ?? ''].some((value) => value.toLowerCase().includes(q)); const type = filter === 'all' || (filter === 'needs' && isNeeds(row)) || (filter === 'failed' && isFailed(row)) || (filter === 'ready' && isReady(row)) || (filter === 'unsupported' && isUnsupported(row)); return matches && type }), [rows, query, filter])
  const countsBy = { all: rows.length, needs: rows.filter(isNeeds).length, failed: rows.filter(isFailed).length, ready: rows.filter(isReady).length, unsupported: rows.filter(isUnsupported).length }
  const checked = rows.filter((row) => row.doc?.user_corrected).length
  const allChecked = countsBy.needs === 0
  const selectedRow = rows.find((row) => row.id === selected) ?? null
  // Only the rows actually rendered as ReviewRow take part in arrow-key
  // navigation, in the order they appear on screen (needs section first,
  // then couldn't-read). Collapsed ready/unsupported rows are excluded.
  const navigableRows = useMemo(() => {
    if (filter === 'needs') return visibleRows.filter(isNeeds)
    if (filter === 'failed') return visibleRows.filter(isFailed)
    if (filter === 'ready') return visibleRows.filter(isReady)
    if (filter === 'unsupported') return visibleRows.filter(isUnsupported)
    return [...visibleRows.filter(isNeeds), ...visibleRows.filter(isFailed)]
  }, [visibleRows, filter])
  // Only sync when it differs: selectDoc is a new function every render, so an unconditional patch loops.
  useEffect(() => { if (selected && selected !== state.selectedDocId) selectDoc(selected) }, [selected, selectDoc, state.selectedDocId])
  const handleKeyFor = (rowId: string) => (event: React.KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    if (navigableRows.length === 0) return
    const at = navigableRows.findIndex((row) => row.id === rowId)
    if (at < 0) return
    const next = navigableRows[(at + (event.key === 'ArrowDown' ? 1 : navigableRows.length - 1)) % navigableRows.length]
    if (next) { setSelected(next.id); rowRefs.current[next.id]?.focus() }
  }
  if (!state.scan) return <div className="p-8"><h1 className="font-display text-[40px] font-normal">Check what Pip found</h1><p>Run a scan first.</p></div>
  return <div className="flex min-h-0 flex-1 flex-col"><div className="mx-auto flex min-h-0 w-full max-w-[1280px] flex-1 flex-col">
    <div className="flex shrink-0 items-end justify-between gap-4 px-8 pb-3 pt-5"><h1 className="m-0 font-display text-[40px] font-normal">{allChecked ? 'All decided. Nice.' : 'Check what Pip found'}</h1><p className="m-0 text-[17px]">{state.folder?.name ?? 'Folder'} · {counts.documents} files{usingFixtures && <span className="ml-2"><Chip tone="info" size="sm">demo data</Chip></span>}</p></div>
    <div className="flex shrink-0 flex-wrap items-center gap-3 px-8 pb-4"><SegmentedFilter value={filter} counts={countsBy} onChange={setFilter} /><SearchPill value={query} onChange={setQuery} /></div>
    <div className="flex min-h-0 flex-1"><section className="min-w-0 flex-1 overflow-y-auto px-8 pb-4" role="listbox" aria-label="Files to check">
      {countsBy.needs > 0 && <><h2 className="mb-2 mt-1 font-display text-[24px] font-normal">needs you · {countsBy.needs}</h2><div className="space-y-2">{visibleRows.filter(isNeeds).map((row) => <ReviewRow key={row.id} row={row} selected={selected === row.id} onClick={() => setSelected(row.id)} onKeyDown={handleKeyFor(row.id)} buttonRef={(element) => { rowRefs.current[row.id] = element }} />)}</div></>}
      {countsBy.failed > 0 && <><h2 className="mb-2 mt-5 font-display text-[24px] font-normal">couldn't read · {countsBy.failed} <span className="font-sans text-[16px] text-graphite">(doesn't block you · goes to Uncategorized/)</span></h2><div className="space-y-2">{visibleRows.filter(isFailed).map((row) => <ReviewRow key={row.id} row={row} selected={selected === row.id} onClick={() => setSelected(row.id)} onKeyDown={handleKeyFor(row.id)} buttonRef={(element) => { rowRefs.current[row.id] = element }} />)}</div></>}
      {filter === 'ready' && <div className="mt-5 space-y-2">{visibleRows.filter(isReady).map((row) => <ReviewRow key={row.id} row={row} selected={selected === row.id} onClick={() => setSelected(row.id)} onKeyDown={handleKeyFor(row.id)} buttonRef={(element) => { rowRefs.current[row.id] = element }} />)}</div>}
      {filter === 'unsupported' && <div className="mt-5 space-y-2">{visibleRows.filter(isUnsupported).map((row) => <ReviewRow key={row.id} row={row} selected={selected === row.id} onClick={() => setSelected(row.id)} onKeyDown={handleKeyFor(row.id)} buttonRef={(element) => { rowRefs.current[row.id] = element }} />)}</div>}
      <div className="mt-5 space-y-2">{countsBy.ready > 0 && <button type="button" className="flex w-full items-center justify-between rounded-[10px] border-[2.5px] border-dashed border-ink bg-paper px-4 py-3 text-left" onClick={() => setFilter('ready')}>{countsBy.ready} ready files · show <ChevronDown size={20} aria-hidden /></button>}{countsBy.unsupported > 0 && <button type="button" className="flex w-full items-center justify-between rounded-[10px] border-[2.5px] border-dashed border-ink bg-paper px-4 py-3 text-left" onClick={() => setFilter('unsupported')}>{countsBy.unsupported} not supported · show <ChevronDown size={20} aria-hidden /></button>}</div>
    </section>{selectedRow?.doc ? <DetailPanel key={selectedRow.id} row={selectedRow} onClose={() => { setSelected(null); selectDoc(null) }} /> : allChecked && state.plan ? <ResolvedPanel plan={state.plan} scanCount={counts.documents} unsupportedCount={countsBy.unsupported} /> : null}</div></div>
    <PageFooter className="!h-[72px]" left={<><PaperButton variant="link" className="mr-3" onClick={() => navigate('dashboard')}>← back to start</PaperButton><ProgressDots checked={checked} total={counts.documents} /><span>{checked} of {counts.documents} decided · nothing has moved</span></>} right={<PaperButton variant="primary" disabled={!allChecked} disabledReason={!allChecked ? `check ${counts.blocking} more file(s) first` : undefined} reasonId="check-next-reason" onClick={() => navigate('plan')}>{allChecked ? 'Continue to totals →' : 'Totals →'}</PaperButton>} />
  </div>
}
