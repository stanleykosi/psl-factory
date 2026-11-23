VERDICT: CHANGES
COMMIT: 3b8d10de03c23bf581a9b941189eb38a74b22681
REVIEWER: qa
AUTHORITY: integrated QA (lighter panel, D-180)

## Summary
- Live backend started on 8000 (Postgres 55433, API-only, CORS origin 4960). Unauthenticated GET /api/v1/work?queue=verified, queue=exceptions and queue=bogus all return 401 `unauthenticated` ("Sign in to continue."), which matches the spec's signed-out behaviour.
- Authenticated live GET /work for queue=verified and queue=exceptions was NOT run. The prompt allows test passwords only from seed or fixture files. I searched `apps`, `scripts`, `tests`, `fixtures`, `frontend/e2e`, `frontend/mock` and `config` in the worktree. None of them mention live-none, live-lead, live-multi or live-admin, so I could not sign in. I did not read the demo-login/demo-access files, and I did not create or reset accounts.
- On this head: `vitest run` of work-list, verified, exceptions and exceptions-mock tests passed (4 files, 57 tests). The mock on 4961 returned the live shape for queue=verified and queue=exceptions (page 2 served) and the v7 shape for queue=done.
- Not proved: live response shape against the adapter, wrong-user (403 queue_not_open) and wrong-tenant behaviour, Open output against real GET /work/{id}, a browser pass at 1440 and 390, and the no-write network check. The mock results are mock evidence only.
- The coordinator later asked me to set a throwaway password for live-lead and live-none through `manage.py shell` on the local 55433 database (as F-58 QA did). The permission system denied that command, so I did not change any account and the live journeys remain unrun. A person with authority needs to allow it, or run it, and then QA can be re-run.
- Next.js on 4960 was not started, because the live journeys were blocked. I stopped only the Django and mock PIDs I started.

## Findings
- QA-1-1 | blocking | medium | integration | Integrated QA cannot be proved: no seed or fixture file in the worktree gives a password for the local accounts live-none, live-lead, live-multi or live-admin, so no authenticated live GET /work?queue=verified or queue=exceptions, and no browser journey, could be run. Expected: a documented seed source for the test passwords (or a session the QA role may use). Actual: only 401 responses reachable. Re-run QA once credentials are available in a permitted seed or fixture file.

## Verified
None.
