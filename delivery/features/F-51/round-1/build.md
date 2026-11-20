STATUS: READY
COMMIT: c4bd4510133c0c807bf0ae1d2068f8b7a14b6ff8
BUILDER: builder
LANE: full

## Summary
- "Fixed asset schedule" is a live Start work line for the finance persona: F-47's Proof box (kind `ppe_register`, fixed case `C-FIN-PPE` rev 4), optional Prior schedule and optional Accounting note, button "Start schedule", lands on `/work/W-3901`.
- "Cash forecast" is a start with no file: Scenario, As of, Months, Audience (3 segments from data, none preselected) and read-only Sources as returned; button "Start forecast"; lands on `/work/W-4001`. No Proof box.
- D-130 followed: no forecast Proof box; lines served to `finance_lead` only; Accounting note optional starting at "None"; Audience options from data.
- Mock only: new backend-stated 422 samples (Months 1 to 12, As of date, listed audience) and cookie value `start_hold` (forecast lands on `W-4006`). No `src` logic added except two button labels.
- Contract mock only; nothing released.

## Changes
- `frontend/src/features/start-work/labels.ts`: `fixed_assets` "Start schedule", `cash_forecast` "Start forecast" (only src change).
- `frontend/mock/start-work.mjs`: WORK_IDS for both lines, `forecastProblems` (backend-stated 422s), `start_hold`.
- `frontend/mock/fixtures/start-work/lines.finance_lead.json`: the two lines; `options/prior_schedule.json`, `options/scenario.json` new.
- Allowed outside lane: `frontend/mock/fixtures/me.finance_lead.json` (`startable_lines`).
- New tests: `tests/start-work-ppe-forecast.test.tsx` (22), `tests/start-work-ppe-forecast-mock.test.ts` (24), `e2e/start-work-ppe-forecast.spec.ts` (9 x 2 viewports).
- Existing assertions updated only for finance_lead's line count 3 to 5 (unavoidable when lines are added): `tests/start-work-mock.test.ts`, `tests/start-work-proof-mock.test.ts`, `tests/start-work.test.tsx` (3 spots), `tests/rfp-intake-mock.test.ts`.
- `delivery/BACKEND-HANDOFF.md`: "Added during F-51" section. `delivery/features/F-51/fidelity-exceptions.json` and `round-1/fidelity/`.

## Fixes
- none (round 1).

## Acceptance criteria
1. [x] Fixed-asset drawer from data: component test (order proof, prior_schedule, accounting_note; "(optional)" labels; "Start schedule"); e2e both viewports.
2. [x] Forecast from data, no file: component test (0 file inputs, no "Choose a file", Sources follows a changed fixture, Audience segments).
3. [~] Nothing computed or defaulted: no audience preselected, Months/As of empty, diff grep for `months *[<>]|new Date(|accepted` is empty. DEVIATION: Start is NOT disabled while required fields are empty. F-05's existing behaviour (unchanged) sends the start and the server's "<Label> is required." shows under each field; my test asserts that real behaviour. Disabled-until-filled would need a change in shared LineForm; I did not make it. Needs a decision.
4. [x] Only Finance gets the lines; `/me` equals E-LINES for every persona (mock test).
5. [x] Upload to `/api/v1/cases/C-FIN-PPE/evidence`, schema-valid body, "Uploading…" then "Uploaded · 96 KB"; answer without `evidence_id` reads "Not uploaded", no proof sent (component, e2e log).
6. [x] Proof required (422 "Proof is required." under Proof); revisions 4, 5, start 6 with second id; removing a card sends nothing; no "deleted" in start-work source.
7. [x] Start held while uploading and failed (component, e2e).
8. [~] Wrong record: 422 "That proof isn't on this record. Add it again." tested. Upload with kind `ppe_register` to C-0101, C-FIN-LEDGER, C-FIN-FORECAST is refused (4xx) and moves no revision, but is NOT a guaranteed 404: F-47's tested routing leaves non-owned cases with the F-09/F-11 owners (422 on kind). Not changed (those mocks are out of lane).
9. [x] One start each (double press), lands on W-3901 / W-4001.
10. [x] Forecast body is scenario, as_of, months (integer), audience only; the three 422 sentences word for word under their field, values kept.
11. [x] start_hold lands on W-4006, "SETUP NEEDED", no Decide button (e2e).
12. [x] start_uncertain both lines (same body and key, one start recorded); upload_uncertain; stale 409 on upload and forecast start.
13. [x] 401 signed-out with next; 403/404 wording; no `case_revision` stays "can't start here yet".
14. [x] Hostile file name as text, no `accept`, no `href` from data, 200 without `case_revision` reuses last revision, no "0 KB". Diff grep for `PROOF_TYPES|accept=|useMe|/api/v1/me` empty.
15. [x] e2e at 390: Choose a file, "×", Try again, Start, segments and selects at least 44 px; no sideways scroll; Escape closes and returns focus.
16. [ ] Fidelity NOT met, see below.
17. [x] axe (all 5 wcag tags) clean at 1440 and 390: both drawers empty, uploading, uploaded, failed, 422 under Proof and Months, Check again.
18. [x] No hex or px added; no local copies of shared components.
19. [x] Mock matches the contract (schema-validated lines, options, upload 200, start 201); reset restores 4, 2, 6, 3, 2.
20. [x] checks.sh exit 0 (3267 tests, build) under the shared lock; lock released.

## Validation
- `bash delivery/checks.sh` under the lock: exit 0; vitest 134 files, 3267 passed. (Two earlier runs failed on lint warnings and then on the rfp-intake line count; both fixed.)
- e2e (ports 4896/4897): `npx playwright test e2e/start-work-ppe-forecast.spec.ts e2e/start-work-proof.spec.ts e2e/start-work.spec.ts`: 36 passed and 2 Escape tests failed (test bug: focus not in the drawer); fixed and re-run: 2 passed. Net 38 passed.
- Demo left running: app 4965 (production build, API_ORIGIN=http://127.0.0.1:4964, FRAME_FIXTURES=1) and mock 4964; both answer 200. Worktree clean, pushed.

## Fidelity
One run, production build, finance_lead, driver `round-1/fidelity/_driver` (captures the whole sheet, union height). Run with NO exceptions; exceptions then written from the reports (not re-measured):
| Board | coverage | visual |
|---|---|---|
| SCR-04-desktop-ppe 1440 | 87.2 | 42.8 |
| SCR-04-mobile-ppe 390 | 64.3 | 49.8 |
| SCR-04-desktop-forecast 1440 | 82.1 | 42.1 |
| SCR-04-mobile-forecast 390 | 50.0 | 47.4 |
- `fidelity-exceptions.json`: 12 numbered exceptions, all "builder proposal, pending design engineer", covering every missing item (Conflicts 2, 3, 5). By the arithmetic every missing item is excepted, so coverage with exceptions would be 100%, but that is not re-measured.
- Visual is far under 70 on all four, so no D-83 waiver can be proposed; a design-engineer decision is needed. Causes seen in the side-by-side: the capture includes the full My work page under the scrim (2271 / 2684 px high vs the board's 900 / 844 sample list); the board shows Management selected, the build has Internal (D-130: nothing preselected, driver picks Internal); As of and Months sit side by side on the board but stack in the build (real layout difference, shared field layout, not changed).
- Exceptions "As of" and "Months" labels (text) are unverified: the labels are visible in the built page; UI review should confirm.

## Pending items
- Decision: Start disabled until required fields filled (criterion 3) vs F-05's server-names-what-is-missing behaviour.
- Decision: Accounting note has four sample options ("Sample note A" to "D") rather than the spec's two, because the shared drawer draws three or fewer choices as segments; four gives the board's "None ▾" select that can be cleared. Fixture only, placeholders not business terms. Also the lines do not carry `sample: true` (the generated schema forbids it); options in the new option files do.
- Decision: visual scores (above), phone sheet taller than board, As of and Months side by side.
- Backend items: fixed case and revision source (gaps-e q3), `ppe_register` kind, Accounting-note and Audience lists, whether Group is offered while NOT SET, Months/As of validation, `next` (G-SCR04P-9), who may start the lines, source of the Sources text. All in BACKEND-HANDOFF.md.
- Mock-only: cookie value `start_hold`; ids `EV-SW-C-FIN-PPE-<n>`; both lines and two option files.
