VERDICT: PASS
COMMIT: f6e9a9ecdc299700381927a13d66386138d83e5c
REVIEWER: reviewer-technical
AUTHORITY: reviewer-technical

## Summary
- The frame, client, mock and styles match the C1-C5 contract. The diff is confined to `frontend/`, with no protected or backend files touched.
- I read the client, errors, AppShell, states, TopNav, PhoneBar, mock and shell.css in full. No spec deviation is blocking.
- The error mapping, in-memory CSRF handling, 401 sign-in link and sample-label rule follow C3 and C5.
- The tests cover the criteria, including negative CSRF and scenario cases. I found no weakened or skipped test.
- I did not rerun the checks. `checks.md` shows GATE: PASS, and the hex and storage greps came back clean.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `frontend/mock/server.mjs` `parseCookies`: `decodeURIComponent` on a malformed cookie value such as `%` throws inside the `end` handler. That is an uncaught exception, and it kills the local mock process. Wrap it in a try/catch and keep the raw value.
- TECH-1-2 | non-blocking | low | frontend | `frontend/next.config.ts`: `API_ORIGIN` defaults to the mock (127.0.0.1:4010) in every build, including production. A forgotten variable silently points a deployed build at nothing, or at sample data. This is the spec's chosen seam, so it is acceptable. FE-CONNECT-1 should make a production build fail when `API_ORIGIN` is unset.
- TECH-1-3 | non-blocking | low | product | At 720-900px with five destinations, rule (f) squeezes the who-text to nothing. The name is invisible on the bar, though it stays in the phone menu and the DOM. The builder flagged this. It follows the spec letter, so the design owner needs to decide on wrap or a shorter line.
- TECH-1-4 | non-blocking | low | frontend | Declared deviations are minor and reasoned: the `Archivo` `@font-face` alias, the extra shell.css rules and the inline `marginLeft/flex` style on the TopNav wrapper (the inline style could move into shell.css). The same-name font alias is a drift risk if the fontsource files are renamed.
- TECH-1-5 | non-blocking | low | frontend | `frontend/package.json` `engines` says `>=24`, but jsdom 31.0.1 needs Node >=24.15. Local Node 24.12 produces EBADENGINE warnings. Raise `engines` or pin jsdom to a version that fits.

## Verified
