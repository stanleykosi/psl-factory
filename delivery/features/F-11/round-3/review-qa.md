VERDICT: PASS
COMMIT: 604e1b0a0f8fb3ac2cee49124f70370b1343e6de
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (UI-only feature: shared next build on 4111 against the contract mock on 4112)

## Summary
- I tested the shared production build at http://localhost:4111. It is next-server with cwd `f-11/frontend`, and its BUILD_ID was written at 09:07, after the head commit at 08:56. The contract mock ran at http://127.0.0.1:4112. I reset the mock (204) before and after every journey that changed data. All 17 tests in `e2e/setup.spec.ts` pass against this build, including both QA-1-1 regression tests.
- What round 3 changed holds up in the browser at 390:
  - **Phone bar:** "← Setup" (named "Back to Setup", linking to /setup/roles) sits in the frame bar, with no Menu and no Setup link inside the page. RULES appears only on Finance and Delivery. Following the link reaches /setup/roles, where Menu returns and the note is gone.
  - **After a withdrawn right:** one focused alert, the panel closes and no Save button remains (tested as admin and finance_lead).
  - **After Show more:** when Show more brings back an editable rule, the panel returns and the stale "panel has closed" text is gone.
  - **After a 500 then a read-only re-read:** the alert has the uncertain-result text plus the panel-closed text and never "Nothing you entered was saved". This holds on Rules and Finance, whether or not the PUT reached the mock.
- The negative cases still behave as specified:
  - **API:** 403 for the pm and none personas, the forbidden scenario, the readonly scenario, a non-editable row, a missing or another persona's CSRF token, and pm uploads. 404 for an unknown component and an unknown case. 409 for a stale revision, a replayed save and a replayed upload. 422 for a bad revision, a role outside the options and missing upload fields.
  - **Browser:** a network failure, a routed 404, a routed 500, the stale cookie (409) and the invalid cookie (422) each send exactly one PUT even on a double click.
  - **Read-only on phones:** the readonly persona and phones stay read-only, with no writes and no reachable desktop controls.
- Still unproved: there is no real backend. T-SETUP, `proof_case`, `cursor` and `expected_revision` minimum 0 are proposals that only the mock implements. Tenancy is not tested, because the mock has no tenants (isolation per persona was checked instead). There is no real evidence store and no live CSRF/session (mock tokens only). The Show more journey needed list responses altered in the browser, because the mock's `many` scenario has no editable row on a later page.

## Findings
- QA-3-1 | non-blocking | low | frontend | Focus drops to `body` when the last Show more is activated by keyboard. Repro: admin, `psl_mock_setup=many`, 1440, `/setup/rules`. Focus "Show more" and press Enter. Expected: focus moves to a sensible place, such as the first new row or the table. Actual: 55 rows render, the button unmounts, `document.activeElement` is BODY, and the next Tab starts again at the top of the page. The same thing happens in the QA-1-1 Show more path, where the panel returns but focus is on body. This was not introduced in round 3 (the paging code is unchanged), and AC 19 does not specify focus. Path: frontend/src/features/setup/SetupFrame.tsx (Show more / the paging footer).

## Verified
- QA-1-1 | verified | e2e "right withdrawn after load…" and "finance: a group losing its only editable rule…" pass on 4111. Separately, as finance_lead on /setup/rules, a mid-edit `psl_mock_setup=readonly` made the Save return 403 and the requests were GET, PUT, GET. The only main alert reads "Your role does not allow this. You can no longer change these rules, so the Set a rule panel has closed. Nothing you entered was saved." Focus is on that alert and there are 0 Save buttons.
- QA-1-2 | verified | `POST /__mock/reset` followed by an upload to `/cases/C-SETUP-1/evidence` answered `EV-1` on two consecutive reset-then-upload runs. The sha256 equals `shasum -a 256` of "hello".
- FID-2-1 | verified (QA lens) | The phone bar link and note were confirmed live at 390 for admin with mobile data, admin with desktop data and finance_lead with readonly data (see Evidence A). The second Tab lands on "Back to Setup". The UI review owns visual fidelity.
- TECH-2-1 | verified (QA lens) | See Evidence D. After Show more there is no alert, the "panel has closed" text is gone, the panel is back with "QA extra editable rule" in the picker, and there is 1 Save button.
- SEC-2-1 | verified (QA lens) | See Evidence C and C2. With a 500 and a read-only re-read, `hasEditorGone` is true and `hasNotSaved` is false on Rules (admin) and Finance (finance_lead), and also when the PUT really saved (200 at the mock) before the routed 500.

## Evidence
Setup: nothing was started or stopped. I used Playwright from `f-11/frontend/node_modules` with a scratchpad config (baseURL 4111, no webServer, outputDir in the scratchpad). The scratch scripts are deleted and the worktree is clean. The kept evidence is in `round-3/qa-evidence/`: `journeys.log` (one line per browser check), `phone-finance-bar-390.png` (the bar with "← Setup" and RULES) and `rules-after-show-more-1440.png`.

**E2E**
- `cd frontend && MOCK_PORT=4112 npx playwright test --config <scratchpad>/pw.config.mjs` (testMatch `setup.spec.ts`): 17 passed in 31.3s. Coverage:
  - AC 1, 2, 5, 8, 10, 11, 14, 16-21 and 24;
  - QA-1-1 on Rules and Finance;
  - the phone bar check for AC 18;
  - axe at 1440 and 390.

**API (curl through `http://localhost:4111/api/v1`)**
- GET `/setup/rules`:
  - admin and finance_lead 200; pm and none 403;
  - admin: 10 items, `not_set_count` 8, `roles_missing_count` 2;
  - the forbidden scenario: 403.
- PUT `presale.rfp_assigner`:
  - no CSRF and the finance_lead token sent as admin: 403 `csrf_failed`;
  - pm, the readonly scenario and `finance.short_payments`: 403 forbidden;
  - `nope.x`: 404;
  - `expected_revision` -1: 422 "expected_revision". Role `admin`: 422 "value.roles";
  - `expected_revision` 1: 409;
  - a valid save: 200 rev 1, and the replay is 409. The GET then shows rev 1 "PMO Lead" with count 7, while finance_lead still sees rev 0 and count 8.
- POST evidence:
  - 200 `EV-1` after reset, and the replay is 409;
  - no CSRF: 403 `csrf_failed`. pm: 403;
  - C-NOPE: 404. Missing fields: 422 naming `filename`, `content_base64` and `case_revision`.

**Browser journeys (headless chromium)**
- A, phone at 390, for admin+mobile, admin+desktop and finance_lead+readonly:
  - each view has the bar link `{text "← Setup", label "Back to Setup", href "/setup/roles"}`, menu 0 and 0 Setup links in the page;
  - the note is null on Rules and "RULES" on Finance and Delivery;
  - the h1 is "Rules · 6 not set" (mobile data) or "Rules · 8 not set" (desktop data);
  - there are 0 visible controls in `main`, `scrollWidth` is 390 and no write requests are sent;
  - 40 Tabs never focus inside `.setup-desktop`;
  - following the back link reaches /setup/roles, with the note null and Menu back;
  - pm on the phone gets "This section isn’t open to your role." with Menu, no back link and 0 setup calls.
- B, a withdrawn right as finance_lead on Rules: see QA-1-1 above.
- C, a routed 500 on PUT with the cookie switched to readonly before Save (admin on Rules, and finance_lead on Finance with "Set BU totals rules" open): one alert with focus reads "We couldn’t confirm the save. Nothing new is shown for this rule, so you can save again. You can no longer change these rules, so the Set a rule panel has closed." There are 0 Save buttons and the requests were GET, PUT, GET.
- C2, the PUT forwarded to the mock with desktop cookies (200, saved) and then answered 500, with the re-read read-only: the same text, and no "Nothing you entered was saved". The readonly scenario data does not reflect the desktop save, so "Nothing new is shown" is consistent with what was re-read.
- D, Show more:
  - after the 403 closed the panel, the first-page re-read was given a `next_cursor`, and the cursor page returned one editable row;
  - after Show more there are no alerts, the stale callout is gone, the picker reads ["QA extra editable rule"] and there is 1 Save button;
  - requests: GET, GET, PUT, GET, GET `?cursor=o%3Aqa`.
- E, save failures with editable data, each from a double click on Save:
  - abort (network failure): one PUT, then a re-read. The text is "We couldn’t confirm the save… you can save again.", the Why is kept and focus is on the alert;
  - 404: "We could not find that record.", focus on the alert, the Why kept, one PUT and one re-read;
  - 500: the same as abort;
  - the stale cookie (409): the stale message has focus and the Why is cleared;
  - the invalid cookie (422): "Check these fields: reason, starts." and the Why is kept. Starts and Why have `aria-invalid`, and there was no re-read.

## Notes
- After 40 Tabs at 390 focus wraps to "Skip to main content". While focused, that link overlays the bar's back link and intercepts a pointer click. This is normal skip-link behaviour in the shared frame and does not belong to F-11, so it is not raised as a finding.
- TECH-3-1 (a stale `closedNotice` that is hidden, not cleared) was not reproducible through a normal path. In journey D the callout did not reappear.
