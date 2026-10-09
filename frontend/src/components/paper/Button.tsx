import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react'
import { cx } from '../ui/cx'

/**
 * Buttons from the component sheet.
 * - primary: ink fill, grey offset shadow. One per screen, bottom-right.
 * - secondary: paper with ink outline and ink shadow.
 * - careful: pink highlighter (e.g. "Put files back").
 * - link: underlined text.
 * Disabled = dashed grey border + pencil fill, and always a visible reason next to it
 * (`disabledReason`), never a tooltip only.
 */
type Variant = 'primary' | 'secondary' | 'careful' | 'link'
type Size = 'lg' | 'md' | 'sm'

const BOXED = 'inline-flex shrink-0 select-none items-center justify-center gap-2.5 whitespace-nowrap font-sans transition-[transform,box-shadow] duration-100'
const PRESS = 'enabled:active:translate-x-[3px] enabled:active:translate-y-[3px] enabled:active:shadow-none'

const SIZE: Record<Size, string> = {
  lg: 'h-[58px] rounded-[16px] border-[3px] px-[26px] text-[25px]',
  md: 'h-[54px] rounded-[16px] border-[3px] px-[26px] text-[24px] leading-none',
  sm: 'h-12 rounded-[14px] border-[2.5px] px-5 text-[21px]',
}

const VARIANT: Record<Exclude<Variant, 'link'>, string> = {
  primary: 'border-ink bg-ink text-paper shadow-btn',
  secondary: 'border-ink bg-paper text-ink shadow-btn-ink',
  careful: 'border-ink bg-hl-oops text-ink shadow-btn-ink',
}

const DISABLED = 'disabled:border-dashed disabled:border-btn-shadow disabled:bg-pencil disabled:text-graphite disabled:shadow-none'

const LINK = 'inline-flex h-11 shrink-0 items-center gap-2 border-0 bg-transparent px-1.5 font-sans text-[20px] text-ink underline decoration-2 underline-offset-4 enabled:hover:decoration-[3px] disabled:text-graphite disabled:no-underline'

export interface PaperButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  /** Visible reason shown next to a disabled button, linked via aria-describedby. */
  disabledReason?: ReactNode
  reasonId?: string
  /** React 19 passes `ref` as a prop; it lands on the <button> (e.g. a dialog's initial focus). */
  ref?: Ref<HTMLButtonElement>
  children: ReactNode
}

export function PaperButton({ variant = 'secondary', size = 'md', disabledReason, reasonId, className, children, type = 'button', disabled, ...rest }: PaperButtonProps) {
  const showReason = Boolean(disabled && disabledReason)
  const button = (
    <button
      type={type}
      disabled={disabled}
      aria-describedby={showReason && reasonId ? reasonId : rest['aria-describedby']}
      className={cx(variant === 'link' ? LINK : cx(BOXED, SIZE[size], VARIANT[variant], PRESS, DISABLED), className)}
      {...rest}
    >
      {children}
    </button>
  )
  if (!showReason) return button
  return (
    <span className="inline-flex items-center gap-3.5">
      <span id={reasonId} className="text-[17px] text-graphite">
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
        'inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[12px] border-[2.5px] border-ink text-ink transition-colors duration-100',
        pressed ? 'bg-hl-check' : 'bg-paper hover:bg-pencil',
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  )
}
