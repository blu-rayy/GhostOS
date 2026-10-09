import { useState } from 'react'
import { useApp } from '../../state/AppState'
import type { BatchResult, PlanPreview } from '../../types/api'
import { PIP_LINES } from '../../lib/copy'
import { files } from '../../lib/totals'
import { basename } from '../../lib/viewModel'
import { PaperButton } from '../../components/paper/Button'
import { Chip } from '../../components/paper/Chip'
import { PageFooter } from '../../components/paper/PageFooter'
import { PaperCard } from '../../components/paper/PaperCard'
import { StickyNote } from '../../components/paper/StickyNote'
import { PipWithBubble } from '../../components/pip/Pip'
import { PutBackConfirm } from '../done/DonePage'

/**
 * 3d · Some files didn't move (BatchResult.failed[] not empty).
 * Wording stays "didn't reach their new folder" until Developer 1 confirms that a failed
 * move leaves the original untouched (R2). No retry button until a retry endpoint exists (R3).
 */
export function MoveProblems({ batch, plan, folderName }: { batch: BatchResult; plan: PlanPreview; folderName: string }) {
  const { state, navigate, undoBatch } = useApp()
  const [confirmOpen, setConfirmOpen] = useState(false)
  const k = batch.failed.length
  const moved = batch.moved

  const nameOf = (fileId: string) => {
    const path = state.scan?.documents.find((d) => d.file_id === fileId)?.relative_path ?? plan.operations.find((op) => op.file_id === fileId)?.original_relative_path
    return path ? basename(path) : fileId
  }

  return (
    <>
      <div className="mx-auto grid min-h-0 w-full max-w-[1366px] flex-1 grid-cols-[360px_minmax(0,1fr)] items-center gap-10 px-16 pb-5 pt-[26px]">
        <PipWithBubble mood="sigh" line={PIP_LINES.refused(k)} size={240} tailOffset={110} />
        <div className="flex min-h-0 min-w-0 flex-col py-2">
          <p className="m-0 text-[20px] text-graphite">{folderName}</p>
          <h1 className="m-0 font-display text-[52px] font-normal leading-tight">
            {moved} moved, {k} didn't.
          </h1>
          <StickyNote tone="pink" alert tilt={-0.8} className="mt-4 max-w-[640px] px-4 py-3">
            <p className="m-0 text-[19px] leading-6">{k === 1 ? "This file didn't reach its new folder." : `These ${k} files didn't reach their new folder.`}</p>
          </StickyNote>
          <PaperCard as="section" aria-label="Files that didn't move" className="mt-5 min-h-0 max-w-[760px] overflow-y-auto px-5 py-2">
            <ul className="m-0 list-none p-0">
              {batch.failed.map((f) => (
                <li key={f.file_id} className="flex items-center gap-4 border-b-[1.5px] border-dashed border-pencil py-2.5 last:border-b-0">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-[15px]">{nameOf(f.file_id)}</span>
                    <span className="block text-[17px] text-graphite">{f.error}</span>
                  </span>
                  <Chip tone="oops" size="sm">
                    didn't move
                  </Chip>
                </li>
              ))}
            </ul>
          </PaperCard>
          {moved > 0 && (
            <div className="mt-5 flex items-center gap-4">
              <PaperButton variant="secondary" size="sm" onClick={() => setConfirmOpen(true)}>
                Put all {moved} back
              </PaperButton>
              <span className="text-[17px] text-graphite">undo this whole move, like it never happened</span>
            </div>
          )}
        </div>
      </div>
      <PageFooter
        className="!h-[72px]"
        left={<span className="text-[17px] text-graphite">the {files(moved)} that moved are in their new folders</span>}
        right={
          <PaperButton variant="primary" onClick={() => navigate('completion')}>
            Leave the {k} where they are →
          </PaperButton>
        }
      />
      <PutBackConfirm
        open={confirmOpen}
        n={moved}
        savedCsv={state.activity.some((e) => e.type === 'report_exported')}
        onCancel={() => setConfirmOpen(false)}
        onConfirm={() => {
          setConfirmOpen(false)
          // Done shows the undo result (put back / some stayed).
          navigate('completion')
          void undoBatch()
        }}
      />
    </>
  )
}
