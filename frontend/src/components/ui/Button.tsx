import type { ButtonHTMLAttributes, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cx } from './cx';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success';
type Size = 'sm' | 'md';

const VARIANT: Record<Variant, string> = {
  primary: 'bg-accent text-accent-fg hover:bg-accent-hover disabled:bg-accent/40 disabled:text-accent-fg/60',
  secondary: 'bg-surface-2 text-fg border border-line hover:border-line-strong hover:bg-surface-3 disabled:text-fg-subtle disabled:hover:bg-surface-2',
  ghost: 'text-fg-muted hover:text-fg hover:bg-surface-3 disabled:text-fg-subtle disabled:hover:bg-transparent',
  danger: 'bg-danger/15 text-danger border border-danger/40 hover:bg-danger/25 disabled:opacity-50',
  success: 'bg-success text-bg hover:bg-success/90 disabled:opacity-50',
};

const SIZE: Record<Size, string> = {
  sm: 'h-7 px-2.5 text-xs gap-1.5',
  md: 'h-8 px-3 text-sm gap-2',
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  icon?: LucideIcon;
  iconRight?: LucideIcon;
  children?: ReactNode;
}

export function Button({ variant = 'secondary', size = 'md', icon: Icon, iconRight: IconRight, className, children, type = 'button', ...rest }: ButtonProps) {
  const iconSize = size === 'sm' ? 14 : 16;
  return (
    <button
      type={type}
      className={cx(
        'inline-flex shrink-0 select-none items-center justify-center whitespace-nowrap rounded-md font-medium transition-colors duration-[120ms]',
        VARIANT[variant],
        SIZE[size],
        !children && (size === 'sm' ? 'w-7 px-0' : 'w-8 px-0'),
        className,
      )}
      {...rest}
    >
      {Icon && <Icon size={iconSize} strokeWidth={2} aria-hidden />}
      {children}
      {IconRight && <IconRight size={iconSize} strokeWidth={2} aria-hidden />}
    </button>
  );
}
