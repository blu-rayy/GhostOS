import type { ButtonHTMLAttributes, ReactNode } from 'react'
import { cx } from '../ui/cx'

/**
 * Buttons from the component sheet.
 * - primary: ink fill, one per screen, bottom-right.
 * - secondary: paper with ink outline.
 * - careful: pink highlighter (e.g. "Put files back").
 * - quiet: underlined text link.
 * A disabled primary/secondary must always come with a visible reason (`disabledReason`).
 */
type Variant = 'primary' | 'secondary' | 'careful' | 'quiet'

const BASE = 'inline-flex shrink-0 select-none items-center justify-center gap-2 whitespace-nowrap font-sans transition-[transform,box-shadow] duration-100'

const VARIANT: Record<Variant, string> = {
  primary: 'h-12 rounded-[14px] border-[2.5px] border-ink bg-ink px-5 text-[21px] text-paper shadow-raised-soft enabled:active:translate-x-[2px] enabled:active:translate-y-[2px] enabled:active:shadow-none',
  secondary: 'h-12 rounded-[14px] border-[2.5px] border-ink bg-paper px-[18px] text-[21px] text-ink shadow-raised enabled:active:translate-x-[2px] enabled:active:translate-y-[2px] enabled:active:shadow-none',
  careful: 'h-12 rounded-[14px] border-[2.5px] border-ink bg-hl-oops px-[18px] text-[21px] text-ink shadow-raised enabled:active:translate-x-[2px] enabled:active:translate-y-[2px] enabled:active:shadow-none',
  quiet: 'h-10 border-0 bg-transparent px-1.5 text-xl text-ink underline decoration-2 underline-offset-4 enabled:hover:decoration-[3px]',
}

const DISABLED = 'disabled:border-dashed disabled:border-[#9a9a9a] disabled:bg-pencil disabled:text-graphite disabled:shadow-none'

export interface PaperButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  /** Shown next to a disabled button and linked via aria-describedby. */
  disabledReason?: ReactNode
  reasonId?: string
  children: ReactNode
}

export function PaperButton({ variant = 'secondary', disabledReason, reasonId, className, children, type = 'button', disabled, ...rest }: PaperButtonProps) {
  const button = (
    <button
      type={type}
      disabled={disabled}
      aria-describedby={disabled && disabledReason && reasonId ? reasonId : rest['aria-describedby']}
      className={cx(BASE, VARIANT[variant], variant !== 'quiet' && DISABLED, variant === 'quiet' && 'disabled:text-graphite disabled:no-underline', className)}
      {...rest}
    >
      {children}
    </button>
  )
  if (!disabled || !disabledReason) return button
  return (
    <span className="inline-flex items-center gap-3">
      <span id={reasonId} className="text-base text-fg-muted">
        {disabledReason}
      </span>
      {button}
    </span>
  )
}

/** Square icon-only button (header History / Settings). Always needs an accessible label. */
export function IconButton({ label, pressed, className, children, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; pressed?: boolean; children: ReactNode }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      className={cx(
        'inline-flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] border-[2.5px] border-ink text-ink transition-colors duration-100',
        pressed ? 'bg-hl-check' : 'bg-paper hover:bg-pencil',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
