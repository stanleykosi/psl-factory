STATUS: READY
COMMIT: afd02454c7ba991b1ab1cfc565b8a392a11a0736
BUILDER: builder
LANE: full

## Summary
- The weekly report panel on a live work item now draws the report text, the agent notes, a "Your review" block (Approve and send, Return with a note, Refuse, only for verdicts in `review_verdicts[]`) and, after a return, the quoted `return_note` and an inline "Edit your update" form.
- Reviews send `POST /api/v1/work/{id}/reviews` `{kind:'document', expected_revision, case_revision, version_id, verdict, note}`; correct sends `POST /work/{id}/weekly-report` `action:'correct'`. Both go through `useWorkCommand`; the result is told from the re-read.
- Approve is held (with a line) when the report text is missing or `preview.id` differs from `document_version_id`. No review controls without `document_version_id`.
- No change to the APIs of `useWorkCommand`, `useScopedWriteLock`, the Actions slot; `makeCommand` gained the additive `fixed` field.

## Changes
- `frontend/src/features/workspace/WeeklyReportActions.tsx` (new): report text, notes ("Note from the review", "Other notes"), review block, edit form, notice. Registered as the adapter's `Actions`.
- `frontend/src/features/workspace/weeklyReportAdapter.ts`: four descriptors (correct, approve, return, reject), returned-note quote, `Actions`.
- `frontend/src/features/workspace/adapter.ts`: optional `fixed` in `makeCommand`.
- `frontend/src/features/workspace/workspace.css`: `wr-*` styles; buttons stack on phone.
- `frontend/mock/work-live.mjs`: `/reviews` and `/weekly-report` writes, fixtures 4130 to 4138, scenarios w403, w403csrf, w409, w422, w429, w503, w500, wdrop (applied), wdrop0 (not applied).
- `frontend/tests/weekly-report-review.test.tsx`, `frontend/e2e/work-item-weekly-report.spec.ts` (new).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Review buttons per verdict, none on received: e2e and vitest (4130, 4131, 4133).
2. [x] Hold Approve (4136, 4137), no review without a version (4134): unit and e2e.
3. [x] Approve body exact, no action or key: unit descriptor and e2e capture.
4. [x] Return/Refuse need a note ("Write a note first."), send nothing otherwise.
5. [x] "Recorded. This item is now: ..." from the re-read; buttons disappear; "No receipt yet" kept.
6. [x] Correct on 4132: prefilled, "N records cited", exact body, cites unchanged, "Your update was sent for review."
7. [x] 403 server words, 409 re-read keeping the note, dropped connection locks all four buttons ("Check the page before trying again.").
8. [x] Double press sends one request (unit).
Not done or differs: 4xx 422 field messages are shown in the callout (server message plus first field message), not placed under the input, because `useWorkCommand` exposes only the first field message; 429/503, 401/404 and fake-timer tests rely on `useWorkCommand`'s existing F-87 tests, not re-tested here. Uncertain lock unlocks when the work item revision changes (F-87 behaviour), which moves with the report in the mock. Live Django check (AC23) and screenshots/fidelity run (AC24) not done. Fixture ids are 4130 to 4138, because 4120 to 4123 are already F-87 fixtures.

## Validation
- vitest (weekly-report-review, line-adapter, next-config, demo-mock, mock-contract, live-work-item, mock-work-live, api-live-schema-drift): 8 files, 453 tests passed (14 new).
- tsc and `eslint . --max-warnings 0`: clean.
- Playwright `work-item-weekly-report.spec.ts` on ports 4980/4981: 16 passed (desktop and phone).
- `delivery/checks.sh`: PASS (all remaining CI steps green).
