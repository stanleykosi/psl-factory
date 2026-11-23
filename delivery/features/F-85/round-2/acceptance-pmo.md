VERDICT: PASS
COMMIT: cdea4f987fb2e1d59cf051a8bdf96dd7197cf6e9
REVIEWER: pmo-acceptance
AUTHORITY: PMO delivery acceptance (D-180 lighter panel; delivery only, not client/product acceptance, merge or release)

## Summary
- Status: mock-proved, live pending. Round 1's acceptance still holds on the same basis. Round 2 only adapted the mock and tests to API 1.24.0 (MAIN-1-1), then merged main at API 1.26.0 with no F-85 code change (`round-2/build.md`). The delivered behaviour is the round-1 behaviour, so the round-1 coverage of task FE-CONNECT-1 (SCR-02) carries over. The feature has no operation IDs.
- Evidence on this head: the gate passed on attempt 2 (`round-2/checks.md`; attempt 1 was a 1800 s timeout, exit 124, not a code failure). Technical, security, UX and UI reviews and integrated QA all passed on cdea4f98. QA re-ran the mock in a browser at 1440 and 390 for /work/4101 to 4108 and the history filters, and the unit tests (50) pass.
- The one blocking finding, MAIN-1-1, is VERIFIED by reviewer-technical on this head. No blocking finding is open. No accepted risk or waiver is involved.
- Live is still unproved: criteria 2 and 19, the live half of 22, and the live 404 and 403 wording. Cause: the shared test database lacks main's migrations (QA-2-1, `workflows_factorywork.status_changed_at`, policy 0102), so every live work read answers 500. QA-2-1 is an environment gap, and nothing in F-85's code is at fault. Live sign-in, csrf_failed and 401 shapes were shown. In the browser the 500 shows a "couldn't load" state, not a blank page.
- Product acceptance of cdea4f98 is recorded by the main coordinator in `round-2/acceptance-product.md` (passed, per `feature.json`). I did not edit it. Low findings carry into F-87. The parent package and this feature must keep saying "mock-proved, live pending" until PMO-2-1 is closed.

## Findings
- PMO-2-1 | non-blocking | medium | integration | Live proof is still missing, which is PMO-1-1 carried forward and now tied to QA-2-1. Expected: criteria 2, 19, the live half of 22, and the signed-in 404 and 403 reading "This record is unavailable." compared against live Django (8020, Postgres 55433). Actual: unproved. The live work endpoints answer 500 until the database has main's migrations (agents 0004 to 0023, core 0003 to 0008, documents, identity, policy to 0104), and there is no seeded weekly report item and no object storage for the upload. Delivery acceptance rests on the mock being validated against the contract (`tests/mock-work-live.test.ts` passes in the gate) plus the drift test. To close: (a) the design engineer applies the migrations, and the coordinator seeds one work item and one weekly report item for `live-lead`; (b) QA re-runs the live journeys and compares the page with `GET /api/v1/work/{id}`, `/history` and `/weekly-report`; (c) start storage and upload one PDF on a case the account may write to. Do this before any live claim and before F-87's writes are accepted live. Until then the status stays "mock-proved, live pending".
- PMO-2-2 | non-blocking | low | pmo | Scope note on the changed-path list. `feature.json` `git.changed_paths` for this head lists many backend, migration and contract files, plus other lanes' mock files. They come from the main merges (API 1.24.0 and 1.26.0), not from F-85 work. F-85's own paths are `frontend/src/features/work-item/live/`, the shared workspace adapter and evidence picker, `frontend/mock/work-live.mjs`, and their tests and e2e. I could not check each merged file line by line. The build and coordinator notes record a clean merge with no F-85 change, and the gate passed. Do not read the list as F-85 scope. Rely on the merge-base diff at integration.
- PMO-2-3 | non-blocking | low | pmo | Round-1 PMO-1-2 (criterion 3 holds for `work-item/live/` only, and the v7 frame must be removed once the last line moves) and PMO-1-3 (criteria 7 and 8 rest on unit tests; QA-2-2 and QA-2-4 repeat this) still stand. Re-check after F-58 and a per-route mock scenario exist. Build.md also records 38 full-vitest failures in lane A's /me and /projects mocks (not F-85 files) from before the main merge. The gate passed after the merge, so I take them as resolved by main. Lane A owns confirming that.

## Verified
- PMO-1-1 | reopen | Not closed. It carries into PMO-2-1, since live proof is still missing.
- PMO-1-2 | reopen | Not closed. It carries into PMO-2-3, since the v7 frame is still present.
- PMO-1-3 | reopen | Not closed. It carries into PMO-2-3, since F-58 and a per-route scenario are not in.

## Checked
- Acceptance criteria: criteria 1, 3 to 18, 20, 21 and 23 to 31 keep their round-1 passing evidence in `round-1/build.md`, `round-1/review-qa.md` and the round-2 re-run. MAIN-1-1 (history `actor_kind`, `entry_id` and `next_before`) is covered by the mock contract test and the live-work-item tests.
- Blocking findings: MAIN-1-1 is the only one, and it is VERIFIED (`feature.json`, reviewer-technical, cdea4f98).
- Docs and handoff: `round-2/build.md` has the changes, fixes and coordinator note. The spec requires no other handoff document.
- Parent claims: F-85 claims no money or client-facing writes, station track, six facts or agent steps. Those stay with F-87 and with the open board questions LC-Q1, LC-Q4 and LC-Q6.
