import type { ReactNode } from 'react'
import { cx } from '../ui/cx'

/**
 * Pip: GhostOS's grumpy ghost in glasses (Brand v3 · Paper sketch + Pip).
 * Rules: at most one Pip per screen, only in empty / scanning / done / error
 * moments, never inside lists or forms. His line is the joke; a plain factual
 * line always sits beside it (see PipMoment).
 *
 * Drawings are ported from the brand sheet (120×130 viewBox) and share the
 * "ink" wobble filter rendered once by <InkDefs /> in the app shell.
 */

export type PipMood = 'hello' | 'waiting' | 'reading' | 'suspicious' | 'done' | 'sigh' | 'guard'

const INK = '#1a1a1a'
export const INK_FILTER_ID = 'ghostos-ink'

/** SVG filter that gives strokes a slightly hand-inked wobble. Render once per document. */
export function InkDefs() {
  return (
    <svg width="0" height="0" className="absolute" aria-hidden focusable="false">
      <defs>
        <filter id={INK_FILTER_ID} x="-5%" y="-5%" width="110%" height="110%">
          <feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves={2} seed={7} />
          <feDisplacementMap in="SourceGraphic" scale={2.3} />
        </filter>
      </defs>
    </svg>
  )
}

const BODY = 'M20 60a40 40 0 0 1 80 0v50q-6.67 10-13.33 0t-13.33 0t-13.33 0t-13.33 0t-13.33 0t-13.33 0Z'
const line = { stroke: INK, fill: 'none', strokeLinecap: 'round' as const }

function Body({ w = 3.5 }: { w?: number }) {
  return <path d={BODY} fill="#fff" stroke={INK} strokeWidth={w} strokeLinejoin="round" />
}

/** Round glasses; `y` is the lens centre line. */
function Glasses({ y = 62, w = 3 }: { y?: number; w?: number }) {
  return (
    <>
      <circle cx="47" cy={y} r="10" fill="#fff" stroke={INK} strokeWidth={w} />
      <circle cx="73" cy={y} r="10" fill="#fff" stroke={INK} strokeWidth={w} />
      <path d={`M57 ${y - 1}q3-2 6 0M37 ${y - 2}l-9-3M83 ${y - 2}l9-3`} {...line} strokeWidth={w} />
    </>
  )
}

/** Heavy-lidded half-closed eyes, Pip's default "unimpressed" look. */
function Lids({ y = 61, r = 3 }: { y?: number; r?: number }) {
  return (
    <>
      <path d={`M40 ${y}h14M66 ${y}h14`} {...line} strokeWidth={2.6} />
      <path d={`M${47 - r} ${y + 0.5}a${r} ${r} 0 0 0 ${r * 2} 0ZM${73 - r} ${y + 0.5}a${r} ${r} 0 0 0 ${r * 2} 0Z`} fill={INK} />
    </>
  )
}

function Bags() {
  return <path d="M40 77q7 3 14 0M66 77q7 3 14 0" {...line} strokeWidth={1.6} />
}

/** Dashed ground shadow and the single curl of hair used on the large moods. */
function Ground() {
  return <ellipse cx="60" cy="125" rx="32" ry="3.5" fill="none" stroke={INK} strokeWidth="1.8" strokeDasharray="4 4" />
}
function Hair() {
  return <path d="M60 21q5-9-2-13" {...line} strokeWidth={2.4} />
}

const MOODS: Record<PipMood, { label: string; art: ReactNode }> = {
  hello: {
    label: 'Pip, a grumpy ghost in glasses, waving without enthusiasm',
    art: (
      <>
        <ellipse cx="60" cy="124" rx="30" ry="4" fill="none" stroke={INK} strokeWidth="2" strokeDasharray="4 4" />
        <Body w={3} />
        <path d="M60 21q5-9-2-13" {...line} strokeWidth={2.5} />
        <path d="M99 80c6-1 9-5 9-10" {...line} strokeWidth={3} />
        <path d="M104 64l2 3M110 64l-1 3" {...line} strokeWidth={1.8} />
        <path d="M21 80c-5 2-8 6-7 11" {...line} strokeWidth={3} />
        <Glasses />
        <Lids y={60} r={4} />
        <Bags />
        <path d="M53 88q7-5 14 0" {...line} strokeWidth={3} />
      </>
    ),
  },
  waiting: {
    label: 'Pip waiting with a coffee mug',
    art: (
      <>
        <Ground />
        <Body w={3} />
        <Hair />
        <Glasses w={2.6} />
        <Lids />
        <Bags />
        <path d="M52 87h12" {...line} strokeWidth={2.6} />
        <path d="M68 95h18v15a4 4 0 0 1-4 4H72a4 4 0 0 1-4-4Z" fill="#fff" stroke={INK} strokeWidth="2.6" strokeLinejoin="round" />
        <path d="M86 99h3a4 4 0 0 1 0 8h-3" stroke={INK} strokeWidth="2.6" fill="none" />
        <path d="M73 90q2-3 0-6M80 90q2-3 0-6" {...line} strokeWidth={1.8} />
        <path d="M21 80c-5 2-8 6-7 11" {...line} strokeWidth={2.6} />
      </>
    ),
  },
  reading: {
    label: 'Pip reading a receipt over his glasses',
    art: (
      <>
        <Ground />
        <Body w={3} />
        <Hair />
        <Glasses y={66} w={2.6} />
        <Lids y={66} />
        <path d="M38 50l14 2M68 52l14-2" {...line} strokeWidth={2.3} />
        <path d="M30 86h60v30H30Z" fill="#fff" stroke={INK} strokeWidth="2.6" strokeLinejoin="round" />
        <path d="M37 95h44M37 103h34M37 110h22" {...line} strokeWidth={2.2} />
      </>
    ),
  },
  suspicious: {
    label: 'Pip suspicious, one eyebrow raised',
    art: (
      <>
        <Body />
        <path d="M37 46l15 5M64 44l16-6" {...line} strokeWidth={3} />
        <Glasses />
        <path d="M40 61h14" {...line} strokeWidth={2.6} />
        <path d="M44 61.5a3 3 0 0 0 6 0Z" fill={INK} />
        <circle cx="73" cy="62" r="3.5" fill={INK} />
        <Bags />
        <path d="M52 88q4-3 8 0t8 0" {...line} strokeWidth={3} />
        <path d="M96 14q8-4 10 3t-6 9v4M100 35v1" {...line} strokeWidth={3} />
      </>
    ),
  },
  done: {
    label: 'Pip reluctantly satisfied, one tiny party streamer',
    art: (
      <>
        <path d="M104 22q4 4 0 8t0 8" {...line} strokeWidth={2.5} />
        <Body />
        <path d="M99 76c5-3 7-8 6-14M21 80c-5 2-8 6-7 11" {...line} strokeWidth={3} />
        <Glasses />
        <path d="M41 63q6-4 12 0M67 63q6-4 12 0" {...line} strokeWidth={2.6} />
        <Bags />
        <path d="M55 86q6 3 11-1" {...line} strokeWidth={3} />
      </>
    ),
  },
  sigh: {
    label: 'Pip sighing, glasses crooked',
    art: (
      <>
        <Ground />
        <Body w={3} />
        <Hair />
        <g transform="rotate(-8 60 62)">
          <Glasses w={2.6} />
          <path d="M75 55l-4 12" {...line} strokeWidth={1.4} />
        </g>
        <path d="M41 62q6 3 12 0M67 59q6 3 12 0" {...line} strokeWidth={2.3} />
        <Bags />
        <ellipse cx="60" cy="88" rx="4" ry="3" fill="none" stroke={INK} strokeWidth="2.3" />
        <path d="M66 90q8 2 14-2" {...line} strokeWidth={1.6} strokeDasharray="3 3" />
        <path d="M21 80c-5 2-8 6-7 11M99 80c5 2 8 6 7 11" {...line} strokeWidth={2.6} />
      </>
    ),
  },
  guard: {
    label: 'Pip on guard, arms crossed',
    art: (
      <>
        <Body />
        <path d="M30 44l17 6M90 44l-17 6" {...line} strokeWidth={3} />
        <Glasses y={60} />
        <Lids y={59} />
        <path d="M53 80h14" {...line} strokeWidth={3} />
        <path d="M24 96q20-8 44 2M96 96q-20-8-44 2M24 96q20 6 40 0M96 96q-18 7-36 1" {...line} strokeWidth={3} />
      </>
    ),
  },
}

export function Pip({ mood, size = 120, className, decorative = false }: { mood: PipMood; size?: number; className?: string; decorative?: boolean }) {
  const m = MOODS[mood]
  return (
    <svg
      width={size}
      height={Math.round((size * 130) / 120)}
      viewBox="0 0 120 130"
      className={cx('shrink-0', className)}
      role={decorative ? undefined : 'img'}
      aria-label={decorative ? undefined : m.label}
      aria-hidden={decorative || undefined}
      focusable="false"
    >
      <g filter={`url(#${INK_FILTER_ID})`}>{m.art}</g>
    </svg>
  )
}

/** Small brand mark for the header (heavier strokes so it reads at 34px). */
export function PipMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={Math.round((size * 130) / 120)} viewBox="0 0 120 130" aria-hidden focusable="false" className="shrink-0">
      <g filter={`url(#${INK_FILTER_ID})`}>
        <Body w={5} />
        <Glasses w={4.5} />
        <path d="M40 60h14M66 60h14" {...line} strokeWidth={4} />
        <path d="M53 88q7-5 14 0" {...line} strokeWidth={4.5} />
      </g>
    </svg>
  )
}

/**
 * Pip's speech bubble, in Gochi Hand. `tail="down"` points at Pip standing below
 * (Start screens); `tail="left"` points at Pip beside it.
 */
export function SpeechBubble({ children, className, tail = 'left', tailOffset = 40 }: { children: ReactNode; className?: string; tail?: 'left' | 'down'; tailOffset?: number }) {
  return (
    <div className={cx('relative rounded-[18px] border-[2.5px] border-ink bg-paper font-display', tail === 'down' ? 'px-4 py-2.5 text-[24px] leading-tight shadow-card-sm' : 'px-3 py-2 text-[22px] leading-7', className)}>
      {children}
      {tail === 'down' ? (
        <svg width="26" height="22" viewBox="0 0 26 22" className="absolute -bottom-[21px]" style={{ left: tailOffset }} aria-hidden focusable="false">
          <path d="M2 1 8 20 20 1" fill="#fff" stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
        </svg>
      ) : (
        <svg width="22" height="18" viewBox="0 0 22 18" className="absolute -left-[20px] bottom-2.5" aria-hidden focusable="false">
          <path d="M21 2 2 15 21 12" fill="#fff" stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
        </svg>
      )}
    </div>
  )
}

/**
 * Pip standing under his speech bubble (Start screens). The bubble text is Pip's
 * line; Pip himself is decorative because the bubble already says it.
 */
export function PipWithBubble({ mood, line: text, size, className, bubbleClassName, tailOffset }: { mood: PipMood; line: string; size: number; className?: string; bubbleClassName?: string; tailOffset?: number }) {
  return (
    <figure className={cx('m-0 flex flex-col items-center', className)}>
      <figcaption className={cx('max-w-full', bubbleClassName)}>
        <SpeechBubble tail="down" tailOffset={tailOffset}>
          <span className="sr-only">Pip says: </span>
          {text}
        </SpeechBubble>
      </figcaption>
      <Pip mood={mood} size={size} decorative className="mt-3" />
    </figure>
  )
}

/**
 * Pip plus his joke, with the plain factual line beside it. The fact is the
 * real message; the joke is flavour and is never the only place information appears.
 */
export function PipMoment({
  mood,
  joke,
  fact,
  children,
  size = 120,
  className,
}: {
  mood: PipMood
  joke: string
  fact: ReactNode
  children?: ReactNode
  size?: number
  className?: string
}) {
  return (
    <div className={cx('flex items-end gap-6', className)}>
      <Pip mood={mood} size={size} />
      <div className="flex min-w-0 flex-col gap-3 pb-2">
        <SpeechBubble className="self-start">
          <span className="sr-only">Pip says: </span>
          {joke}
        </SpeechBubble>
        <div className="text-lg leading-7">{fact}</div>
        {children}
      </div>
    </div>
  )
}
