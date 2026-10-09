# Document-aware review

## Why this is needed

GhostOS's pitch is that sensitive paperwork stays on-device and that file
operations are transparent, reviewable, and reversible. The current Check flow
assumes every uncertain document can be repaired by entering a shop, date, and
amount. That is wrong for birth certificates, identity records, legal papers,
medical records, and other non-transactional documents. The UI must never ask a
user to invent financial fields for a document that does not have them.

## Contract decision

Keep the existing `category` because it controls the safe, code-owned folder
map and totals. Add a separate backend-owned `document_kind` that describes
what the paper is, and derive the editable-field profile from it in code.

Suggested values:

- `receipt` — a single point-of-sale transaction.
- `invoice` — a bill or request for payment.
- `statement` — a bank, card, utility, or account statement; not one expense.
- `identity_or_civil` — identity cards, birth certificates, marriage records,
  passports, and similar civil records.
- `legal` — contracts, court, tax, or other legal paperwork.
- `medical` — medical records, prescriptions, or health paperwork.
- `other` — sensitive or personal paperwork that does not fit above.
- `uncertain` — the local model cannot safely determine the kind.

The backend must expose a derived `field_profile`, never accept a model-supplied
list of fields, and keep the model unable to influence destination paths:

- `transaction`: `merchant`, `date`, `amount`, and `currency` may be shown.
- `reference`: only document-specific reference metadata supported by the
  contract may be shown; do not reuse transaction fields by default.
- `none`: no editable transaction fields.

For `statement`, `identity_or_civil`, `legal`, `medical`, `other`, and
`uncertain`, the default Check experience is a classification/explanation card
with the extracted evidence and an explicit “file without transaction details”
or “leave in Needs Review” decision. It must not render shop, amount, or date
inputs unless the backend explicitly returns a compatible field profile.

`category` remains the safe organization decision. A non-transactional paper
can be filed under `Other/` (or `Needs Review/` when uncertain) without being
counted in totals. No amount is invented to make it fit the totals flow.

## Cascaded tasks

### Developer 1 — API and schema owner

- Extend the canonical Pydantic and frontend-facing contracts with
  `document_kind` and derived `field_profile`.
- Define the enum values, backwards-compatibility behavior for old fixture
  payloads, and correction rules for non-transactional documents.
- Make the backend reject contradictory combinations such as
  `document_kind=identity_or_civil` with a transaction-only correction.
- Add contract examples for a receipt, a bank statement, and a birth
  certificate.

### Developer 2 — local AI/classification owner

- Update the Ollama structured prompt and typed adapter to classify
  `document_kind` separately from the existing folder `category`.
- Add evidence and conservative uncertainty behavior for statements and
  non-transactional sensitive paperwork; never infer merchant/amount/date just
  to fill a schema.
- Add evaluation fixtures for a bank statement, birth certificate, identity
  record, legal document, and medical document, including expected kind and
  expected field profile.
- Preserve the offline guarantee and ensure model output cannot provide paths
  or an arbitrary field list.

### Developer 3 — Check UI and totals owner

- Render correction fields from the backend `field_profile`, not from the
  category or from assumptions about every document.
- Add a non-transactional Check state that shows kind, evidence, explanation,
  destination, and explicit file/leave-for-review actions without shop/date/
  amount inputs.
- Keep statements out of the single-expense totals flow unless the contract
  explicitly supports a user-selected transaction within the statement.
- Add fixtures and UI tests covering receipt, statement, birth certificate,
  and uncertain documents.

### Developer 4 — integration and QA owner

- Add an end-to-end acceptance case proving a birth certificate can be
  reviewed and filed without entering a date or amount.
- Add a statement case proving it is not presented as one expense and does not
  silently contribute to totals.
- Verify the local-only, reviewable, reversible path with Wi-Fi disabled and
  record the result in `docs/qa/`.
- Treat any accepted non-transactional document with an invented amount, or
  any move without an explicit user decision, as a blocking safety defect.

## Acceptance criteria

1. A receipt still shows the existing merchant/date/amount correction flow.
2. A birth certificate never shows amount or shop inputs.
3. A bank statement is visibly identified as a statement, is not forced into a
   single expense, and does not enter currency totals by default.
4. An uncertain document can remain in `Needs Review/` without fabricated
   metadata.
5. Every destination remains generated by backend code from the fixed category
   map, and the full flow works offline with evidence and undo.
