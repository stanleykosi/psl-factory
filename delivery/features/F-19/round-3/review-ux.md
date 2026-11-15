VERDICT: PASS
COMMIT: 95903eeb853bc2c9a244eb2e4d19174871d875de
REVIEWER: reviewer-ux
AUTHORITY: delegated UX review

## Findings
- none

Notes (diff review only, no browser run, per the lean re-review brief):
- QA-2-1 fixed: the failure notice (stale 409, server 403, unconfirmed, saved-but-unread) is now role="alert", so screen readers announce it. The plain "Billing contact saved." keeps role="status". 422 behaviour is unchanged.
- QA-2-2 fixed: the notice has tabIndex -1 and an effect focuses it each time a failure notice is set, so focus no longer falls to the body.
- Phone Save bar: scroll-margin-bottom 96px on the notice keeps the focus scroll clear of the sticky bar. I judged 96px from the CSS; I did not measure the bar's height on a device.
- Not checked with a real screen reader (the builder says the same). Role and focus are asserted in the tests.
