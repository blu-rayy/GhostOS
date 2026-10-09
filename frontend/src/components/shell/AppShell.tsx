import type { ReactNode } from 'react';
import { InkDefs } from '../pip/Pip';
import { Header } from './Header';

/** Header-only shell (no sidebar). Minimum supported window width is 1100px. */
export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-full min-w-[1100px] flex-col">
      <InkDefs />
      <Header />
      <main className="paper-grid flex min-h-0 flex-1 flex-col">{children}</main>
    </div>
  );
}
