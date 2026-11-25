STATUS: READY
COMMIT: 96f9ecd33ce95924bebc73146adae191b928f792
BUILDER: builder
LANE: full

## Summary
- `/work/{id}` for an income schedule item now reads the live `GET /work/{id}/finance-schedule` through a new line adapter and draws stage, finding, income rows, result, possible duplicates, returned rows, hold-code sentences and (for `kind: inventory`) coverage and schedules, read only.
- A reviewer records a decision with `POST /work/{id}/reviews` (kind `schedule`) from the Actions slot: evidence choice from the read's `evidence[]`, a required note, and one button per verdict in `review_verdicts[]` (Approve, Return, Reject, Withdraw approval). Sent by `useWorkCommand`, so the press lock, uncertain lock, CSRF refresh and re-read are the shared ones.
- Lean mode (D-210): no review agents. Fidelity tool not run (boards are not matched one for one under the recorded D-173/D-181/D-182/D-187 exceptions, and LD-Q2/LD-Q4 accept plain forms); the Playwright spec checks both widths for overflow and 44px targets.

## Changes
- `frontend/src/features/workspace/incomeSchedulesAdapter.ts` (new): `LineAdapter` for panel key `finance-schedule`; `scheduleSections`, `scheduleCommands`, `offeredVerdicts`, `amountText`.
- `frontend/src/features/workspace/IncomeScheduleReview.tsx` (new): the decision form (Actions slot).
- `frontend/src/features/workspace/lines/index.ts`: one import line.
- `frontend/src/api/types.ts`: one line, `LiveSchedule` (generated type, no hand-written shape).
- `frontend/mock/income-schedules-live.mjs` (new), `frontend/mock/server.mjs` (import, reset call, route block).
- `frontend/tests/income-schedules.test.tsx` (new, 24 tests), `frontend/e2e/income-schedules.spec.ts` (new, 10 tests).
- Shared files (`adapter.ts`, `useWorkCommand.ts`, `makeCommand`, work-item) not changed. The `action: null` bug in `makeCommand` does not bite: the body has no `action`, and `verdict`, `evidence_id`, `note` come from the press while `kind` and `target_id` are fixed.

## Fixes
None (round 1).

## Decisions I made where the spec and the contract disagree
- Panel key is `finance-schedule`, not `income-schedules`. The backend names panels by route (`apps/core/factory_api/work.py:400`: `'finance-schedules/v1': ('finance-schedule',)`).
- The spec's fixture `4205` has `review_id: null` with `review_verdicts: ["revoke"]` and AC5 says it shows Withdraw approval, but the read-mapping table says the panel needs `review_id` not null. I followed AC5 and the fixture: the panel is shown when `review_hold_code` is null, `schedule_id` is not null and the read lists a known verdict. `review_id` is not a gate. Backend can say if that is wrong.
- The contract's patterns for `income.entity`, `income.report_line` and `duplicates[]` are code-like (`^[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}$`), so the spec's fixture text "Row 7 may repeat row 3" is not a valid duplicate string. Fixture uses `row-7`; shown as returned.
- Mock ids 4201 to 4207 and 4299 are free on main (no clash).
- Error words: the shared sender's 409, uncertain and 403 words are replaced in this form by the spec's schedule wording ("This schedule changed while you were reading it, so nothing was recorded.", "We couldn't confirm whether your decision was recorded. Check the schedule before trying again.", "You can't review this schedule."). The server's own message follows as detail.
- The note is cleared after a decision is accepted; it and the evidence choice stay after a 409 or any error.

## Acceptance criteria
1. [x] `/work/4203` stage, finding, rows, result, exactly Approve, Return, Reject: vitest page test, e2e (both widths).
2. [ ] Against live Django: not checked here (no live write or session allowed; read shapes validated against the contract schema in vitest, mock validated against `finance-schedule` 200 and `reviews` 200).
3. [x] null amount and null total read "Unknown": `amountText` unit test, `4201`/`4203` tests, e2e.
4. [x] No money arithmetic: grep for `parseFloat|Number(` in the two new source files returns nothing; amounts go through `formatAmount` only (string grouping).
5. [x] Only listed verdicts: 4203 three, 4205 only Withdraw approval, 4201/4204/4206 none, unknown verdict string no button (unit and page tests, e2e).
6. [x] `reviewer_missing` and `review_rule_missing` sentences; no panel, name or link (unit and page tests, e2e 4206).
7. [x] Nothing sent without evidence and a note, Approve included; reasons shown ("Choose the evidence this decision rests on.", "Add a note."): test asserts zero POSTs; e2e.
8. [x] Approve on 4203 sends exactly one `{kind:"schedule", expected_revision:5, case_revision:12, target_id:9, verdict:"approve", evidence_id:61, note}` with `X-CSRFToken: t`: vitest and e2e.
9. [x] Page shows state from the re-read: `wstale` scenario (200 but the re-read is unchanged) shows no "Verified".
10. [x] 409: schedule wording, re-read, note and evidence kept.
11. [x] Dropped connection: unconfirmed wording, buttons disabled, one POST. 503 and 429 say "Try again shortly." (503 is not locked by the shared sender; it is not treated as unknown there, an existing shared rule I did not change).
12. [x] 403 `csrf_failed`: "Press the button again.", no no-access state, one call (refresh is the shared sender's).
13. [x] 4299: unavailable, no title (page test and e2e). The write-side 404 uses the shared sender's access-lost path.
14. [x] 422 with `fields[]`: server message and first field message shown, input kept.
15. [x] Evidence select offers only `evidence[]` rows; no file input; empty `evidence[]` shows the "no evidence" line and no buttons (code path; the page test checks the single option and no file input).
16. [x] 4204: "Returned for correction" and rows only, no note, no correct control; grep finds no `correct_and_resubmit` or `liveApi.POST` in the new files.
17. [x] Possible duplicates read only (4202).
18. [x] Inventory 4207: coverage "Partial", schedules read only, restricted schedule shows its key only, no income block.
19. [x] "Posted to ledger" and Export text appear nowhere in the new source files (page test asserts none in the DOM). "Posted to ledger: NO" is hidden because the read has no field (D-182).
20. [x] No hold code and no verdicts: no panel and no "reviewer not set" text (unit test).
21. [~] Viewport checks at 1440 and 390 on the mock: no horizontal overflow, 44px targets on phone (e2e). I did not compare screenshots with the boards or run the fidelity tool.
22. [x] New tests for `sections`, `commands` (null tokens stay null), the gate and each error mapping.

## Held (by design, with the reason)
- Exports, correct and resubmit, settle a duplicate, accounting adjustments: F-101B.
- Reviewer's quoted note on a returned schedule: the read carries only `returned.review_id` and rows.
- "Posted to ledger", "Prepared by", "Approved by", "Verification scope", "You didn't prepare it" basis line: no field on the read.
- A Setup link and any reviewer name: not drawn.
- Nothing is disabled on a per-write basis for an unclear body: the review body is fully settled by E-21/E-22.

## Validation
- `tsc --noEmit`: clean. `eslint . --max-warnings 0`: clean.
- `node --check` on `mock/server.mjs` and `mock/income-schedules-live.mjs`: ok.
- vitest: `tests/income-schedules.test.tsx` 24/24; next-config, demo-mock, mock-contract, line-adapter, live-work-item: 381/381 together. Full suite on the pre-fix head: 193 of 194 files, 4506 of 4507 tests; the one failure was my own stale re-read test, since fixed and re-run green (24/24). I did not repeat the 10 minute full run after that test-only change.
- Playwright `e2e/income-schedules.spec.ts` on ports 4950 (app) and 4951 (mock): 10/10 (desktop 1440 and phone 390). Playwright started and stopped its own servers; nothing is left listening on those ports.
- Not run: `delivery/checks.sh` (CI mode waits for GitHub), the fidelity tool, any live Django call.

## Shared-code notes for the coordinator
- `useWorkCommand` treats 503 as "unknown" for the return value but does not lock the command or re-read; the spec (AC11) wants buttons disabled until a re-read after a 503. Not changed here; a shared fix would serve every line.
- `mock/server.mjs` gains one import, one reset call and one route block; the parallel F-102 builder will touch the same regions, so expect a trivial merge conflict.
