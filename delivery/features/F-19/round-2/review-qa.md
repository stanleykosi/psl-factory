VERDICT: CHANGES
COMMIT: 41b4925c441959c3a4fc2b7eaf8437fa35791109
REVIEWER: qa
AUTHORITY: integrated QA

## Summary
- **What ran.** A production build (`next build`, `FRAME_FIXTURES=1`, `API_ORIGIN=http://127.0.0.1:4662`) served by `next start -p 4661` in the worktree, against the contract mock (`MOCK_PORT=4662 node mock/server.mjs`). A headless Chromium session (`f-19-qa`, timezone Africa/Lagos, reduced motion) drove the pages at 1440 and 390. Script: `/private/tmp/claude-501/f19-qa/qa.mjs`; output: `run2.log` and `shots/` in the same folder. There were 141 checks: 126 passed. All 15 failures are explained below; 6 of them are real (QA-2-1), and the others came from the frame or from my own checks. I also ran direct `curl` checks on the mock, and `npx vitest run tests/clients-mock.test.ts tests/clients.test.tsx tests/shell.test.tsx` (78 tests passed).
- **Proved end to end on the mock.**
  - List: six rows in the order returned; the missing-contact marker on Lagoon Health and Ojo Foods; Tamarind Loans shows 0 projects and "Not given"; Kora Logistics shows ₦0.00 as a real amount; unknown owed reads "Unknown amount not known", never 0. The count line reads "6 clients as of 14 Nov, 10:00 · 2 missing billing contact". The page sends no `limit`. Projects is `aria-current` in the top bar. Title sizes are 40px at 1440 and 26px at 390, and the phone back link is "Projects".
  - Paging (`many`): 20 rows load with "20 clients loaded" and no missing figure. "Show more" sends `cursor=o20`. When the second page fails, the loaded rows stay and "Try again" appears. After the retry there are 25 unique rows, the line reads "25 clients as of …" and the button is gone.
  - List states: empty list; 401 links to `next=/clients`; 403 and 404 both show the no-access page; 502 shows the error card, and "Try again" only reads.
  - Detail CL-3501: the banner comes from `blocked[]`, the project links to `/projects/P-0101`, and owed shows "Unknown". Save is enabled. A blank press, a name-only press and a whitespace-only press each send 0 PUTs, show the message beside the blank field and move focus to the first blank field.
  - Save request: a double press sends exactly 1 PUT. The body is exactly `{expected_revision:3,name,email}` and carries `x-csrftoken: mock-csrf-pm`. After the 200 there is exactly 1 detail GET, the banner and orange borders are gone, and "Billing contact saved." appears in `role=status`.
  - Save errors:
    - 422: the message sits beside the field, with `aria-invalid` and `aria-describedby`. The summary is `role=alert`, focus moves to the first invalid input, entries are kept and nothing reloads.
    - 409 (CL-3508): one reload, typed text kept, "Current: …" shown, nothing resent. The next press carries the reloaded revision and saves.
    - 403: one reload. When the reload says `can_change:false`, the page turns read-only and keeps the server message.
    - PUT without CSRF: the mock answers 403 and the page shows "Your session check failed…".
    - 401 on PUT: the signed-out callout.
    - Network failure or 502: "We couldn’t confirm…", 1 reload, 1 PUT, no resend. This holds even when the backend stored the save and the response was lost: the reload shows the stored values and the next press carries revision 4. If the reload also fails, Save goes away, the inputs become read-only and "Try again" only reads. If the save returns 200 but the reload fails, the page shows "Saved. We couldn’t refresh…" and Save stays off.
  - Other detail cases: read-only CL-3503 at both widths; CL-3507 shows the Sample tag and "Unknown"; CL-3509 has no banner, no money and shows "No projects yet."; CL-3599, a 403 on GET and an encoded odd id all show the no-access page, with one `h1`, a generic title and no name. axe found 0 violations on every state checked at both widths, and there is no sideways scroll.
- **What blocks.** Three outcomes of a save are not announced to screen readers: 409, 403 and "couldn’t confirm". Keyboard focus also drops to `<body>` after every press (QA-2-1, QA-2-2).
- **Not proved without a real backend.**
  - Everything above runs against the contract mock, and D-CLIENTS-VIEW is still proposed. Not tested:
    - real authority (`can_change`) and tenant scoping;
    - whether one person's save is visible to another (the mock stores each persona's saves separately, so cross-user visibility cannot be tested);
    - real CSRF and session handling;
    - real revision concurrency between two people;
    - how a real server behaves when it stores a write and then fails.
  - I injected the 403, 401 and 409 answers to the PUT as `X-Mock-Scenario` headers. I made the network failures and 5xx answers with Playwright `route` (abort, or fulfil after a real `route.fetch` to the mock). The `can_change:false` reload was the real mock reply with that one field changed.

## Findings
- QA-2-1 | blocking | medium | frontend | **Some save results are never announced (WCAG 2.1 AA 4.1.3 Status Messages; A-ACCESSIBILITY).**
  - **Which messages:** the notices after a save press: "This client changed while you were editing…" (409), the server message on a 403 (for example "Your role does not allow this." or "Your session check failed…"), "We couldn’t confirm the change was saved." and "Saved. We couldn’t refresh the page…".
  - **Where:** they render as plain `<p>` elements inside `div.clients__notice`, with no `role`, no `aria-live` and no live ancestor (`frontend/src/features/clients/BillingContactForm.tsx:239-247`).
  - **Seen in the browser:** the accessibility snapshot after a 409 shows the notice as a plain paragraph. Focus is on `BODY` (see QA-2-2). A screen-reader user who presses Save hears nothing and does not learn that the save failed or may not have happened. The live-region check failed for 409 at 1440 and 390, for 403, and for all three uncertain cases (`run2.log`).
  - **Expected:** these outcomes are announced: `role="alert"` for 409, 403 and uncertain; `role="status"` is acceptable for saved-but-unread. The F-12 precedent (`frontend/src/features/alerts/AlertSettingsPage.tsx:168-173`) uses `role="alert"` plus focus on the callout.
  - **Tests:** the e2e axe run cannot catch this. Add a component assertion for each notice.
- QA-2-2 | non-blocking | low | frontend | **Focus is lost after each save press.**
  - **Cause:** Save gets `disabled={busy}` while the request is in flight (`BillingContactForm.tsx:232`). Chromium drops focus from a disabled button, so after the press resolves `document.activeElement` is `BODY`. I saw this after a 409. After a 200 and after a 403 that turns the page read-only, focus also cannot return, because the button has been re-rendered or removed.
  - **Effect:** a keyboard user has to Tab again from the top of the page. On the 422 path this does not happen, because focus moves to the invalid input.
  - **Fix:** moving focus to the notice from QA-2-1 (`tabIndex={-1}`, as F-12 does), or using `aria-disabled` together with the existing ref guard instead of `disabled`, fixes both.
- QA-2-3 | non-blocking | low | integration | **With persona `none`, the clients no-access page never appears in a real browser.**
  - **What happens:** the frame stops first, because `/me` gives that persona no destinations, and shows "No sections are open to your role yet." with no `h1`. The same happens on `/projects`, so this is existing frame behaviour, not this feature's.
  - **What still holds:** AC 8 and AC 12 are met through the component stubs, and in the browser through a 403 or 404 on the clients calls for an allowed persona (one `h1`, generic title, no name, 0 axe violations).
  - **For the record:** the frame's no-sections page has no `h1`. That belongs to the frame owner, not F-19.

## Verified
- UI-1-1 | verified | In the browser at 1440 and 390, Save is enabled with the inputs empty. A blank press sends 0 PUTs, both messages appear and focus goes to `client-name`. A name-only press shows only the email message and focus goes to `client-email`. A whitespace-only email sends 0 PUTs.
- UI-1-2 | verified | Before the save, both inputs carry `clients__needed`. After a 200 the class is gone, because `billing_contact.set` is now true.
- UI-1-3 | verified | At 390 the `.clients__bar` computed position is `sticky` (`shots/detail-saved-390.png`).
- UI-1-4 | verified | At 390 the accessibility snapshot still exposes the region "Billing contact" with its level-2 heading, and the panel frame is not drawn on screen.
- UI-1-5 | verified | "Patient app" is a link to `/projects/P-0101` at both widths. I did not judge the colour; UI review did.
- UI-1-6 | verified | `[aria-current="page"]` is "Projects" on `/clients` and on `/clients/CL-3501` at 1440.
- UX-1-2 | verified | Same evidence as UI-1-1 and UI-1-2.
- UX-1-4 | verified | The name input's `aria-describedby` includes `client-name-help` (and also `client-name-error` when there is an error).

## Notes
- In the HTML, `CL-3599` and `CL-3501` appear only inside Next's flight data, as the route parameter from the URL the person typed. They never appear in visible text, the title or the phone bar. This discloses nothing.
- The mock answers `limit=7` with 404 `invalid_query`. That is consistent with v7, where E-CLIENTS declares no 422, and with the projects mock.
- Mock-only results are labelled as such above. No real provider or backend was involved.
- I started a mock on 4662 (PID 58690) and an app on 4661 (PID 58692) and stopped both by PID. The worktree `git status` is clean, and `frontend/test-results` does not exist. Disk had 5.2 GB free at the start and 5.1 GB at the end.
