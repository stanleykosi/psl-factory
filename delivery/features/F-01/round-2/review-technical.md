VERDICT: PASS
COMMIT: 96aa11efcea1cc7c596159d1b1e72aa79f2fca40
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- The round-2 diff (f6e9a9e..96aa11e) is confined to `frontend/`: top bar CSS, the error card, a not-found page, the mock cookie fix and `allowedDevOrigins`.
- The role stays in the DOM and the accessible name (visually hidden, not removed), as the design decision requires.
- Each fix has a test: the malformed-cookie case, error card structure for 404, 500 and network, the not-found page, and bar width tests.
- The two items the builder left open (TECH-1-2, TECH-1-5) were non-blocking and the reasons stand.
- I did not rerun the checks. `checks.md` shows GATE: PASS on this head.

## Findings
- TECH-2-1 | non-blocking | low | frontend | `frontend/src/shell/DestinationPage.tsx` `UnknownPage`: `visibleDestinations(...)[0]` assumes at least one visible destination. A persona with none would throw on `first.href`. The current mock personas all have destinations, so this is only a guard for FE-CONNECT-1.
- TECH-2-2 | non-blocking | low | frontend | `frontend/next.config.ts`: `allowedDevOrigins: ['127.0.0.1']` is dev only and harmless. Carry TECH-1-2 (fail closed on a missing `API_ORIGIN` in production) and TECH-1-5 (jsdom needs Node >=24.15 while `engines` says `>=24`) into FE-CONNECT-1 or the Node upgrade.

## Verified
- TECH-1-1 | verified | `decodeCookie` in `frontend/mock/server.mjs` catches the throw and keeps the raw value. The test in `frontend/tests/mock-contract.test.ts` covers it.
- TECH-1-3 | verified | Resolved by the design owner's decision: name only from 720px to 1079px. Rule (f) in `shell.css` hides the role visually and keeps it for screen readers.
- TECH-1-4 | verified | The inline style is now the `.shell-navend` class in `shell.css`.
- TECH-1-2 | verified | Left as is, accepted. The spec chose this seam.
- TECH-1-5 | verified | Left as is, accepted. Node upgrade is the clean fix.
