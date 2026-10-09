import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { InkDefs, Pip, PipMark, type PipMood } from '../components/pip/Pip'

/**
 * Pip lab (developer tool, dev server only): every Pip animation playing in place, each
 * labelled underneath. Nothing here is a copy:
 * - "In the app" renders the real <Pip> component (float + hem ripple) for every mood.
 * - "On the desktop" loads the real electron/pip-overlay.html in an iframe and drives it
 *   through the same window.pipSession calls (or dive query) that electron/main.cjs uses,
 *   inside a small box so Pip stays put. Change Pip.tsx or the overlay and this updates.
 */

const MOODS: { mood: PipMood; desc: string }[] = [
  { mood: 'hello', desc: 'Start, before a folder is picked' },
  { mood: 'waiting', desc: 'Start · 1a "…go on, pick a folder."' },
  { mood: 'reading', desc: 'Start · 1c while files are read' },
  { mood: 'suspicious', desc: 'Check · something looks off' },
  { mood: 'carrying', desc: 'Totals · 3c while files move' },
  { mood: 'done', desc: 'Done · 4a all tidy' },
  { mood: 'shrug', desc: 'Done · 4c files put back' },
  { mood: 'sigh', desc: "Errors · 1d, 3d, 4d some didn't work" },
  { mood: 'guard', desc: 'Offline / privacy moments' },
]

const OVERLAY_SRC = '/electron/pip-overlay.html'
const CELL_W = 300
const CELL_H = 280

type OverlayWindow = Window & {
  pipSession?: {
    init(args: { items: OverlayItem[]; win: Box; randomFiles?: boolean }): void
    target(relPath: string): void
    stop(): void
  }
}
type Box = { x: number; y: number; width: number; height: number }
type OverlayItem = Box & { name: string; img?: string; bg?: string }

/** A stand-in for a snapshotted Explorer icon: a page with a folded corner and a name. */
function fakeIcon(name: string, dark: boolean): string {
  const c = document.createElement('canvas')
  c.width = 90
  c.height = 100
  const g = c.getContext('2d')!
  g.fillStyle = dark ? '#202020' : '#ffffff'
  g.fillRect(0, 0, 90, 100)
  g.fillStyle = dark ? '#e9e9e9' : '#ffffff'
  g.strokeStyle = dark ? '#bdbdbd' : '#6b6b6b'
  g.lineWidth = 2
  g.beginPath()
  g.moveTo(25, 10)
  g.lineTo(55, 10)
  g.lineTo(67, 22)
  g.lineTo(67, 66)
  g.lineTo(25, 66)
  g.closePath()
  g.fill()
  g.stroke()
  g.beginPath()
  g.moveTo(55, 10)
  g.lineTo(55, 22)
  g.lineTo(67, 22)
  g.stroke()
  g.fillStyle = dark ? '#f1f1f1' : '#1a1a1a'
  g.font = '12px Segoe UI, sans-serif'
  g.textAlign = 'center'
  g.fillText(name, 45, 86)
  return c.toDataURL()
}

/** Item centred in the cell, as the overlay would get it from Explorer. */
function centredItem(name: string, dark: boolean): OverlayItem {
  return { name, x: (CELL_W - 90) / 2, y: 110, width: 90, height: 100, img: fakeIcon(name, dark), bg: dark ? 'rgb(32,32,32)' : 'rgb(255,255,255)' }
}

/** A "window" whose roam area is a 10px square in the middle, so wandering Pip stays put. */
const STILL_WIN: Box = { x: CELL_W / 2 - 95, y: 0, width: 190, height: 240 }

export function PipLab() {
  const reduced = useMemo(() => matchMedia('(prefers-reduced-motion: reduce)').matches, [])
  return (
    // The app locks body scrolling (index.css), so the lab scrolls itself.
    <div className="h-full overflow-y-auto bg-paper px-10 py-8 text-ink" style={{ backgroundImage: 'radial-gradient(#d6d6d6 1.2px, transparent 1.3px)', backgroundSize: '22px 22px' }}>
      <InkDefs />
      <header className="mb-6 flex items-end justify-between gap-6">
        <div>
          <h1 className="m-0 font-display text-[48px] font-normal leading-none">Pip lab</h1>
          <p className="m-0 mt-2 text-[18px] text-graphite">Every Pip animation, in place. Developer tool: served by the dev server only, not part of the app.</p>
        </div>
        <PipMark size={48} />
      </header>

      {reduced && (
        <p className="mb-6 rounded-[10px] border-[2.5px] border-ink bg-note-oops px-4 py-2 text-[17px]">
          Your system has "reduce motion" on, so Pip stays still and the desktop overlay does nothing (by design). Turn it off to see the animations.
        </p>
      )}

      <Section title="In the app" sub="The <Pip> component: he floats, his shadow breathes and his hem ripples.">
        {MOODS.map(({ mood, desc }) => (
          <Cell key={mood} name={mood} desc={desc}>
            <Pip mood={mood} size={170} />
          </Cell>
        ))}
        <Cell name="mark" desc="Header logo · static, heavier strokes">
          <PipMark size={110} />
        </Cell>
      </Section>

      <Section title="On the desktop" sub="The real overlay (electron/pip-overlay.html), driven the way the Electron main process drives it.">
        <OverlayCell
          name="possess"
          desc="Reading: Pip slips into the file being read; the icon lifts, wobbles and glows"
          run={(api) => {
            api.init({ items: [centredItem('receipt', false)], win: { x: 0, y: 0, width: CELL_W, height: CELL_H } })
            setTimeout(() => api.target('receipt.pdf'), 300)
          }}
        />
        <OverlayCell
          name="possess · dark Explorer"
          desc="Same, on a dark theme: the dashed aura switches to light ink"
          dark
          run={(api) => {
            api.init({ items: [centredItem('invoice', true)], win: { x: 0, y: 0, width: CELL_W, height: CELL_H } })
            setTimeout(() => api.target('invoice.pdf'), 300)
          }}
        />
        <OverlayCell name="carry" desc="Reading, between files: Pip carries a box around (here: on the spot)" run={(api) => api.init({ items: [], win: STILL_WIN })} />
        <OverlayCell
          name="bye"
          desc="Reading done: Pip waves, then poofs away"
          loopMs={3600}
          run={(api) => {
            api.init({ items: [], win: STILL_WIN })
            setTimeout(() => api.stop(), 1200)
          }}
        />
        <DiveCell />
      </Section>
    </div>
  )
}

function Section({ title, sub, children }: { title: string; sub: string; children: ReactNode }) {
  return (
    <section className="mb-10">
      <h2 className="m-0 font-display text-[32px] font-normal">{title}</h2>
      <p className="m-0 mb-4 text-[17px] text-graphite">{sub}</p>
      <div className="grid gap-5" style={{ gridTemplateColumns: `repeat(auto-fill, minmax(${CELL_W}px, 1fr))` }}>
        {children}
      </div>
    </section>
  )
}

function Cell({ name, desc, dark, children }: { name: string; desc: string; dark?: boolean; children: ReactNode }) {
  return (
    <figure className="m-0 flex flex-col overflow-hidden rounded-[14px] border-[2.5px] border-ink bg-paper shadow-[4px_4px_0_#1a1a1a]">
      <div className="relative flex items-center justify-center overflow-hidden" style={{ height: CELL_H, background: dark ? '#202020' : undefined }}>
        {children}
      </div>
      <figcaption className="border-t-[2.5px] border-dashed border-ink px-4 py-2.5">
        <div className="font-mono text-[16px] font-bold">{name}</div>
        <div className="text-[16px] leading-5 text-graphite">{desc}</div>
      </figcaption>
    </figure>
  )
}

/** Loads the overlay page and runs `run` against its pipSession; reloads every `loopMs` if set. */
function OverlayCell({ name, desc, dark, loopMs, run }: { name: string; desc: string; dark?: boolean; loopMs?: number; run: (api: NonNullable<OverlayWindow['pipSession']>) => void }) {
  const [round, setRound] = useState(0)
  useEffect(() => {
    if (!loopMs) return
    const id = window.setInterval(() => setRound((r) => r + 1), loopMs)
    return () => window.clearInterval(id)
  }, [loopMs])

  return (
    <Cell name={name} desc={desc} dark={dark}>
      <iframe
        key={round}
        title={name}
        src={OVERLAY_SRC}
        width={CELL_W}
        height={CELL_H}
        className="block border-0"
        style={{ colorScheme: 'normal', background: 'transparent' }}
        onLoad={(e) => {
          const api = (e.currentTarget.contentWindow as OverlayWindow | null)?.pipSession
          if (api) run(api)
        }}
      />
    </Cell>
  )
}

/** After a move: the one-shot flight into a folder, replayed. Drawn bigger, then scaled to fit. */
function DiveCell() {
  const [round, setRound] = useState(0)
  useEffect(() => {
    const id = window.setInterval(() => setRound((r) => r + 1), 3800)
    return () => window.clearInterval(id)
  }, [])
  const scale = 0.6
  const W = CELL_W / scale
  const H = CELL_H / scale
  const target = { x: W - 170, y: H - 190, w: 90, h: 100 }
  const q = new URLSearchParams({ sx: '110', sy: String(H - 110), tx: String(target.x), ty: String(target.y), tw: String(target.w), th: String(target.h) })
  return (
    <Cell name="dive" desc="After a move: Pip flies into the folder that got the most files">
      <div className="absolute left-0 top-0" style={{ width: W, height: H, transform: `scale(${scale})`, transformOrigin: '0 0' }}>
        <svg className="absolute" style={{ left: target.x, top: target.y + 10 }} width={target.w} height={target.h - 20} viewBox="0 0 64 54" aria-hidden>
          <path d="M3 8h22l6 6h30v36H3Z" fill="#ffe066" stroke="#1a1a1a" strokeWidth="3" strokeLinejoin="round" />
          <path d="M3 20h58" stroke="#1a1a1a" strokeWidth="3" />
        </svg>
        <iframe key={round} title="dive" src={`${OVERLAY_SRC}?${q}`} width={W} height={H} className="absolute left-0 top-0 block border-0" style={{ background: 'transparent' }} />
      </div>
    </Cell>
  )
}
