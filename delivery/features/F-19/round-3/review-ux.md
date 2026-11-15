VERDICT: PASS
COMMIT: a4a906cadfbafced2c20f8535467cb32db06c3eb
REVIEWER: reviewer-ux
AUTHORITY: delegated UX review

## Re-confirmed on the synced head
- `git diff --stat 95903eeb a4a906ca -- frontend/src/features/clients frontend/src/app/clients frontend/src/shell` is empty: no Clients page, Clients feature file or shell file changed.
- The shared top bar is therefore unchanged, and the line-layout frame applies only to work items with a line workspace. Nothing alters the Clients pages for a PM or a Finance user.
- The merge's other changes (backend, tests, docs) are outside the UX lens. e2e clients passed after the merge, per the brief; I did not re-run a browser walk.
- My earlier PASS at 95903eeb stands. No new findings.

## Earlier review (at 95903eeb)

## Findings
- none

Notes (diff review only, no browser run, per the lean re-review brief):
- QA-2-1 fixed: the failure notice (stale 409, server 403, unconfirmed, saved-but-unread) is now role="alert", so screen readers announce it. The plain "Billing contact saved." keeps role="status". 422 behaviour is unchanged.
- QA-2-2 fixed: the notice has tabIndex -1 and an effect focuses it each time a failure notice is set, so focus no longer falls to the body.
- Phone Save bar: scroll-margin-bottom 96px on the notice keeps the focus scroll clear of the sticky bar. I judged 96px from the CSS; I did not measure the bar's height on a device.
- Not checked with a real screen reader (the builder says the same). Role and focus are asserted in the tests.
