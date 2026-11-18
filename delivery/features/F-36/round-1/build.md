STATUS: READY
COMMIT: 023ad69ede328ce092a5c2d2cd91ec3b462ac6bd
BUILDER: builder
LANE: full

## Summary
- A PMO Lead on My work → Unassigned presses an RFP row and the shared Drawer "Assign accountable PM" opens over the list (`?queue=unassigned&assign=<id>`; phone sheet). It lists only `assign.candidates`, chooses nobody, and sends one E-WORK-ASSIGN. No `assign` means no control (the page goes on to `/work/<id>`); nothing is read from `/me`.
- Success words appear only after the item and list are re-read; stale, 422, 5xx, network and written-then-failed cases never say "assigned" early and never resend.
- Overlay (mock only, `frontend/mock/proposals/rfp-assign.json`): `assign.roles` + `acting_role` (G-24-1), `assign.evidence_kind` + `evidence_id`/`case_revision` (G-24-2), `assign.next` (G-24-3). Without them the page sends exactly the typed body.
- Reuses F-30/F-31 `AssignForm` and `useWorkspaceAssign` (additive props; `done` now set after the re-read) and F-09 `ProofField`/`useEvidenceUpload`.
- Round 1: first build; conflicts as approved in D-118. Exceptions and waivers are "builder proposal, pending design engineer".

## Changes
- `frontend/src/features/rfp/AssignPmDrawer.tsx` (new), `proposals.ts` (new readers), `rfp.css` (additive, tokens only).
- `features/workspace/AssignForm.tsx`: optional `words`, `hint`, `lead`/`middle`/`tail`, `formId`, `actions`, `ariaLabel`; a choice a re-read no longer lists is cleared with "That person can no longer be chosen." `useWorkspaceAssign.ts`: `AssignRequest` extras, notice set after the re-read (`assignedTo`, `reread`), stale version falls back to the item's `revision`. F-30/F-31 call sites unchanged.
- `features/my-work`: `model.ts` (`assign` in View/parseView/viewSearch), `WorkRows.tsx` (`hrefFor`), `MyWork.tsx` (list view ignores `assign` so the list is not reloaded; `refresh(force)` returns whether it read; notice; mounts the Drawer), `my-work.css`.
- `features/response/labels.ts`: `fileSize` returns "Size unknown" for a non-finite size (test-proven defect: showed "NaN KB"). Listed as the one shared-file change.
- Mock: persona `pmo_lead` (`me.pmo_lead.json`, `server.mjs`, `alerts.mjs`), `work-list.mjs` (Lead; written rows dropped, count down), `workspace.mjs` (revision on items with no workspace, overlay request validation, acting_role/evidence_id 422, case_revision 409, `<id>.assign.json` script), `response.mjs` (`assign.evidence_kind` kind and grant, exported `evidenceIssued`); fixtures W-3301..W-3306 (+ `.next`, `W-3306.assign.json`), list rows, board entry.
- Tests: `tests/rfp-assign.test.tsx` (29, real mock over HTTP), `tests/rfp-assign-mock.test.ts` (26), `tests/mock-contract.test.ts` (persona row, notification id, overlay-key strip), `e2e/rfp-assign.spec.ts`.
- `delivery/BACKEND-HANDOFF.md`: "Added during F-36".

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Opens over My work, closes without a request, focus returns: e2e desktop (Escape, Cancel, ×, link focused) and phone; component test (list read once).
2. [x] Candidates only from the response, nothing chosen, counts "3 people"/"1 person", no "0": `rfp-assign.test.tsx`.
3. [x] No assign, no control: W-3305 and a stripped W-3301 copy redirect to `/work/<id>`; W-3304 shows the empty sentence. The diff reads no `/me`/`useMe`; the only `roles` is the item's `assign.roles` (a response key). Component test asserts no `/api/v1/me` call.
4. [x] Acting role from the response only: W-3301 text and no `acting_role`; W-3302 select PMO Lead/CEO, CEO sends `acting_role: "ceo"`; same choices for personas pm and ceo.
5. [x] Next-step sentences word for word; fixed sentence has no WhatsApp/email/Tola.
6. [x] Typed assign body validates against the generated schema, one POST on a double press; mock log shows one assignment.
7. [x] Held list re-read: no "is now with" and the Drawer stays; then notice, row gone, tab count 5; item re-read failure shows "sent, but we couldn't refresh".
8. [x] Proof upload (`assignment_proof`, case_revision 1), assign sends `acting_role`, `evidence_id`, `case_revision: 2`; Assign held during upload; failed file blocks with the sentence; removing it sends without `evidence_id`.
9. [x] Validation, W-3303 note, over-long note, 422 under person_id/acting_role/evidence_id with entries kept.
10. [x] Stale: 409 → re-read, stale sentence, choice kept, one POST after 60 s of fake time, next press `expected_revision: 2`.
11. [x] W-3306 (written then 500): "Assigned to Tunde Bello", no form, one POST. `uncertain`: form kept, Try again sends exactly one more. Network error: re-read first, no resend. e2e checks the mock's assignments.
12. [x] 401 (next = panel URL), 403, write 403 show the not-open view with no client/name; pm keeps "Only Leads can see unassigned work." **Deviation:** the e2e not-open state uses W-1099 (the mock's no-access id); W-3399 has no fixture so the mock serves its default item (no `assign`, so the page goes to `/work/W-3399`). The component test makes W-3399 answer 404.
13. [x] Unknown parts, "Assigned to Unknown", "Size unknown" (component tests).
14. [x] Phone: same parts in one column, no Cancel, Assign PM full width and pinned, no sideways scroll, every target at least 44px before and after upload and on Try again (e2e).
15. [~] Fidelity below. Coverage 100% after exceptions on both boards; desktop visual 91.8 (PASS); phone visual 75.6, under 90, above the D-83 floor 70, with a board-level waiver (builder proposal, pending design engineer). Exceptions: all in `delivery/features/F-36/fidelity-exceptions.json`, each with Conflicts number.
16. [x] axe (wcag2a/aa/21/22aa) at 1440: W-3301, W-3302 before/after upload, W-3304, validation, 422, uncertain, not-open, list after success; at 390: W-3301, W-3302, W-3304. Reduced motion: nothing animating in the dialog (desktop).
17. [x] No hex/rgb/hsl or literal px in the added CSS; shared Drawer, Select, TextArea, Button, Callout, ValidationSummary, ProofField.
18. [x] `rfp-assign-mock.test.ts`: fixtures validate with overlay keys removed and overlay keys validate against the overlay; extra key 422; overlay only for overlay items; acting_role/evidence_id 422; revision on an item with no workspace; written assignment drops the row; reset restores.
19. [x] No change in `src/api`, `apps`, `architecture`, `design`, `src/shell`, `features/start-work`, protected paths, or existing fixtures except appended `pmo_lead` rows. Contract proposals (mock only): `assign.roles[] {role,label}` (G-24-1), request `acting_role` (G-24-1), `assign.evidence_kind` (G-24-2), request `evidence_id` and `case_revision` (G-24-2), `assign.next {summary, agent?, channels[]}` (G-24-3); meaning of `assign.role`, G-24-4 and the three questions are in BACKEND-HANDOFF.md.
20. [x] Existing behaviour green (see Validation); W-2413/W-2601 words and Finance Lead receipt rows ending on W-1137/W-1138 (e2e).

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` under the shared lock: EXIT 0 (lint, typecheck, 109 files / 2535 unit tests, production build), on commit d126f226-era code. After it I changed only `AssignPmDrawer.tsx` (keepTop, button kind), `rfp.css` and the e2e; tsc and eslint on those pass and the e2e below ran on them. No failure in an untouched file occurred.
- `E2E_PORT=4966 MOCK_PORT=4967 npx playwright test e2e/rfp-assign.spec.ts e2e/my-work.spec.ts e2e/issue-detail.spec.ts e2e/response.spec.ts`: 78 passed. An earlier run had 2 failures in my own spec (axe target-size on the validation summary links, fixed in CSS; W-3399 not a 404 in the mock, e2e now uses W-1099); the fixed run is all green. `frontend/test-results` deleted.
- Fidelity: production build with API_ORIGIN pointing at the mock on 4964, app on 4965, shared tool unmodified, cookies `psl_mock_persona=pmo_lead,psl_mock_worklist=board`, output in `delivery/features/F-36/round-1/fidelity/`. (A first attempt hit an app built with the default API origin and showed "couldn't load your account"; it was discarded and the app rebuilt before the real run. The run was repeated once after keepTop/orange button and five more exceptions.)
- My servers on 4964 to 4967 stopped.

## Scores
- SCR-24-desktop at 1440: coverage 73.8 raw, 100 with exceptions; visual 91.8; PASS.
- SCR-24-mobile at 390: coverage 50 raw, 100 with exceptions; visual 75.6; tool FAIL on the default 90 only; board-level waiver proposed (D-83, floor 70; Conflicts 2, 5, 7, 8, 9, 10).
