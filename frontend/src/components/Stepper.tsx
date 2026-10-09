export type Step = 'select' | 'review' | 'plan'

const STEPS: { id: Step; label: string; hint: string }[] = [
  { id: 'select', label: 'Choose folder', hint: 'Pick a folder and scan it' },
  { id: 'review', label: 'Review documents', hint: 'Check evidence and fix flags' },
  { id: 'plan', label: 'Preview & approve', hint: 'Check moves and the report, then approve' },
]

interface Props {
  current: Step
  reachable: Set<Step>
  onSelect: (step: Step) => void
}

export function Stepper({ current, reachable, onSelect }: Props) {
  return (
    <nav className="stepper" aria-label="Workflow steps">
      <ol>
        {STEPS.map((s, i) => (
          <li key={s.id}>
            <button
              className={`step ${s.id === current ? 'step-current' : ''}`}
              disabled={!reachable.has(s.id)}
              aria-current={s.id === current ? 'step' : undefined}
              onClick={() => onSelect(s.id)}
            >
              <span className="step-num">{i + 1}</span>
              <span className="step-text">
                <span className="step-label">{s.label}</span>
                <span className="step-hint">{s.hint}</span>
              </span>
            </button>
          </li>
        ))}
      </ol>
    </nav>
  )
}
