import { AppShell } from './components/shell/AppShell';
import { ActivityPage } from './pages/ActivityPage';
import { FilesPage } from './pages/FilesPage';
import { SettingsPage } from './pages/SettingsPage';
import { DonePage } from './pages/done/DonePage';
import { StartPage } from './pages/start/StartPage';
import { TotalsPage } from './pages/totals/TotalsPage';
import { AppStateProvider, useApp } from './state/AppState';

function CurrentView() {
  const { state } = useApp();
  switch (state.view) {
    // Step 1 · Start (paper redesign): one page, state picked from the session phase.
    case 'dashboard':
    case 'folder':
    case 'scanning':
      return <StartPage />;
    case 'files':
      return <FilesPage />;
    // Step 3 · Totals (paper redesign) replaces the old plan and report screens.
    case 'plan':
    case 'report':
      return <TotalsPage />;
    case 'activity':
      return <ActivityPage />;
    case 'completion':
      // Step 4 · Done (paper redesign).
      return <DonePage />;
    case 'settings':
      return <SettingsPage />;
  }
}

export default function App() {
  return (
    <AppStateProvider>
      <AppShell>
        <CurrentView />
      </AppShell>
    </AppStateProvider>
  );
}
