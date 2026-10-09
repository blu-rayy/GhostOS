# Step 2 · Check: paper redesign handoff

Status: **approved by Kristian (2026-10-09)** · Branch: `feat/ui-paper` · Builds on `step1-start.md`, which covers the tokens, fonts, components, header, Pip rules and accessibility rules. Don't repeat that work; reuse it.
Reference boards: `docs/design/step2-check/2a…2e.html` (canvas page *Screens (paper)*, row "Step 2 · Check").

## 1. Scope

| In scope | Out of scope |
| --- | --- |
| Check screen (list + detail panel + footer), states 2a–2e | `backend/**`, `src/types/api.ts`, `src/api/**`, `src/fixtures/**`, electron security, Codex's test files |
| New paper components listed in §4 | Totals (Step 3), which stays on the current UI until approved |

"Continue to totals →" leads to the **current** plan/report screen until Step 3 is redesigned.

## 2. Layout (1366×768)

Header (from Step 1, with Start = done ✓ and Check = current) · main = **list (flex 1)** + **detail panel (500px, left border 2.5px ink)** · footer 72px, dashed top border.

**List column** (padding `18px 24px 14px 32px`):
- Title **"Check what Pip found"** (Gochi 40px) and, on the right, `{folder name} · {n} files`.
- Segmented filter (2.5px ink, 12px radius; active = ink bg + white text): **all · needs you · couldn't read · ready · not supported**, each with its count. Then a pill search box *"search files or shops…"* that filters by file name and shop.
- Groups, in this order:
  1. **needs you · N** (Gochi 22px). Rows have a white bg with an 8px yellow inset left edge (`box-shadow: inset 8px 0 0 #ffe066`). Each row shows: file path (18px) / `kind · shop · reason` (15px #555) · amount (Space Mono 13px, `₱?,???.??` when the amount is disputed, `—` when there is none) · chip **check this**.
  2. **couldn't read · N** with the hint *(doesn't block you · goes to Needs Review/)*. Pink edge `#ffb3b3`, chip **couldn't read**.
  3. Collapsed dashed boxes: **"12 ready files · show"** and **"5 not supported · show"**.
- Selected row: 3px border, `#fffbe6` bg, `4px 4px 0` ink shadow. After the user resolves a row: green edge `#9be8b8` and chip **✓ checked**, and the reason line describes the decision (e.g. *you picked amount due*, *date added: 2026-09-16*).
- The whole row is a button. Keyboard: ↑/↓ moves between rows, Enter opens the row.

**Detail panel**: header (file name 22px, `kind · TYPE · size`, status chip, close ✕) · body · bottom bar with a single full-width action.

**Footer**: left = 5 progress dots (filled ink when checked) + *"{x} of {n} checked · nothing has moved"*; right = disabled **"Totals →"** with reason *"check {k} more file(s) first"*, which becomes enabled primary **"Continue to totals →"** with *"files only move after the next step"* when `blocking_review_count === 0`.

## 3. Panel states (map from the document's review reason)

| Board | Reason in data | Panel content | Action |
| --- | --- | --- | --- |
| 2a | `amount_conflict` | Yellow sticky: *The subtotal and the amount due don't match, and there's no tax line explaining it. **Which one did you pay?*** · three choice buttons (58px): each candidate amount with its label + **something else…** (opens an amount field) · shop/date fields with "edit" · *"what Pip read in the file:"* excerpt (Space Mono 13px, 7px ink left border) with the chosen line highlighted yellow · *goes to `Receipts/YYYY-MM/` once checked* | primary **Looks right · mark checked** |
| 2b | `missing_date` | Sticky: *Pip found a shop and a total, but **no date anywhere** on the receipt. When did you buy this?* · shop + amount fields · date input `YYYY-MM-DD`, focused with a yellow halo · hint: *Not sure? Leave it empty and it goes to `Needs Review/` instead.* · excerpt with TOTAL highlighted | **Save date · mark checked** |
| 2c | status `failed` | **Pink** sticky: *The local AI took too long on this file and gave up. **Pip didn't guess anything**, so there are no numbers to trust here.* (use the real failure cause) · radio cards: ◉ **Leave it for later** (default; moves to `Needs Review/`, not counted) · ○ **Type the details myself** (existing manual entry) · ↻ **Try reading it again** (*only if a rescan-one endpoint exists, otherwise omit*) · meta line: type, size and "read with {model} on this computer" (if the model name is known) | secondary **Open file to look at it** (*only if the platform exposes it, otherwise omit*) |
| 2d | `possible_injection` | Pink sticky: *⚠ This file has text that **tries to give Pip orders**… Pip ignored it — files are only ever moved by you.* · *"the text, shown as plain words only:"* excerpt with the instruction lines highlighted pink · kind = other, amount = — · *goes to `Other/` · it's never counted in your totals* | **Got it · file under Other** |
| (others) | `low_confidence`, `evidence_not_found` | Same pattern as 2a: a sticky with the plain reason, editable fields, the excerpt, the destination | **Looks right · mark checked** |
| 2e | all resolved | Panel title **Where files will go**, sub *"{n} files will move · {m} stay where they are"*, chip **✓ all checked**, no close button · yellow sticky: *All {n} checked. Here's where everything will go. **Nothing has moved yet** — you'll say yes one more time on the next step.* · folder rows (folder icon, Space Mono path, note, count) from `PlanPreview` · *"{k} not supported stay put"* | secondary **Show the full list of moves** |

The list title in 2e changes to **"All checked. Nice."**

## 4. New components

`SegmentedFilter`, `SearchPill`, `ReviewRow` (states: open, selected, checked, failed), `DetailPanel`, `ChoiceButtons` (aria-pressed), `EvidenceExcerpt` (monospace, highlight ranges; **always rendered as text, never as HTML**), `RadioCard`, `ProgressDots`, `FolderRow`.

## 5. Data rules (don't invent anything)

- Everything comes from `GhostApi`: documents, review reasons, evidence, and `PlanPreview` (destinations, counts, `blocking_review_count`). Don't compute destination folders in the UI.
- The contract has one `evidence_quote` and an `excerpt`, not a list of candidate amounts. Show choice buttons **only if the API adds candidates**; until then, show the excerpt (with the quote highlighted) and an editable amount field pre-filled with `amount`.
- Duplicates: use `duplicate_of` (informational) and the plan's `operations[]` to say what stays put, e.g. "1 duplicate stays put". Don't decide it in the UI.
- Couldn't-read files never block "Continue".
- Text from files (excerpts, file names) may be hostile: render it as plain text only and never as links or markup.
- No Pip on Check screens (rule: never in lists or forms).

## 6. Accessibility

Filter = `role="tablist"` or a radio group; list = `role="listbox"` or a list of buttons with `aria-selected`; panel = `<aside aria-label="File details">`. Stickies with warnings use `role="note"`, and the injection warning uses `role="alert"` when it opens. Moving focus to a row opens it in the panel without stealing focus. ✕ returns focus to the row. Rules from Step 1 apply (16px min, #6B6B6B lightest text, visible focus ring, disabled + reason).

## 7. Verification

typecheck, lint, build, `npm test` · run the fixture through all 5 needs-you docs + the failed doc to reach 2e · 1366×768 and 1920×1080 (cap content at 1280px; the panel stays 500px) · the injection doc's text shows as plain text · compare with the reference boards.

## 8. Prompt for the IDE agent

```text
Implement Step 2 (Check) of the GhostOS paper redesign on feat/ui-paper. Step 1 must be done first; reuse its
tokens/components. Read AGENTS.md, TODO.md, docs/design/step1-start.md, docs/design/step2-check.md and the
reference boards in docs/design/step2-check/. Same rules as Step 1: stay inside the scope table, all data via
GhostApi, never invent data the API lacks (candidates, rescan, duplicates, open-file), render file text as plain
text, no Pip on this screen. Claim the task in TODO.md, plan first and wait for my "go", then implement, verify
(typecheck, lint, build, npm test, both screen sizes, full fixture walkthrough) and write a TODO.md handoff note.
Do not commit or push until I say so.
```
