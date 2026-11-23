VERDICT: PASS
COMMIT: cf5074164183ccd9027b818fe6a3b64099288c2b
REVIEWER: qa
AUTHORITY: integrated QA (lighter panel, D-180)

## Summary
- Re-run AFTER the merge: this file was first written for ed72928f. The coordinator then merged origin/main (F-58 sign-in) as cf507416 and squash-merged PR #102 before QA covered it; the run below was done after the fact, on the worktree at cf507416.
- On cf507416: `E2E_PORT=4970 MOCK_PORT=4971 npx playwright test e2e/projects.spec.ts e2e/delivery-release.spec.ts` gave 50 passed, 0 failed (3.1m). That includes "signed out: 401 on the list and on a journey" (e2e/projects.spec.ts:359), which asserts the main-area "Sign in" link has href `/sign-in?next=%2Fprojects` (and `...%2Fprojects%2FP-0101` on a journey); `src/app/sign-in/page.tsx` from F-58 exists. I did not use a separate `dev.mjs`: the Playwright config builds and starts its own servers and refuses to reuse ports, so it would clash. No process of mine remains; 4970 and 4971 were free after.
- `npx vitest run tests/start-work.test.tsx tests/shell-live.test.tsx` on cf507416: 2 files, 93 tests passed (run alone, not under load).
- Earlier evidence for ed72928f (kept below, not re-run on cf507416; the live-data checks are carried forward by impact assessment, since the merge brought in sign-in only):
- Mock e2e on this head (own app on 4970, mock on 4971, `E2E_PORT=4970 MOCK_PORT=4971 npx playwright test e2e/projects.spec.ts e2e/delivery-release.spec.ts`; the Playwright config builds and starts its own servers, so the separate `dev.mjs` I tried first was stopped before the run): 50 passed, 0 failed, including the "project tab: Documents" step at desktop and phone.
- Live populated check with Django `force_login` (read-only, test client against the local PG, no account, role or record changed): GET `/api/v1/projects?status=all` returned 200 for all three accounts and validated against `contracts/psl-factory.openapi.json` with no errors. live-lead saw 2 projects and live-multi saw the same 2 (0d790a54-63ad-4416-9df9-d616c079992b and b0f4e2f4-f89c-48f7-92fe-60cb70837399, both titled "Local live workspace"). live-admin saw 1 (0d790a54-...).
- GET `/api/v1/projects/0d790a54-...` (first project of each account) returned 200 and validated with no errors. tabs were: live-lead journey, milestones, registers, actions; live-multi journey, milestones, money; live-admin journey. Every body had facts {total 0, waiting 0, stopped 0, finance null, engagement null}, items [] and next_page null.
- Scratch vitest outside the repo (`/private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/vt/cap.test.ts`) ran the captured bodies through `src/features/projects/model.ts`. isProjectList and isJourney accepted all six bodies, visibleTabs kept the live tab keys in order, projectCounts gave 0/0/0, null phase and lifecycle gave "Unknown", null finance and engagement gave "Not available", and shownText gave "2 shown" or "1 shown". The pass is on the model only; I did not render the pages against the live bodies.
- Not proved: rows with real work items (items [] in every live body), a non-null manager, lifecycle, phase, finance or engagement, a live next_cursor ("Show more"), and the live Delivery tab. The local data has no such records. The list schema's cursor field is `next_cursor` and the journey's is `next_page`. Both validate. Processes: my dev.mjs (killed by PID); the Playwright servers exited with the run; I started no Django server (test client only). Ports 4970, 4971 and 8010 were free at the end.

## Findings
None.

## Verified
- QA-1-1 | verified | On cf507416 and earlier on ed72928f: `e2e/projects.spec.ts` 28 of 28 and `e2e/delivery-release.spec.ts` passed on head ed72928f (50 passed in total). The Documents tab step now expects /projects/P-0101 and passes at desktop 1440 and phone 390.
- QA-1-2 | verified | A populated live body was exercised for live-lead, live-multi and live-admin (2, 2 and 1 projects; detail 200 on the first). Both bodies match the contract and the model handles every field. Rows with items, finance or engagement values, and paging remain unproved live because the local data has none (see Summary).
