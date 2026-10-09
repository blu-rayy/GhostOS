import { useApp } from '../../state/AppState'
import { STEP_LABELS, WORDS } from '../../lib/copy'
import { STEPS, canOpenStep, isStepDone, stepForView, type StepContext } from '../../lib/steps'
import { Tag } from '../paper/Chip'
import { IconButton } from '../paper/Button'
import { HistoryIcon, LockIcon, SettingsIcon } from '../paper/icons'
import { PipMark } from '../pip/Pip'
import { cx } from '../ui/cx'
import { useServiceStates } from './useServiceStates'

/**
 * The only navigation: logo, the 4-step tracker, the offline pill, a
 * "demo data" tag when fixtures are in use, and History / Settings buttons.
 */
export function Header() {
  const { state, navigate, usingFixtures } = useApp()
  const ctx: StepContext = { phase: state.phase, hasScan: state.scan !== null, hasApprovedPlan: state.approvedPlan !== null }
  const current = stepForView(state.view)

  return (
    <header className="relative z-10 flex h-[68px] shrink-0 items-center gap-5 border-b-[2.5px] border-ink bg-paper px-6">
      <div className="flex items-center gap-2">
        <PipMark />
        <span className="font-display text-[28px] leading-none">ghostOS</span>
      </div>

      <nav aria-label="Steps" className="ml-2">
        <ol className="flex items-center gap-1.5">
          {STEPS.map((s, i) => {
            const label = STEP_LABELS[s.index]
            const isCurrent = current === s.index
            const done = !isCurrent && isStepDone(s.index, ctx)
            const can = canOpenStep(s.index, ctx)
            const later = !isCurrent && !done && !can
            return (
              <li key={label} className="flex items-center gap-1.5">
                {i > 0 && <span aria-hidden className={cx('w-6 border-t-[2.5px]', later ? 'border-dashed border-[#9a9a9a]' : 'border-solid border-ink')} />}
                <button
                  type="button"
                  disabled={!can && !isCurrent}
                  aria-current={isCurrent ? 'step' : undefined}
                  onClick={() => navigate(s.view)}
                  className={cx(
                    'inline-flex h-9 items-center gap-1.5 rounded-full border-[2.5px] pl-1 pr-3 text-lg',
                    isCurrent ? 'border-ink bg-hl-check' : 'border-transparent',
                    later ? 'text-graphite' : 'text-ink',
                    can && !isCurrent && 'hover:border-ink',
                  )}
                >
                  <span
                    aria-hidden
                    className={cx(
                      'inline-flex h-6 w-6 items-center justify-center rounded-full text-[15px] leading-none',
                      done ? 'bg-ink text-paper' : later ? 'border-[2.5px] border-dashed border-[#9a9a9a]' : 'border-[2.5px] border-ink bg-paper',
                    )}
                  >
                    {done ? '✓' : s.index + 1}
                  </span>
                  {label}
                  <span className="sr-only">{isCurrent ? ' (you are here)' : done ? ' (done)' : later ? ' (not yet)' : ''}</span>
                </button>
              </li>
            )
          })}
        </ol>
      </nav>

      <div className="ml-auto flex items-center gap-2.5">
        <OfflinePill />
        {usingFixtures && (
          <Tag tone="info" title="These are the bundled sample files, not files from your computer.">
            {WORDS.demoData.toLowerCase()}
          </Tag>
        )}
        <IconButton label={WORDS.history} pressed={state.view === 'activity'} onClick={() => navigate(state.view === 'activity' ? backView(state.phase) : 'activity')}>
          <HistoryIcon size={22} crisp />
        </IconButton>
        <IconButton label={WORDS.settings} pressed={state.view === 'settings'} onClick={() => navigate(state.view === 'settings' ? backView(state.phase) : 'settings')}>
          <SettingsIcon size={22} crisp />
        </IconButton>
      </div>
    </header>
  )
}

/** Where closing History / Settings returns to. */
function backView(phase: StepContext['phase']) {
  switch (phase) {
    case 'reviewing':
      return 'files' as const
    case 'organizing':
    case 'organized':
    case 'undoing':
    case 'undone':
      return 'completion' as const
    default:
      return 'dashboard' as const
  }
}

/**
 * "Offline · on this computer", backed by what /api/status reports
 * (external_requests == 0). Never claims more than was checked.
 */
function OfflinePill() {
  const svc = useServiceStates()
  const { state, usingFixtures } = useApp()
  if (svc.external > 0) {
    return (
      <span role="status" className="inline-flex items-center gap-1.5 rounded-full border-[2.5px] border-ink bg-hl-oops px-3 text-[17px] leading-7">
        <LockIcon size={16} crisp />
        {svc.external} outside {svc.external === 1 ? 'request' : 'requests'}
      </span>
    )
  }
  if (!usingFixtures && (state.statusError || !state.status)) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded-full border-[2.5px] border-dashed border-graphite px-3 text-[17px] leading-7 text-fg-muted"
        title={state.statusError ?? 'Checking the local service…'}
      >
        <LockIcon size={16} crisp />
        {state.statusError ? "can't check status" : 'checking…'}
      </span>
    )
  }
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border-[2.5px] border-ink px-3 text-[17px] leading-7"
      title={usingFixtures ? 'Demo mode: the sample data is bundled with the app. Nothing is sent anywhere.' : 'The local service reports no requests outside this computer.'}
    >
      <LockIcon size={16} crisp />
      {WORDS.offline.toLowerCase()}
    </span>
  )
}
