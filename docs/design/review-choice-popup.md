# Review choice pop-up (before Check)

Status: **proposed, 2026-10-10 03:10.** Code freeze is 10:00 AM today, so this
spec has a freeze-safe version (no backend change) and a post-freeze follow-up.

## Why

After reading, some files always need a person: a total that disagrees, a missing
date, a statement or birth certificate, an unclear scan, a suspicious file. Today
the user must open every one of them in Check before **Move** unlocks. For a
quick demo, or a user who just wants the clear-cut files sorted, that is a wall.

Give the user one explicit choice up front:

1. **Review them one by one**: today's Check flow, unchanged.
2. **Put them all in Needs Review/**: file every flagged item into
   `Needs Review/` without opening them, and continue.

Either way nothing moves until the user presses **Move** on Totals, and nothing
set aside is counted in the totals.

## When it appears

- Right after reading finishes, before the Check list is shown.
- Only when `PlanPreview.blocking_review_count > 0`. With nothing to review,
  go straight to Check as today.
- Once per scan. Coming back to Check (back links, step tracker) never shows
  it again.
- Not for files that couldn't be read (`status: failed`): they already go to
  `Needs Review/` and never block.

## What it says

Paper dialog, same style as the "Move files?" and "Put files back?" dialogs
(`PaperDialog`, `role="alertdialog"`):

> **7 files need a look**
> Pip wasn't sure about these. You can check them now, or set them aside in
> **Needs Review/** and look later. Set-aside files aren't counted in your
> totals, and nothing moves until you press Move.
>
> - 3 totals or dates to confirm
> - 3 papers that aren't receipts (statements, IDs, unclear)
> - 1 file with suspicious text
>
> [ **Review them one by one** ] (primary, initial focus)
> [ Put all 7 in Needs Review/ ] (secondary)

- The grouped counts come from each file's first review flag and its
  `field_profile`. Exact wording is Dev 3's call; the numbers must come from the
  plan, never be estimated.
- **Esc / closing = review one by one.** That keeps today's behaviour, so the
  default is the safe one.
- Pip may appear (mood `suspicious`, one Pip per screen rule).

## What "Put all in Needs Review/" does

### Freeze-safe version (recommended for today, no backend change)

For every document where `status === "needs_review" && !user_corrected`, the
frontend sends the **existing** correction call, the same payload as the
"Leave for review" button that Kurt confirmed on 2026-10-10:

```http
PATCH /api/documents/{file_id}
{ "category": "uncertain", "accept": true }
```

Backend behaviour today (traced against `main`):

- `accept: true` sets `user_corrected`, clears review flags and sets
  `status: ok`, so the file stops blocking Move.
- `category: "uncertain"` routes it to `Needs Review/`.
- `uncertain` is never a report row, so it is never counted in the totals.
- No shop, date, amount, `document_kind` or `field_profile` is sent. The
  backend rejects those for non-transaction records anyway.

Then reload the plan once and open **Check** with everything resolved (the
"All checked" state). The user can still open any item and decide differently
before moving. Going straight to Totals is an option, but Check shows the user
what was set aside, so Check it is.

Rules:

- Calls run **one at a time** (the session store is in-memory; no need to
  stress it), with progress in the dialog ("Setting aside 3 of 7…").
- **Partial failure:** stop, keep what succeeded, show which file failed and
  why, and leave the user in Check with the rest still to review. Never retry
  silently and never report success for a failed call.
- Log one History entry: "Set aside 7 files in Needs Review/".
- Prompt-injection files (`possible_injection`) are included. Set aside, they
  are still never interpreted.

### Known side effect to handle (Dev 3)

Setting a flagged **receipt or invoice** aside overwrites its `category` with
`uncertain`, while its backend `document_kind` (e.g. `receipt`) and therefore
`field_profile: transaction` stay as they were. If the user later reopens it in
Check and presses **Looks right**, today's panel only sends shop, date and amount,
so the category stays `uncertain` and the file still goes to `Needs Review/`.
When a transaction document is reviewed, the panel must also send
`category: document_kind` (`receipt` or `invoice`) to file it properly.

### Post-freeze version (Dev 1, optional)

A dedicated endpoint that defers without overwriting the model's category:

```http
POST /api/scans/{scan_id}/defer-reviews
-> { "deferred": ["f07", "f13", …], "plan_revision": n }
```

It sets a backend-owned `deferred: true` (routes to `Needs Review/`, never
counted, does not block), keeps `category` intact so a later review restores it
cleanly, and is one request instead of N. Not needed for the demo.

## Totals: fix the Needs Review/ label

`lib/totals.ts` `folderNote()` labels `Needs Review/` as **"couldn't read"**.
Once files can be set aside on purpose, that is wrong (screenshot: 3 files, of
which only 1 was unreadable). Change the note to **"look later"** (already used
on Done), or show the real split when it's available: "1 couldn't read ·
2 set aside".

## Cascaded tasks

### Developer 1 — API owner

- Freeze-safe: nothing to change. Confirm the batch of
  `{category: "uncertain", accept: true}` calls is fine to run back to back
  (each bumps the plan revision).
- Post-freeze (optional): `POST /api/scans/{scan_id}/defer-reviews` as above,
  with tests that deferred files go to `Needs Review/`, are excluded from
  `report_rows`, don't block, and keep their original `category`.

### Developer 2 — local AI owner

- No model or prompt change. Make sure every review flag the validator emits has
  a clear `message`; the dialog groups files by them.

### Developer 3 — UI owner (Kristian)

- Dialog after reading when `blocking_review_count > 0`, once per scan; Esc =
  review one by one.
- "Put all in Needs Review/": sequential PATCH loop with progress, partial
  failure handling, one History entry, then Check in the "All checked" state.
- Fix the side effect above: reviewing a transaction document sends
  `category: document_kind`.
- `folderNote()` label fix on Totals.
- Demo mock: no change needed (the mock already mirrors the PATCH rules).
  Add vitest cases below.

### Developer 4 — QA owner

Fixture scan (20 docs, 7 blocking) plus one live offline run:

1. Reading finishes with blocking files → the dialog shows the right count.
2. **Review one by one** → Check exactly as before; Move stays locked until
   all are decided.
3. **Put all in Needs Review/** → 7 PATCH calls, Move unlocks, Totals shows
   those 7 under `Needs Review/` with the new label, totals unchanged.
4. Totals amounts before and after setting aside are identical (nothing set
   aside is ever counted).
5. Reopen a set-aside receipt in Check, fix it, **Looks right** → it moves to
   `Receipts/YYYY-MM/` and is counted.
6. Partial failure (stop the backend mid-batch) → error shown, nothing reported
   as done that wasn't, user left in Check.
7. A scan with no blocking files → no dialog.
8. Esc on the dialog → Check, nothing changed.

## Acceptance criteria

- The choice is explicit; the safe default (review one by one) is what Esc and
  closing do.
- Setting aside never counts a file in the totals and never moves anything
  before **Move**.
- No transaction fields, `document_kind` or `field_profile` are sent by the
  bulk action.
- Every set-aside file can still be reviewed individually before moving.
- `Needs Review/` is no longer described as "couldn't read" when it holds
  set-aside files.
