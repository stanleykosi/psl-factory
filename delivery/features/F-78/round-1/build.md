STATUS: READY
COMMIT: 07aca01552f49d7d12a62a81baa077e2b2394cc7
BUILDER: builder
LANE: frontend

## Summary
- New SCR-19 page `/projects/[caseId]/milestones/complete?name=`: shows the exact milestone, the proofs on record (radio list, Show more), an optional private PDF (shared EvidencePicker, only when `can_attach_pdf`), the confirmation, and one "Mark complete".
- "Mark complete" shows only when the server's options read says `can_complete`; holds show plain words and no control. No role check in the UI.
- One press is one POST. "Milestone recorded" shows only from the re-read of `GET .../milestones/{id}` (name must match). 409 reloads options and keeps input; uncertain results are never resent ("Check again" reads options only).
- Milestones tab gets a "Mark complete" link per uncompleted stage row (from an unnamed options read) and one hold line; a failed options read changes nothing.
- Two F-71 carry-overs fixed as separate commits.
- LB-2 OPEN: whether the server enforces PMO Lead authority on POST milestones/completions is unconfirmed. The UI follows `can_complete` and invents no role rule. Flag it in the PR body (criterion 20).

## Changes
- `src/features/projects/MilestoneComplete.tsx`, `MilestoneCompleteRoute.tsx` (Suspense + `?name=`), `useMilestoneComplete.ts` (options, write, re-read, 409, uncertain), `milestone-complete.css`, `src/app/projects/[caseId]/milestones/complete/page.tsx`.
- `milestonesModel.ts`: `isCompletionOptions`, `isRecordedCompletion`, `HOLD_WORDS`, `holdText`, `usableName`, `completeHref`.
- `useMilestones.ts`: exported `readCompletion`, `readOptions`; tab `entry` read. `MilestonesTab.tsx`: link and hold line.
- `mock/milestone-complete.mjs` (all scenarios from the spec) and its registration in `mock/server.mjs` (small, in commit 625906e4; it also resets on /__mock/reset).
- Tests: `tests/milestone-complete.test.tsx` (new), `tests/mock-live-milestone-complete.test.ts` (Ajv, new), `tests/milestones.test.tsx` (entry cases; read counts now include the options read).
- Lane C's EvidencePicker/evidence.ts used unchanged; no token keys in `inputs`. src/shell and src/api untouched.

## Fixes
- QA-2-1 | 0289000b | money.spec.ts expects the head "Where a figure comes from"
- TECH-2-1 / QA-2-2 | 12150119 | Proof button is a real toggle; aria-expanded stays true from press to second press

## Acceptance criteria
1. [x] Control follows the server: milestone-complete.test.tsx (can_complete true/false); no role code in the new files.
2. [x] Each hold shows words and no control, raw code absent: test.
3. [x] Button disabled until proof and confirmation: test.
4. [x] One POST with exact body `{revision,name,evidence_id}`: test.
5. [x] PDF: files POST first, second tick needed, body `{upload_id, checked:true}`; no PDF zone when can_attach_pdf false: test.
6. [x] Double activation sends one POST: test.
7. [x] "Checking the record…" before re-read; failed re-read never says recorded, Check again only GETs: tests.
8. [x] Recorded view from re-read; mismatched name not shown as recorded: tests.
9. [x] 409 keeps input, one options reload, next POST has new revision: test.
10. [x] 503 uncertain: no resend; Check again reads options; name_in_use says "now recorded"; not-recorded returns the form: tests (real timers, short wait rather than a fake 60 s advance, since no timer exists in the code).
11. [x] 403, 404, 422, 400, 413, 415, 429 wording: one test each. 401 is handled by SignedOutState in code; not separately tested.
12. [x] Options 403 and an invalid body: no control, no partial data: test.
13. [x] No invoice wording or billing/work requests: asserted in the recorded test.
14. [x] Milestones tab link/hold/failed-read: three cases added to milestones.test.tsx.
15. [x] No name or over 200 characters: no request: test.
16. [x] Show more asks `?name=&page=2`, no duplicate ids: test.
17. [x] Ajv test for every mock scenario and the write shapes: 24 tests pass.
18. [ ] Phone and desktop browser check: NOT done (no dev server allowed). CSS has a 720 px bottom bar and 100% width card.
19. [ ] Live smoke on Django 8010: integration owner.
20. [ ] LB-2 text in PR body: coordinator.

## Validation
- `npx tsc --noEmit -p .` exit 0; `npx eslint` on touched paths exit 0.
- `npx vitest run tests/milestone-complete.test.tsx tests/mock-live-milestone-complete.test.ts` 42 passed; `tests/milestones.test.tsx` 36 passed.
- e2e money.spec.ts edit not run (no server). Fidelity tool NOT run (needs a production build and server): open item for the coordinator.
- Not run: full suite (gate on GitHub Actions).

## Notes for the coordinator
- Page also reads `GET /projects/{id}` (useProject) for the breadcrumb project name, as the document review page does; not before a usable name.
- `proof_required` with `can_attach_pdf` true shows the PDF zone but no control and no re-read (spec literal); the upload cannot lead anywhere until the next page load. Consider a backend/spec question.
- After an uncertain or unconfirmed result the form and Mark complete are hidden (never offered again for that entry); the choices stay in state and return if the check says "not recorded".
- The Milestones tab now makes a third read (unnamed options). In the mock, default scenario `ok` shows links on uncompleted rows.
- Other e2e specs that count milestones-tab requests may need the extra read; not checked.

## Gate fix (attempt 1)
- cash-forecast guard: `Number(value)` replaced by `parseInt(value, 10)` and the `useMe` destination check removed from MilestoneComplete.tsx (access is the server's 403/404). cash-forecast and milestone-complete tests pass (68).
