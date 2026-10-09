import { useApp } from '../../state/AppState'
import { STEP_LABELS, WORDS } from '../../lib/copy'
import { describeScanError } from '../../lib/scanError'
import { STEPS, canOpenStep, isStepDone, stepForView, type StepContext, type StepIndex } from '../../lib/steps'
import type { View } from '../../types/ui'
import { Tag } from '../paper/Chip'
import { IconButton } from '../paper/Button'
import { HistoryIcon, LockIcon, SettingsIcon } from '../paper/icons'
import { PipMark } from '../pip/Pip'
import { cx } from '../ui/cx'
import { useServiceStates } from './useServiceStates'

type StepState = 'done' | 'current' | 'later'

/**
 * The only navigation: logo, the 4-step tracker, the offline pill, a "demo data"
 * chip when fixtures are in use, and History / Settings buttons.
 */
export function Header() {
  const { state, navigate, usingFixtures } = useApp()
  const ctx: StepContext = { phase: state.phase, hasScan: state.scan !== null, hasApprovedPlan: state.approvedPlan !== null }
  const current = stepForView(state.view)
  const someNotMoved = (state.batch?.failed.length ?? 0) > 0 && state.phase === 'organized'
  const stepState = (i: StepIndex): StepState => (i === current ? 'current' : isStepDone(i, ctx, current) ? 'done' : 'later')

  return (
    <header className="relative z-10 flex h-16 shrink-0 items-center gap-5 border-b-[2.5px] border-ink bg-paper px-7">
      <div className="flex items-center gap-2">
        <PipMark size={32} />
        <span className="font-display text-[28px] leading-none">ghostOS</span>
      </div>

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
        <IconButton label={WORDS.history} pressed={state.view === 'activity'} onClick={() => navigate(state.view === 'activity' ? backView(ctx, someNotMoved) : 'activity')}>
          <HistoryIcon size={20} crisp />
        </IconButton>
        <IconButton label={WORDS.settings} pressed={state.view === 'settings'} onClick={() => navigate(state.view === 'settings' ? backView(ctx, someNotMoved) : 'settings')}>
          <SettingsIcon size={20} crisp />
        </IconButton>
      </div>
    </header>
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
    'inline-flex items-center gap-1.5 rounded-full border-[2.5px]',
    state === 'current' ? 'border-ink bg-hl-check py-px pl-1 pr-3' : 'border-transparent py-px pl-0.5 pr-2',
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

/** Where closing History / Settings returns to. */
function backView(ctx: StepContext, someNotMoved: boolean): View {
  if (ctx.phase === 'organizing' || someNotMoved) return 'report'
  if (ctx.hasApprovedPlan) return 'completion'
  if (ctx.hasScan && ctx.phase === 'reviewing') return 'files'
  return 'dashboard'
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
      {WORDS.offline.toLowerCase()}
    </span>
  )
}
