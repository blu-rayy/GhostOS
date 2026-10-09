import { useRef } from 'react'
import { PaperButton } from '../components/paper/Button'
import { PaperDialog } from '../components/paper/PaperDialog'
import { Pip } from '../components/pip/Pip'
import { files } from '../lib/totals'
import { reviewChoiceGroups } from '../lib/viewModel'
import { useApp } from '../state/AppState'

/**
 * Review choice (docs/design/review-choice-popup.md): right after reading, when files block Move,
 * check them one by one or set them all aside in Uncategorized/ (backend partial mode). Shown
 * once per scan. Esc and closing mean "one by one", which changes nothing.
 */
export function ReviewChoiceDialog() {
  const { state, chooseReview } = useApp()
  const oneByOne = useRef<HTMLButtonElement>(null)
  const g = reviewChoiceGroups(state.scan?.documents ?? [])
  // The plan's count is the source of truth; if the grouping disagrees, show only the total.
  const total = state.plan?.blocking_review_count ?? g.total
  const grouped = g.total === total
  const lines = [
    [g.confirm, g.confirm === 1 ? 'total or date to confirm' : 'totals or dates to confirm'],
    [g.notReceipts, g.notReceipts === 1 ? "paper that isn't a receipt (statement, ID, unclear)" : "papers that aren't receipts (statements, IDs, unclear)"],
    [g.suspicious, g.suspicious === 1 ? 'file with suspicious text' : 'files with suspicious text'],
  ] as const
  const open = state.reviewChoicePending && state.view === 'files' && total > 0

  return (
    <PaperDialog open={open} onCancel={() => void chooseReview('one-by-one')} labelledBy="review-choice-title" describedBy="review-choice-desc" initialFocus={oneByOne}>
      <div className="px-8 pb-6 pt-6">
        <div className="flex items-start gap-4">
          <div className="min-w-0 flex-1">
            <h2 id="review-choice-title" className="m-0 font-display text-[36px] font-normal leading-tight">
              {files(total)} need a look
            </h2>
            <p id="review-choice-desc" className="m-0 mt-2 text-[18px] leading-7">
              Pip wasn't sure about these. You can check them now, or set them aside in{' '}
              <span className="rounded-[6px] bg-path-box px-1.5 font-mono text-[15px]">Uncategorized/</span> and look later. Set-aside files aren't counted in your totals, and nothing moves until you press Move.
            </p>
          </div>
          <Pip mood="suspicious" size={86} decorative className="shrink-0" />
        </div>
        {grouped && (
          <ul className="m-0 mt-4 list-none space-y-1 rounded-[12px] border-[2px] border-dashed border-ink px-4 py-2 text-[17px]">
            {lines
              .filter(([n]) => n > 0)
              .map(([n, text]) => (
                <li key={text} className="flex items-baseline gap-3">
                  <span className="w-8 text-right font-mono text-[16px] font-bold">{n}</span>
                  <span>{text}</span>
                </li>
              ))}
          </ul>
        )}
        <div className="mt-6 flex items-center justify-end gap-4">
          <PaperButton variant="secondary" size="sm" onClick={() => void chooseReview('set-aside')}>
            Set all {total} aside
          </PaperButton>
          <PaperButton ref={oneByOne} variant="primary" size="sm" onClick={() => void chooseReview('one-by-one')}>
            Review them one by one
          </PaperButton>
        </div>
      </div>
    </PaperDialog>
  )
}
