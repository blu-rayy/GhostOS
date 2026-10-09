import { AppShell } from './components/shell/AppShell';
import { ActivityPage } from './pages/ActivityPage';
import { CompletionPage } from './pages/CompletionPage';
import { DashboardPage } from './pages/DashboardPage';
import { FilesPage } from './pages/FilesPage';
import { FolderSelectPage } from './pages/FolderSelectPage';
import { PlanPage } from './pages/PlanPage';
import { ReportPage } from './pages/ReportPage';
import { ScanningPage } from './pages/ScanningPage';
import { SettingsPage } from './pages/SettingsPage';
import { AppStateProvider, useApp } from './state/AppState';

function CurrentView() {
  const { state } = useApp();
  switch (state.view) {
    case 'dashboard':
      return <DashboardPage />;
    case 'folder':
      return <FolderSelectPage />;
    case 'scanning':
      return <ScanningPage />;
    case 'files':
      return <FilesPage />;
    case 'plan':
      return <PlanPage />;
    case 'report':
      return <ReportPage />;
    case 'activity':
      return <ActivityPage />;
    case 'completion':
      return <CompletionPage />;
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
