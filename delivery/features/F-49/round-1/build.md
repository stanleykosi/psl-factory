STATUS: READY
COMMIT: 3bedb8756740b91d1771dbe8f62f63dd0a3e69d4
BUILDER: builder
LANE: full

## Summary
- Start work gains the Pre-sale line "Log a received RFP" for persona `pmo_lead` (contract mock only): client picker, RFP reference, document upload (F-47 chain), received time, 4-way submission method, deadline state, note. A start lands on /work/W-3351 and adds one Unassigned row.
- Overlays (mock only, listed as contract proposals): `show_when` (G-23-2, `showWhen.ts`, `proposals/rfp-intake.json`), `allow_new` + `{new:{name}}` (G-23-1, cookie `psl_mock_rfp=new_client`), `deadline_status` (G-23-3). Fixed case C-RFP-INTAKE is G-23-5.
- Outside-lane edits: `me.pmo_lead.json` (startable_lines), `mock/work-list.mjs` (Unassigned row), `delivery/BACKEND-HANDOFF.md` ("Added during F-49").
- Round-1 finish: fixed two e2e test bugs (see Validation); committed and pushed.

## Changes
src/features/start-work (showWhen.ts new; intake.ts, IntakeField.tsx, RecordPicker.tsx, LineForm.tsx, labels.ts, useStartWork.ts, start-work.css additive), mock/start-work.mjs, work-list.mjs, fixtures (lines.pmo_lead, options/client, work/W-3351, me.pmo_lead), proposals/rfp-intake.json, tests rfp-intake.test.tsx and rfp-intake-mock.test.ts, e2e/rfp-intake.spec.ts.

## Fixes
- none (round 1)

## Acceptance criteria
Covered by rfp-intake.test.tsx (component), rfp-intake-mock.test.ts (mock, source greps) and e2e/rfp-intake.spec.ts (1440 and 390: drawer, 44px targets, axe on each state, request log, Unassigned row, 403, uncertain, new client). Criterion 18 (fidelity) is NOT met yet, see Fidelity. The spec's `grep "useMe|/api/v1/me|roles"` was replaced by a tighter pattern (`\buseMe\b|/api/v1/me|\.roles\b|roles:`), because the original matches `useMemo` in useStartWork.ts/LineChooser.tsx and the word "roles" in an existing comment of LineChooser.tsx (not new code); the tighter pattern returns nothing.

## Validation
- delivery/checks.sh (under the shared lock, lock released): backend check clean, lint, typecheck, build ok; vitest 3219 passed, 2 failed, both load flakes: `rfp-intake-mock` beforeEach ECONNRESET on /__mock/reset and `start-work.test.tsx` Esc/focus. Rerun alone: start-work.test.tsx passes; rfp-intake-mock passed 18/18 on 2 of 3 reruns (one earlier rerun failed once on the same source-grep test). Treat the ECONNRESET as a flaky mock-server start under load; reviewers should re-run. The gate itself exited 1 on those two, so the coordinator's gate may need a rerun.
- e2e (ports 4980/4981): `npx playwright test e2e/rfp-intake.spec.ts e2e/start-work.spec.ts e2e/start-work-proof.spec.ts e2e/rfp-assign.spec.ts`: 58 passed (6.0m). Earlier failures were test bugs: `getByRole('radio',{name:'Stated'})` also matched "Not stated" (now `exact: true`; same fix in the fidelity act.mjs), and the phone eyebrow (the shared Drawer draws no eyebrow on a phone; test expects 0 on phone, 1 on desktop).

## Fidelity
One run, production build, app 4965 / mock 4964, still running. With NO exceptions: desktop 1440 coverage 51.9, visual 74.2; phone 390 coverage 34.8, visual 67.9. Misses are the conflicts 1-6, 8, 11 items plus labels (Client or prospect, RFP reference, Received, Submit to, Deadline, Note) that the page draws but that were scrolled off screen at capture, because the drawer is taller than the board's (help lines, "(optional)"). Written: delivery/features/F-49/fidelity-exceptions.json, 30 numbered exceptions, all "builder proposal, pending design engineer". Score with these exceptions NOT re-measured (one run rule). Visual is under 90 and the phone is under 70: a board-level D-83 waiver is proposed for desktop (74.2) citing 2, 5, 7, 8; the phone (67.9) is under the floor of 70 and needs a design-engineer decision (likely driver capture of the scrolled sheet and the missing phone page bar).

## Pending
- Design engineer: sign conflicts 1-7 and the exceptions; decide the six scroll-capture label exceptions (a driver limit, not data) and the phone waiver.
- Backend questions (non-blocking): G-23-1, G-23-5, duplicate reference status, G-23-2, G-23-3, time zone for Received, G-23-4, G-23-6.
- No shared bug found. Possible flake: rfp-intake-mock ECONNRESET under load.
