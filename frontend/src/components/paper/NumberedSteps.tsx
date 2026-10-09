import type { ReactNode } from 'react'
import { cx } from '../ui/cx'

/** Circled 1-2-3 list ("what happens next", "how to fix it"). */
export function NumberedSteps({ steps, className }: { steps: ReactNode[]; className?: string }) {
  return (
    <ol className={cx('m-0 flex list-none flex-col gap-3 p-0', className)}>
      {steps.map((step, i) => (
        <li key={i} className="flex items-start gap-3 text-[20px] leading-[1.3]">
          <span aria-hidden className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border-[2.5px] border-ink text-[17px] leading-none">
            {i + 1}
          </span>
          <span>{step}</span>
        </li>
      ))}
    </ol>
  )
}
