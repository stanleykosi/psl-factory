STATUS: READY
COMMIT: ef0362f8cfe0fd7dab7e1ce57eb419db93395954
BUILDER: builder
LANE: full

## Summary
- Shared Start work change (every line, F-05, F-47, F-49, F-51): pressing Start or Log RFP with a required field empty now shows each "<Label> is required." on the page, moves focus to the first, and sends nothing. Uses the `required` flag lines already send.
- Forecast: As of and Months on one row; Audience starts on the option the line's data names (Management).
- Fixed assets: "Optional" is a muted line under Prior schedule and Accounting note (scoped to `fixed_assets`); two sample notes "Sample: note A/B".
- Exceptions updated (sheet frame, remove ×, calendar icon, Optional exception removed).

## Changes
- `frontend/src/features/start-work/intake.ts`: `emptyRequired`. `useStartWork.ts`: check in submit, errors clear on change, focus request, `defaultChoices`. `LineForm.tsx`: focus effect, As of / Months pair row. `IntakeField.tsx`, `labels.ts`: Optional line, select for Accounting note, pair, all keyed to line key. `start-work.css`: `.sw-pair`.
- `frontend/mock/fixtures/start-work/lines.finance_lead.json`: two sample notes; audience field `value: "management"`.
- Tests updated: start-work.test.tsx (invoice, leadership 409), start-work-proof.test.tsx (minutes), start-work-ppe-forecast.test.tsx, e2e start-work.spec.ts and start-work-ppe-forecast.spec.ts. Added: per-family empty-press tests in rfp-intake.test.tsx (F-49), start-work-proof.test.tsx (F-47: income schedules, minutes), start-work.test.tsx (F-05 invoice), start-work-ppe-forecast.test.tsx (F-51).
- SHARED CHANGE for the coordinator: the required check is in shared `useStartForm`; F-05, F-47 and F-49 now behave the same. Project lines still keep Start off until a project is chosen (unchanged). Contract note: there is no contract field for a choice default. I used the field-level `value` (schema-valid, documented for display fields) naming an option; the coordinator may want the contract to define it.

## Fixes
- UI-1-1 | As of and Months share one row (`.sw-pair`, 12px gap) at 1440 and 390 | 80f773d3
- UI-1-2 | "Optional" is a separate muted line under Prior schedule and Accounting note, fixed_assets only | 80f773d3
- UI-1-3 | Audience default read from the line's data (Management selected); a line naming none selects none | 80f773d3
- UX-1-2 | two Accounting note options, "Sample: note A" and "Sample: note B", drawn as a select | 80f773d3
- UI-1-4 | kept F-05's bottom sheet; honest exceptions citing the signed 14 and 19 Nov frame items | b50b0b7c
- UI-1-5 | exceptions for the proof card's remove "×" and the calendar icon | b50b0b7c
- UX-1-1 | required fields shown and nothing sent (answers the open Start-enabled decision: Start stays enabled, press names the fields) | 80f773d3
- TECH-1-1 | same shared check; spec criteria 3 and 6 are now met in behaviour | 80f773d3
- F-49 QA-2-1 (batch B) | Log RFP with required fields empty sends nothing, names each field, focuses the first; test added | 80f773d3

## Acceptance criteria
1. [x] Fixed-asset and forecast drawers from data: component tests, e2e at both viewports.
2. [x] Nothing computed in browser: Months and As of empty; Audience from data default only; no new Date or month rule added.
3. [x] Required fields empty: messages on the page, focus first, no send (tests for F-05, F-47, F-49, F-51 lines; e2e forecast and invoice).
4. [x] Other criteria unchanged from round 1 (all 22+ tests pass).
5. [~] Fidelity: see below; not at visual 90 (capture limit, tall page behind the drawer).

## Validation
- `bash delivery/checks.sh` under the lock: exit 0, 134 files, 3273 tests passed, build ok (run on 80f773d3; b50b0b7c only changes a CSS gap, 8px to 12px). Lock released by me after the run.
- e2e (ports 4896/4897): start-work, start-work-proof, rfp-intake, start-work-ppe-forecast: 48 passed.
- Fidelity, one run, production build, 4965/4964 (`round-2/fidelity`): coverage with the round-1 exceptions 100 on all four; raw coverage / visual: desktop ppe 89.7 / 42.3, mobile ppe 71.4 / 49.9, desktop forecast 82.1 / 43.3, mobile forecast 50.0 / 48.1. Visual under 90 because the page capture is 2.5x to 3x the board height (list under the scrim, same limit as F-49); side-by-side shows the drawer matches (As of / Months row, Management selected). Exceptions file updated after the run (Optional removed, three added); not re-measured. Waiver proposal: the four boards, pending the design engineer.
- Demo left running: app 4965 (production build, API_ORIGIN http://127.0.0.1:4964, FRAME_FIXTURES=1) and mock 4964. Worktree clean and pushed.
