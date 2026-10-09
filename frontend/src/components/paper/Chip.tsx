import type { ReactNode } from 'react'
import { cx } from '../ui/cx'

/**
 * Status chips: highlighter colour + a word, never colour alone.
 * Categories (invoice, receipt, other) are plain words and do not use chips.
 */
export type ChipTone = 'check' | 'done' | 'oops' | 'info' | 'plain' | 'muted' | 'ink'

const TONE: Record<ChipTone, string> = {
  check: 'border-solid border-ink bg-hl-check',
  done: 'border-solid border-ink bg-hl-done',
  oops: 'border-solid border-ink bg-hl-oops',
  info: 'border-solid border-ink bg-hl-info',
  plain: 'border-solid border-ink bg-paper',
  muted: 'border-dashed border-graphite text-fg-muted',
  ink: 'border-solid border-ink bg-ink text-paper',
}

export function Chip({ tone = 'plain', children, className, title }: { tone?: ChipTone; children: ReactNode; className?: string; title?: string }) {
  return (
    <span title={title} className={cx('inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full border-[2.5px] px-3 text-[17px] leading-6', TONE[tone], className)}>
      {children}
    </span>
  )
}

/** Small tag used in the header, e.g. "demo data". */
export function Tag({ tone = 'info', children, title }: { tone?: ChipTone; children: ReactNode; title?: string }) {
  return (
    <Chip tone={tone} title={title} className="px-2.5 text-base">
      {children}
    </Chip>
  )
}
