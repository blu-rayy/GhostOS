import { PIP_LINES } from '../../lib/copy'
import { files } from '../../lib/totals'
import { PaperButton } from '../../components/paper/Button'
import { HatchProgress } from '../../components/paper/HatchProgress'
import { PageFooter } from '../../components/paper/PageFooter'
import { PaperCard } from '../../components/paper/PaperCard'
import { PipWithBubble } from '../../components/pip/Pip'

/**
 * 3c · Moving, fallback version: approve only returns when every move is done, so there
 * are no counts and no "just moved" list, only an indeterminate bar. Never fake progress.
 * The counted version and "stop after this file" wait for the batch-progress and cancel
 * endpoints (R1, R4 in docs/frontend-api-handoff.md).
 */
export function MovingScreen({ total, moved, folderName, onDone }: { total: number; moved?: number; folderName: string; onDone?: () => void }) {
  // `moved` set: the move has finished; a short "All moved." beat before Done (scene change 3 -> 4).
  const finished = moved !== undefined
  return (
    <>
      <div className="mx-auto grid min-h-0 w-full max-w-[1366px] flex-1 grid-cols-[360px_minmax(0,1fr)] items-center gap-10 px-16 pb-5 pt-[26px]">
        <PipWithBubble mood="carrying" line={finished ? PIP_LINES.setDown : PIP_LINES.carrying(total)} size={260} tailOffset={110} />
        <div className="min-w-0">
          <p className="m-0 text-[20px] text-graphite">{folderName}</p>
          <h1 key={finished ? 'done' : 'moving'} className={`m-0 font-display text-[52px] font-normal leading-tight ${finished ? 'animate-rise-in' : ''}`}>
            {finished ? 'All moved.' : 'Moving your files…'}
          </h1>
          <PaperCard className="mt-6 max-w-[620px] px-6 py-5">
            <p className="m-0 text-[20px]" role="status">
              {finished ? `✓ moved ${files(moved)}` : `moving ${files(total)}…`}
            </p>
            <HatchProgress value={finished ? 1 : null} label="Moving files" className="mt-3" />
          </PaperCard>
        </div>
      </div>
      <PageFooter
        className="!h-[72px]"
        left={
          <span className="flex items-center gap-2 text-[17px]">
            <InfoGlyph />
            {finished ? 'Everything is in its new folder.' : 'Keep GhostOS open until this finishes.'}
          </span>
        }
        right={
          finished ? (
            <PaperButton variant="primary" onClick={onDone}>
              Done →
            </PaperButton>
          ) : (
            <PaperButton variant="primary" disabled disabledReason="opens when moving is done" reasonId="moving-done-reason">
              Done →
            </PaperButton>
          )
        }
      />
    </>
  )
}

function InfoGlyph() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" aria-hidden focusable="false" className="shrink-0">
      <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6M12 7.5v.5" />
      </g>
    </svg>
  )
}
