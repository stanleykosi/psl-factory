STATUS: READY
COMMIT: cfd8a916060e08c73e7217af956fe4d3b98f41a1
BUILDER: builder
LANE: full

## Summary
- Screen readers now hear upload failures (UX-1-1). Each failed file's words are read out as `role="alert"`, the same way Callout announces a problem. The words are hidden on screen because the card already shows them.
- A 422 under Proof is now linked to the Proof box (`aria-describedby` and `aria-invalid`), the same way IntakeField links field errors (TECH-1-3).
- Try again no longer uploads to a case the drawer has dropped. The re-read now refuses, so the upload hook stops (TECH-1-1).
- The mock now gives an upload to start work only when the case is one that line starts on, not just when the kind matches (TECH-1-2 / security note).
- No layout changed, so there was no fidelity re-run. `round-1/fidelity/scores.txt` was refreshed from the saved reports (UI-1-2).

## Changes
- `frontend/src/features/start-work/StartProof.tsx`:
  - For each failed file (other than 403/404, which the drawer Callout already announces), adds a hidden `role="alert"` span: "<name>: Not uploaded. <reason>".
  - The fieldset drops `role="presentation"` and gets `aria-describedby` (the error's id) and `aria-invalid` when a 422 names Proof.
- `frontend/src/features/start-work/start-work.css`: adds `.sw-announce`, a screen-reader-only rule using the same hiding as the file's existing `.sw-range .psl-label` rule. Nothing visible changes.
- `frontend/src/features/start-work/useStartWork.ts`: `rereadCase` now throws a `not_found` ApiError in three cases: the fixed line is gone from E-LINES, no project is chosen, or the chosen project is no longer served (that one also clears it with "That choice is no longer available."). F-09's hook treats the throw as an access error: no upload is sent, the file is dropped, and the drawer says "You can't add proof to this item."
- `frontend/mock/start-work.mjs` and `frontend/mock/server.mjs`: `ownsUpload(url, raw, persona)` now also requires the `case_id` to be a case that line starts on (its fixed case, or a project option served to the persona). Any other upload goes to its F-09 or F-11 owner. In `server.mjs` the change is to the call inside the F-47 branch and to its comment.
- Tests:
  - `tests/start-work-proof.test.tsx` gains 4 tests (36 in total). The card-text helper now tolerates the hidden announcement.
  - `tests/start-work-proof-mock.test.ts` gains a routing test (18 in total). One assertion changed with the new routing: the ledger kind on `C-FIN-SCHEDULES` used to be a start-work 404. It now goes to the F-09 owner, which answers 422 for the kind, and the start-work revision stays at 3. A finance_lead upload to `C-0102` still answers 404 (criterion 12).
  - `e2e/start-work-proof.spec.ts` checks the announcement in the ledger failed state.

### Edit outside the lane recorded (TECH-1-4)
- `delivery/BACKEND-HANDOFF.md` gained "## Added during F-47: Start work proof upload (19 Nov)" in round 1 (commit c3b03bfb). The coordinator asked for it in the round-1 prompt. That edit to this file was missing from the round-1 build.md list; this round's file does not touch it.

## Fixes
- UX-1-1 | 8d7da0c4 | Upload failures are announced with their words (hidden `role="alert"` per failed file). Test "UX-1-1: each upload failure is announced…" covers a 422 `.exe`, a 500, a 409 and a 200 without an id. e2e "ledger states" checks the alert text at 1440 and 390, and axe stays clean.
- TECH-1-3 | 8d7da0c4 | The Proof fieldset carries `aria-describedby` pointing at the 422 message and `aria-invalid="true"`. Test "TECH-1-3: a 422 for Proof describes the Proof box…".
- TECH-1-1 | 8d7da0c4 | Try again sends no upload once the fixed line or the chosen project is gone. The re-read throws `not_found`, so the hook stops. Two tests, "TECH-1-1: Try again sends nothing once the fixed case… / the chosen project…", each assert one upload in total.
- TECH-1-2 | 8d7da0c4 | `ownsUpload` checks the case as well as the kind. The test "ownsUpload needs the kind of a served line and a case that line starts on" covers 9 combinations across personas.
- TECH-1-4 | 8d7da0c4 | The BACKEND-HANDOFF.md edit is now recorded in this file (above).
- UI-1-2 | (factory file, no commit) | `round-1/fidelity/scores.txt` was regenerated from the saved `report.json` files with the current `fidelity-exceptions.json`, using the tool's role and name matching. It now reads 100.0 with exceptions on all 8 boards, and a new `visual-waiver` column marks the 6 D-83 waivers. The `report.json` files themselves stay as the round-1 run wrote them.

Not fixed (non-blocking, left for the design engineer or a later round):
- UX-1-2: no line beside a held Start. The card's "Not uploaded" text is the reason shown, and the spec draws no such line.
- UX-1-3: the desktop "×" is 24 px. The spec asks for 44 px on phones only, and F-09's size is shared.
- UX-1-4: the file input is named through the Proof group's `aria-labelledby`. The e2e axe runs at both widths are clean.
- UI-1-3: two boards were drawn with fallback fonts. No re-run this round, as instructed.

## Acceptance criteria
All 23 criteria are as recorded in round-1/build.md. Two changed this round:
18. [x] Accessibility: upload problems are now announced (`role="alert"`). e2e axe is clean at 1440 and 390 in the same states as round 1.
20. [x] Mock matches the contract: routing now requires both kind and case. F-09 and F-11 routing tests are unchanged and green.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-47 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (under `.checks.lock`, load below 14) exited 0. The Django check found no issues; lint and typecheck were clean; vitest gave **102 files, 2322 tests passed**; the build succeeded.
- `cd frontend && E2E_PORT=4942 MOCK_PORT=4943 npx playwright test e2e/start-work-proof.spec.ts e2e/start-work.spec.ts e2e/response.spec.ts e2e/workspace.spec.ts` gave **77 passed** (3.7 min), run after the last change. `frontend/test-results` was deleted.
- Fidelity: no re-run. The only CSS added is the screen-reader-only `.sw-announce` rule; nothing visible changed.

## Blocked
None.

## Merge with dlv-00 (F-31..F-33, #65)
- Merged `origin/dlv-00-delivery-setup` into the branch. Merge commit and new head: `cfd8a916060e08c73e7217af956fe4d3b98f41a1` (parents 8d7da0c4 and the dlv-00 tip). Pushed. No AI trailer.
- **Conflicts: one.** `delivery/BACKEND-HANDOFF.md` had both sides appending at the end of the file. I kept all sections in date order: F-31 (engagement and planning), F-32 (delivery tab and release gates), F-33 (income schedules), then F-47 (Start work proof upload).
- **Merged without conflict, then checked:**
  - `frontend/mock/server.mjs`: identical to the F-47 side. The F-47 upload branch and the `cookies` pass-through on the start-work line are both present. dlv-00 added no `server.mjs` dispatch that this side lacks.
  - `frontend/mock/fixtures/me.finance_lead.json`: `startable_lines` is still `invoice, income_schedules, ledger_sources`. dlv-00 made no other change to it.
  - `frontend/tests/mock-contract.test.ts` and `frontend/src/features/response/useResponse.ts`: dlv-00's changes came in cleanly. Neither side's lists or regexes collided.
  - F-09's `ProofField` is unchanged, so F-31's chip × rule and the step form keep their behaviour. The `useEvidenceUpload.ts` `evidence_id` guard is still there.
- **Evidence kinds after the merge:** F-31 adds `plan` and `proof`. These don't collide with Start work's kinds (`meeting_notes`, `client_request`, `schedule_source`, `ledger_source`), and uploads are routed by kind and case, so the F-09, F-11 and F-31 owners keep their uploads.
- `cd /Users/Hunchoo/psl-factory-worktrees/f-47 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (under `.checks.lock`, load below 14) exited 0. The Django check found no issues; lint and typecheck were clean; vitest gave **110 files, 2552 tests passed**; the build succeeded.
- `cd frontend && E2E_PORT=4942 MOCK_PORT=4943 npx playwright test e2e/start-work-proof.spec.ts e2e/start-work.spec.ts e2e/response.spec.ts e2e/workspace.spec.ts e2e/engagement-planning.spec.ts` gave **99 passed, 0 failed, 0 flaky** (8.9 min). `frontend/test-results` was deleted.
