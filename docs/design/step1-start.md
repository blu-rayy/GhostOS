# Step 1 · Start: paper redesign handoff

Status: **approved by Kristian (2026-10-09)** · Target branch: `feat/ui-paper` · Source of truth: the Claude Design canvas "GhostOS UI Prototype", page *Screens (paper)*, boards 1a–1d. Static copies of those boards are in `docs/design/step1-start/` (open them in a browser for pixel reference; they pull Google Fonts for preview only, and the app must never do that).

This is the first slice of the paper redesign. Only the Start step changes. Check, Expenses and Done keep the current UI until their designs are approved.

---

## 0. Branch setup (Kristian, PowerShell)

The main checkout is on `qa/frontend-tests` with Codex's unstaged changes in it. Don't switch it. Use a separate worktree so both agents can work at once:

```powershell
cd C:\Users\otaku\Documents\VSC\GhostOS
git fetch
git worktree add ..\GhostOS-ui-paper -b feat/ui-paper origin/main   # or "main" if there is no remote main
Copy-Item -Recurse docs\design ..\GhostOS-ui-paper\docs\design
cd ..\GhostOS-ui-paper\frontend
npm install
```

Open `GhostOS-ui-paper` in VS Code and give the prompt in section 9 to the IDE agent there.

---

## 1. Scope

| In scope | Out of scope (do not touch) |
| --- | --- |
| Paper design tokens and local fonts | `backend/**` |
| Shared paper components (section 4) | `src/types/api.ts`, `src/api/**`, `src/fixtures/**` (the contract) |
| New app header with the 4-step tracker | `electron/**` security settings (preload API stays `platform, version, capabilities, selectFolder`) |
| Start screen, states 1a–1d | Check / Expenses / Done / History / Settings screens (keep current UI, only re-skin the header around them) |
| Header icons that open the current Activity and Settings screens | Codex's files: `vitest.config.ts`, `src/test/**`, `*.test.ts`, `docs/qa/**` |

---

## 2. Design tokens

Add to `src/index.css` `@theme` (light is the only theme for the paper UI; leave the dark tokens alone for now).

| Token | Value | Use |
| --- | --- | --- |
| `--color-ink` | `#1A1A1A` | text, outlines, primary button |
| `--color-paper` | `#FFFFFF` | cards, header, footer |
| `--color-pencil` | `#F1F1EF` | disabled fill, path box (`#F6F6F4`) |
| `--color-graphite` | `#6B6B6B` | secondary text (5.3:1 on white) |
| `--color-dot` | `#D6D6D6` | dot-grid background |
| `--color-hl-check` | `#FFE066` | current step, "check this", highlights |
| `--color-hl-done` | `#9BE8B8` | "ready", supported types |
| `--color-hl-oops` | `#FFB3B3` | "couldn't read" |
| `--color-sticky` | `#FFF3A8` | yellow sticky note |
| `--color-sticky-pink` | `#FFD6D6` | error sticky, warning pill |

**Background:** `background: #fff radial-gradient(#d6d6d6 1.2px, transparent 1.3px) 0 0 / 22px 22px`.

**Hand-drawn shapes:**
- card A: `border-radius: 255px 16px 225px 16px / 16px 225px 16px 255px`
- card B (mirrored): `border-radius: 16px 225px 16px 255px / 255px 16px 225px 16px`
- outlines 2.5px ink (3px on big buttons). Shadows are offsets with no blur: cards `6px 6px 0 #1a1a1a`, small cards `4px 4px 0`, primary button `5px 5px 0 #9a9a9a`, secondary button `5px 5px 0 #1a1a1a`.
- sticky notes: square corners, rotated −0.6° to −1°, `4–5px` ink shadow.
- marker highlight on words: `background: linear-gradient(transparent 50%, #ffe066 50%, #ffe066 92%, transparent 92%)`.

**Ink filter:** one `<svg>` defs at app root with `<filter id="ink"><feTurbulence type="fractalNoise" baseFrequency="0.04" numOctaves="2" seed="7"/><feDisplacementMap in="SourceGraphic" scale="2.2"/></filter>`. Apply it **only to Pip and decorative icons**, never to text or controls (readability and performance).

## 3. Fonts (must be bundled locally)

| Font | Use | Min size |
| --- | --- | --- |
| Gochi Hand | page titles, card titles, Pip's speech, logo | 22px |
| Patrick Hand | all body text and buttons | **16px** |
| Space Mono | money, dates, counts, file paths | 13px |

Use `@fontsource/gochi-hand`, `@fontsource/patrick-hand` and `@fontsource/space-mono` (all OFL). **No Google Fonts or CDN at runtime.** The CSP stays as it is (`font-src 'self'`). This is a `package.json` change, so post it in `TODO.md` first and wait for Kristian's OK (team rule).

## 4. Components to build (`src/components/paper/`)

| Component | Notes |
| --- | --- |
| `PaperCard` | `variant: 'a' \| 'b'`, `shadow: 'sm' \| 'md'` |
| `Button` | `primary` (ink bg, white text, grey shadow; **one per screen, bottom-right**), `secondary` (white, ink shadow), `link` (underlined text), and disabled state: dashed `#9a9a9a` border, pencil fill, plus a **visible reason text next to it** (e.g. "opens when reading is done") |
| `StickyNote` | `tone: 'yellow' \| 'pink'`, optional `role="alert"` |
| `Chip` | `tone: 'check' \| 'done' \| 'oops' \| 'muted'` (muted = dashed border) |
| `HatchProgress` | 26px bar with ink diagonal hatching, `role="progressbar"` and aria values |
| `NumberedSteps` | circled 1-2-3 list used in 1b and 1d |
| `SpeechBubble` | rounded bubble with a tail, Pip's voice, Gochi Hand |
| `Pip` | `mood: 'mini' \| 'waiting' \| 'reading' \| 'sigh'`, SVG paths in section 7; decorative moods get `aria-hidden`, and the label text lives in the bubble |
| `AppHeader` | section 5 |
| `PageFooter` | 84px, top border 2.5px dashed ink, padding `0 64px`, left slot + right slot |

## 5. App header (all screens)

64px, white, bottom border 2.5px ink, padding `0 28px`.

- **Left:** mini Pip (32×35) + "ghostOS" in Gochi Hand 28px.
- **Step tracker** (`<nav aria-label="Steps">`, `aria-current="step"` on current):
  - done: filled ink circle with ✓ + label
  - current: yellow pill `#FFE066`, 2.5px ink border, white numbered circle inside
  - later: dashed grey circle + label. **Use `#6B6B6B` for the label text, not the canvas's `#8A8A8A`** (3.5:1 fails AA at 18px).
  - connectors: 24px line, solid ink between done steps, dashed grey otherwise.
  - Steps are **not clickable forward**. A done step may be clicked to go back only where the current flow already allows it.
- **Right:** status pill, then History and Settings icon buttons (40×40, 12px radius, `aria-label`).
  - Pill normal: lock icon + "offline · on this computer".
  - Pill when the local AI health check fails: pink `#FFD6D6`, "offline · local AI not answering".
  - When fixture data is in use, add a chip **"demo data"** next to the pill. Never present mock data as real (AGENTS.md).
- History → the current Activity screen; Settings → the current Settings screen (both become panels later).

## 6. Start screen states

Map to the existing state in `src/state/` (no new state machine). Keep all calls through `GhostApi` and `src/platform`.

### 1a · Nothing picked yet (`no folder selected`)
- Two columns: text (1fr) | Pip (400px). Main padding `0 96px`, vertically centred.
- "step 1 of 4" (graphite 20px) → title **"Let's tidy a folder."** (Gochi 64px) → body (23px, max 600px): *Pick the folder with your invoices and receipts. Pip reads them here, on this computer, and suggests where each one should go.*
- Buttons: primary **"Choose folder…"** (folder icon) → `platform.selectFolder()`. Secondary **"try the demo files"** → existing sample-folder action (sets demo data mode).
- Hint (18px, #555): *PDFs with text, TXT and CSV · up to 100 files · subfolders included*
- Pip `waiting` (250×271, with mug) + bubble *"…go on, pick a folder."*
- Three promise cards across the bottom (card A / B / A, `4px` shadow): **reads only**: *Reading never moves, renames or deletes anything.* · **you decide**: *Nothing moves until you press "Move files". You can put them back later.* · **stays here**: *No uploads, no cloud AI. The model runs on this computer.*
- If `capabilities.selectFolder` is false (browser mode), the primary is the disabled style with the reason *"folder picking needs the desktop app"*, and "try the demo files" becomes the primary.

### 1b · Folder chosen (`folder selected, not scanning`)
- Padding `34px 64px 24px`. "step 1 of 4" + title **"Ready when you are."** (52px).
- Grid `1.25fr 1fr`, gap 28px.
- Left card A (6px shadow): yellow folder icon, "your folder" label, folder **name** (32px), link "change" (re-opens picker). Below: full path in Space Mono 14px on `#F6F6F4` with a 2px dashed grey border. Then a dashed divider, **"what happens next"** and numbered steps:
  1. Pip reads every supported file in this folder and its subfolders.
  2. You check anything he isn't sure about.
  3. Files only move when you press "Move files" (marker highlight). You can put them back.
- Right card B: **"Pip reads"** chips (done tone): PDF with text · TXT · CSV. **"Pip skips (and tells you)"** chips (muted): photos · Word files · scanned PDFs · files over 10 MB · shortcuts. *Up to 100 files per run.*
- Yellow sticky (−1°): *Reading only looks. Nothing gets moved, renamed or deleted, and nothing leaves this computer.*
- Footer: link "← choose another folder" | primary **"Start reading →"** → existing scan action.
- No Pip on this screen. Don't show a file count, since the picker returns `documentCount: null`.
- If the supported-type list or limits differ from what the API/mock enforce, **use the API's values** and tell Kristian. Don't hard-code a promise the backend doesn't keep.

### 1c · Pip is reading (`scanning`)
- Grid `380px 1fr`, gap 40px. Left: Pip `reading` (270×292, holding a receipt) + bubble *"reading {total} files. riveting."*
- Right: folder name (graphite) + title **"Reading your files…"**.
- Progress card A: "**{done}** of {total} files read" (Space Mono numbers), `HatchProgress`, "now reading `{path}`".
  - The time estimate ("about 20 seconds left") is shown **only if the API provides one**. Never make it up.
  - Unknown total → indeterminate bar and "reading files…".
- "just read" card B: last 4 results (name · amount in Space Mono · chip **ready / check this / couldn't read**), but **only if the scan progress exposes per-file results**; otherwise omit the card and leave the space to the progress card. Unknown amounts show `—`.
- Footer left: lock icon + *Nothing moves while Pip reads. Everything stays on this computer.* Right: disabled **"Check files →"** with reason *"opens when reading is done"*. When the scan finishes, go to the existing review screen (as today).
- A cancel control isn't designed yet. Keep the existing one if there is one and style it as a `link` button in the footer left; otherwise don't add one.

### 1d · Scan stopped (`scan error`)
- Same grid as 1c. Pip `sigh` (crooked glasses) + bubble *"\*sigh\*. that didn't work."*
- Title **"The reading stopped."**
- Pink sticky (`role="alert"`): *Pip stopped at file {n} of {total} because the local AI isn't answering.* / **Nothing was changed.** *No files moved, and no plan was made.* Use the real error. For other error types, write the plain cause in the same sentence form ("…because the folder can't be opened"). Never show a stack trace; put technical detail behind a "details" link if it exists.
- Card A **"how to fix it"**: (1) Open **Ollama** on this computer and wait until it says it's running. (2) Press "Try again" (marker highlight). Pip starts the folder from the top. Note: *Still stuck? Settings shows whether the local AI and the model are running. GhostOS never switches to a cloud AI.* Show the Ollama steps only for the AI-unavailable error.
- Header pill switches to the pink "local AI not answering" variant.
- Footer: link "← choose another folder" | primary **"Try again"** → restart scan.
- Reproduce with `mockScenario.scanError = true`.

## 7. Pip SVG (viewBox `0 0 120 130`, ink `#1a1a1a`)

Common body: `M20 60a40 40 0 0 1 80 0v50q-6.67 10-13.33 0t-13.33 0t-13.33 0t-13.33 0t-13.33 0t-13.33 0Z` (white fill, stroke 3, round joins) · hair `M60 21q5-9-2-13` · shadow ellipse `cx60 cy125 rx32 ry3.5` dashed `4 4`.

| Mood | Face parts (stroke ≈2.3–2.6) |
| --- | --- |
| `mini` (header) | body stroke 5; glasses circles cx 47/73 cy 62 r 10 (stroke 4.5); lids `M40 60h14M66 60h14`; frown `M53 88q7-5 14 0`; no hair or shadow |
| `waiting` (1a) | glasses cx 47/73 cy 62 r 10; bridge/arms `M57 61q3-2 6 0M37 60l-9-3M83 60l9-3`; lids `M40 61h14M66 61h14`; pupils `M44 61.5a3 3 0 0 0 6 0ZM70 61.5a3 3 0 0 0 6 0Z`; bags `M40 77q7 3 14 0M66 77q7 3 14 0` (1.6); flat mouth `M52 87h12`; mug `M68 95h18v15a4 4 0 0 1-4 4H72a4 4 0 0 1-4-4Z` + handle `M86 99h3a4 4 0 0 1 0 8h-3` + steam `M73 90q2-3 0-6M80 90q2-3 0-6`; arm `M21 80c-5 2-8 6-7 11` |
| `reading` (1c) | same glasses/lids/pupils moved down 4 (cy 66); brows `M38 50l14 2M68 52l14-2`; paper `M30 86h60v30H30Z` with lines `M37 95h44M37 103h34M37 110h22` |
| `sigh` (1d) | glasses group `rotate(-8 60 62)` with crack `M75 55l-4 12`; closed eyes `M41 62q6 3 12 0M67 59q6 3 12 0`; bags; open mouth ellipse `cx60 cy88 rx4 ry3`; sigh puff `M66 90q8 2 14-2` dashed `3 3`; both arms `M21 80c-5 2-8 6-7 11M99 80c5 2 8 6 7 11` |

Exact markup is in the reference HTML files. **Pip rules:** at most one per screen; only in empty, reading, done and error moments; never in lists or forms; the joke goes next to a plain fact; never joke about money or the user's mistakes.

## 8. Layout, accessibility and checks

- Designed at **1366×768**. At **1920×1080** keep the header full width and cap the main content at `max-width: 1280px`, centred. No horizontal scroll at either size, and nothing cut off at 768px height.
- Focus ring on every control: `outline: 3px solid #1a1a1a; outline-offset: 3px` + `box-shadow: 0 0 0 6px #ffe066`. Don't remove outlines.
- Text ≥16px everywhere; contrast ≥4.5:1 (graphite `#6B6B6B` is the lightest allowed text colour).
- Disabled buttons use `disabled` plus visible reason text, not a tooltip only.
- `prefers-reduced-motion`: no animation required. If you add a bar shimmer, disable it there.
- Wording comes from this doc; don't revert to old labels ("Fixture data", "Approve and Organize", etc.).

**Verification before handoff:** `npm run typecheck`, `npm run lint`, `npm run build`, `npm test` (Codex's suite must still pass) · browser at 1366×768 and 1920×1080 through 1a → 1b → 1c → Check, plus 1d via `scanError` · DevTools Network shows no external font/CDN requests · `npm run dev` Electron smoke test · compare against the reference HTML files side by side.

---

## 9. Prompt for the IDE agent (paste into Claude Code / Codex in `GhostOS-ui-paper`)

```text
You are implementing Step 1 (Start) of the GhostOS paper redesign on branch feat/ui-paper.

Read first, in order: AGENTS.md, TODO.md, docs/design/step1-start.md (the spec, source of truth), and the
reference boards in docs/design/step1-start/*.html. Run `git status` and `git branch --show-current`; stop
and tell me if you are not on feat/ui-paper.

Rules:
- Only the Start step, the app header and shared paper components change. Check/Expenses/Done/History/Settings
  keep their current UI inside the new header.
- Do not touch backend/**, src/types/api.ts, src/api/**, src/fixtures/**, electron security settings, or Codex's
  test files (vitest.config.ts, src/test/**, *.test.ts, docs/qa/**).
- All data via GhostApi and src/platform; no new filesystem or network access. No Google Fonts/CDN: bundle fonts
  with @fontsource. Before changing package.json, add a TODO.md entry with the exact diff and wait for my OK.
- Never invent data the API doesn't provide (time estimates, per-file results, file counts) and never present
  demo data as real: show the "demo data" chip.
- Follow the spec's accessibility rules (16px min, #6B6B6B lightest text, visible focus ring, disabled + reason).
- Claim the task in TODO.md (Owner: <you> for Kristian, branch feat/ui-paper) before editing code.

Plan first: list the files you will add/change and how each state 1a–1d maps to the existing app state, then
wait for my "go". After implementing, run typecheck, lint, build and npm test, check 1366×768 and 1920×1080 and
the scanError path, and write a handoff note in TODO.md (what changed, verification, open questions). Do not
commit or push until I say so.
```
