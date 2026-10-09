import {
  AlertTriangle,
  ArrowRightLeft,
  CheckCircle2,
  Download,
  FileSearch,
  FileSpreadsheet,
  FolderOpen,
  PencilLine,
  PlayCircle,
  ShieldCheck,
  Undo2,
  UserCheck,
  XCircle,
  type LucideIcon,
} from 'lucide-react';
import { formatDateTime, formatTime } from '../../lib/format';
import type { ActivityEvent, ActivityType } from '../../types/ui';
import { cx } from '../ui/cx';

const ICON: Record<ActivityType, LucideIcon> = {
  folder_selected: FolderOpen,
  scan_started: PlayCircle,
  document_analyzed: FileSearch,
  scan_completed: CheckCircle2,
  scan_failed: XCircle,
  record_corrected: PencilLine,
  record_reviewed: UserCheck,
  plan_approved: ShieldCheck,
  file_moved: ArrowRightLeft,
  report_generated: FileSpreadsheet,
  report_exported: Download,
  undo_started: Undo2,
  undo_completed: Undo2,
  undo_conflict: AlertTriangle,
  action_failed: XCircle,
};

const EVENT_LABEL: Record<ActivityType, string> = {
  folder_selected: 'Folder selected',
  scan_started: 'Scan started',
  document_analyzed: 'Document analyzed',
  scan_completed: 'Scan completed',
  scan_failed: 'Scan failed',
  record_corrected: 'Record corrected',
  record_reviewed: 'Record reviewed',
  plan_approved: 'Plan approved',
  file_moved: 'File moved',
  report_generated: 'Report generated',
  report_exported: 'Report exported',
  undo_started: 'Undo started',
  undo_completed: 'Undo completed',
  undo_conflict: 'Undo conflict',
  action_failed: 'Action failed',
};

const LEVEL = {
  info: 'text-fg-muted bg-surface-3 border-line-strong',
  success: 'text-success bg-success/12 border-success/30',
  warning: 'text-warning bg-warning/12 border-warning/35',
  error: 'text-danger bg-danger/12 border-danger/35',
};

export function ActivityTimeline({ events, compact = false, onSelectDoc }: { events: ActivityEvent[]; compact?: boolean; onSelectDoc?: (id: string) => void }) {
  return (
    <ol className="relative">
      {events.map((e, i) => {
        const Icon = ICON[e.type];
        const last = i === events.length - 1;
        return (
          <li key={e.id} className="relative flex gap-3 pb-3 last:pb-0">
            {!last && <span className="absolute left-[13px] top-7 h-[calc(100%-24px)] w-px bg-line" aria-hidden />}
            <span className={cx('z-[1] flex h-7 w-7 shrink-0 items-center justify-center rounded-full border', LEVEL[e.level])}>
              <Icon size={13} aria-hidden />
            </span>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex items-baseline justify-between gap-3">
                <div className="min-w-0 truncate text-sm">
                  {!compact && <span className="mr-2 text-2xs font-semibold uppercase tracking-wide text-fg-subtle">{EVENT_LABEL[e.type]}</span>}
                  <span className="text-fg">{e.title}</span>
                </div>
                <time dateTime={e.at} className="tabular shrink-0 text-2xs text-fg-subtle">
                  {compact ? formatTime(e.at) : formatDateTime(e.at)}
                </time>
              </div>
              {e.detail && <div className={cx('mt-0.5 truncate text-xs text-fg-muted', !compact && 'whitespace-normal')}>{e.detail}</div>}
              {!compact && e.fileId && onSelectDoc && (
                <button type="button" className="mt-1 text-2xs text-accent-hover hover:underline" onClick={() => onSelectDoc(e.fileId!)}>
                  Open record
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}
