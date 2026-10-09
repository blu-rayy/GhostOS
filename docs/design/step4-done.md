# Step 4 · Done: paper redesign handoff

Status: **approved by Kristian (2026-10-09)** · Branch: `feat/ui-paper` · Builds on `step1-start.md` (tokens, components, header, Pip rules, accessibility rules).
Reference boards: `docs/design/step4-done/4a…4d.html` (canvas row "Step 4 · Done").

## 1. Scope

| In scope | Out of scope |
| --- | --- |
| Done screen after files are moved; put-back confirm, result and conflict states (4a–4d) | `backend/**`, the API contract, fixtures, Codex's tests |
| New Pip moods `done` and `shrug` | Step 3 (Totals/move), which stays on the current UI; reach Done the way the current completion screen is reached today |
| | **"Open folder"** needs a new preload method, so it's a separate task that Kristian has to approve (Electron change). Until then, **omit the button** |

## 2. Layout

Header: Start ✓, Check ✓, Totals ✓ (solid connectors), **Done** = current. Main: grid `340px 1fr`, gap 40px, padding `24px 64px 18px`. Left column = Pip + speech bubble; right column = content. Footer 72px, dashed top border.

## 3. States

### 4a · All tidy (after a successful move)
- Pip `done` + bubble *"17 files. sorted. you're welcome."* (use the real count).
- Folder name (graphite) + title **"All tidy."** (Gochi 56px) + *"{moved} files moved into {k} folders. {stayed} stayed where they were."*
- Card A **"where they went"**: folder rows from the move result. Card B **"totals"**: one line per currency (never added together), plus secondary **Save list as CSV** (existing export).
- Row under a dashed divider: (Open folder, omitted for now) · *"Moved the wrong way? You can undo it all."* · **careful** button **"Put files back…"** (pink `#ffd6d6`, ink border/shadow).
- Footer: history icon + *"Saved in History · {date, time}"* (from `BatchResult.committed_at`) | primary **Tidy another folder** → back to Start 1a.

### 4b · Confirm putting files back (`role="alertdialog"`)
- Dimmed page (`rgba(255,255,255,.72)`), dialog 560px, card B shape, `8px` ink shadow.
- **"Put {n} files back?"** · *Each file goes back to **exactly where it was** before you pressed Move.* State what happens to the created folders **only as the undo endpoint actually does it**; if unknown, leave that sentence out.
- Yellow sticky: *Your saved CSV stays. If you changed a moved file since, Pip leaves that one alone and tells you.*
- Buttons: secondary **Keep them where they are** (initial focus) · primary **Put {n} files back** (ink with a pink `#ffb3b3` offset shadow to signal care). Esc = keep.

### 4c · Put back (undo fully succeeded)
- Pip `shrug` + bubble *"fine. undone. as if i never tried."*
- Title **"Back how it was."** + a plain summary. Ticks: *{n} of {n} files put back* · *nothing deleted, nothing renamed* · *your CSV is still saved* (only claims that are true).
- *This shows up in History as "put back".* (if an activity log exists; otherwise omit)
- Footer: primary **Tidy a folder**.

### 4d · Some files stayed (undo conflicts)
- Pip `sigh` (from Step 1) + bubble *"two of them got comfy."*
- Title **"{ok} back, {stuck} stayed."** · pink sticky (`role="alert"`): *Pip didn't overwrite anything. These {stuck} stay in their new folder until you decide.*
- Card: one row per conflict: file name, plain reason, and its current folder in Space Mono. Reasons come from `UndoResult.conflicts[].reason` (shown verbatim, so the backend should write it for the end user). If it is empty, use *"couldn't go back safely"*. Example reasons: *a different file with this name is in the old spot now* · *you edited it after it was moved*.
- *You can move these yourself, or leave them. Pip won't touch them again.*
- Footer: primary **OK, leave them**.
- Reproduce with `mockScenario.undoConflict = true`.

## 4. Pip moods (viewBox 0 0 120 130)

Exact SVGs are in the reference boards (`4a` = done, `4c` = shrug, `4d` = sigh).
- `done`: standard glasses/lids/pupils/bags, small smirk `M54 86q6 3 11-1`, green clipboard `M70 88h22v28H70Z` (#9be8b8) with clip `M76 86h10v5H76Z` and check `M75 102l4 4 8-9`, left arm.
- `shrug`: standard face, flat mouth `M53 87h14`, raised arms `M21 80q-9-2-12-10M99 80q9-2 12-10`.

## 5. Data rules

- Counts, folders, totals and conflicts come from the organize/undo results and `PlanPreview` via `GhostApi`. Don't recompute them in the UI.
- Undo has no pre-check endpoint, so conflicts appear **after** the undo returns (4d is a result screen, not a warning).
- Totals per currency, no conversion.
- Jokes stay next to plain facts and never about money or the user's mistakes.

## 6. Verification

typecheck, lint, build, `npm test` · fixture flow to Done (4a) → Put back → 4c · with `undoConflict` → 4d · keyboard: the dialog traps focus and Esc cancels · 1366×768 and 1920×1080 · compare with the reference boards.

## 7. Prompt for the IDE agent

```text
Implement Step 4 (Done) of the GhostOS paper redesign on feat/ui-paper, after Steps 1 and 2. Read AGENTS.md,
TODO.md, docs/design/step1-start.md, docs/design/step4-done.md and docs/design/step4-done/*.html. Same rules:
stay in scope, all data via GhostApi, only state what the API confirms (undo folder cleanup, timestamps,
conflict reasons), omit "Open folder" (needs an Electron preload change I must approve separately). Claim the task in
TODO.md, plan first and wait for my "go", then implement, verify (including mockScenario.undoConflict) and
write a TODO.md handoff note. Do not commit or push until I say so.
```
