# Review choice pop-up (before Check)

Status: **proposed, rev 2, 2026-10-10 ~03:40.** Checked against `main` at
`0dfdb65` ("standardize uncategorized destinations") plus `9a909c7`.
Code freeze is 10:00 AM. Rev 1 was written against an older `main` (before the
`Uncategorized/` rename and the backend's partial sort mode) and is superseded.

## Why

After reading, some files always need a person: a total that disagrees, a missing
date, a statement or birth certificate, an unclear scan, a suspicious file. Today
**Move** stays locked until every one of them is opened in Check. Give the user
one explicit choice up front:

1. **Review them one by one**: today's Check flow, unchanged (`mode=blocking`).
2. **Put them all in Uncategorized/**: leave them unchecked, file them to
   `Uncategorized/`, keep them out of the totals, and let Move go ahead
   (`mode=partial`).

Either way nothing moves until the user presses **Move**, and nothing set aside is
counted in the totals.

## The backend already supports option 2 (no backend change needed)

`0dfdb65` added a sort mode, `SortMode = "blocking" | "partial"`
(`backend/app/schemas.py`):

- `GET /api/scans/{scan_id}/plan?mode=partial` builds a plan in which documents
  with `status == "needs_review"` and not `user_corrected` go to `Uncategorized/`
  (the "Waiting for human review" branch of `_build_plan`, which runs before the
  document-aware branch) and get **no** report row, so they are never counted.
  The response includes `"mode"`.
- `POST /api/plans/{plan_id}/approve` with `{"mode": "partial"}` approves even
  with unresolved items. The mode must match the previewed snapshot: approving
  with `{}` (implicit `blocking`) a partial plan → **409**; an older preview in
  another mode is superseded → refresh before approving.
- Undo works the same (tested: `test_partial_mode_routes_unsorted_and_requires_matching_explicit_approval`).
- `blocking` stays the default for every existing call, so nothing changes for
  users who don't pick option 2.

Because option 2 is a **plan mode, not a per-file correction**, no document is
modified: no category is overwritten, nothing is accepted on the user's behalf,
and every set-aside file can still be opened and decided individually in Check.

## When the pop-up appears

- Right after reading finishes, before the Check list is shown.
- Only when the plan's `blocking_review_count > 0`. With nothing to review, go
  straight to Check as today.
- Once per scan. Coming back to Check (back links, step tracker) never shows it
  again. The chosen mode is remembered for the scan.
- Files that couldn't be read (`status: "failed"`) never block and already go to
  `Uncategorized/`; they are not counted in the pop-up.

## What it says

`PaperDialog`, default dialog role, like **Move files?**
(`TotalsSummary.tsx`). Only **Put files back?** (`DonePage.tsx`) uses
`role="alertdialog"`. This is a choice, not a warning, so the default role is right.

> **7 files need a look**
> Pip wasn't sure about these. You can check them now, or set them aside in
> **Uncategorized/** and look later. Set-aside files aren't counted in your
> totals, and nothing moves until you press Move.
>
> - 3 totals or dates to confirm
> - 3 papers that aren't receipts (statements, IDs, unclear)
> - 1 file with suspicious text
>
> [ **Review them one by one** ] (primary, initial focus)
> [ Set all 7 aside in Uncategorized/ ] (secondary)

- **Counts come from `state.scan.documents`, not the plan.** The plan response
  only has operations, report rows, totals and `blocking_review_count`. Group the
  documents with `status === "needs_review" && !user_corrected` by their first
  review flag and their `field_profile`. The total must equal the plan's
  `blocking_review_count`; if it doesn't, show only the total.
- **Esc / closing = review one by one** (the safe default: nothing changes).
- Pip may appear (mood `suspicious`; one Pip per screen).

## What "Set all aside" does (frontend, Dev 3)

1. Remember `sortMode = "partial"` for this scan (session state, reset by
   `resetSession`).
2. Reload the plan with `?mode=partial`. Every later plan reload (after any
   correction) must pass the same mode.
3. Go straight to **Step 3 · Totals** (nothing is left to decide). "← back to
   check" still opens Check, where the set-aside files are listed as "set aside ·
   goes to Uncategorized/" and **Continue to totals** is enabled.
4. **Move** approves with `{"mode": "partial"}`. If the backend answers 409
   (stale or mismatched snapshot), reload the plan in the same mode and ask the
   user to press Move again. Never retry silently.
5. If the user reviews a set-aside file anyway, the normal correction flow
   applies and it leaves `Uncategorized/` as usual. No special handling.
6. Offer a way back to strict checking on Check ("Review the rest instead"),
   which switches to `blocking` and reloads the plan.

Code changes this implies:

- `api/client.ts` / `api/http.ts`: `getPlan(scanId, mode?)` →
  `/api/scans/{id}/plan?mode=…`; `approvePlan(planId, mode?)` → body
  `{ mode }`. Omit the mode for `blocking` so today's requests are unchanged.
- `types/api.ts`: add `mode?: "blocking" | "partial"` to `PlanPreview`.
- `api/mock.ts`: implement both modes the way `_build_plan` and `approve_plan`
  do (partial routing, no report rows for unresolved items, 409 on mode
  mismatch). The mock was updated tonight to the merged PATCH and routing rules
  (`Uncategorized/`, document-aware `Other/` branch, `needsReview` =
  `status === "needs_review" && !user_corrected`, `status: "ok"` on accept,
  422s), but it has **no** sort modes yet.
- `types/ui.ts`: a new History event type, e.g. `reviews_set_aside`, logged
  once ("Set 7 files aside in Uncategorized/"). The existing `record_reviewed`
  is per file and doesn't fit.
- `lib/totals.ts` `folderNote()`: `Uncategorized/` is labelled **"couldn't
  read"**. With set-aside files that's wrong (3 files, 1 unreadable). Use **"look
  later"**, as Done already does (`doneNote()` in `DonePage.tsx`), and update
  `totals.test.ts`.

## Open decision for Dev 1: "Leave for review" now files to Other/

Separate from the pop-up, but found while checking it. Since `9a909c7`,
`_build_plan` sends every **reviewed** document-aware non-transaction paper to
`Other/`, whatever its category:

```python
elif document_aware and field_profile != "transaction":
    folder = "Other"
```

So the per-file **Leave for review** button (`{"category": "uncertain",
"accept": true}`, confirmed by Kurt) on a statement, ID or unclear scan now
lands in `Other/`, not `Uncategorized/`. The Check panel still promises
"Leave for review → Uncategorized/", and that's false today. Options:

- **A (recommended, one line, backend):** keep `uncertain` in `Uncategorized/`:
  `folder = "Uncategorized" if category == "uncertain" else "Other"`.
- **B (frontend):** in the panel, "Leave for review" stops sending a correction
  and just leaves the file unchecked. It then only works in `partial` mode.

Until one is chosen, the frontend tests assert today's backend behaviour
(`Other/`).

## Corrections to rev 1 (from review)

| Rev 1 said | Actually (on `main`) |
|---|---|
| `Needs Review/` | The folder is **`Uncategorized/`** everywhere (`0dfdb65`). |
| Loop `PATCH {category: "uncertain", accept: true}` over every file | Use the backend's **`mode=partial`**; no document is modified. This also removes the category-overwrite side effect and the `document_kind`-null fallback problem. |
| Same `alertdialog` style as "Move files?" | "Move files?" uses the default role; only "Put files back?" uses `alertdialog`. |
| Backend rejects `document_kind` | `document_kind` is **accepted** (validated: unsupported values and kind/category contradictions → 422). Only `field_profile` and other backend-controlled fields are always 422. Money fields → 422 unless the resulting profile is `transaction`. |
| Mock already mirrors the PATCH rules | True for the PATCH and routing rules after tonight's update; **not** for sort modes (see above). |
| Grouped counts from the plan | From `scan.documents`; the plan doesn't carry per-file flags. |
| "Add vitest cases below" (none listed) | Listed under Dev 3 and Dev 4 below. |
| Injection files filed "under Other/" | Set aside, an unchecked injection file goes to `Uncategorized/` (it is unresolved), not `Other/` as the panel's "Got it" would. Intended: it stays out of sight until someone looks at it. |

## Cascaded tasks

### Developer 1 — API owner

- Nothing required for the pop-up: `mode=partial` is already on `main`.
- Decide the "Leave for review" routing (option A above).
- Confirm `blocking_review_count` in a `partial` plan still reports the
  unresolved total (the pop-up and Check footer use it).

### Developer 2 — local AI owner

- No model change. Every review flag the validator emits needs a clear
  `message`; the pop-up groups by flag.

### Developer 3 — UI owner (Kristian)

- Pop-up, sort-mode state, API/mock/type changes, History event, `folderNote()`
  fix, all listed above.
- Vitest cases: mock `partial` plan routes the 7 unresolved fixture files to
  `Uncategorized/` with no report rows and unchanged totals; `approvePlan` with a
  mismatched mode → 409; `blocking` still refuses with unresolved items;
  `folderNote('Uncategorized/') === 'look later'`.

### Developer 4 — QA owner

Fixture scan (20 docs, 7 blocking) plus one live offline run:

1. Reading finishes with blocking files → pop-up with the right total.
2. **Review one by one** → Check exactly as before; Move locked until decided.
3. **Set all aside** → Check shows them as set aside; Totals lists 7 more files
   under `Uncategorized/` labelled "look later"; totals amounts identical to
   before.
4. Move → files land in `Uncategorized/`; Put back restores them.
5. Set aside, then review one receipt properly → it files to `Receipts/YYYY-MM/`
   and is counted; the rest stay in `Uncategorized/`.
6. Correct a file after setting aside, then press Move without the plan
   reloading → 409 handled (reload, ask again), nothing moved silently.
7. Scan with no blocking files → no pop-up.
8. Esc on the pop-up → Check, `blocking` mode, nothing changed.

## Acceptance criteria

- The choice is explicit; Esc/close keeps strict review.
- Setting aside modifies no document, counts nothing, and moves nothing before
  **Move**.
- Every set-aside file can still be reviewed individually before moving.
- Approval always sends the mode the user previewed; mismatches are surfaced,
  never retried silently.
- `Uncategorized/` is no longer described as "couldn't read" when it holds
  set-aside files.
