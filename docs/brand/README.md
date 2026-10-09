# GhostOS brand assets (for the pitch deck)

Exported from the app's own code, so the deck matches the app exactly.
Style name: **"Paper sketch + Pip"**. Black ink on white paper, a dotted grid,
handwriting for voice, a typewriter font for numbers.

## Files

| Folder | What | Use |
|---|---|---|
| `png/` | Pip in 9 moods + the header mark, 720×780, transparent background | Google Slides, Keynote, Canva, PowerPoint |
| `svg/` | Same drawings as vectors | PowerPoint, Figma; scale without blur |
| `screens/` | The 17 screen designs, 1366×768 | Product/workflow slides |

The SVGs use a filter for the hand-inked wobble. Apps that ignore SVG
filters (some PowerPoint versions) show clean lines instead. Use the PNG if
the wobble matters.

`screens/` are **design boards** (`docs/design/`), not captures of the
running app. Their data is made up. Label them as designs, or use real app
screenshots for anything you present as working.

## Pip

Grumpy ghost in glasses. His line is the joke; a plain fact always sits next
to it. At most one Pip per slide.

| File | Mood | Line used in the app |
|---|---|---|
| `pip-hello` | waving, unenthused | "hi. I sort your receipts. I never leave this computer. I never leave, period." |
| `pip-waiting` | coffee mug | "…go on, pick a folder." |
| `pip-reading` | reading a receipt | "reading 18 files. riveting. (still on this computer)" |
| `pip-suspicious` | one eyebrow up | "two totals disagree. which one did you actually pay?" |
| `pip-carrying` | carrying a box, sweating | "carrying 17 files. my back." |
| `pip-done` | clipboard with a check | "17 files. sorted. you're welcome." |
| `pip-shrug` | shrugging | "fine. undone. as if i never tried." |
| `pip-sigh` | crooked glasses, frazzled hair | "couldn't read this one. nothing changed." |
| `pip-guard` | holding a shield | "offline. your files stay right here. so do I." |
| `pip-mark` | logo mark | Header logo, next to the lowercase wordmark "ghostos". |

Good fits: `guard` for the "why local AI" slide, `suspicious` for evidence
and review, `carrying` for approve and move, `shrug` for undo, `done` for
the closing slide.

## Colours

| Name | Hex | Meaning |
|---|---|---|
| Ink | `#1A1A1A` | Text, outlines, primary buttons |
| Paper | `#FFFFFF` | Background |
| Pencil | `#F1F1EF` | Quiet fills |
| Graphite | `#6B6B6B` | Secondary text |
| Dots | `#D6D6D6` | Dotted grid (1.2px dots, 22px apart) |
| Check (yellow) | `#FFE066` | Needs you |
| Done (green) | `#9BE8B8` | Ready / done |
| Oops (pink) | `#FFB3B3` | Couldn't read, careful actions |
| Info (blue) | `#C9D7FF` | Demo data, duplicates |
| Sticky note | `#FFF3A8` | Notes |
| Sticky pink | `#FFD6D6` | Warning notes |

Colour is only a highlighter behind ink text, and only when it means something.

## Fonts (all free on Google Fonts)

- **Gochi Hand**: headings and Pip's speech bubbles.
- **Patrick Hand**: body text.
- **Space Mono** (400/700): numbers, amounts, file paths.

## Regenerating

Pip comes from `frontend/src/components/pip/Pip.tsx` and the colours from
`frontend/src/index.css`. If either changes, re-export rather than editing
these files by hand.
