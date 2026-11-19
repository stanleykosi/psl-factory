STATUS: READY
COMMIT: 32c97d3df9f2b6f5ae78bf523744c57ee74d83b4
BUILDER: builder
LANE: full

## Summary
- **Contract mock only. Nothing is submitted, emailed or delivered.** "Submitted", "Emailed", "Received", "TL-SUB-0091" and every receipt word are fixture text, shown only after the re-read returns them. The company forms are a test template. D-LINE-WORKSPACE and D-RFP-OUTCOME stay proposed.
- The RFP Submission tab (`tab.work_id`) opens the submission item inside the F-18 frame. The PM sees the pack, the checks and Tola's card, and can edit the cover letter and send for review. The document reviewer approves, returns or rejects that exact pack version in place (claim, then decide with `expected_revision`).
- Controls come only from `you_can_act`, the steps and `allowed_actions`. After an uncertain send only the reconcile panel shows, with no second send. Unknown values read "Unknown". No amount anywhere.
- Fixtures W-3501 to W-3509 with sidecars, W-3505 reconcile sidecars, document D-3501; tests: 43 component, 18 mock, e2e spec (9 items x 2 widths plus flows).

## Spec vs merged code (re-verified)
- F-37 is merged: `RfpFrame.Tab` already has `requirements`/`team_input`/`outcome` branches and `LineHeader` already draws the frame for `rfp_response`. Kept untouched; added one `submission` branch (`tab.work_id` only) and made the same frame condition also cover `rfp_submission` with `current="submission"`.
- InlineDecide now carries the F-35/F-39 stale-409 fix (`onStale`), so the two-reviewer case is covered by a test (notice plus unsent note, no buttons).
- The spec says E-DOCUMENT needs no mock change, but `mock/documents.mjs` served only D-2901 (501 otherwise). Added a 4-line D-3501 v1 branch (contradicts AC 24 "no mock *.mjs change"; AC 17 needs it).
- The spec said a failed step shows "Not recorded". The merged shared writer shows the step label plus "We couldn't confirm this step. Check the page before trying again." Used the merged wording; Try again reuses the key.
- Spec grep `TEST TEMPLATE` in src returns nothing; it finds the generic labels in `DocumentParts`, `DocumentReview`, `DocumentsTab`, `SampleLabel` (not changed). The test excludes that phrase only.
- Spec's `workspace.version` is left out of the fixtures: it drew an extra mono line the boards do not have.
- Spec ports 4951/4952; the demo uses 4985/4984, e2e ran on 4951/4952.
- Review item W-3502 has no `rfp`, so phone back is "Queue", and desktop uses the crumb header. Banner is a panel row with the returned tag (spec Conflicts 23).

## Changes
- `src/features/rfp/RfpFrame.tsx`: `submission` tab links to `/work/{tab.work_id}` only when returned.
- `src/features/work-item/WorkItemView.tsx`: frame for `rfp_submission`; no state-tag fallback on that line; phone back "RFP" to the first other tab with a page.
- `src/features/work-item/WorkItemOverview.tsx`: no task card for decided or step-less tasks on `rfp_submission`.
- `src/features/workspace/Workspace.tsx` (scoped to `rfp_submission`): agent card beside sections when Tola is `done`; item title as h2 under the frame with the workspace status at the end of the title line; banner tone from status tone; phone Drawer for forms.
- `src/features/workspace/InlineDecide.tsx`: "Goes to {decision.recipient}" only when returned (no existing in-place decide fixture carries one); a step with `disabled_reason` is drawn disabled with a visible line and `aria-describedby`.
- `src/features/workspace/Sections.tsx`: a checklist item's `cite_label` is drawn ("FROM THE RFP, P.2"); no earlier checklist fixture carries one.
- `mock/documents.mjs`: D-3501 v1.
- Fixtures: `mock/fixtures/work/W-3501..W-3509` (+ `.next`, `.steps`, `.approve/.return/.reject` sidecars), `mock/fixtures/response/W-3505.{delivered,not_delivered,unknown}.json`, `mock/fixtures/documents/D-3501.1.json`.
- Tests: `tests/rfp-submission.test.tsx`, `tests/rfp-submission-mock.test.ts`, `e2e/rfp-submission.spec.ts`. Two existing allowlists widened by `35` only: `tests/mock-contract.test.ts` (links), `tests/income-schedule-mock.test.ts` (verdict). No assertion removed.
- `delivery/BACKEND-HANDOFF.md`: "Added during F-38" section.
- Shared files touched: Workspace, InlineDecide, Sections, WorkItemOverview, WorkItemView, RfpFrame, each scoped as above.

## Fixes
None (round 1).

## Acceptance criteria
1. [~] Fidelity: all 8 boards run once on a production build; coverage and visual not at 100/90 (see Fidelity). Waivers proposed, unsigned.
2. [x] Exceptions: 33 entries, each with Conflicts number, `approved_by: builder proposal, pending design engineer`; none hides data.
3. [x] Draft from data: `rfp-submission.test.tsx` "W-3501 at 1440".
4. [x] Tab link additive: RfpFrame and header tests; `rfp.test.tsx`, `e2e/rfp.spec.ts` green.
5. [x] Computes nothing: modified-copy test; src checks for date arithmetic and MB.
6. [x] Unknown is never 0: W-3509 test.
7. [x] Agent work is not a decision: W-3501 test.
8. [x] Controls from you_can_act only: W-3502, W-3501.next, W-3509, W-3503/4, W-3507, W-3508, three personas.
9. [x] Send for review: one POST, double press one, 500 re-read and same key, 409.
10. [x] Edit cover letter: prefill, blank refused and focused, 422 under field, Drawer at 390.
11. [x] Approve: one claim, one decision `{approve, expected_revision:1}` valid against schema; Submitted only from re-read.
12. [x] Return/Reject note rules; RETURNED TO PM / REJECTED; phone Drawer.
13. [x] 409 on W-3506 shows v2; new press sends `expected_revision: 2`.
14. [x] (a) uncertain approve, (b) 500 and network with 60 s timer, (c) step uncertain, (d) not_delivered, unknown, 5xx on reconcile (delivered covered by the mock test with evidence and by rendering the sidecar; the panel's browser reload is a real page reload, so the component test re-opens the served item), (e) lock before and after reload.
15. [x] Receipts: five values test; "Delivered" and "delivery confirmed" absent from src.
16. [x] Record the outcome only where `rfp_outcome` returned; e2e click-through.
17. [x] Full pack: one GET, Test template, 404 line.
18. [x] 401, 403, 404, decide 403.
19. [x] Only GETs on load (plus the reviewer's one claim, which is not a decision); no POST after 60 s.
20. [x] Phone: one column, "RFP" back, Drawer, 44px targets in the page body. Not met: the shared "History" link (42x24) and the shell back link (41x44) are shell and shared-header items; excluded from the test and listed below.
21. [x] axe at 1440 and 390 on W-3501..W-3509, open Drawer, note error, uncertain with reconcile, not-open view.
22. [x] No new colours or px in CSS (no CSS file changed); components from `@/components`.
23. [x] Mock test (18 tests).
24. [~] Contract not extended except the documented `mock/documents.mjs` change and the two test allowlists.
25. [x] Existing tests green (see Validation).
26. [x] No overclaim; this file states the above.

## Validation
- `delivery/checks.sh` (under the shared lock), final run on eae52c70: lint, typecheck, build OK; vitest 3134 of 3135 passed. The one failure, `tests/start-work.test.tsx` Esc/focus, passed on its own rerun (61 of 61) and is load flakiness (load average 40+). Earlier run: `tests/ledger-source.test.tsx` 401 test also failed under load and passed on rerun. Run before this: the new tests and the two widened allowlists were fixed after the first run's 4 real failures (response-mock schema on sidecar `links`, verdict allowlist).
- e2e (`E2E_PORT=4951 MOCK_PORT=4952 npx playwright test e2e/rfp-submission.spec.ts e2e/rfp.spec.ts e2e/response.spec.ts e2e/workspace.spec.ts`): 124 passed, 1 failed (phone outcome text, a test assertion); fixed in e8ec75b5 and the test passed on its own run (2 passed, desktop and phone). Not re-run as one block after that edit.
- Vitest on the new tests: 43 + 18 pass.

## Fidelity (one run, production build, app 4985, mock 4984)
Scores in `round-1/fidelity/scores.txt`. Visual: desktop draft 89, review 80.2, submitted 74.2, submitted-portal 78; phone draft 78.1, review 79.3, submitted 83.1, submitted-portal 82.2. Coverage 78.1, 80, 77.8, 77.8, 57.1, 77.8, 50, 50 (with only the tab exceptions during the run: 93.8, 80, 92.6, 92.6 on desktop). The full 33-entry exceptions list was written after the run from its missing and extra lists and was not re-run (one run per round), so coverage with exceptions at 100 is unconfirmed. All 8 are under 90 and at or above 70: 8 visual waivers are proposed in `fidelity-exceptions.json` (`visual_waivers`), marked "builder proposal, pending design engineer (not signed)". Visible gaps: banner is a panel row not a green band; "Record the outcome" is the shared outcome link above Next, not the primary button in the Next card; shared frame and alerts bell.

## Pending items for others
- Design engineer: sign or refuse the 33 exceptions and 8 waivers; board text still says "all 4 approvals" (D-APPROVAL-ORDER says 3).
- Shared bugs (fix once, not here): the "History" link in the shared line header and the shell's back link are under 44px wide or high on phone; the shared uncertain notice contains the word "resend" in a sentence (not a control).
- Backend: items listed in the BACKEND-HANDOFF section (G-40-1..9, G-23-4, G-26-1, G-26-3, PMO-3-1, `rfp` omitted on reviewer read, D-RETURN).
- PSL questions 11 to 15 (test-template pack, submit-by lead time, what "delivered" means, what Return/Reject do, whether the publisher is the reviewer).
- Demo left running: app 4985 (build predates the last e2e-only commit but contains all source) and mock 4984. The 4985 build directory was rebuilt by the e2e and checks runs; the server was started before that and still answers 200.

## Merge note
- Merged origin/dlv-00-delivery-setup (F-40 handover, PRs #75/#78) into this branch as 32c97d3d. Conflicts in WorkItemView.tsx, Workspace.tsx and mock-contract.test.ts resolved keeping both sides: screenHeading now also gates titleShown, phone back handles deliveryId then rfpBack, links allow-list is W-(23|25|26|31|35|36|37). checks.sh passed (130 files, 3171 tests, build); tsc and eslint clean.
