# F-119's closure and retrospective, with UX-5-1 fixed

> Tasks: FE-DELIVERY-CLOSURE. Architecture: v9 package, live contract `contracts/psl-factory.openapi.json` 1.24.0 (origin/main b8542c79), as F-119. Design: approved 13 Nov canvas under the recorded exceptions D-173/D-181 and D-202 (LD-Q5); screens: SCR-33 (desktop and mobile boards).

## Summary
- F-119B is the follow-up record for F-119 (D-208). F-119 is CLOSED as superseded; its record is not reopened.
- It adopts `delivery/features/F-119/spec.md` unchanged as binding. Its acceptance criteria 1 to 23 apply as written and are not restated here.
- One new criterion (24) covers UX-5-1: on a 390px phone, a control that takes keyboard focus ends fully above the fixed Save bar (WCAG 2.4.11).
- The candidate is branch head `9d9b149c0eee33789567d9006229314f1224d6d0`. No new code is expected beyond UX-5-1, which that commit already fixes.
- Nothing merges unreviewed. F-119B runs gate, lenses, QA, PMO and merge as normal (D-208 steps 2 and 3).

## Context
- The code, routes, endpoints, records and Contract are those of F-119's spec: `frontend/src/app/projects/[caseId]/retrospective/**`, `frontend/src/features/retrospective/**` (`RetroForm.tsx`, `retrospective.css`, `summary.ts`, `model.ts`, `ActionForm.tsx`, `ChecklistStrip.tsx`), `frontend/e2e/retrospective.spec.ts`. No backend change.
- Commit 9d9b149c (`Scroll a focused control above the phone Save bar using the bar's real height`) changes three files: `frontend/e2e/retrospective.spec.ts`, `frontend/src/features/retrospective/RetroForm.tsx` and `frontend/src/features/retrospective/retrospective.css`. It adds a `focusin` handler on phone that scrolls a focused control clear of the bar, measures the bar height into `--retro-bar`, and adds the phone focus test.
- Evidence carried over (cited, not re-earned):
  - F-119 rounds 1 to 5 reviews: `delivery/features/F-119/round-1` to `round-5` (`review-technical.md`, `review-ui.md`, `review-ux.md`, `checks.md`, `build.md`). Round 5 gate PASS at 53c24b19.
  - D-206 sixth-round fix at 9d9b149c, recorded in `delivery/features/F-119/round-6/build.md` (UX-5-1, TECH-5-1, TECH-5-2).
  - D-202 signatures (LD-Q5): 28 exceptions and 2 D-83 visual waivers in `delivery/features/F-119/fidelity-exceptions.json` (SCR-33 desktop 78.8, phone 76.6). LD-Q6: keep "saved".
  - Open non-blocking findings carried into F-119B: TECH-5-3 (Decisions and Save remount when the viewport crosses 720px; values survive in `draft`, focus is lost on resize) and UX-3-1 (stale-decision polish, listed open; see Assumptions).

## Contract
As F-119's spec, Contract section (routes, reads, Save, follow-up action, screen states, fixtures). Nothing in the contract changes in F-119B.

## Lanes
- **Frontend lane (owner):** the paths in Context. The UX-5-1 fix is already on the candidate head.
- **Backend lane:** none.
- **Integration owner:** as F-119 (F-118 links to the page through `retrospective_url`).
- **Protected paths:** `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json` are unchanged.

## Build
- The candidate is branch head `9d9b149c0eee33789567d9006229314f1224d6d0`. It already carries the UX-5-1 fix, so no new code is expected beyond UX-5-1.
- The round runs on that head or later (D-208 step 1). Any new code is limited to what criterion 24 needs after the re-check.
- Round numbers in F-119B start at 1. Findings cited from F-119 keep their F-119 round (for example UX-5-1 and TECH-5-3).

## Acceptance criteria
1. to 23. Apply F-119's acceptance criteria 1 to 23 unchanged, on the F-119B round head. — verify: as named in `delivery/features/F-119/spec.md` (gate `delivery/checks.sh`, `frontend/e2e/retrospective.spec.ts`, `npm test` in `frontend/`).
24. (UX-5-1) At 390px width on `/projects/<2001>/retrospective?dossier=5001`, every control in the form that takes keyboard focus (reached by Tab from the first box through to Save and the decisions and follow-up controls) ends fully above the fixed Save bar: its bounding box bottom is at or above the bar's top. For each one, `document.elementFromPoint` at the control's centre returns that control or one of its descendants. Negative case: a control hidden under the bar fails the check. — verify: the phone focus test in `frontend/e2e/retrospective.spec.ts` (Playwright, mobile 390px project), run on the F-119B round head and recorded in the round's `checks.md`.

## Out of scope
- Everything F-119 left out (F-119 spec, Out of scope), including F-85 picker, F-118 closure screen, SCR-47/48, hypercare, and upload-to-evidence.
- Any change to F-119's contract, acceptance criteria 1 to 23, or the board conflicts.
- Reopening F-119 or changing its closed record. Linking an existing action, editing saved versions and a second retrospective.
- Fixing TECH-5-3 unless the re-check shows it now blocks (it is non-blocking and carried as is).

## Assumptions
- F-119B round numbering starts at 1 with a fresh rework budget: D-208 creates a new record, so its budget is its own.
- UX-3-1 is carried as open as the request states, but `delivery/events.jsonl` shows it fixed in F-119 round 4 and verified by reviewer-technical at 14:50; no reviewer-ux re-verify is recorded. The round-1 reviewer may close it on re-check.
- F-119 spec Questions 1 to 5 (decision rows, "When it was held", notes file source, footnote wording, checklist strip without dossier) have no answer recorded in D-202, which records only LD-Q5 and LD-Q6. The round-1 to 5 build followed F-119's recommended options. The approver should confirm this is accepted, because it is a product call and not a builder call.
- The D-202 signatures (LD-Q5, LD-Q6) cover F-119B unchanged, because the board and exceptions do not change.

## Conflicts with the boards
- None new. The conflicts in F-119's spec ("Conflicts with the boards", items 1 to 8) carry over unchanged, and the D-202 "Sign all" covers the 28 exceptions and 2 waivers in `fidelity-exceptions.json`. UX-5-1 is a layout fix that the boards do not draw.

## Coordinator note
- F-119 spec Questions 1 to 5 were answered by D-187 (LD-Q2): every recommended option in the lane D specs is accepted. They are not open.
- UX-3-1 (phone bar pinned only ~290px) was fixed in F-119 round 4 and verified by reviewer-ux in round-4/review-ux.md ("UX-3-1 | verified").
