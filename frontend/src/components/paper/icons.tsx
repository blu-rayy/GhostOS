import type { ReactNode } from 'react'
import { INK_FILTER_ID } from '../pip/Pip'

/**
 * Hand-drawn 2px ink icons from the Brand v3 sheet. Decorative by default
 * (the surrounding button or text carries the meaning); pass `label` when the
 * icon stands alone.
 */
export interface IconProps {
  size?: number
  label?: string
  className?: string
  /** Skip the wobble filter (e.g. for very small sizes where it smears). */
  crisp?: boolean
}

function Icon({ size = 22, label, className, crisp, strokeWidth = 2, children }: IconProps & { strokeWidth?: number; children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      className={className}
      role={label ? 'img' : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      focusable="false"
    >
      <g filter={crisp ? undefined : `url(#${INK_FILTER_ID})`} fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
        {children}
      </g>
    </svg>
  )
}

export const HomeIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 11l9-7 9 7v9H3Z" />
    <path d="M10 20v-6h4v6" />
  </Icon>
)

export const FolderIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 6h7l2 2h9v11H3Z" />
  </Icon>
)

export const SearchIcon = (p: IconProps) => (
  <Icon strokeWidth={2.4} {...p}>
    <circle cx="10" cy="10" r="6" />
    <path d="M15 15l5 5" />
  </Icon>
)

export const CheckIcon = (p: IconProps) => (
  <Icon strokeWidth={2.2} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M8 12l3 3 5-6" />
  </Icon>
)

export const UndoIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 7 4 12l5 5" />
    <path d="M4 12h10a6 6 0 0 1 0 12" />
  </Icon>
)

export const LockIcon = (p: IconProps) => (
  <Icon strokeWidth={2.4} {...p}>
    <rect x="5" y="11" width="14" height="10" rx="2" />
    <path d="M8 11V8a4 4 0 0 1 8 0v3" />
  </Icon>
)

export const HistoryIcon = (p: IconProps) => (
  <Icon strokeWidth={2.2} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Icon>
)

export const SettingsIcon = (p: IconProps) => (
  <Icon strokeWidth={2.2} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M5 19l2-2M17 7l2-2" />
  </Icon>
)

export const FileIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M6 3h9l4 4v14H6Z" />
    <path d="M9 11h7M9 15h5" />
  </Icon>
)

export const CloseIcon = (p: IconProps) => (
  <Icon strokeWidth={2.4} {...p}>
    <path d="M6 6l12 12M18 6 6 18" />
  </Icon>
)

export const AlertIcon = (p: IconProps) => (
  <Icon strokeWidth={2.2} {...p}>
    <path d="M12 3 2 20h20Z" />
    <path d="M12 10v4M12 17v.5" />
  </Icon>
)
