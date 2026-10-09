import { AlertTriangle, ArrowLeft, Info, ShieldCheck } from 'lucide-react'
import type { ProposedOperation } from '../../types/api'
import { Button } from '../ui/Button'
import { Banner, PathText } from '../ui/Layout'

export function ApprovalDialogBody({
  operations,
  reviewFolderCount,
  leftCount,
  collisions,
  rootName,
  usingFixtures,
  acknowledged,
  onAcknowledge,
}: {
  operations: ProposedOperation[]
  reviewFolderCount: number
  leftCount: number
  collisions: number
  rootName: string
  usingFixtures: boolean
  acknowledged: boolean
  onAcknowledge: (v: boolean) => void
}) {
  return (
    <div className="space-y-4">
      <p className="text-fg">
        Approving authorizes GhostOS to move <strong>{operations.length} files</strong> to the destinations below, inside <strong>{rootName}</strong>.
      </p>
      <div className="grid grid-cols-3 gap-2 text-center">
        {(
          [
            ['Will move', operations.length - reviewFolderCount, 'text-accent-hover'],
            ['To Needs Review/', reviewFolderCount, 'text-warning'],
            ['Stay in place', leftCount, 'text-fg-muted'],
          ] as const
        ).map(([label, n, cls]) => (
          <div key={label} className="rounded-md border border-line bg-surface-2 py-2">
            <div className={`tabular text-xl font-semibold ${cls}`}>{n}</div>
            <div className="text-2xs text-fg-subtle">{label}</div>
          </div>
        ))}
      </div>
      <div className="scroll-area max-h-40 rounded-md border border-line bg-bg/50 px-3 py-2">
        <ul className="space-y-1">
          {operations.map((m) => (
            <li key={m.file_id} className="flex min-w-0 items-center gap-2 text-xs">
              <PathText className="w-2/5 truncate text-fg-muted">{m.original_relative_path}</PathText>
              <span className="text-fg-subtle">→</span>
              <PathText className="min-w-0 flex-1 truncate">{m.destination_relative_path}</PathText>
            </li>
          ))}
        </ul>
      </div>
      {collisions > 0 && (
        <Banner tone="warning" icon={AlertTriangle}>
          {collisions} destination {collisions === 1 ? 'name was' : 'names were'} given a numeric suffix to avoid overwriting.
        </Banner>
      )}
      <ul className="space-y-1.5 text-xs text-fg-muted">
        <li className="flex gap-2">
          <ShieldCheck size={14} className="shrink-0 text-success" />
          Nothing is deleted. Duplicates are moved like any other file, never removed.
        </li>
        <li className="flex gap-2">
          <ShieldCheck size={14} className="shrink-0 text-success" />
          Every move stays inside the selected folder. Existing files are never overwritten.
        </li>
        <li className="flex gap-2">
          <ShieldCheck size={14} className="shrink-0 text-success" />
          The batch is logged. Undo restores files whose original location is still free.
        </li>
      </ul>
      {usingFixtures && (
        <Banner tone="info" icon={Info}>
          Fixture mode: the mock backend only pretends to move files. Nothing on this computer changes.
        </Banner>
      )}
      <label className="flex cursor-pointer items-start gap-2 rounded-md border border-line bg-surface-2 px-3 py-2.5">
        <input type="checkbox" className="mt-0.5 accent-[rgb(var(--accent))]" checked={acknowledged} onChange={(e) => onAcknowledge(e.target.checked)} />
        <span>I reviewed the plan and authorize these {operations.length} moves.</span>
      </label>
    </div>
  )
}

export function BackToReviewButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="ghost" icon={ArrowLeft} onClick={onClick}>
      Back to review
    </Button>
  )
}
