VERDICT: PASS
COMMIT: 0758d3e3f8568c084ed88b1c37a05f0641d62510
REVIEWER: reviewer-qa
AUTHORITY: integrated QA reviewer

## Summary
- Tested on the shared production build http://localhost:4611, served from the f-05 worktree. Its `.next/BUILD_ID` is dated 16:47, after the head commit at 16:27, and the served chunks contain the `startsWith("//")` fix. The build talks to the contract mock on :4612. In a headless browser, 21 of 21 journeys passed: 19 at 1440 and 2 at 390. I also made 14 direct API calls through :4611. I reset the mock before and after every journey that changed data, and reset it again at the end (204).
- Success path: pm opens the invoice drawer with the main button, picks Lagoon and Milestone 3, adds a note and presses "Start the invoice". The browser lands on `/work/W-1401` and the page shows its title. There was exactly one POST. It carried `X-CSRFToken: mock-csrf-pm` and the five keys. The ceo's main button opens "Choose a line" with 8 lines. On the phone, "+ Start" opens a bottom sheet 390 px wide with no sideways scroll. The phone path reaches W-1401 the same way.
- Failure paths all behaved as the spec requires:
  - 422: the missing milestone shows inline (`aria-invalid`, focus on the callout). The Harmattan billing-contact problem shows in its own box. The next press uses a new key.
  - 409: the typed values are kept, the revision is re-read with `q=<label>`, nothing is resent automatically, and the next press uses a new key.
  - 403: values are kept and the drawer stays open.
  - 500 and network loss: the fields lock, nothing is resent in 3 s, and "Check again" resends the same key and body. That retry gets the stored 201, so nothing starts twice. In the network-loss case the mock had already recorded the start.
  - 401: on submit and on the chooser, the drawer shows the signed-out state with `next=%2Fmy-work`.
  - Persona with no lines: no Start control at all.
  - The double press sent one POST.
- Journey links: I fed `journey_url` into the live E-LINES response. These values produce no link: `/.//evil.example`, `//evil.example`, `/%2e//evil.example`, `https://evil.example/x`, `javascript:alert(1)` and `http://localhost:4611//evil.example`. `/projects?x=1#h` is linked as-is.
- Not proven here:
  - All of this runs against the contract mock, not the real backend, which does not exist yet (T-START, FE-CONNECT-1). Server-side duplicate detection after the user leaves an uncertain drawer (PMO-0-2) is still unproven.
  - The 500 and network-loss faults were injected in the browser (`page.route`), not by the server.
  - The 401, 403 and 409 answers came from the mock's scenario cookie, so in the 409 case the "reloaded" revision is the same value.
  - I did not re-test the other 7 lines' intakes or run axe, because unit tests, e2e tests and the UX review already cover them.

## Findings
None.

## Verified
- SEC-3-1 / TECH-3-1 | verified | Browser J10: with `journey_url` set to `/.//evil.example`, `/%2e//evil.example` or `http://localhost:4611//evil.example` in the live E-LINES answer, the invoice drawer draws "What happens next" with no "See the full…" link, and there is no `a[href*=evil]`. The control value `/projects?x=1#h` is linked with exactly that href (qa-evidence/browser-journeys.txt).
- TECH-2-1 | verified | `//evil.example`, `https://evil.example/x` and `javascript:alert(1)` are also refused in the built page (J10).
- TECH-2-2 | verified | J4: after the Harmattan 422, switching to Lagoon and Milestone 3 lets start be pressed again. It sends a new key and lands on W-1401.
- TECH-2-4 | verified (partly) | J4 shows the unmatched `billing_contact` problem as its own box ("Billing contact — The client register has no billing contact…"). I did not drive the proof-plus-duplicate case in the browser, because the mock does not produce it. The component test covers it.
- UI-2-1, UI-2-3 | not re-tested | Visual only; the UI and UX reviews verified both at this head.

## Notes
- Evidence is in `delivery/features/F-05/round-3/qa-evidence/`:
  - `api-journeys.txt`: the exact curl commands and their answers. A 201 replay with the same key returns the identical body. The same key with a different body gives 409 `idempotency_key_reused`. Revision 5 gives 409 `stale_revision`. finance_lead starting weekly_report gives 403 `forbidden`. Another persona's CSRF token, or no token, gives 403 `csrf_failed`. An extra property gives 422 naming `evil`. A missing milestone gives 422. pm sending Kora's case gives 404. The `none` persona gets 404 for options and an empty E-LINES list. The 401 scenario on E-LINES gives 401.
  - `browser-journeys.txt`: the per-journey results.
  - `qa.spec.ts.txt`: the scratch spec I ran.
  - 5 screenshots: W-1401 landing, 422, 409, uncertain, and the phone sheet.
- Spec criterion 3 says pm's direct open shows no "change line". The build shows "Line chosen from the Start work menu · change line" every time, from 720px up. Round 2 changed this on purpose to match the SCR-04 boards (round-2 build.md, UI-1-5), and the UI and UX reviews accepted it. The spec text is now out of date; this is not a defect.
- The callout reads "1 thing to fix before Chidi can start." (singular), where the spec text says "1 things". Round 2 accepted this wording.
- I started or stopped no servers, did not build or copy `frontend/`, and did not run `npm ci`. The worktree is clean. I deleted the scratch files.
