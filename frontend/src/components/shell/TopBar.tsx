import { Check, FolderOpen, Lock } from 'lucide-react';
import { useApp } from '../../state/AppState';
import type { SessionPhase, View } from '../../types/ui';
import { FixtureTag } from '../ui/Badge';
import { cx } from '../ui/cx';

const STEPS: { label: string; view: View }[] = [
  { label: 'Select', view: 'folder' },
  { label: 'Scan', view: 'scanning' },
  { label: 'Review', view: 'files' },
  { label: 'Approve', view: 'plan' },
  { label: 'Done', view: 'completion' },
];

function stepIndex(phase: SessionPhase): number {
  switch (phase) {
    case 'idle':
      return -1;
    case 'folder_selected':
      return 0;
    case 'scanning':
    case 'scan_failed':
      return 1;
    case 'reviewing':
      return 2;
    case 'organizing':
      return 3;
    default:
      return 4;
  }
}

/** Session context strip: current folder, workflow progress and the local-only promise. */
export function TopBar() {
  const { state, navigate, usingFixtures } = useApp();
  const current = stepIndex(state.phase);
  const reachable = (i: number) => {
    if (i === 0) return true;
    if (i === 1) return current >= 1;
    if (i === 2 || i === 3) return state.scan !== null && state.phase !== 'scanning';
    return state.approvedPlan !== null;
  };

  return (
    <div className="flex h-11 shrink-0 items-center gap-4 border-b border-line bg-surface-1/60 px-6">
      <div className="flex min-w-0 items-center gap-2 text-sm">
        <FolderOpen size={15} className="shrink-0 text-fg-subtle" aria-hidden />
        {state.folder ? (
          <>
            <span className="truncate font-medium" title={state.folder.path ?? state.folder.name}>
              {state.folder.name}
            </span>
            {usingFixtures && <FixtureTag />}
          </>
        ) : (
          <span className="text-fg-subtle">No folder selected</span>
        )}
      </div>

      {current >= 0 && (
        <ol className="ml-auto hidden items-center gap-1 lg:flex" aria-label="Workflow progress">
          {STEPS.map((s, i) => {
            const done = i < current || (i === 4 && current === 4 && state.phase !== 'organizing');
            const active = i === current;
            const can = reachable(i);
            return (
              <li key={s.label} className="flex items-center gap-1">
                {i > 0 && <span className={cx('h-px w-4', i <= current ? 'bg-accent/60' : 'bg-line-strong')} aria-hidden />}
                <button
                  type="button"
                  disabled={!can}
                  onClick={() => navigate(s.view)}
                  className={cx(
                    'flex h-6 items-center gap-1.5 rounded-full px-2 text-2xs font-medium transition-colors duration-[120ms]',
                    active ? 'bg-accent/15 text-accent-hover' : done ? 'text-fg-muted hover:text-fg' : 'text-fg-subtle',
                    can && !active && 'hover:bg-surface-3',
                  )}
                >
                  <span
                    className={cx(
                      'flex h-4 w-4 items-center justify-center rounded-full text-[10px]',
                      done ? 'bg-accent text-accent-fg' : active ? 'border border-accent text-accent-hover' : 'border border-line-strong',
                    )}
                  >
                    {done ? <Check size={10} strokeWidth={3} /> : i + 1}
                  </span>
                  {s.label}
                </button>
              </li>
            );
          })}
        </ol>
      )}

      <div className={cx('flex items-center gap-1.5 text-2xs text-fg-subtle', current < 0 && 'ml-auto')} title="GhostOS never sends documents to a cloud service.">
        <Lock size={12} aria-hidden />
        Processed on this device
      </div>
    </div>
  );
}
