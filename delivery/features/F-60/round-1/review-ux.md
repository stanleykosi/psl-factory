VERDICT: PASS
COMMIT: f2a1ebfd541d2a248f6e0ef7985b31b561ca7582
REVIEWER: reviewer-ux
AUTHORITY: UX reviewer

## Summary
- Read the diff and spec only (D-180 lighter panel); the app was not run, so phone width, keyboard order and screen-reader announcements were not walked in a browser.
- All the spec's states are in the code: loading, cannot-open with Try again, unavailable (one wording for every reason), form, field and page errors, done, and not-admitted.
- Copy, the "At least 12 characters" hint, the single automatic retry after a CSRF refusal, and the "try signing in" sentence after network or 5xx errors match the spec and the settled exceptions (D-182, D-185, D-187).
- Accessibility: focus moves to the heading in the done state and to the callout in the unavailable state; the email field is read-only, not disabled; the form posts as method="post" with preventDefault so passwords can't land in the URL.
- Token handling: the fragment is read once, cleared with replaceState, and sent only in the POST bodies; referrer is no-referrer and /staff/join is in PUBLIC_PATHS.

## Findings
None.

## Verified
None. Round 1.

## Notes
- Unconfirmed without a browser walk: phone width, keyboard order and screen-reader announcements.
