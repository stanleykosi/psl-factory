STATUS: READY
COMMIT: 831b17164ca8b1200e9ff84d2d486ea0d7dc7dc5
BUILDER: builder
LANE: full

## Summary
- New `/notifications` (SCR-15): the person's own alerts with avatar, text, meta line ("Chidi · WhatsApp and email · 10:42"), NEW while unread, search, Filter (agent, unread), "N ALERTS", Show more. Opening an unread alert POSTs mark-read (CSRF) and then goes to `/work/<work_id>` whether the POST worked or not.
- New `/settings/alerts` ("How you're alerted"): a WhatsApp/email switch matrix per returned event, digest and quiet-hours selects, the masked number card, and "Save settings" (CSRF, revisioned PUT). 409 re-reads and drops edits, 422 shows the message, 401 shows signed out. The phone has event cards, a quiet-hours line and a pinned Save.
- Proposal fields are never defaulted. With `bare` there is no search, Filter, count or unread text, and settings shows the error card.
- Contract mock: `mock/alerts.mjs`, a verbatim v7 overlay, and board-shaped fixtures for board, phone, empty, many, bare, stale, invalid and locked. `server.mjs` gets the listed 7-item seam. Nothing is sent anywhere.
- All four SCR-15 boards pass the fidelity gate after the requested exceptions: desktop 97.8, phone 92.9, desktop settings 96.4, phone settings 97.6.

## Changes
- `frontend/src/app/notifications/page.tsx`, `frontend/src/app/settings/alerts/page.tsx`: thin pages with static titles ("Notifications · PSL Factory", "Alert settings · PSL Factory").
- `frontend/src/features/alerts/`
  - `contract-proposal.ts`: the `openapi-typescript mock/proposals/alerts.json` output between BEGIN/END markers, plus aliases. Removed at the rebase.
  - `api.ts`: `alertsApi = api as unknown as Client<AlertPaths>`, which reuses the shared client and its CSRF middleware. Removed at the rebase.
  - `model.ts`: agent name and image, meta line, count line, URL view parse/build, query builder (q/agent/unread/cursor only, never limit), draft, and the PUT body builder.
  - `NotificationsPage.tsx`, `AlertsFilterPanel.tsx` (CMP-22 on the my-work pattern), `AlertSettingsPage.tsx`, `AlertSwitch.tsx` (native `button role="switch"`), `useIsPhone.ts`, `alerts.css` (tokens and `color-mix` only; the unread tint is `color-mix(in srgb, var(--signal-tint) 40%, var(--surface))`).
- `frontend/mock/alerts.mjs`: `createAlertsMock({ overlay })`, `ALERT_OPERATIONS` and `ALERT_SCENARIOS`. Scenario comes from cookie `psl_mock_alerts`, else env `MOCK_ALERTS_SCENARIO`, else `board`. State is kept per persona:scenario, and dates are shifted so that `as_of` falls on today in Lagos. The rules are as in the spec.
  - `bare` drops proposal fields, ignores q/agent/unread (as a v4 backend would) and answers 404 to the two v7-only operations.
  - Other personas (pm, none) always serve their own records. Scenarios other than `empty` and `bare` shape finance_lead's data only.
- `frontend/mock/proposals/alerts.json`: the three v7 path items, verbatim, plus v7 `components` (security schemes only).
- Fixtures:
  - `mock/fixtures/E-NOTIFICATIONS.json`, `E-NOTIFICATION-READ.json`, `E-ALERT-PREFS-READ.json`, `E-ALERT-PREFS.json`: the board bodies.
  - `mock/fixtures/alerts/`: notifications for pm, none, many and empty; prefs for pm, none, phone, locked and invalid.
- `frontend/mock/server.mjs` seam (the whole edit):
  1. one header comment line;
  2. `import { ALERT_OPERATIONS, createAlertsMock } from './alerts.mjs';` and `const overlay = …proposals/alerts.json`;
  3. `routes.push(...loadRoutes(overlay).filter(…method/template the openapi lacks))`;
  4. the four ids appended to `M1_OPERATIONS`;
  5. `const alerts = createAlertsMock({ overlay });`;
  6. `alerts.reset();` in `/__mock/reset`;
  7. the one dispatch line after the CSRF check.
- `frontend/tests/mock-contract.test.ts`, edits (a) to (c) only:
  - (a) overlay path items listed before the v4 ones, so `byId` takes the four alert operations from the overlay;
  - (b) `BODY['E-ALERT-PREFS']`;
  - (c) `NOTIFICATION_IDS` per persona for `notification_id`.
- New tests: `tests/alerts-model.test.ts`, `tests/alerts.test.tsx`, `tests/alerts-settings.test.tsx`, `tests/alerts-mock.test.ts`, `e2e/alerts.spec.ts`.
- Not touched: `src/shell/**`, `src/api/**`, `src/styles/**`, `package.json`, the lockfile, playwright and vitest configs, `architecture/**`, `design/**`, `public/**` and the protected delivery files. `git diff --stat 92d029b..HEAD -- frontend/src/api frontend/package.json frontend/tests/api-schema-drift.test.ts frontend/src/shell` is empty.
- Factory files: `round-1/fidelity/` holds the four reports, `results.txt` and `exception-requests.json`.

**Deviation needing the design engineer (E-4):** the phone back links "← Home" and "← Notifications" sit at the right, level with the heading, not on their own line under the frame bar.
- On their own line they pushed every row down, and SCR-15-mobile scored visual 76.2.
- This follows the D-19 precedent (F-10) until the frame gets its back-link slot (D-13).
- The fidelity tool reports them as moved, not missing.

**For the backend developer (PMO-0-4, engineering proposals):**
- (a) `channel` and `frequency` go back exactly as read, and a non-enum value gets the API's 422 (shown verbatim).
- (b) `expected_revision` is the read `revision`, and is omitted when none was read.
- (c) The PUT sends only `events[].{key, whatsapp, email}` (every event, in order, locked ones as read), plus `digest_at`/`quiet_hours` from the returned options, on desktop only.
- (d) Mark-read runs before navigation. A failure still navigates, NEW stays, and nothing retries.
- (e) The masked number is shown byte-for-byte and never sent.
- Mock assumptions: `total` is the filtered count, and `unread_count` is all of the person's unread alerts.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Overlay verbatim v7: `alerts-mock.test.ts` deep-equals the three path items against v7, validates every fixture against the overlay 200, and validates the proposal-stripped bodies and the UI-built PUT bodies against v4. Negative run: appending " (edited)" to the overlay's `/api/v1/notifications` get description made "the three path items deep-equal …" fail. The file was restored, and the test passes again.
2. [x] Local types match: the same file regenerates the types into a temp dir and compares them with the BEGIN/END block. The F-13 files' diff is empty (above).
3. [x] Generic mock test: `npx vitest run tests/mock-contract.test.ts` passes (84 tests), including "E-NOTIFICATIONS / E-NOTIFICATION-READ / E-ALERT-PREFS-READ / E-ALERT-PREFS succeeds for persona …" for all three personas and every declared error status. The diffs are limited to edits (a) to (c) and seam items 1 to 7.
4. [x] Own records: pm's list is N-0101/N-0102 only. pm marking N-0001/N-0002 answers 404, and finance_lead's rows are unchanged. pm's number is "+234 805 *** 1180" and never contains 4412. The grep finds no person or user_id request parameter (only comments and the `psl-tag--person` class).
5. [x] CSRF: the mock answers 403 csrf_failed with no token or another persona's token, on both writes. The UI tests see `X-CSRFToken: mock-csrf-finance_lead` on the POST and the PUT.
6. [x] List at 1440: `alerts.test.tsx` and e2e check the order, texts, the four `/agents/*.png` images (loaded), and that only row 1 has the tint and weight 600. Screenshot `alerts-list-1440.png`.
7. [x] List at 390: e2e checks "← Home", search, the 44×44 Filter icon button, the rows, then "Alert settings", with no eyebrow, no count line and no horizontal scroll. The back link placement is E-4 (above).
8. [x] Meta rules: `alerts-model.test.ts` covers every listed case, plus Lagos-day edges.
9. [x] Bare: e2e "bare" covers the list (agent · time, no search, Filter, count or unread), open → `/work/W-1001`, NEW kept on return, and the settings error card with Reference not_found and no table or Save. The unit test covers a 200 with no events (missing_events) and dropping URL filters when `total` is absent.
10. [x] Search/Filter: e2e covers payroll → 1 ALERT and `q=payroll`; Chidi → 2 rows and "Filter · 1"; the "1 unread" hint → 1 NEW row; no match → "Clear search and filters" → 4 rows; the phone bottom sheet; and that requests carry only q/agent/unread/cursor.
11. [x] Opening: e2e sees one POST with the CSRF token → `/work/W-1001`. Back shows no NEW and "0 unread". Row 4 sends no POST → W-1006. Row 3 → W-1099 shows the no-access state and no payroll text. Unit tests cover a 500 or network failure: navigation still happens, one POST, NEW stays.
12. [x] States (unit and e2e): empty ("No alerts yet.", "0 ALERTS"), loading, a 404 card with Try again, "Last loaded HH:MM." after a network abort, and many/Show more including the failure callout.
13. [x] 401: list `next=%2Fnotifications` (with `%3Fq%3Dpay` when searched), settings read and save `next=%2Fsettings%2Falerts`. Covered by unit tests and e2e via `page.route`.
14. [x] Settings at 1440: unit and e2e check the whole board (matrix values, selects, number card, Save).
15. [x] Switches: `role="switch"`, `aria-checked` and the names. e2e Space toggles "Email, Work I started is stuck". Locked switches are aria-disabled, don't change on click or Space, and are sent as read.
16. [x] Save body: deep-equal in the unit test and e2e (`expected_revision: 3`, five events, `digest_at` "09:00", `quiet_hours` "20-07-weekends"). "Your alert settings are saved." shows. The reload shows the saved values. The second save sends 4.
17. [x] Stale: e2e and unit check the callout text, its focus, decision WhatsApp back on, "Email, Work I started is stuck" off, and the next save with 4.
18. [x] Invalid: `channel: "sms"` is sent, and "We couldn't save your settings. Check these fields: channel." shows, focused. The edits stay.
19. [x] Save failures (unit): 500 and network keep the edits, show the reference and send no further PUT. A double press while saving sends one PUT.
20. [x] Phone settings (e2e cookie `psl_mock_alerts=phone`, at path `/`): four cards, "Daily digest", the quiet-hours line, the pinned footer Save; no digest select and no number. Board shows a fifth card. The phone body has no `digest_at`/`quiet_hours`. No horizontal scroll.
21. [x] Masked number: every PUT body in the unit tests is free of 4412, masked, label, timing and note. `masked_number` is read in one place only (`AlertSettingsPage.tsx:211`).
22. [x] Direct loads render both headings and titles (e2e). Signed-out `next` is covered by the existing frame case (no frame edit).
23. [x] Accessibility: axe (wcag2a/2aa/21a/21aa/22aa) is clean on:
    - the list default, the Filter open, empty and error, at both widths;
    - the settings default, saved, stale and invalid, at 1440 and 390.
    Tab order and focus rings (row, switch, select, Save) are checked, as are 44px phone targets and reduced motion during loading.
24. [x] Fidelity (production `next start` on 4201, mock on 4202 after `/__mock/reset`, `--exceptions round-1/fidelity/exception-requests.json --wait-ms 800`):
    - SCR-15-desktop 1440: PASS, 100% with exceptions, visual 97.8.
    - SCR-15-mobile 390: PASS, 100%, visual 92.9.
    - SCR-15-desktop-settings 1440: PASS, 100% with exceptions, visual 96.4.
    - SCR-15-mobile-settings 390 (mock started with `MOCK_ALERTS_SCENARIO=phone`): PASS, 100% with exceptions, visual 97.6.
    The requests are E-2 (Start work, More ways to start: frame) and a new E-6: the phone words "WhatsApp"/"Email" beside each switch are aria-hidden as the spec requires, so the tool cannot read them. E-1, E-3, E-4 and E-5 are recorded in the same file. Only the design engineer can approve them.
25. [x] Suite and build: `delivery/checks.sh` exits 0, and the diff lists only Lanes paths plus `src/features/alerts/useIsPhone.ts` (inside `features/alerts/**`).

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-12 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` → exit 0. Django check is clean; lint, typecheck and `vitest` pass (17 files, 414 tests); `next build` lists `/notifications` and `/settings/alerts`.
- `cd frontend && E2E_PORT=4201 MOCK_PORT=4202 npm run test:e2e` → 110 passed, including 27 in `e2e/alerts.spec.ts`.
- The fidelity runs above. Reports are in `delivery/features/F-12/round-1/fidelity/<board>-<width>/`, with a summary in `results.txt`.
- The servers I started on 4201/4202 were stopped, and `frontend/test-results` was deleted.
- Everything ran against the contract mock (sample data). No WhatsApp or email provider was contacted, and there is no real backend for these operations yet (T-ALERTS).

## Blocked
