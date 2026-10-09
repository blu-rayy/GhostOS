import type { ElementType, ReactNode } from 'react'
import { cx } from '../ui/cx'

/** Hand-drawn card. Variant 'b' mirrors 'a'; alternate them when cards sit side by side. */
export function PaperCard({
  variant = 'a',
  shadow = 'md',
  as: Tag = 'div',
  className,
  children,
  ...rest
}: {
  variant?: 'a' | 'b'
  shadow?: 'sm' | 'md'
  as?: ElementType
  className?: string
  children: ReactNode
  'aria-label'?: string
  'aria-labelledby'?: string
}) {
  return (
    <Tag
      className={cx('border-[2.5px] border-ink bg-paper', variant === 'a' ? 'sketch-a' : 'sketch-b', shadow === 'md' ? 'shadow-card' : 'shadow-card-sm', className)}
      {...rest}
    >
      {children}
    </Tag>
  )
}

/** Card title in Gochi Hand. */
export function CardTitle({ children, className, as: Tag = 'h2', size = 'md' }: { children: ReactNode; className?: string; as?: ElementType; size?: 'sm' | 'md' }) {
  return <Tag className={cx('m-0 font-display font-normal leading-tight', size === 'md' ? 'text-[28px]' : 'text-[24px]', className)}>{children}</Tag>
}
