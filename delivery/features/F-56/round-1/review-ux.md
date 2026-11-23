VERDICT: PASS
COMMIT: abf2482a0bbc656b975f1f1afda722df6cdf7941
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux

## Summary
- No screen changes. The diff only deletes FactoryDesk, removes its branch in AppShell and narrows the proxy.
- On the dev server at port 3000, `/` and `/my-work` return 200 with the app's own frame. No `psl-work-client` is in the page.
- `/no-such-page`, `/static/x.js` and `/factory-assets/work-client.js` return our "Page not found" page, not Django JSON.
- `/accounts/login/` redirects (308) to a Next 404. This is the known and accepted gap (D-172, no sign-in page until wave 1).
- Limits: I used curl, not a browser session, so phone width, keyboard use and the signed-out render were not walked. The signed-out state is covered by the unchanged shell tests and `shell-no-embed.test.tsx`, and I did not re-run them.

## Findings
None.

## Verified
