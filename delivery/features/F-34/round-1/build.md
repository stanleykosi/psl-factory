STATUS: READY
COMMIT: 512e5bc3ca426ddf049cb23ec6272cd4cd2848e4
BUILDER: builder
LANE: full

## Summary
- Code, fixtures, tests and e2e for SCR-46 part 1 (running, record, setup-needed, qualified) are built and pushed on the contract mock only. Nothing is deployed, evaluated or qualified.
- BLOCKED only on the design-fidelity gate. The scores below were taken before the exceptions file had the tool's exact missing items, so coverage is under 100 on all 8 boards. The final exceptions file is written but not scored. The re-run was refused by the permission system, so I stopped.
- Shared fixes: (1) an empty tag cell already reads Unknown (F-31), so only a regression test was added; (2) the "Done: ..." notice now follows the re-read in `useWorkspaceStep.ts`, a byte-for-byte copy of F-41's version (origin/fe-payments-payments-list-and-reminder, per the coordinator note) so the later merge is trivial; (3) the mock's `upload` already accepts a workspace step's evidence kind (F-31), so only tests were added.

## What is sent, and what stays held
- Contract mock only. Nothing is deployed, evaluated or qualified, and no one is given authority.
- Every "Day 10 of 30", "30 days · from Setup", Met and "qualified" is fixture text. PSL has not set `delivery.hypercare_window` or `delivery.hypercare_criteria` (D11 open). The honest state is the setup-needed hold: W-3103, and the mock's re-read after Record release.
- Sent: `record_release` (version, released_at, environment, deployment log uploaded first with kind `deployment_log`) and `log_observation` (what, optional proof). Each carries CSRF, `expected_revision` and one `idempotency_key`. Nothing else is sent.
- Held: the window and criteria (D11, D-ADMIN-AUTHORITY); the observation record (G-46-1); the evaluation trigger (G-46-2); where the incidents count comes from; `environment` free text or list; whether a PM gets the Setup link.
- "Qualified" and the green banner appear only when the returned status tone is `verified` (W-3104). W-3110 (agent step marked done) shows neither.

## Changes
- `frontend/mock/fixtures/work/W-3101..W-3112` (+ `.next`, `.steps` sidecars) and `W-3120`: the four states, the failure paths and the Unknown, unavailable and agent cases. Case revision 2, as the mock's upload compares for P-0101.
- `frontend/mock/fixtures/projects/P-0101.json`: one added line, `"work_id": "W-3101"` on the Hypercare row.
- `frontend/mock/proposals/delivery-hypercare.json`: `setup_rules` link overlay (G-F34-1).
- `src/features/workspace/proposals.ts`, `Links.tsx`: `setup_rules` link kind, drawn only for a known area. `src/features/setup/format.ts`: `AREA_ROUTES` is now exported (one word; the spec says to import it).
- `src/features/workspace/useWorkspaceStep.ts`: done and queued notices after the re-read (same as F-41).
- Tests: new `tests/hypercare.test.tsx` (29), `tests/delivery-hypercare-mock.test.ts` (34), `e2e/delivery-hypercare.spec.ts` (21). Edited: the three Hypercare link assertions (`delivery-overview.test.tsx` x2, `delivery-release-mock.test.ts`); `mock-contract.test.ts` (setup_rules link schema and the links-fixture name pattern now includes W-31xx); `e2e/delivery-release.spec.ts` (the sub-nav now lists Hypercare). These last two are needed by the new fixtures and are additive.
- `delivery/BACKEND-HANDOFF.md`: "Added during F-34: hypercare (19 Nov)".
- Factory: `delivery/features/F-34/fidelity-exceptions.json`; `round-1/fidelity/` (run.sh, drive-states.mjs, serve-frozen.mjs, reports, scores.txt).

## Acceptance criteria
1. [ ] Fidelity, 8 boards: NOT MET (see Scores).
2. [x] Driven state is the real UI: `drive-states.mjs` presses, types and uploads, makes only the freeze edits, and throws if the workspace log has any step; it ran clean.
3. [ ] Exceptions limited: the file is written (26 entries and 7 visual waivers, each `approved_by: "builder proposal, pending design engineer"`, mapped to Conflicts numbers) but not yet scored.
4. [x] Hypercare row links to /work/W-3101: tests and e2e.
5. [x] Four states from data: `hypercare.test.tsx`, e2e at 1440 and 390.
6. [x] Hold has no controls; Setup link only when returned and the area is known: component tests.
7. [x] Qualified only when verified; W-3110 shows no banner or link; amber copy: component tests.
8. [x] Unknown: W-3111 test.
9. [x] Controls only from the response; same for pm, finance_lead, ceo: component tests.
10. [x] Record release: e2e with recorded requests, one upload and one step with `expected_revision` 1.
11. [x] No success before the re-read: the deferred re-read test fails on the old hook and passes now.
12. [x] Uncertain paths W-3105..W-3108, W-3112 and a network failure: component and e2e tests.
13. [x] Log an observation. 14. [x] 422, 403, upload 5xx, `none` persona 403 (mock test).
15. [x] Access: 401, 403, 404. 16. [x] Phone: one column, 44px (the shared proof chip's remove button, 24px, is excluded from the e2e check; it is existing shared code). 17. [x] Axe clean.
18. [x] No colour literals or new components in the diff.
19. [x] Mock matches the contract. 20. [x] Contract not extended. 21. [x] Existing behaviour not weakened. 22. [x] This file carries the overclaim section.

## Validation
- `delivery/checks.sh` (under the lock, load below 14): lint, typecheck and Django check passed; unit tests 2507 of 2509 passed. The two failures were `tests/setup-rules.test.tsx` (403 focus) and `tests/start-work.test.tsx` (422 focus), files I did not touch. Both pass alone (42 and 48 tests) and `hypercare.test.tsx` passed in the same run; one `hypercare` test (422 form message) failed once under load and passed on re-run. The gate's final `npm run build` step was not reached after those failures; `npm run build` itself ran clean twice (e2e and fidelity builds).
- e2e (`E2E_PORT=4962 MOCK_PORT=4963`): hypercare + delivery-release + workspace specs, 76 passed and 4 of my own failed (a wrong no-access id, a chip 44px check, a stale-message assertion), fixed; `delivery-hypercare.spec.ts` re-run alone: 21 passed. `frontend/test-results` deleted.
- `npx tsc --noEmit` and `npm run lint`: clean.

## Scores (8 boards, production build, API_ORIGIN pointed at the mock on 4960)
The first live run used a build pointed at the wrong mock port (error page), so it is not counted. Then one live run (6 boards) and one frozen run (2 record boards) were scored with an exceptions file that did not yet name the frame items. Coverage with exceptions, visual:

| Board | Width | Coverage with exceptions | Visual |
|---|---|---|---|
| SCR-46-desktop | 1440 | 71.7 | 92.3 |
| SCR-46-desktop-setup-needed | 1440 | 71.7 | 77.1 |
| SCR-46-desktop-qualified | 1440 | 64.9 | 80.4 |
| SCR-46-mobile | 390 | 75 | 84.5 |
| SCR-46-mobile-setup-needed | 390 | 40 | 80 |
| SCR-46-mobile-qualified | 390 | 40 | 81.5 |
| SCR-46-desktop-record | 1440 | 60.9 | 82.7 |
| SCR-46-mobile-record | 390 | 50 | 77.5 |

Every missing item in those reports is a frame item (crumbs, signed-in name, project tab bar, delivery sub-nav, phone bar words), a sample-data difference (Tamarind Loans, 2027) or a field label/value drawn as an input on the record boards. All are now listed in `fidelity-exceptions.json`, and visual waivers are written for the 7 boards under 90 (all 70 or more). The exceptions were not scored.

## Blocked
- Who: the coordinator. What: one more fidelity run of the 8 boards with the final `fidelity-exceptions.json` (`bash round-1/fidelity/run.sh frozen`, then restart the mock and app on 4960/4961 and `bash run.sh live`; `scores.txt` must be emptied first). My attempt to start it was refused by the permission system, so I stopped, and I have not worked around it. My servers are stopped.
- If coverage is not 100 after that run, the remaining items are listed in each `SCR-46-*/report.json`.
- Open design-engineer decisions: all exceptions and waivers (builder proposal, pending design engineer); the Conflicts 1 to 5 answers were approved as recommended (D-118).

## Coordinator: scored fidelity re-run (19 Nov)
The builder's re-run was refused by the permission system; the design engineer approved the coordinator running it ("Yes, run it"). The coordinator ran `round-1/fidelity/run.sh live` then `frozen` unmodified against a production build of 512e5bc3 (mock 4960, app 4961; the frozen boards served by serve-frozen.mjs), with the final fidelity-exceptions.json. The first run's scores are kept in scores-first-run.txt. Result (scores.txt): coverage with exceptions 100 on all 8 boards; visual desktop 92.3 (pass) / setup-needed 77.1 / qualified 80.4 / record 82.7, phone 84.5 / 80.0 / 81.5 / 77.5. The 7 boards under 90 carry the 7 proposed D-83 waivers (pending the design engineer). Status set to READY by the coordinator on that basis.
