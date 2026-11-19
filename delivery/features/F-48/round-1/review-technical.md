VERDICT: CHANGES
COMMIT: 8a9755d4f598464231786ff2100fd420a93b31a4
REVIEWER: reviewer-technical
AUTHORITY: delivery technical review

## Summary
- The pose mapping is right: `poseFor` returns `cant` for `cannot_answer` only; the side panel and the phone card use `zainab-cant.png` and the other statuses are unchanged.
- `cannot_reason` renders as its own plain line through `ChatMessage`; no HTML path was added and the frontend contract and schema are untouched.
- Blocking: the CV-2404 thread draws the restricted record's label ("ACCESS · payroll (restricted)") in a step's "Read:" line at both widths, which breaks spec criterion 10.
- Blocking: the spec's CV-2404 tests are missing (wrong-user and unknown-id cases, and `cannot_reason` markup); two fidelity exception entries have no Conflicts number.
- Scope is clean: no changes under `src/api`, `apps`, `architecture`, `design`, `mock/assistant.mjs` or `src/shell`.

## Findings
- TECH-1-1 | blocking | high | frontend | Restricted record label shown on CV-2404. Expected (spec criterion 10): the restricted record's label and reference are not in `document.body.textContent`. Actual: `stepsOf` (`frontend/src/features/assistant/model.ts:16-24`) passes `step_details[0].reference.label` ("ACCESS · payroll (restricted)", `frontend/mock/fixtures/assistant/CV-2404.json:37`) as the step's source; `stepRecord` in `Thread.tsx:16-18` returns the words unlinked when there is no `work_id`; `AgentChecklist.tsx:80-85` draws it as "Read: ACCESS · payroll (restricted)" at both widths. No test asserts its absence for CV-2404 (the CV-2403 test at `frontend/tests/assistant.test.tsx:442` covers `source_details` only). Fix: do not draw a step reference that names a restricted record (the step has no permission to show its label), and add a `body.textContent` assertion for CV-2404 at 1440 and 390. If the contract should mark the step reference `restricted`, raise that with integration; do not widen the fixture.
- TECH-1-2 | blocking | medium | frontend | Spec-named tests not added. Expected: criterion 12 adds CV-2404 to the wrong-user case (`assistant.test.tsx:509` tests CV-2401 only, and CV-2499 is covered by `assistant-mock.test.ts`, not the component); criterion 8 renders `cannot_reason` containing `<img src=x onerror=alert(1)>` and `**bold**`, not created as elements and not trimmed. Actual: build.md says "I added no CV-2404 wrong-user or cannot_reason-markup case". The F-24 markup test (`assistant.test.tsx:410-424`) uses message `text`, not `cannot_reason`. Fix: add both component tests, using the existing mock wiring.
- TECH-1-3 | blocking | low | frontend | Fidelity exceptions missing Conflicts numbers. Expected (criterion 3): every entry has a Conflicts number. Actual: `delivery/features/F-48/fidelity-exceptions.json` entries "ACCESS · payroll (restricted)" and "Repeated list items with 2 text field(s) each" have none. The restricted-label entry also says "its label and reference are never in the page", which is false while TECH-1-1 stands; correct it when TECH-1-1 is fixed. F-24 entries are carried over unchanged (checked: 27 of 27).
- TECH-1-4 | non-blocking | low | frontend | The test at `frontend/tests/assistant.test.tsx` (CV-2404 "text and reason are separate lines") asserts `not.toBe` between two element lookups. It passes whenever both texts exist, including when they share a parent. Assert that the reason sits in its own `.cmp-chat__cannot` element.

## Verified
- None. Round 1: no earlier findings to retest.
- Checked and passing on read: `poseFor` order (`SidePanel.tsx:13-17`); phone-only inline card gated on `cannot_answer` and the first agent message (`Thread.tsx:41`); side sentence from `status` (`labels.ts:55-56`); `cannot_reason` passed as `cannot` text (`ChatMessage.tsx:57`); `SourceTag restricted` draws no label or link (`SourceTag.tsx:13-21`); no `innerHTML` or staff-cost or Ask HR strings in `frontend/src`; CSS adds no colour literals; the three `-cant.png` files are web-resized versions (1024x1536 to 253x380) of the design source, aspect preserved, not drawn.
