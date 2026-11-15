VERDICT: PASS
COMMIT: a4a906cadfbafced2c20f8535467cb32db06c3eb
REVIEWER: qa
AUTHORITY: integrated QA

## Re-confirmed on the synced head

Head a4a906ca differs from the earlier pass only by a merge of origin/dlv-00-delivery-setup (shared mock server conflict resolved; operations now include Clients and Templates). Ran `cd frontend && E2E_PORT=4661 MOCK_PORT=4662 npx playwright test e2e/clients.spec.ts --reporter=line`: 16 passed (desktop 1440 and phone 390: list, empty, Show more, signed-out/error, detail, 422, read-only, not-open). test-results deleted; ports 4661/4662 free. The earlier 140/140 result and its unproved items stand unchanged.

---
Earlier review (commit 95903eeb):

## Summary
- **Scope.** This is a re-check after the fix. I tested only what round 3 changed (diff 41b4925c..95903eeb: `BillingContactForm.tsx`, `clients.css` and the component tests), plus a quick smoke test of the normal save.
- **What ran.**
  - I built the production app at head 95903eeb with `FRAME_FIXTURES=1 API_ORIGIN=http://127.0.0.1:4662 npx next build`, which exited 0.
  - The app ran with `next start -p 4661` against the contract mock (`MOCK_PORT=4662 node mock/server.mjs`), both from the worktree `frontend/`.
  - A headless Chromium session (`f-19-qa`, timezone Africa/Lagos, reduced motion) drove `/clients/CL-3508` and `/clients/CL-3501` at 1440x900 and 390x844 as persona `pm`.
  - Save was pressed with the keyboard: Tab from the email field to Save, then Enter.
  - Script: `/private/tmp/claude-501/f19-qa/qa3.mjs`. Output: `run3.log` and `shots3/` in the same folder. Result: 140 checks, 140 passed.
  - I also ran `probe3.mjs` at 390x520 and 390x420 to test the Save-bar overlap on short phone screens.
- **How the failures were made.**
  - The 409 came from the mock's own stale client, CL-3508.
  - The 403 was injected as the `X-Mock-Scenario: 403` header on the PUT.
  - The network failure was a Playwright `route.abort('connectionreset')` on the PUT.
  - The 502 was tested twice: once returned instead of the PUT, and once returned after a real `route.fetch` had already stored the save on the mock.
  - "Saved, but the reload failed" was a 503 on the detail GET after a real 200 PUT.
  - "Unconfirmed, and the reload also failed" was an aborted PUT plus one aborted detail GET.
- **Proved (both widths, all six failure cases).**
  - Each notice is a `div.clients__notice` with `role="alert"` and the right text, and the accessibility tree shows exactly one alert holding that text.
  - `document.activeElement` is the notice after the press, not `body` or the top of the page, and the notice shows a solid focus outline.
  - The notice is inside the viewport.
  - Shift+Tab from the notice goes back to Save, or to the email field when Save is removed. Tab from the "unconfirmed, reload failed" notice reaches "Try again".
  - axe (WCAG 2.0, 2.1 and 2.2 A/AA) found 0 violations in every notice state.
  - Exactly 1 PUT was sent each time, with no automatic resend.
- **Not covered by the phone Save bar.**
  - At 390x844 the notice ends above the sticky Save bar (bar top y=762). Hit-testing the notice's middle and bottom returns the notice itself.
  - On shorter phone screens the scroll-margin keeps it clear: at 390x520 the notice spans y=378..419 and the bar starts at y=438; at 390x420 it spans y=283..324 and the bar starts at y=338.
  - In the two states where Save is removed (unconfirmed with reload failed, and saved but not refreshed), there is no bar to cover it.
- **No focus stealing.** After the 409 notice takes focus, clicking into the name field and typing keeps focus in the field. A second press then saves, shows the `role=status` message and sends 2 PUTs in total.
- **Smoke test, no regression (both widths).**
  - A blank press sends 0 PUTs, shows both field messages, moves focus to the name field and shows no alert notice.
  - A double press during a slowed PUT sends exactly 1 PUT.
  - The 200 shows "Billing contact saved." in `role=status`, not as an alert. The "no billing contact" banner is gone and focus does not fall to `body`.
- **Not proved.**
  - I did not use a real screen reader (VoiceOver or NVDA). Only the role, the accessibility tree and focus were checked in Chromium.
  - Everything ran against the contract mock, not a real backend.
  - The untouched paths from round 2 (list, paging, 401, 422, read-only, no access) were not re-run. Round 3 touched only the notice markup, its focus effect and one CSS rule, so those round 2 results stand. QA-2-3 (the frame's page for persona `none`) is unchanged and still belongs to the frame owner.
- **Housekeeping.**
  - I started the mock on port 4662 (PID 74699) and the app on port 4661 (npx PID 74701, server PID 74731), and stopped them by those PIDs. Both ports are free afterwards.
  - The worktree `git status` is clean and `frontend/test-results` does not exist.
  - Disk had 5.1 GB free at the start and 6.3 GB at the end.

## Verified
- QA-2-1 | verified | All four notice types are in `role="alert"` and are each exposed as one alert with their text, at 1440 and 390: the 409 "This client changed while you were editing…", the 403 server message "Your role does not allow this.", "We couldn't confirm the change was saved." (network abort, 502 before the save, 502 after the save, and with the reload failing too) and "Saved. We couldn't refresh the page; reload to see the latest.". The plain 200 confirmation stays `role=status`. On the phone the sticky Save bar does not cover any notice, at 844, 520 and 420 px tall.
- QA-2-2 | verified | After a keyboard press of Save, focus lands on the notice (a `tabIndex=-1` div with a visible outline), never on `body`. Shift+Tab returns to Save or the email field, and Tab reaches "Try again" where it is shown. Typing in a field afterwards does not pull focus back to the notice.

## Findings
none
