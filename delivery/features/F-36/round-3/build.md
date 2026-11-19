STATUS: READY
COMMIT: ba1ee621c715fa9ca4cfdbd22cf22f2620028305
BUILDER: builder
LANE: full

## Summary
- Round 3 fixes QA-2-1: a 422 that names `acting_role` or `evidence_id` is now mapped to the visible role and proof fields, with the page's own words, a top summary linked to them, and focus on the first. No raw "Check these fields: …" sentence is shown when any named field has its own message.
- QA-2-3 and the reopened UX-1-1 had the same cause or a one-line fix (below). QA-2-2 is in the shared ValidationSummary (read-only here); not changed, and I found no scoped fix that does not copy the component.
- No layout change, so no fidelity re-run; round-2 scores stand (desktop 1440 visual 94.1, phone 390 visual 75.6, coverage 100 with exceptions).

## Changes
- `frontend/src/features/rfp/AssignPmDrawer.tsx`: own `ValidationSummary` for the role and proof (also for the empty role and the blocked file); `id` and `tabIndex=-1` on the proof block and the text-only role row; the message is shown under a text-only role row too; the invalid result returns no `message` when a named field has its own words; focus after the summary has taken its own; the item-read error card no longer repeats "Nothing was changed.".
- Tests: `rfp-assign.test.tsx` (5 new: acting_role, evidence_id, both, role with PM, role as text, plus the single "Nothing was changed."; blocked-file test updated for the summary), `e2e/rfp-assign.spec.ts` (422 on both, focus, axe).

## Fixes
- QA-2-1 | 4f53c9f1 | 422 on acting_role and evidence_id: own words under each field, a linked summary, focus on the first, entries kept, no raw sentence.
- QA-2-3 | 4f53c9f1 | removed the repeated "Nothing was changed." in the item-read error card.
- UX-1-1 | 4f53c9f1 | the backend's raw "Check these fields: …" summary no longer shows for acting_role or evidence_id.

## Acceptance criteria
Round 1 and 2 criteria still hold; criterion 9 (422 under the named fields, a summary, entries kept) now holds for all four fields.

## Validation
- `checks.sh` under the lock: EXIT 0, 109 files, 2540 tests passed (rfp-assign.test.tsx has 35).
- `E2E_PORT=4966 MOCK_PORT=4967 npx playwright test e2e/rfp-assign.spec.ts`: 24 passed. test-results deleted.
- No fidelity re-run (no layout change).
