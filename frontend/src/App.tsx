import { HistoryPanel } from './components/panels/HistoryPanel';
import { SettingsPanel } from './components/panels/SettingsPanel';
import { AppShell } from './components/shell/AppShell';
import { SidePanel } from './components/shell/SidePanel';
import { FilesPage } from './pages/FilesPage';
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
    case 'completion':
      // Step 4 · Done (paper redesign).
      return <DonePage />;
  }
}

/** History and Settings open as side panels over the current step. */
function Panels() {
  const { state, dispatch } = useApp();
  const close = () => dispatch({ type: 'patch', patch: { panel: null } });
  return (
    <>
      <SidePanel open={state.panel === 'history'} title="History" onClose={close}>
        <HistoryPanel />
      </SidePanel>
      <SidePanel open={state.panel === 'settings'} title="Settings" onClose={close}>
        <SettingsPanel />
      </SidePanel>
    </>
  );
}

export default function App() {
  return (
    <AppStateProvider>
      <AppShell>
        <CurrentView />
        <Panels />
      </AppShell>
    </AppStateProvider>
  );
}
