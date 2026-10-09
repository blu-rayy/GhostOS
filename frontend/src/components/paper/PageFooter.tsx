import type { ReactNode } from 'react'

/** 84px action bar under a screen: quiet action left, main action right. */
export function PageFooter({ left, right, className }: { left?: ReactNode; right?: ReactNode; className?: string }) {
  return (
    <footer className={`h-[84px] shrink-0 border-t-[2.5px] border-dashed border-ink bg-paper ${className ?? ''}`}>
      <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between gap-6 px-16">
        <div className="flex min-w-0 items-center gap-2">{left}</div>
        <div className="flex shrink-0 items-center gap-3.5">{right}</div>
      </div>
    </footer>
  )
}
