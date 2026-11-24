VERDICT: PASS
COMMIT: 86e1a6cfc20e7f6d999d4472374f7a8298fcd29a
REVIEWER: qa-reviewer
AUTHORITY: integrated QA

## Summary
- Playwright against the mock (contract mock on 4970, production `next start` on 4971), desktop 1440, 1024 and phone 390: `e2e/project-tabs.spec.ts` and `e2e/money.spec.ts` give 49 passed, 0 failed. Round 3 had 2 failed.
- Touched unit files pass: `tests/milestones-model.test.ts` and `tests/milestones.test.tsx`, 51 passed.
- Live: "Mark complete" is hidden for every staff role until backend LB-2 is fixed (no role carries `milestone.complete`). This is a backend issue, not a frontend failure.
- Round-3 journey evidence is carried forward (see below). The code of the Mark complete page did not change in round 4; the main merge touched only `mock/server.mjs` (alerts import kept).
- Not proved: a real completion, the real PDF upload and the real re-read against Django. LB-2 blocks the live write, and no local project has a signed baseline with proof.

## Findings
None.

## Verified
- QA-3-1 | verified | `E2E_PORT=4971 MOCK_PORT=4970 npx playwright test e2e/project-tabs.spec.ts e2e/money.spec.ts`: 49 passed. The milestones case now passes on desktop and phone ("Mark complete only on open stages") and the new case "no 'Mark complete' link where the server does not allow completing" (norole, zero links) passes on both.
- QA-3-2 | verified | `npx vitest run tests/milestones-model.test.ts tests/milestones.test.tsx`: 51 passed, including the `sections: []` case that now shows the empty state. Not re-run live: LB-2 and local data limits are unchanged, so the live `live-multi` page was not reopened.
- UI-1-4 | not mine | no code change; carried as the builder states.

## Carried forward from round 3 (still stands)
- The Mark complete page and its panel code are unchanged since d9f900c2, so the mock journeys stand: existing proof and PDF upload with the check-file tick, "Recorded" only after the re-read, every hold line (baseline, proofreq, inuse, norole), 403 and 404, 409 with kept choices and retry on revision 6, uncertain 503 with Check again (both outcomes), re-read failure, paging, no-name message. Round 3 ran vitest `milestone-complete` 45 and `mock-live-milestone-complete` 17; those were not re-run here (lean mode).
- Live (Django 8010, Postgres 55433): hidden for all staff roles (LB-2); POST without CSRF gives 403 `csrf_failed`; empty name 422; unknown case or milestone 404. No database writes.

## Notes
- Stack: Playwright started and stopped its own mock (4970) and next start (4971); no listener remains on either port. Disk was 23 GiB free.
