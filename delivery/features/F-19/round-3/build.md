STATUS: READY
COMMIT: 95903eeb853bc2c9a244eb2e4d19174871d875de
BUILDER: builder
LANE: full

## Summary
- Round 3 is a small fix for QA-2-1 / QA-2-2 only.
- The billing contact failure notices (409 stale, server 403 message, "We couldn't confirm the change was saved.", "Saved. We couldn't refresh the page...") now have role="alert", and focus moves to the notice after the press.
- The notice has a scroll-margin so the phone's sticky Save bar does not cover it.
- The plain "Billing contact saved." keeps its role="status"; 422 behaviour is unchanged.

## Changes
- frontend/src/features/clients/BillingContactForm.tsx: notice div gets ref, tabIndex -1, role="alert"; an effect focuses it when a failure notice is set.
- frontend/src/features/clients/clients.css: `.clients__notice` scroll-margin-bottom and outline-offset. No visible layout change, so no fidelity run (nothing visible moved; the notice only gains a focus ring when focused).
- frontend/tests/clients.test.tsx: the 200-with-failed-reload, 409, 403 and unconfirmed (network error and 502) tests now assert role="alert" and that document.activeElement is the notice.

## Fixes
- QA-2-1 | 95903eeb | role="alert" and focus on each failure notice, scroll-margin for the phone bar
- QA-2-2 | 95903eeb | focus now lands on the notice after Save instead of falling to the top

## Acceptance criteria
1. [x] Failure notices are announced and focused: component tests assert role and focus for each notice; 5 of them fail on the old component (verified by stashing the source change) and pass now.
2. [x] QA-2-3 not changed: persona `none` sees the frame's own no-sections page. That is a frame/integration note; the frame was left alone.

## Validation
- `bash delivery/checks.sh` in the worktree: exit 0 (the run's output ended in the Next build route table).
- `npx vitest run tests/clients.test.tsx`: 31 passed (old source: 5 failed).
- `npx playwright test e2e/clients.spec.ts` with E2E_PORT=4631 MOCK_PORT=4632 FRAME_FIXTURES=1: 16 passed. test-results deleted, no servers left on those ports.
- Disk: 5.1 GB free before starting.
- Not run: the screen-reader behaviour was not checked with a real screen reader; only role and focus in jsdom.

## Blocked
n/a
