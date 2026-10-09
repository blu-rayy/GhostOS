# Step 3 · Totals: paper redesign handoff

Status: **approved by Kristian (2026-10-09)** · Branch: `feat/ui-paper` · Builds on `step1-start.md` (tokens, components, header, Pip rules, accessibility rules) and `step2-check.md` (`FolderRow`).
Reference boards: `docs/design/step3-totals/3a…3d.html` (canvas row "Step 3 · Totals").

**Decisions (Kristian, 2026-10-09):**
1. The step is called **Totals**, not Expenses. Invoices can be income and the contract has no income/expense type yet. Use neutral words everywhere ("totals", "counted"); don't say "expense". A type may come later (Developer 1).
2. 3c (moving progress) and 3d (some files didn't move) **are built now**. 3d works with today's contract. 3c needs a new endpoint, so until it exists it uses the simple fallback in §3 (see the API requests in `docs/frontend-api-handoff.md`).
3. All dates, amounts and folders come from the API. The dates on the reference boards are placeholders.

## 1. Scope

| In scope | Out of scope |
| --- | --- |
| Totals screen (3a), move confirmation (3b), moving (3c), move problems (3d) | `backend/**`, `src/types/api.ts`, `src/api/http.ts` contract changes (ask Developer 1 first), fixtures, Codex's tests |
| Optional mock-only additions in `src/api/mock.ts` to demo 3c/3d (behind `mockScenario` flags, off by default) | Any real file operation in the renderer: moving happens only through `GhostApi.approve` |

This replaces the current plan/report screen. Step 2's "Continue to totals →" now leads here, and a successful move leads to Done (Step 4).

## 2. 3a · Totals (data: `PlanPreview`)

Header: Start ✓, Check ✓, **Totals** current. Main grid `1fr 360px`, gap 26px, padding `18px 32px 14px`.

**Left column**
- Title **"Your totals"** (Gochi 42px) and, on the right, `{n} files · {month range} · {folder}`.
- One card per entry in `totals[]` (alternating card A/B, `4px` shadow): label `{currency name} · {row_count} files`, amount in Space Mono 26px bold with a green marker highlight. **Never add currencies together.** If there are 3 or more currencies, wrap the cards to a second line.
- Yellow sticky next to them (only when there are 2 or more currencies): *Kept separate. Pip doesn't convert currencies, so nothing gets guessed.*
- Card **"the list"**: filter chips `all · {month} …` built from the rows' months + "sorted by date". Columns: **date** (Space Mono) · **shop** (+ green chip **✓ you checked** when `user_corrected`) · **kind** · **amount** (right-aligned, Space Mono) · **goes to** (destination folder from `operations[]`). Only `accepted` rows count toward the totals. Rows still marked `needs_review` can't appear here, since Check blocks them.
- The list scrolls inside its card. The page itself never scrolls at 768px.

**Right column**
- Card B **"ready to move"**: `FolderRow` per destination folder with counts from `operations[]`, notes *not counted* (Other/) and *couldn't read* (Needs Review/). Below a dashed divider: *"{moves} move · {stay} stay where they are"* + link **see every move**, which opens a sheet listing every `original → destination` and marks `collision_suffixed` names with a chip **"(2) added"**.
- Secondary **Save list as CSV** (existing export; *saved on this computer · works in Excel or Sheets*).
- Yellow sticky at the bottom: *Moving is the only step that changes your folder. You can put everything back from **History**.*

**Footer**: link **← back to check** · *"nothing has moved yet"* · primary **"Move {moves} files →"** (opens 3b). If `blocking_review_count > 0`, the primary is disabled with the reason *"check {k} more file(s) first"*. That shouldn't normally happen, but guard it anyway.

## 3. States

### 3b · Confirm the move (`role="dialog"`, aria-modal)
3a stays visible underneath, dimmed with `rgba(255,255,255,.72)`. The dialog is 560px, card A shape, 8px ink shadow.
**"Move {n} files?"** · *They'll go into new folders inside `{folder}/`. Nothing is deleted or renamed, except (2) added if a name is already taken.* (Show the "(2)" clause only when some operation has `collision_suffixed`.) · dashed box with the `FolderRow`s · undo line with an icon: *Changed your mind later? **History → Put files back** returns all {n} to where they were.*
Buttons: secondary **Not yet** (initial focus, Esc) · primary **Move {n} files** → `GhostApi.approve(plan_id)`.

### 3c · Moving
- Pip `carrying` (box of files, sweat drop) + bubble *"carrying {n} files. my back."*. Folder name + title **"Moving your files…"**.
- **With a progress endpoint** (requested, see API requests): progress card *"{moved} of {total} moved"*, `HatchProgress`, *now moving `{current_file}`*, and a **"just moved"** card with the last 4 `file → folder · moved` rows.
- **Fallback with today's contract** (`approve` returns only when finished): the same screen with an **indeterminate** hatch bar and *"moving {n} files…"*, and no counts and no "just moved" list. Never fake progress.
- Footer: info icon + *Keep GhostOS open until this finishes.* · link **stop after this file** (*only if a cancel endpoint exists, otherwise omit*) · disabled **Done →** with *"opens when moving is done"*.
- On success (`failed[]` empty) → Done 4a.

### 3d · Some files didn't move (`BatchResult.failed[]` not empty)
- Pip `sigh` + bubble *"{k == 2 ? 'two' : k} of them refused to budge."* (keep it short; for k > 3 use *"a few of them refused to budge."*).
- Title **"{moved} moved, {k} didn't."** · pink sticky (`role="alert"`): *These {k} files are **still where they were**. Nothing was lost or half-copied.* (**Requires backend confirmation** that a failed move leaves the original untouched. Until Developer 1 confirms, use: *These {k} files didn't reach their new folder.*)
- Card: one row per `failed[]` entry: file name (from `file_id` → document) + `error` shown verbatim as the plain reason + chip **didn't move**.
- Secondary **Put all {moved} back** → existing undo for `batch_id` (with 4b-style confirmation) + *undo this whole move, like it never happened*.
- Footer: link **leave the {k} where they are →** (goes to Done 4a with the partial counts) · primary **Try the {k} again** (*only if a retry endpoint exists; otherwise make "leave them" the primary and omit this button*).

## 4. Pip mood `carrying` (viewBox 0 0 120 130)

Exact SVG is in `3c-moving.html`. Standard body + hair; glasses/lids/pupils raised 4px (cy 58); strained mouth `M54 76q6-3 12 0`; sweat drop `M101 40q3 5 0 7q-3-2 0-7Z` (fill `#c9d7ff`); yellow box `M30 84h60v30H30Z` with lid line `M30 92h60` and tape `M54 84v8M66 84v8`; arms `M22 92q4 6 8 8M98 92q-4 6-8 8`.

## 5. Data rules

- Totals, rows, destinations and counts come only from `PlanPreview`. The UI never sums amounts itself (decimal strings, no floats).
- Never present demo/fixture runs as real: the "demo data" chip from Step 1 stays visible.
- Copy the counts in buttons from the data (`Move {operations.length} files`). Never hard-code 17.

## 6. Verification

typecheck, lint, build, `npm test` · fixture flow Check → Totals → confirm → move → Done · a mock scenario with 2 failed moves for 3d (add `mockScenario.moveFailures`, off by default) · the dialog traps focus and Esc cancels · 1366×768 and 1920×1080 · the list scrolls inside its card at 768px · compare with the reference boards.

## 7. Prompt for the IDE agent

```text
Implement Step 3 (Totals) of the GhostOS paper redesign on feat/ui-paper, after Steps 1, 2 and 4. Read AGENTS.md,
TODO.md, docs/design/step1-start.md, docs/design/step3-totals.md, docs/frontend-api-handoff.md (section
"Requests from the paper redesign") and docs/design/step3-totals/*.html. The step is named "Totals": no
"expense" wording. All numbers come from PlanPreview/BatchResult via GhostApi; never sum amounts or fake progress.
3c uses the indeterminate fallback until a batch-progress endpoint exists; omit cancel/retry buttons until their
endpoints exist. Mock additions only behind mockScenario flags (off by default). Claim the task in TODO.md, plan
first and wait for my "go", then implement, verify and write a TODO.md handoff note. Do not commit or push until I say so.
```
