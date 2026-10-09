import type { ReactNode } from 'react'
import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDashed,
  FileQuestion,
  FileText,
  Folder,
  Receipt,
  Sparkles,
  UserCheck,
  XCircle,
  type LucideIcon,
} from 'lucide-react'
import type { Category, ReportRowStatus } from '../../types/api'
import type { RowStatus } from '../../types/ui'
import { cx } from './cx'

export type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info'

const TONE: Record<Tone, string> = {
  neutral: 'bg-surface-3 text-fg-muted border-line-strong',
  accent: 'bg-accent/15 text-accent-hover border-accent/30',
  success: 'bg-success/12 text-success border-success/30',
  warning: 'bg-warning/12 text-warning border-warning/35',
  danger: 'bg-danger/12 text-danger border-danger/35',
  info: 'bg-info/12 text-info border-info/30',
}

export function Badge({ tone = 'neutral', icon: Icon, children, className, title }: { tone?: Tone; icon?: LucideIcon; children: ReactNode; className?: string; title?: string }) {
  return (
    <span
      title={title}
      className={cx('inline-flex h-5 shrink-0 items-center gap-1 whitespace-nowrap rounded-sm border px-1.5 text-2xs font-medium', TONE[tone], className)}
    >
      {Icon && <Icon size={12} strokeWidth={2.25} aria-hidden />}
      {children}
    </span>
  )
}

const CATEGORY: Record<Category, { label: string; tone: Tone; icon: LucideIcon }> = {
  invoice: { label: 'Invoice', tone: 'accent', icon: FileText },
  receipt: { label: 'Receipt', tone: 'info', icon: Receipt },
  other: { label: 'Other', tone: 'neutral', icon: Folder },
  uncertain: { label: 'Uncertain', tone: 'warning', icon: FileQuestion },
}

export function CategoryBadge({ category }: { category: Category | null }) {
  if (!category) return <Badge tone="neutral" icon={CircleDashed}>Unknown</Badge>
  const c = CATEGORY[category]
  return (
    <Badge tone={c.tone} icon={c.icon}>
      {c.label}
    </Badge>
  )
}

const STATUS: Record<RowStatus, { label: string; tone: Tone; icon: LucideIcon; title: string }> = {
  extracted: { label: 'Extracted', tone: 'neutral', icon: Sparkles, title: 'Extracted locally with no review flags. Not checked by a person.' },
  needs_review: { label: 'Needs review', tone: 'warning', icon: AlertTriangle, title: 'Has review flags. Blocks approval until reviewed.' },
  reviewed: { label: 'Reviewed', tone: 'success', icon: UserCheck, title: 'Confirmed or corrected by you.' },
  failed: { label: 'Failed', tone: 'danger', icon: XCircle, title: 'No usable classification. Filed under Needs Review/.' },
  skipped: { label: 'Skipped', tone: 'neutral', icon: Ban, title: 'Not processed (unsupported, too large, no text, or a link).' },
}

export function ReviewStatusBadge({ status }: { status: RowStatus }) {
  const s = STATUS[status]
  return (
    <Badge tone={s.tone} icon={s.icon} title={s.title}>
      {s.label}
    </Badge>
  )
}

const ROW: Record<ReportRowStatus, { label: string; tone: Tone; icon: LucideIcon }> = {
  accepted: { label: 'Accepted', tone: 'success', icon: CheckCircle2 },
  needs_review: { label: 'Needs review', tone: 'warning', icon: AlertTriangle },
}

export function ReportStatusBadge({ status, title }: { status: ReportRowStatus; title?: string }) {
  const s = ROW[status]
  return (
    <Badge tone={s.tone} icon={s.icon} title={title}>
      {s.label}
    </Badge>
  )
}

export function FixtureTag({ className }: { className?: string }) {
  return (
    <Badge tone="info" className={className} title="These are the bundled sample files, not files from your computer.">
      Demo data
    </Badge>
  )
}
