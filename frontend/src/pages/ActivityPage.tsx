import { useMemo, useState } from 'react';
import { FolderOpen, History, Info, RotateCcw, ServerCrash } from 'lucide-react';
import { ActivityTimeline } from '../components/activity/ActivityTimeline';
import { Button } from '../components/ui/Button';
import { Banner, EmptyState, PageHeader } from '../components/ui/Layout';
import { SearchInput, Segmented } from '../components/ui/Toolbar';
import { useApp } from '../state/AppState';
import type { ActivityType } from '../types/ui';

type Group = 'all' | 'scan' | 'review' | 'files' | 'undo';
const GROUPS: Record<Exclude<Group, 'all'>, ActivityType[]> = {
  scan: ['folder_selected', 'scan_started', 'document_analyzed', 'scan_completed', 'scan_failed'],
  review: ['record_corrected', 'record_reviewed'],
  files: ['plan_approved', 'file_moved', 'report_generated', 'report_exported'],
  undo: ['undo_started', 'undo_completed', 'undo_conflict', 'action_failed'],
};

export function ActivityPage() {
  const { state, selectDoc, navigate, dispatch } = useApp();
  const [group, setGroup] = useState<Group>('all');
  const [query, setQuery] = useState('');
  const events = state.activity;

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    return events.filter((e) => {
      if (group !== 'all' && !GROUPS[group].includes(e.type)) return false;
      return !q || `${e.title} ${e.detail ?? ''}`.toLowerCase().includes(q);
    });
  }, [events, group, query]);
  const count = (g: Exclude<Group, 'all'>) => events.filter((e) => GROUPS[g].includes(e.type)).length;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <PageHeader title="Activity" breadcrumbs={['Activity']} description="An auditable, chronological record of everything GhostOS did in this session, newest first." />

      {state.simulateActivityError ? (
        <EmptyState
          icon={ServerCrash}
          title="Activity log could not be loaded"
          className="flex-1"
          actions={
            <Button icon={RotateCcw} onClick={() => dispatch({ type: 'patch', patch: { simulateActivityError: false } })}>
              Retry
            </Button>
          }
        >
          Simulated failure (Settings → Demo scenarios). Your files are unaffected; events are still recorded and appear when the log loads.
        </EmptyState>
      ) : events.length === 0 ? (
        <EmptyState icon={History} title="No activity yet" className="flex-1" actions={<Button icon={FolderOpen} onClick={() => navigate('folder')}>Select Folder</Button>}>
          Selecting a folder, scanning, correcting records, approving a plan and undoing a batch are all recorded here.
        </EmptyState>
      ) : (
        <>
          <div className="flex shrink-0 flex-wrap items-center gap-2 px-6 py-3">
            <SearchInput value={query} onChange={setQuery} placeholder="Search activity" />
            <Segmented<Group>
              label="Event type"
              value={group}
              onChange={setGroup}
              options={[
                { value: 'all', label: 'All', count: events.length },
                { value: 'scan', label: 'Scan', count: count('scan') },
                { value: 'review', label: 'Review', count: count('review') },
                { value: 'files', label: 'Files & reports', count: count('files') },
                { value: 'undo', label: 'Undo & errors', count: count('undo') },
              ]}
            />
          </div>
          <div className="px-6">
            <Banner tone="neutral" icon={Info}>
              Session log kept by this window only. There is no activity endpoint in the API contract yet, so the log resets when the app restarts.
            </Banner>
          </div>
          <div className="scroll-area mx-6 my-3 min-h-0 flex-1 rounded-lg border border-line bg-surface-1 px-5 py-4">
            {visible.length === 0 ? (
              <EmptyState icon={History} title="No matching events" />
            ) : (
              <ActivityTimeline
                events={visible}
                onSelectDoc={(id) => {
                  selectDoc(id);
                  navigate('files');
                }}
              />
            )}
          </div>
        </>
      )}
    </div>
  );
}
