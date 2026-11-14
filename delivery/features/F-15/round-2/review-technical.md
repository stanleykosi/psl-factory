VERDICT: PASS
COMMIT: abf4b7a0660a481a3b97648b400f86fe8bdcce4c
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-1-1 to TECH-1-4 are fixed in code and each new test would fail on the round-1 code (code read of 07d078e..abf4b7a; gate and e2e were run by the builder, not repeated).
- Phone focus: the opener is now a bar selector, looked up again on close and after the path changes, so the remounted phone bell takes focus after Open and footer links.
- Stale list, 401 on mark-read and drawer offset are handled in `useAlertsFeed`, `useOpenAlert` and `AlertsDrawer`; the CSS changes are scoped to 720-759px and below 380px and leave the 390px boards alone.
- One non-blocking edge below (a pending focus flag when the path does not change).

## Findings
- TECH-2-1 | non-blocking | low | frontend | `leaving.current` in `AppShell.tsx` is set by Open or a footer link and cleared only by a path change or the next bell open. If the target equals the current path (an alert whose work link is the page already shown, or "See all alerts" on /notifications), the flag stays true and the next unrelated navigation moves focus to the bell. Clear it in the close effect when the path did not change, or compare against the path at leave time.

## Verified
- TECH-1-1 | verified | `opener` holds `.shell-phone .shell-bell` or `.shell-topbar .shell-bell`; close and the `[pathname]` effect call `querySelector(...).focus()`, so the remounted (key={pathname}) bell is found. Unit tests "Open on an alert: the phone bar remounts..." (asserts `before.isConnected === false` and focus on the new bell) and "Alert settings and See all alerts" would fail on the old detached-element code. The e2e adds the same on phone.
- TECH-1-2 | verified | `readIds` re-applies read to a late list and subtracts the stale unread from `unread_count` (floored at 0; undefined stays undefined). The new test holds the GET, clicks Open, then releases it and expects badge 3 and "2 need you"; old code gave 4.
- TECH-1-3 | verified | `useOpenAlert` passes an `ApiError` to `onError`; `feed.stop` sets `stopped` only for `unauthenticated`. The 401 test expects 2 lists after the second bell click; old code would send a third.
- TECH-1-4 | verified | the offset is its own layout effect keyed on `phone`; the scroll-lock effect is separate and still runs once. The test flips `matchMedia` while open and expects 56px then 0px; old code stays 56px.

## Notes
- Shell.css: the 720-1079 rule drops the margin offsets, and the narrow-phone block (max-width 379.98px) only touches `.shell-phonebar--bell`, the brand size and the bell slot. Scrim now `var(--scrim)`.
- `overview.spec.ts` and `projects.spec.ts` changes came in with the dlv-00 merge and are outside this feature's diff.
