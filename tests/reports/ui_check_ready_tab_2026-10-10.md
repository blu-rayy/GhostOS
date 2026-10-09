# Check screen: "Ready" rows show "check this" and can't be opened after deciding

**Reported by:** Developer 4 (QA) · **Date:** 2026-10-10 · **Commit:** `9a909c7` (`main`) · **Component:** Check screen (`frontend/src/pages/FilesPage.tsx`, `frontend/src/components/paper/CheckComponents.tsx`) · **Owner:** Dev 3 · **Severity:** Medium (UX and review-flow blocker; no data or file-safety impact)

## What the user sees

1. On the Check screen, open a non-payment document (birth certificate, statement, legal or medical paper) and press **"Leave for review"** or **"File it · no payment details"**.
2. Open the **Ready** tab.
3. Several rows show a yellow **"check this"** chip, as if they still need attention.
4. **Clicking those rows does nothing.** No detail panel opens, so the user can't inspect a file or change a decision they just made.

Observed by Developer 4 in the running app (live backend). The causes below were confirmed by reading the code. No browser automation was used.

## Cause 1: once nothing blocks, the side panel ignores row clicks

[`FilesPage.tsx:131`](../../frontend/src/pages/FilesPage.tsx#L131):

```tsx
{allChecked && state.plan ? <ResolvedPanel … /> : selectedRow?.doc ? <DetailPanel … /> : null}
```

with `allChecked = countsBy.needs === 0` ([line 116](../../frontend/src/pages/FilesPage.tsx#L116)).

- As soon as the last "needs you" file is decided (by **File it**, **Leave for review** or **mark checked**), `allChecked` becomes true.
- From then on, the right side **always** shows the "Where files will go" summary (`ResolvedPanel`).
- Clicking a row still sets `selected` (the row gets the selected outline), but `DetailPanel` is never rendered. **For the user, the rows are dead.**
- Consequences:
  - a decision can't be reviewed or changed after it is made (for example, switching from "Leave for review" to "File it");
  - ready files can't be inspected at all once everything is decided;
  - the only way back is to leave the screen.

## Cause 2: "Ready" rows that were never flagged say "check this"

[`CheckComponents.tsx:44`](../../frontend/src/components/paper/CheckComponents.tsx#L44):

```tsx
<Chip …>{checked ? '✓ checked' : failed ? "couldn't read" : 'check this'}</Chip>
```

`checked` is `doc.user_corrected`. A document the backend accepted without any review flags has `status: "ok"` and `user_corrected: false`. It appears in the Ready tab ([`isReady`, line 14](../../frontend/src/pages/FilesPage.tsx#L14): `status === 'ok' || user_corrected`), but its chip falls through to **"check this"**, and the row has the yellow "needs attention" stripe. That contradicts the Ready tab itself and the row text ("Ready to file.").

## Related observations (same flow)

| # | Severity | Observation |
|---|---|---|
| O1 | Medium (wording) | **"Leave for review" reads as "checked".** The decision sends `{category:"uncertain", accept:true}` ([`viewModel.ts` `NON_TRANSACTION_DECISIONS`](../../frontend/src/lib/viewModel.ts)). The backend then sets `user_corrected:true, status:"ok"`, so the file moves out of "needs you" into Ready, the chip says **"✓ checked"**, the row says "you checked this file", and the footer counts it as checked. A user who chose *leave for review* may expect it to stay in a review list. |
| O2 | Medium (wording) | **"Leave for review" still moves the file.** On approval the plan moves it into a `Needs Review/` folder inside the chosen root (backend fixed map). The panel's hint says "Leave for review → Needs Review/", but "leave" can read as "don't touch it". Consider "Put in Needs Review folder". |
| O3 | Low | **Arrow-key navigation can jump to the wrong row.** `handleKey` indexes into `visibleRows` (all sections), but each section passes its own local `index`, so ArrowDown/ArrowUp from the "couldn't read" or "ready" sections can select a row in a different section. |

## Suggested fixes (for Dev 3)

1. **Let a row click win over the summary.** Show `DetailPanel` whenever a row is selected, and show `ResolvedPanel` only when nothing is selected (or add a "back to summary" control). For example: `selectedRow?.doc ? <DetailPanel/> : allChecked && state.plan ? <ResolvedPanel/> : null`, and clear `selected` when the last blocking item is resolved so the summary still appears first.
2. **Chip for unflagged ready rows:** use "ready" (done tone, green stripe) when `status === 'ok' && !user_corrected`. Keep "check this" only for `isNeeds(row)`.
3. **Show the decision on decided non-payment rows:** e.g. "✓ filed under Other" or "left in Needs Review" instead of the generic "✓ checked". The panel already computes `decided` (`file` / `leave`).
4. Use the global row index (or look up by id) in `handleKey`.

## How to verify a fix

1. Scan a **copy** of `tests/fixtures/sample_folder`. Don't scan the committed folder: approving would move repository files.
2. Decide every "needs you" document. Then:
   - **click a row in "Ready"**: its detail panel opens;
   - **reopen a non-payment document** and switch between File it and Leave for review: the plan destination updates;
   - **unflagged ready rows** show a "ready" chip, not "check this".
3. **Logic tests:** add vitest coverage for the panel-selection rule and the chip label (the existing `documentAware.test.ts` covers profiles and decisions, but not this rendering rule).

No production code was changed for this report.
