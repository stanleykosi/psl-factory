STATUS: READY
COMMIT: 67cb9702abfa4d95f98a67212d9d079123e6d127
BUILDER: builder
LANE: full

## Summary
- The release line's work item (`/work/{id}`, panel key `release-register`, confirmed on the demo database) now draws the live gates: four phases with D-14 words, the planning decision rows, client testing (read only), blockers, and the six board states derived from the reads.
- Three writes through `useWorkCommand`: decide the planning exit (Approve for release, Return with a note), Prepare release readiness, Record the release (checked PDF). Each button exists only because the read lists it (`verdicts`, `actions`); no client rule on who may decide.
- Built as `releaseAdapter.ts` registered on `release-register` (it reads planning-exit itself; the other panel keys have no adapter, so nothing draws twice), `releaseModel.ts`, `ReleaseActions.tsx`. No new CSS (reuses the `wr-*` classes).

## Changes
- `frontend/src/features/delivery-release/{releaseModel.ts,releaseAdapter.ts,ReleaseActions.tsx}` (new).
- `frontend/mock/delivery-release.mjs` (new), registered in `mock/server.mjs` (route plus reset). `mock/delivery-overview.mjs` NOT changed: it still answers only 2501; the new mock owns ids 48xx before it.
- `src/features/workspace/lines/index.ts`: one import line (the sanctioned seam). No other workspace file changed. `next-config.test.ts`: one allow-list line (`delivery-release.mjs`, it carries the contract's `django_url`).
- Tests: `tests/delivery-release-model.test.ts`, `-live.test.tsx`, `delivery-release-gates-mock.test.ts` (the old `delivery-release-mock.test.ts` is F-32's and untouched), `e2e/delivery-release-gates.spec.ts` (the old `delivery-release.spec.ts` is F-32's and untouched).
- Fixture ids: the spec's 4201 to 4213 are taken, so each is +600: 4801 to 4813, plus new 4814 (proofs, cannot approve directly), 4890 for 404. Contract shapes unchanged.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Four phases, checks, status tags, checklist, planning decision: model test and e2e on 4801.
2. [x] D-14 words and an unknown status in capitals: model test.
3. [x] No "0 records": model test and component test.
4. [x] Six states and precedence (ready, readiness, owner-needed, returned, decision, default), null packet: model test; e2e opens each state at 1440 and 390.
5. [x] Direct approver form: Approve on, Return off until note and proof, "Choose evidence", no Reject: live test and e2e.
6. [x] 4802 sends nothing; 4813 Approve works, Return off: live test.
7. [x] Direct approve sends one POST with loaded tokens and packet, no evidence_id; with a proof includes it; non-direct (4814) only with a proof; "Approved by PMO Lead" comes from the re-read: live test, e2e.
8. [x] Return needs note and proof; issue_id only when a blocker is picked: live test.
9. [x] evidence_id only when chosen and listed; `// @ts-expect-error` that an UploadId is not an EvidenceId: model test.
10. [x] 4803 (packet null) and 4812 (version unknown) send nothing; null token never 0: live and model tests.
11. [x] 4804 no form, "Waiting for the PMO Lead": e2e.
12. [x] Double press sends one request, buttons off while it runs: live test (gated request) and e2e dblclick.
13. [x] Errors 403, csrf, 409, 422, 429, 503, 500, lost answer: live tests (no second write; 500 and lost answer lock the button). csrf: one session read via the shared hook.
14, 15. [x] 4805 and 4806 words; workaround only on 4806.
16. [x] 4807 owner-needed, decision-appointments called only there.
17. [x] 4808 prepare sends one body and re-reads; 4809 has no button.
18, 19. [x] 4810 form gating, upload to the item's case, `observe_release` body with `upload_id`, `checked:true`, no evidence_id.
20. [x] Lost answer after the write: re-read shows "Release recorded"; before it: locked, no second POST.
21. [x] 4811 recorded line, no form.
22. [x] UAT words; a failing client-testing read hides only that row.
23. [x] Removed items not drawn.
24. [x] Forced 403 shows mapped words (e2e).
25. [x] 4890 reads "This record is unavailable." Django 8030 not checked.
26. [ ] Not run against live Django with a write. Read-only check on psl_demo5 (Lagoon, Delta): panel keys `release-register`, `planning-exit`, `client-testing`, `client-testing-pack`; reads match the contract; planning-exit checklist names/status are codes (`planning_sources`, `held`), shown humanised.
27. [x] POSTs only through `useWorkCommand`; zero writes on load (tests).
28. [x] Adapter registered with `Actions`; sections and three descriptors tested.
29. [~] Looked at 4801 desktop and 4810 phone screenshots: no horizontal scroll, order sensible. Design-fidelity tool NOT run (lean mode, no instruction).
30. [x] Tests exist; live-schema.d.ts untouched.

## Validation
- `tsc --noEmit` clean; `eslint . --max-warnings 0` clean; `node --check` on all mock files.
- vitest: next-config, demo-mock, mock-contract, line-adapter, live-work-item plus the three new files: 9 files, 468 tests pass. New tests: 29 model, 34 panel, 7 mock.
- Playwright on 4930/4931, production build: 16 passed (8 tests at 1440 and 390). Servers stopped.

## Held and notes
- "Release recorded" lock wording uses the shared "We couldn't confirm that this happened…" (spec wording "was recorded" not used, per the never-bend rule).
- Success is never said from the 200; no toast is drawn.
- `current_activity` line on readiness not drawn (not in the line context; the page's agent card already shows it).
- Blockers are plain text (no issue route). Reject is not drawn.
- Checklist row named "Planning decision" already comes from the API, so my decision row is labelled "Latest decision".
- Phone: a check with no records shows an empty "Records" label in the stacked table (minor gap).
- Decision form is drawn whenever `verdicts` lists approve or return, except in readiness, ready and owner-needed.
- `makeCommand` bug (`action:null` drops `fixed.action`) avoided: decide has no action; packet goes in `fixed`. Shared bug remains for the coordinator.
- `useWorkCommand` locks on the work item's `revision`, not the read's `expected_revision` (same value in the mock; confirm live).
- `released_at` is sent as an ISO time converted from the local date-time input.
