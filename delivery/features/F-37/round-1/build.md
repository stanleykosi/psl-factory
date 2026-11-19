STATUS: READY
COMMIT: bd083748e523458592303756aec3c820aff2df99
BUILDER: builder
LANE: full

## Summary
- `/work/W-3401..W-3404` (line `rfp_response`) draw F-18's RFP frame on desktop (Requirements current, History link, Team input linking to F-18's form), with the requirement table, Progress, Tola's note, Before review and a disabled "Send for review".
- On the review list the PM can Accept answer, Accept selected (with a select-all header box), Edit answer ("Save and accept", choice prefilled from `values`) or Write my own; Cancel/Escape after a change asks "Discard your changes?" (rfp_response only). Phone forms open in the shared Drawer.
- Contract mock only: nothing is sent to anyone, and no working RFP response is claimed. Pricing, Send for review (part 2) and past-bid results stay held.
- This round also added a phone rule so the select-all box stays reachable in the stacked table.
- Fidelity is NOT at the bar: coverage is 100% after proposed exceptions on all 8 boards, but visual is 67.9 to 75.7, all under 90 (see Pending).

## Changes
- `RfpFrame.tsx`, `rfp.css`: `current` override, Requirements/Team input href rules, `end` slot (History).
- `WorkItemView.tsx`: frame on desktop for `rfp_response`; phone tag from `rfp.status`.
- `Workspace.tsx`: phone Drawer, discard question wiring, focus after a write, `selectAll` control (rfp_response only). `StepForm.tsx`: choice from `initial`, opt-in `askBeforeDiscard` and `closeRef` (other lines unchanged). `Sections.tsx`: `selectAll` slot, and "Suggested by <agent>" now also shows when a tag lacks the agent's name (existing F-17..F-30 tests still pass). `workspace.css`: select-all header kept on screen on phones.
- `mock/workspace.mjs`: `item_ids` 422 for `rfp_response` items. Fixtures W-3401..3404 (+ `.next.*`, `.steps.json`), `mock/proposals/rfp-response.json`.
- Tests: `tests/rfp-requirements.test.tsx`, `tests/rfp-requirements-mock.test.ts`, `e2e/rfp-requirements.spec.ts`. No existing test edited.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Frame, rows, progress, Tola, Unknown, no price, Send disabled, Record, Add requirement: component tests pass.
2. [x] Accept, accept selected, edit, write own, failures, uncertain step, access, personas: component and e2e tests pass.
3. [x] Phone 390: no sideways scroll, 44px targets (History link on the shared line header excluded), axe clean.
4. [ ] Fidelity (17): coverage 100% with proposed exceptions; visual under 90 on all boards (waivers proposed).

## Validation
- `npx vitest run` on rfp-requirements, mock-contract, workspace*, work-item*, rfp: 616 passed.
- `delivery/checks.sh` (under the shared lock): exit 0 (lint, tsc, 116 files / 2694 tests, next build). Run before the last small phone-CSS and select-all class edit; lint, tsc and the workspace and rfp-requirements vitest were re-run after it and pass.
- E2E (ports 4964/4965, 8 specs): first run 218 passed, 4 failed (the uncertain test clicked a disabled button; the phone 44px test measured the bare checkbox; phone select-all was clipped, a real defect, fixed in CSS). After fixes `e2e/rfp-requirements.spec.ts`: 26 passed. The other 7 specs passed in the first run, before the CSS edit; not re-run.
- Fidelity (production build, 4995/4994, `round-1/fidelity/scores.txt`): visual desktop 75.7, review 67.9, edit 68.0, reject 69.4; phone 70.5, review 71.9, edit 73.4, reject 72.0. I extended `drive-states.mjs` and `run.sh` so the review boards are driver-frozen with R-07 ticked.
- Servers on 4964, 4965, 4994, 4995 stopped (one listener still showed on `lsof` count; port not identified).

## Pending (for the design engineer / coordinator)
- `fidelity-exceptions.json`: 52 exceptions and 8 visual waivers, all "builder proposal, pending design engineer", none signed. Some exceptions cover label wording the shared form draws differently (Your answer, Status); the design engineer should confirm none hides a data-supplied value. Three desktop boards (67.9, 68.0, 69.4) are under the D-83 floor of 70 and need a signed one-board exception or a layout decision.
- Conflicts 1 to 6: built as "Recommend" (two sample items, no past-bid result, internal-only reason help, Accept applies at once, link to F-18's form, discard question).
- Contract proposals for the backend: item `values` choice prefill (G-26-3), `steps[].submit_label` (existing F-41 proposal), plus G-26-1/-2/-5, G-24-4 as in spec.
