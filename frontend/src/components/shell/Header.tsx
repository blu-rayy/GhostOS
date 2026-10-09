import { useRef, useState } from 'react'
import { useApp } from '../../state/AppState'
import type { AppState } from '../../state/reducer'
import { STEP_LABELS, WORDS } from '../../lib/copy'
import { describeScanError } from '../../lib/scanError'
import { STEPS, canOpenStep, isStepDone, stepForView, type StepContext, type StepIndex } from '../../lib/steps'
import type { Panel } from '../../types/ui'
import { Tag } from '../paper/Chip'
import { IconButton, PaperButton } from '../paper/Button'
import { PaperDialog } from '../paper/PaperDialog'
import { ComputerIcon, HistoryIcon, LockIcon, SettingsIcon } from '../paper/icons'
import { PipMark } from '../pip/Pip'
import { cx } from '../ui/cx'
import { useServiceStates } from './useServiceStates'

type StepState = 'done' | 'current' | 'later'

/**
 * The only navigation: logo, the 4-step tracker, the offline pill, a "demo data"
 * chip when fixtures are in use, and History / Settings buttons.
 */
export function Header() {
  const { state, navigate, dispatch, resetSession, usingFixtures } = useApp()
  const [confirmStartOver, setConfirmStartOver] = useState(false)
  const loss = startOverLoss(state)
  const goHome = () => (loss === 'busy' ? undefined : loss ? setConfirmStartOver(true) : resetSession())
  const ctx: StepContext = { phase: state.phase, hasScan: state.scan !== null, hasApprovedPlan: state.approvedPlan !== null }
  const current = stepForView(state.view)
  const togglePanel = (panel: Panel) => dispatch({ type: 'patch', patch: { panel: state.panel === panel ? null : panel } })
  const stepState = (i: StepIndex): StepState => (i === current ? 'current' : isStepDone(i, ctx, current) ? 'done' : 'later')

  return (
    <>
    <header className="relative z-10 flex h-16 shrink-0 items-center gap-5 border-b-[2.5px] border-ink bg-paper px-7">
      <button
        type="button"
        aria-label="Go to GhostOS start"
        title="Go to start"
        onClick={goHome}
        className="flex items-center gap-2 rounded-[10px] outline-none transition-transform duration-150 hover:-translate-y-px focus-visible:ring-2 focus-visible:ring-ink focus-visible:ring-offset-2"
      >
        <PipMark size={32} />
        {/* Gochi Hand's capitals barely differ from lowercase, so "OS" is set larger. */}
        <span className="font-display text-[28px] leading-none">
          ghost<span className="text-[37px] tracking-[0.03em]">OS</span>
        </span>
      </button>

      <nav aria-label="Steps" className="ml-4">
        <ol className="m-0 flex list-none items-center gap-1.5 p-0 text-[18px]">
          {STEPS.map((s, i) => {
            const st = stepState(s.index)
            const prev = i > 0 ? stepState(STEPS[i - 1].index) : null
            const solid = prev === 'done' && st !== 'later'
            return (
              <li key={s.index} className="flex items-center gap-1.5">
                {i > 0 && <span aria-hidden className={cx('w-6 border-t-[2.5px]', solid ? 'border-solid border-ink' : 'border-dashed border-btn-shadow')} />}
                <Step label={STEP_LABELS[s.index]} number={s.index + 1} state={st} onOpen={canOpenStep(s.index, current, ctx) ? () => navigate(s.view) : undefined} />
              </li>
            )
          })}
        </ol>
      </nav>

      <div className="ml-auto flex items-center gap-2.5">
        <StatusPill />
        {usingFixtures && (
          <Tag tone="info" title="These are the bundled sample files, not files from your computer.">
            {WORDS.demoData.toLowerCase()}
          </Tag>
        )}
        <IconButton label={WORDS.history} pressed={state.panel === 'history'} onClick={() => togglePanel('history')}>
          <HistoryIcon size={20} crisp />
        </IconButton>
        <IconButton label={WORDS.settings} pressed={state.panel === 'settings'} onClick={() => togglePanel('settings')}>
          <SettingsIcon size={20} crisp />
        </IconButton>
      </div>
    </header>
    <StartOverDialog open={confirmStartOver} loss={loss} onKeep={() => setConfirmStartOver(false)} onStartOver={() => { setConfirmStartOver(false); resetSession() }} />
    </>
  )
}

function Step({ label, number, state, onOpen }: { label: string; number: number; state: StepState; onOpen?: () => void }) {
  const marker =
    state === 'done' ? (
      <span aria-hidden className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-ink text-[15px] leading-none text-paper">
        ✓
      </span>
    ) : state === 'current' ? (
      <span aria-hidden className="inline-flex h-[22px] w-[22px] items-center justify-center rounded-full border-[2.5px] border-ink bg-paper text-[15px] leading-none">
        {number}
      </span>
    ) : (
      <span aria-hidden className="inline-flex h-[22px] w-[22px] items-center justify-center rounded-full border-[2.5px] border-dashed border-btn-shadow text-[15px] leading-none">
        {number}
      </span>
    )
  const body = (
    <>
      {marker}
      {label}
      <span className="sr-only">{state === 'current' ? ' (you are here)' : state === 'done' ? ' (done)' : ' (not yet)'}</span>
    </>
  )
  const cls = cx(
    'inline-flex items-center gap-1.5 rounded-full border-[2.5px] transition-[background-color,border-color,color,padding,transform] duration-300 ease-out',
    state === 'current' ? 'step-current border-ink bg-hl-check py-px pl-1 pr-3' : 'border-transparent py-px pl-0.5 pr-2',
    state === 'later' ? 'text-graphite' : 'text-ink',
  )
  if (onOpen) {
    return (
      <button type="button" onClick={onOpen} className={cx(cls, 'hover:border-ink')}>
        {body}
      </button>
    )
  }
  return (
    <span className={cls} aria-current={state === 'current' ? 'step' : undefined}>
      {body}
    </span>
  )
}

const PILL = 'inline-flex items-center gap-1.5 rounded-full border-[2.5px] px-3 text-[17px] leading-7'

/**
 * "offline · on this computer", backed by /api/status (external_requests == 0).
 * Turns pink when the local AI health check fails or a scan stopped because the
 * local AI didn't answer. Never claims more than was checked.
 */
function StatusPill() {
  const svc = useServiceStates()
  const { state, usingFixtures } = useApp()
  const aiDown = state.status?.model_loaded === false || (state.phase === 'scan_failed' && describeScanError(state.scanError).kind === 'ai')

  if (svc.external > 0) {
    return (
      <span role="status" className={cx(PILL, 'border-ink bg-hl-oops')}>
        <LockIcon size={16} crisp />
        {svc.external} outside {svc.external === 1 ? 'request' : 'requests'}
      </span>
    )
  }
  if (aiDown) {
    return (
      <span role="status" className={cx(PILL, 'border-ink bg-sticky-pink')}>
        <LockIcon size={16} crisp />
        offline · local AI not answering
      </span>
    )
  }
  if (!usingFixtures && (state.statusError || !state.status)) {
    return (
      <span className={cx(PILL, 'border-dashed border-graphite text-fg-muted')} title={state.statusError ?? 'Checking the local service…'}>
        <LockIcon size={16} crisp />
        {state.statusError ? "can't check status" : 'checking…'}
      </span>
    )
  }
  return (
    <span
      className={cx(PILL, 'border-ink bg-paper')}
      title={usingFixtures ? 'Demo mode: the sample data is bundled with the app. Nothing is sent anywhere.' : 'The local service reports no requests outside this computer.'}
    >
      <LockIcon size={16} crisp />
      <span>{WORDS.offline.toLowerCase().split(' · ')[0]}</span>
      {/* Drawn separator dot: a text bullet at this size renders as a speck. */}
      <span aria-hidden className="mx-1 inline-block h-[5px] w-[5px] shrink-0 rounded-full bg-ink" />
      <ComputerIcon size={16} crisp />
      <span className="sr-only">on this computer</span>
    </span>
  )
}

type StartOverLoss = 'reading' | 'checks' | 'moved'

/**
 * What going back to Start would throw away (the session lives only in memory). null: nothing
 * worth confirming (no folder, only a folder picked, or the files were already put back).
 * Never while files are moving or being put back: the logo does nothing then.
 */
function startOverLoss(state: AppState): StartOverLoss | 'busy' | null {
  if (state.phase === 'organizing' || state.phase === 'undoing') return 'busy'
  if (state.batch && state.phase === 'organized') return 'moved'
  if (state.phase === 'scanning') return 'reading'
  if (state.scan && state.phase !== 'undone') return 'checks'
  return null
}

const START_OVER_TEXT: Record<StartOverLoss, { title: string; body: string }> = {
  reading: { title: 'Stop reading and start over?', body: 'Pip is still reading this folder. Starting over stops it. Nothing has been moved.' },
  checks: { title: 'Start over?', body: 'Your checks on this folder will be lost. Nothing has been moved yet.' },
  moved: {
    title: 'Start over?',
    body: "Your files stay in their new folders, but after this GhostOS can't put them back for you. If you might want to undo, use History → Put files back first.",
  },
}

/** Confirms going back to Start from the logo. "Keep working" has focus; Esc keeps working. */
function StartOverDialog({ open, loss, onKeep, onStartOver }: { open: boolean; loss: StartOverLoss | 'busy' | null; onKeep: () => void; onStartOver: () => void }) {
  const keep = useRef<HTMLButtonElement>(null)
  const text = loss && loss !== 'busy' ? START_OVER_TEXT[loss] : null
  return (
    <PaperDialog open={open && text !== null} onCancel={onKeep} role="alertdialog" variant="b" labelledBy="start-over-title" describedBy="start-over-desc" initialFocus={keep}>
      {text && (
        <div className="px-8 pb-6 pt-6">
          <h2 id="start-over-title" className="m-0 font-display text-[36px] font-normal leading-tight">
            {text.title}
          </h2>
          <p id="start-over-desc" className="m-0 mt-2 text-[18px] leading-7">
            {text.body}
          </p>
          <div className="mt-6 flex items-center justify-end gap-4">
            <PaperButton ref={keep} variant="secondary" size="sm" onClick={onKeep}>
              Keep working
            </PaperButton>
            <PaperButton variant="careful" size="sm" onClick={onStartOver}>
              Start over
            </PaperButton>
          </div>
        </div>
      )}
    </PaperDialog>
  )
}
