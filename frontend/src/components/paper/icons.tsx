import type { ReactNode } from 'react'
import { ICON_INK_FILTER_ID } from '../pip/Pip'

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
      <g filter={crisp ? undefined : `url(#${ICON_INK_FILTER_ID})`} fill="none" stroke="currentColor" strokeWidth={strokeWidth} strokeLinecap="round" strokeLinejoin="round">
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

/** Magnifying glass: round lens with a glint, and a thicker handle. */
export const SearchIcon = (p: IconProps) => (
  <Icon strokeWidth={2.2} {...p}>
    <circle cx="10.5" cy="10.5" r="6.5" />
    <path d="M7.6 9.2a3.2 3.2 0 0 1 2-2" strokeWidth={1.6} />
    <path d="M15.4 15.4 20.5 20.5" strokeWidth={3} />
  </Icon>
)

/** Tick in a circle; the tick is centred optically (slightly low and left). */
export const CheckIcon = (p: IconProps) => (
  <Icon strokeWidth={2.2} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M7.8 12.4l2.9 2.9 5.5-6.3" />
  </Icon>
)

export const UndoIcon = (p: IconProps) => (
  <Icon {...p}>
    <path d="M9 7 4 12l5 5" />
    <path d="M4 12h10a6 6 0 0 1 0 12" />
  </Icon>
)

/** Padlock: rounded body, shackle, keyhole. */
export const LockIcon = (p: IconProps) => (
  <Icon strokeWidth={2.2} {...p}>
    <rect x="4.5" y="10.5" width="15" height="10.5" rx="2.5" />
    <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    <circle cx="12" cy="15" r="1.2" fill="currentColor" stroke="none" />
    <path d="M12 15.5v2.3" strokeWidth={1.8} />
  </Icon>
)

/** Desktop computer: local-only / on-this-device cue. */
export const ComputerIcon = (p: IconProps) => (
  <Icon strokeWidth={2.1} {...p}>
    <rect x="3" y="4" width="18" height="13" rx="2" />
    <path d="M8 21h8M12 17v4" />
  </Icon>
)

export const HistoryIcon = (p: IconProps) => (
  <Icon strokeWidth={2.2} {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Icon>
)

/** Gear: 8 flat-topped teeth around a hub. */
export const SettingsIcon = (p: IconProps) => (
  <Icon strokeWidth={2} {...p}>
    <path d="M10.08 4.85 10.5 2.52h3l.42 2.33A7.4 7.4 0 0 1 15.7 5.59l1.94-1.36 2.13 2.13-1.36 1.94a7.4 7.4 0 0 1 .74 1.78l2.33.42v3l-2.33.42a7.4 7.4 0 0 1-.74 1.78l1.36 1.94-2.13 2.13-1.94-1.36a7.4 7.4 0 0 1-1.78.74l-.42 2.33h-3l-.42-2.33a7.4 7.4 0 0 1-1.78-.74l-1.94 1.36-2.13-2.13 1.36-1.94a7.4 7.4 0 0 1-.74-1.78l-2.33-.42v-3l2.33-.42a7.4 7.4 0 0 1 .74-1.78L4.23 6.36l2.13-2.13L8.3 5.59a7.4 7.4 0 0 1 1.78-.74Z" />
    <circle cx="12" cy="12" r="3" />
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
