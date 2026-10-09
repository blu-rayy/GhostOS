import { Activity, FileSpreadsheet, Files, FolderTree, LayoutDashboard, Settings, type LucideIcon } from 'lucide-react';
import { useApp } from '../../state/AppState';
import type { View } from '../../types/ui';
import { cx } from '../ui/cx';
import { LocalStatusIndicator } from './LocalStatusIndicator';
import { Logo } from './Logo';

interface NavItem {
  id: View;
  label: string;
  icon: LucideIcon;
  /** Other views that highlight this item. */
  also?: View[];
}

const NAV: NavItem[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, also: ['folder', 'scanning'] },
  { id: 'files', label: 'Files', icon: Files },
  { id: 'plan', label: 'Organize', icon: FolderTree, also: ['completion'] },
  { id: 'report', label: 'Expense Reports', icon: FileSpreadsheet },
  { id: 'activity', label: 'Activity', icon: Activity },
];

export function Sidebar() {
  const { state, navigate, counts } = useApp();
  const badges: Partial<Record<View, number>> = {
    files: counts.needsReview,
  };

  const item = (n: NavItem) => {
    const active = state.view === n.id || n.also?.includes(state.view);
    const badge = badges[n.id];
    return (
      <li key={n.id}>
        <button
          type="button"
          onClick={() => navigate(n.id)}
          aria-current={active ? 'page' : undefined}
          className={cx(
            'group relative flex h-8 w-full items-center gap-2.5 rounded-md px-2.5 text-sm transition-colors duration-[120ms]',
            active ? 'bg-surface-3 font-medium text-fg' : 'text-fg-muted hover:bg-surface-2 hover:text-fg',
          )}
        >
          {active && <span className="absolute -left-3 top-1.5 h-5 w-0.5 rounded-full bg-accent" aria-hidden />}
          <n.icon size={16} className={active ? 'text-accent-hover' : 'text-fg-subtle group-hover:text-fg-muted'} aria-hidden />
          <span className="flex-1 text-left">{n.label}</span>
          {badge ? (
            <span className="tabular rounded-sm bg-warning/15 px-1.5 text-2xs font-semibold text-warning" title={`${badge} need review`}>
              {badge}
            </span>
          ) : null}
        </button>
      </li>
    );
  };

  return (
    <aside className="flex w-[216px] shrink-0 flex-col border-r border-line bg-surface-1">
      <div className="flex items-center gap-2.5 px-4 pb-4 pt-4">
        <Logo />
        <div className="min-w-0">
          <div className="text-base font-semibold leading-5 tracking-tight">GhostOS</div>
          <div className="text-2xs text-fg-subtle">Local document workspace</div>
        </div>
      </div>
      <nav aria-label="Main" className="flex-1 px-3">
        <ul className="space-y-0.5">{NAV.map(item)}</ul>
        <div className="my-3 border-t border-line" />
        <ul>{item({ id: 'settings', label: 'Settings', icon: Settings })}</ul>
      </nav>
      <div className="p-3">
        <LocalStatusIndicator onOpen={() => navigate('settings')} />
      </div>
    </aside>
  );
}
