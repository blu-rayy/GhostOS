import { createContext, useContext, type ReactNode } from 'react'
import { cx } from '../ui/cx'

/**
 * Pip: GhostOS's grumpy ghost in glasses (Brand v3 · Paper sketch + Pip).
 * Rules: at most one Pip per screen, only in empty / scanning / done / error
 * moments, never inside lists or forms. His line is the joke; a plain factual
 * line always sits beside it (see PipMoment).
 *
 * Drawings are ported from the brand sheet (120×130 viewBox) and drawn as plain
 * vectors: no wobble filter, which rasterised his strokes and made them look blurry.
 */

export type PipMood = 'hello' | 'waiting' | 'reading' | 'suspicious' | 'done' | 'sigh' | 'guard' | 'carrying' | 'shrug'

const INK = '#1a1a1a'
/** Gentle hand-inked wobble for 24-unit icons (Pip himself is drawn without a filter). */
export const ICON_INK_FILTER_ID = 'ghostos-ink-icon'

/** SVG filter that gives icon strokes a slight hand-inked wobble. Render once per document. */
export function InkDefs() {
  return (
    <svg width="0" height="0" className="absolute" aria-hidden focusable="false">
      <defs>
        <filter id={ICON_INK_FILTER_ID} x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence type="fractalNoise" baseFrequency="0.2" numOctaves={2} seed={7} />
          <feDisplacementMap in="SourceGraphic" scale={0.5} />
        </filter>
      </defs>
    </svg>
  )
}

/** Body outline; `hem` is the depth of the wavy bottom edge (10 = the drawn shape). */
const bodyPath = (hem: number) => `M20 60a40 40 0 0 1 80 0v50q-6.67 ${hem} -13.33 0t-13.33 0t-13.33 0t-13.33 0t-13.33 0t-13.33 0Z`
const BODY = bodyPath(10)
/** The hem ripples through these depths (same command structure, so SMIL can tween `d`). */
const HEM_WIGGLE = [10, 5, -4, 5, 10].map(bodyPath).join(';')

/** True inside a full-size <Pip>; the header mark stays still. */
const Animated = createContext(false)

function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}
const line = { stroke: INK, fill: 'none', strokeLinecap: 'round' as const }

function Body({ w = 3.5 }: { w?: number }) {
  const animated = useContext(Animated)
  return (
    <path d={BODY} fill="#fff" stroke={INK} strokeWidth={w} strokeLinejoin="round">
      {animated && <animate attributeName="d" values={HEM_WIGGLE} dur="1.6s" repeatCount="indefinite" />}
    </path>
  )
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

/**
 * Heavy-lidded half-closed eyes, Pip's default "unimpressed" look. `scan`: the pupils
 * sweep left to right along a line of text, pause, and snap back for the next line.
 */
function Lids({ y = 61, r = 3, scan = false }: { y?: number; r?: number; scan?: boolean }) {
  const animated = useContext(Animated)
  return (
    <>
      <path d={`M40 ${y}h14M66 ${y}h14`} {...line} strokeWidth={2.6} />
      <g>
        <path d={`M${47 - r} ${y + 0.5}a${r} ${r} 0 0 0 ${r * 2} 0ZM${73 - r} ${y + 0.5}a${r} ${r} 0 0 0 ${r * 2} 0Z`} fill={INK} />
        {scan && animated && (
          <animateTransform attributeName="transform" type="translate" values="-5 0;5 0;5 0;-5 0" keyTimes="0;0.72;0.84;1" dur="1.9s" repeatCount="indefinite" />
        )}
      </g>
    </>
  )
}

/** The single curl of hair used on the large moods. */
function Hair() {
  return <path d="M60 21q5-9-2-13" {...line} strokeWidth={2.4} />
}

const MOODS: Record<PipMood, { label: string; art: ReactNode }> = {
  hello: {
    label: 'Pip, a grumpy ghost in glasses, waving without enthusiasm',
    art: (
      <>
        <Body w={3} />
        <path d="M60 21q5-9-2-13" {...line} strokeWidth={2.5} />
        <path d="M99 80c6-1 9-5 9-10" {...line} strokeWidth={3} />
        <path d="M104 64l2 3M110 64l-1 3" {...line} strokeWidth={1.8} />
        <path d="M21 80c-5 2-8 6-7 11" {...line} strokeWidth={3} />
        <Glasses />
        <Lids y={60} r={4} />
        <path d="M53 88q7-5 14 0" {...line} strokeWidth={3} />
      </>
    ),
  },
  waiting: {
    label: 'Pip waiting with a coffee mug',
    art: (
      <>
        <Body w={3} />
        <Hair />
        <Glasses w={2.6} />
        <Lids />
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
        <Body w={3} />
        <Hair />
        <Glasses y={66} w={2.6} />
        <Lids y={66} scan />
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
        <Hair />
        <path d="M37 46l15 5M64 44l16-6" {...line} strokeWidth={3} />
        <Glasses />
        <path d="M40 61h14" {...line} strokeWidth={2.6} />
        <path d="M44 61.5a3 3 0 0 0 6 0Z" fill={INK} />
        <circle cx="73" cy="62" r="3.5" fill={INK} />
        <path d="M52 88q4-3 8 0t8 0" {...line} strokeWidth={3} />
        <path d="M96 14q8-4 10 3t-6 9v4M100 35v1" {...line} strokeWidth={3} />
      </>
    ),
  },
  /** Step 4 · Done 4a, exact SVG from docs/design/step4-done/4a-all-tidy.html. */
  done: {
    label: 'Pip holding a clipboard with a check mark, looking smug',
    art: (
      <>
        <Body w={3} />
        <Hair />
        <Glasses w={2.6} />
        <Lids y={60} />
        <path d="M54 86q6 3 11-1" {...line} strokeWidth={2.4} />
        <path d="M70 88h22v28H70Z" fill="#9be8b8" stroke={INK} strokeWidth="2.6" strokeLinejoin="round" />
        <path d="M76 86h10v5H76Z" fill="#fff" stroke={INK} strokeWidth="2" />
        <path d="M75 102l4 4 8-9" {...line} strokeWidth={2.8} strokeLinejoin="round" />
        <path d="M21 80c-5 2-8 6-7 11" {...line} strokeWidth={2.6} />
      </>
    ),
  },
  /** Step 4 · Done 4c, exact SVG from docs/design/step4-done/4c-put-back.html. */
  shrug: {
    label: 'Pip shrugging',
    art: (
      <>
        <Body w={3} />
        <Hair />
        <Glasses w={2.6} />
        <Lids />
        <path d="M53 87h14" {...line} strokeWidth={2.6} />
        <path d="M21 80q-9-2-12-10M99 80q9-2 12-10" {...line} strokeWidth={2.6} />
      </>
    ),
  },
  sigh: {
    label: 'Pip sighing, glasses crooked',
    art: (
      <>
        <Body w={3} />
        {/* Haggard: his one hair has gone into a frazzled curl. */}
        <path d="M60 21c1.5-5 6.5-7.5 5-12.5c-1.2-3.8-6.6-3.6-7.3 0c-0.6 3.1 2.4 4.8 4.6 3.4" {...line} strokeWidth={2.4} />
        <g transform="rotate(-8 60 62)">
          <Glasses w={2.6} />
        </g>
        <path d="M41 62q6 3 12 0M67 59q6 3 12 0" {...line} strokeWidth={2.3} />
        <ellipse cx="60" cy="88" rx="4" ry="3" fill="none" stroke={INK} strokeWidth="2.3" />
        <path d="M21 80c-5 2-8 6-7 11M99 80c5 2 8 6 7 11" {...line} strokeWidth={2.6} />
      </>
    ),
  },
  guard: {
    label: 'Pip on guard, holding a shield',
    art: (
      <>
        <Body />
        <Hair />
        <path d="M30 44l17 6M90 44l-17 6" {...line} strokeWidth={3} />
        <Glasses y={60} />
        <Lids y={59} />
        <path d="M53 80h14" {...line} strokeWidth={3} />
        {/* Free arm hanging at his side. */}
        <path d="M21 80c-5 2-8 6-7 11" {...line} strokeWidth={3} />
        {/* A plain shield held in front of his side. */}
        <path d="M76 73h32v15c0 12-7 18.5-16 22.5c-9-4-16-10.5-16-22.5Z" fill="#fff" stroke={INK} strokeWidth="3" strokeLinejoin="round" />      </>
    ),
  },
  /** Step 3 · Totals 3c, exact SVG from docs/design/step3-totals/3c-moving.html. */
  carrying: {
    label: 'Pip carrying a box of files',
    art: (
      <>
        <Body w={3} />
        <Hair />
        <Glasses y={58} w={2.6} />
        <Lids y={57} />
        <path d="M54 76q6-3 12 0" {...line} strokeWidth={2.4} />
        <path d="M104 29q6.5 9.5 0 14q-6.5-4.5 0-14Z" fill="#c9d7ff" stroke={INK} strokeWidth="2" strokeLinejoin="round" />
        <path d="M30 84h60v30H30Z" fill="#ffe066" stroke={INK} strokeWidth="2.6" strokeLinejoin="round" />
        <path d="M30 92h60M54 84v8M66 84v8" stroke={INK} strokeWidth="2.2" />
        <path d="M22 92q4 6 8 8M98 92q-4 6-8 8" {...line} strokeWidth={2.6} />
      </>
    ),
  },
}

export function Pip({ mood, size = 120, className, decorative = false, still = false }: { mood: PipMood; size?: number; className?: string; decorative?: boolean; still?: boolean }) {
  const m = MOODS[mood]
  const animated = !still && !prefersReducedMotion()
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
      {/* Pip floats: the shadow stays on the ground and shrinks as he rises; his hem ripples. */}
      <ellipse cx="60" cy="125" rx="32" ry="3.5" fill="none" stroke={INK} strokeWidth="1.8" strokeDasharray="4 4" className={animated ? 'pip-shadow' : undefined} />
      <g className={animated ? 'pip-float' : undefined}>
        <Animated.Provider value={animated}>{m.art}</Animated.Provider>
      </g>
    </svg>
  )
}

/** Small brand mark for the header (heavier strokes so it reads at 34px). */
export function PipMark({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={Math.round((size * 130) / 120)} viewBox="0 0 120 130" aria-hidden focusable="false" className="shrink-0">
      <Body w={5} />
      <Glasses w={4.5} />
      <path d="M40 60h14M66 60h14" {...line} strokeWidth={4} />
      <path d="M53 88q7-5 14 0" {...line} strokeWidth={4.5} />
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
        // Starts 6px inside the bubble so the white fill fully covers the bubble's bottom
        // border between the two tail strokes (no hairline at fractional display scales).
        <svg width="26" height="28" viewBox="0 0 26 28" className="absolute -bottom-[21px]" style={{ left: tailOffset }} aria-hidden focusable="false">
          <path d="M2 0H20V7L8 26 2 7Z" fill="#fff" />
          <path d="M2 7 8 26 20 7" fill="none" stroke={INK} strokeWidth="2.5" strokeLinejoin="round" />
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
