import type { CSSProperties, ReactNode } from 'react';
import { InkDefs } from '../pip/Pip';
import { Header } from './Header';
import { useApp } from '../../state/AppState';

/** Header-only shell (no sidebar). Minimum supported window width is 1100px. */
export function AppShell({ children }: { children: ReactNode }) {
  const { platform } = useApp();
  return (
    // --window-bar-h: how much the desktop title bar takes, so overlays (side panels) start below it.
    <div className="flex h-full min-w-[1100px] flex-col" style={{ '--window-bar-h': platform.capabilities.runtime === 'electron' ? '32px' : '0px' } as CSSProperties}>
      <InkDefs />
      {platform.capabilities.runtime === 'electron' && <WindowBar />}
      <Header />
      <main className="paper-grid flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}

/**
 * Frameless window's own title bar: an empty, draggable strip of paper (the header below
 * already shows the ghostOS logo) with hand-drawn minimize / maximize / close buttons.
 */
function WindowBar() {
  const controls = window.ghostos?.windowControls;
  return (
    <div className="flex h-8 shrink-0 items-center bg-paper text-ink" style={{ WebkitAppRegion: 'drag' } as CSSProperties}>
      <div className="min-w-0 flex-1" aria-hidden="true" />
      <div className="flex h-full items-center gap-1 pr-2" style={{ WebkitAppRegion: 'no-drag' } as CSSProperties}>
        <WindowButton label="Minimize" onClick={() => controls?.minimize()}>
          <path d="M6 12.5h12" />
        </WindowButton>
        <WindowButton label="Maximize" onClick={() => controls?.toggleMaximize()}>
          <rect x="6" y="6" width="12" height="12" rx="2.5" />
        </WindowButton>
        <WindowButton label="Close" close onClick={() => controls?.close()}>
          <path d="M7 7l10 10M17 7 7 17" />
        </WindowButton>
      </div>
    </div>
  );
}

/** Ink icon on paper; pencil-grey patch on hover, highlighter pink for close. */
function WindowButton({ label, close, onClick, children }: { label: string; close?: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={`flex h-[26px] w-10 items-center justify-center rounded-[9px] border-2 border-transparent transition-colors duration-100 focus-visible:border-ink focus-visible:outline-none ${close ? 'hover:border-ink hover:bg-hl-oops active:bg-[#ff9a9a]' : 'hover:bg-pencil active:bg-[#e4e4e0]'}`}
      style={{ WebkitAppRegion: 'no-drag' } as CSSProperties}
    >
      <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        {children}
      </svg>
    </button>
  );
}
