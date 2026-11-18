VERDICT: PASS
REVIEWER: qa
COMMIT: 2e9e42e3313d5a5318aa01fc8b585c2d47c5bcb4
AUTHORITY: delivery integrated QA

## Summary
- I ran the real frontend as a production build (`API_ORIGIN=http://127.0.0.1:4974 FRAME_FIXTURES=1 npm run build && npx next start -p 4975`) against the contract mock (`MOCK_PORT=4974 node mock/server.mjs`). The browser session was F-41-qa (Playwright Chromium, `Africa/Lagos`), signed in as `finance_lead` unless a step names another persona. The script and its output are in `/private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/qa-f41/` (`qa.cjs`, `results.json`, `e2e.log`).
- Every journey the brief names passed at 1440 and at 390:
  - the money list: amounts are shown exactly as returned, nothing is computed, and Unknown never shows as 0;
  - search, filters and paging;
  - the W-3801 reminder: Edit, then "Save draft", then Send;
  - the uncertain send, with the lock and reconcile;
  - 409, 422, 5xx and network failures;
  - personas who cannot act, and 401/403/404;
  - 44px targets, no sideways scroll, and axe.
- No blocking finding. The four fixes in this round (UI-2-1, UI-2-2, UX-2-1, UX-2-3) reproduce as fixed on the live build.
- The shared change from round 2 shows the "Done" notice only after the re-read. The other lines still work: W-2209, W-2411, W-2603, W-2901, W-2502 and W-2702 render, and their e2e suites pass.
- e2e: 13 spec files, **307 passed (14.9 min)** on `E2E_PORT=4976 MOCK_PORT=4977`. Targeted vitest: 17 files, **822 passed** (584 + 238).
- **Not proved:**
  - Every result here comes from the contract mock. No real email provider was used, no real receipts and no real backend. So none of the following is proved: per-recipient delivery from a provider, the backend refusing a second send while delivery is uncertain, the backend's idempotency, or draft versioning. All of these are BACKEND-HANDOFF priority 1.
  - The browser has no request timeout, so the 60-second timeout case cannot happen in the browser. The hang was probed: it is TECH-1-2's recorded deviation, and a reload during the hang re-enables Send unless the backend marks the item uncertain.
  - All the policy items listed as held in the spec stay held: recording a payment, short payments, the reminder interval, and who may send.
  - Fidelity was not re-run; I relied on the UI reviewer's reading.
  - The SAMPLE DATA tag is hidden on every screen by the 14 Nov design decision (`NEXT_PUBLIC_SHOW_SAMPLE_LABEL`), so AC10 was checked only by its absence.

## Journeys
Unless a line says otherwise, each line below was run at both 1440 and 390. "POST" means a request the browser sent, recorded by `page.on('request')`. "log" means `GET http://127.0.0.1:4974/__mock/workspace-log`. Before each journey I ran `POST /__mock/reset` (204).

### Payments list (`/finance/payments`)
- **Board, `?status=issued`.** The page text contains every fixture string:
  - all 4 references and clients;
  - ₦3,000,000.00, ₦2,500,000.00, ₦500,000.00, ₦6,800,000.00, ₦0.00, ₦4,100,000.00 and ₦2,200,000.00;
  - the states PART PAID, OVERDUE, BANK DATA MISSING and PAID;
  - overdue by 9, 21 and 6 days, and "—" for INV-0388;
  - "4 INVOICES" and "Updated 12 Nov 10:00";
  - in the strip: "₦7,300,000.00 + Unknown", ₦6,800,000.00, ₦4,700,000.00 and "10 Nov";
  - the coverage sentence and Chidi's three lines.

  Rows come in the returned order. INV-0402 RECEIVED and STILL OWED each read "Unknown amount not known", never 0, blank or a dash. The known zeros for INV-0391 RECEIVED and INV-0388 OWED read ₦0.00. There is no "7.3M", no "Record a payment", and no settled, written off, cleared or balance wording. The page sends one GET with `status=issued` and no POST.
- **Phone, 390.** There are 4 cards. Card 1 reads "INV-0398 · overdue 9 days". The PAID card has no overdue words. Every control is at least 44px. "Open the reminder draft" measures 151.6×44.0 and links to `/work/W-3801`.
- **Nothing computed.** I changed the live mock reply in the browser with `page.route`, one change per run:
  - INV-0398 `received` set to 2,600,000.00: STILL OWED stays ₦500,000.00 and the strip is unchanged.
  - `due.date` changed: overdue by stays "9 days".
  - `total` removed: no count is shown.
  - `owed.amount` set to "500000.10": the page shows ₦500,000.10 exactly.
  - `owed.has_unknown` set to false: "+ Unknown" goes away.
  - `owed.known` set to 1.00: only the OWED cell changes.
  - The PAID row's amounts changed: it still reads PAID.
  - `status` removed: the row reads "Unknown".
  - `agent_note` removed: there is no note and nothing stands in its place.
  - `work_id` removed: there is no link.
- **Variants.**
  - `unknown`: no ₦0.00 and no empty cell (17 "Unknown" at 1440, 13 at 390).
  - `empty`: "No invoices to show yet." and the strip reads Unknown, with no invented figures.
  - `contract`: the strip reads Unknown, there is no coverage sentence, and WORK reads "client · project title".
  - `error`: the problem card shows no client or amount, and Try again sends exactly one more read.
  - `paged`: Show more sends `cursor=o2`, the list goes from 2 to 4 rows, and focus lands on INV-0402.
- **Search, two-character rule.**
  - "H": no read after 900 ms, and Enter on "H" sends no read.
  - "Ha": one read with `q=Ha`.
  - "Harm": the server returns one row and the URL becomes `?q=Harm`.
  - "zzzz": "No invoices match" with Clear filters. Clear filters re-reads without `q`.
  - With the reply replaced to send all 4 rows for `q=Harm`, all 4 are drawn, so the browser does not filter.
- **Filters.** Filter → Overdue → Show results sends `status=overdue`, adds `?status=overdue` to the URL, shows the chip "State · Overdue" and the server returns one row. The chip's × re-reads without `status`. Opening `?status=paid` directly sends `status=paid`.

### Reminder W-3801 (`/work/W-3801`)
- **Draft.** The page shows the fixture's title, Subject, the full message, "INV-0391.pdf", "Uploaded · 84 KB" with the paperclip and no link, Amount ₦6,800,000.00, overdue by 21 days, "None yet" and "None".
  - There is no "7 days" or "second reminder".
  - Load sends no POST.
  - No text claims the reminder was sent or delivered. The words "SENT" and "VERIFIED" are station names marked "Not yet". The only other uses are "Nothing is sent until you press Send", "Reminders sent: None yet" and Chidi's "After you send it, I'll check it was delivered."
- **Edit, then "Save draft".** On desktop the form opens inline; at 390 it opens in the full-height Drawer, and every Drawer target is at least 44px. The form opens with the returned Subject and Message. Its submit button reads "Save draft", and there is no "Edit" button inside the form.
  - An empty Message sends no POST, sets `aria-invalid=true` and moves focus to Message.
  - After filling it in, one POST goes out: `{"expected_revision":1,"step":"edit_draft","idempotency_key":<uuid>,"inputs":{"subject":"Reminder: INV-0391","message":…}}` with `X-CSRFToken`. The re-read shows "Draft v2".
- **Send, double press.** A `dblclick` at 1440, or two taps at 390, sends exactly one POST: `{"expected_revision":2,"step":"send_reminder","idempotency_key":<uuid>}`. Before the press, nothing says sent. After the re-read the page shows "SENT · CHECKING DELIVERY" and "Not yet" for each recipient, never "Delivered". The log reads `["edit_draft","send_reminder"]`, one send per key.
- **Delivered, W-3802.** The status is the backend's DELIVERED. Each recipient reads "RECEIVED 12 Nov 11:06" from `receipt: received`. The vitest double covers a recipient set to `not_yet`: it reads "Not yet", not "Received".
- **Not now.** One `set_aside`, then "SET ASIDE" and "Nothing was sent. The draft is kept." The log holds only `["set_aside"]`. The old "Nothing is sent until you press Send" sentence is gone.
- **Uncertain, W-3803.** The send returns 200 `effect_uncertain`.
  - The page shows "DELIVERY UNCERTAIN", the subtitle "…couldn't be confirmed. Nothing is sent again until a person confirms what happened.", the notice "Delivery to Harmattan Bank couldn’t be confirmed." and UNCERTAIN for each recipient.
  - Send, Edit and Not now are all `aria-disabled`. A forced click on Send sends no POST, at both widths and again after a reload.
  - Reconcile: picking "It didn’t arrive." then "Record and continue" sends one `POST /api/v1/work/W-3803/actions {"expected_revision":2,"action":"reconcile","outcome":"not_delivered"}`. The re-read shows NOT DELIVERED with "Nothing was sent again". The log still holds one `send_reminder`.
- **Other uncertain items.**
  - W-3804 (500 on send): the page re-reads into the uncertain item and the notice reads "We couldn’t confirm this step…". Forcing Send again sends no POST, and the log holds one `send_reminder`.
  - W-3805, opened fresh: Send is off and reconcile is offered.
  - W-3806: the page shows "Someone with reconcile access needs to confirm what happened first." There is no reconcile control and Send is off.
- **Network abort and routed 503 on W-3801.** One POST each. There are no success words and the entries are kept. The notice reads "We couldn’t confirm this step. Check the page before trying again." Send stays `aria-disabled`, and a forced press sends nothing.
- **Hang (routed POST that never answers).** One POST. The button shows the busy "Send reminder…" label with `aria-disabled`. Forcing Edit and Not now sends nothing. After 8 s there are still no success words.
- **409, W-3807.** "This changed while you were working. Showing version 2." with Draft v2 and one POST. Nothing more is sent in the following 1.5 s, and Send stays available for a new press.
- **422, W-3811.** "The message must name the invoice reference." appears under Message through `aria-describedby`. `aria-invalid` is true, the typed text is kept, and there is no Draft v2 and no done notice.
- **A person who can't act.**
  - W-3808 shows "Harmattan Bank has no billing contact yet, so this can’t be sent." Send is off and a forced press sends nothing.
  - W-3809 shows no Send, Edit or Not now.
  - On the list, `pm` and `none` get "You can’t open this page", with no client, amount, invoice id or count.
  - On W-3801, `finance_lead`, `ceo` and `pm` all see the same three controls, taken from the reply.
- **Facts.** W-3810 shows Unknown, not ₦0.00, for the unknown amounts. W-3812 has no attachment line. W-3813 has no sample tag.

### Access (401, 403, 404)
- The list with `pm`, `none`, scenario 403 and scenario 404, and the reminder with 403, 404 and W-1099, were checked at both widths. None shows a client name, ₦ amount, `INV-0…` id or count.
- 401: the page shows "You’re signed out. Sign in", with the link going to `/accounts/login/?next=%2Ffinance%2Fpayments` for the list and `?next=%2Fwork%2FW-3801` for the reminder.
- A routed 401 on Send goes to the signed-out view after one POST, with no second write and no success words.

### Phone, scroll and axe
- No sideways scroll on the list, the reminder, the open Drawer, after a send, or in the uncertain state at 390.
- Reconcile targets are at least 44px.
- axe (`wcag2a/aa`, `wcag21a/aa`, `wcag22aa`) found 0 violations at 1440 and 390 on:
  - the list: board, unknown, and the not-open view (pm);
  - W-3801: the draft, the Edit form with its error (inline and in the Drawer), and after sending;
  - W-3803 uncertain;
  - W-3808.

  `e2e/payments.spec.ts` also covers the open filter panel and the empty list.

### Other lines after the "Done after re-read" change
- **W-2209 weekly**: "Edit your update" → submit sends one `send_to_tola`. After the re-read the notice reads "Sent to Tola on the mock only. Tola is reassembling the report." No page errors.
- **The other five** render with no page errors: W-2411 issue, W-2603 planning, W-2901 minutes, W-2502 release and W-2702 income. Their flows ran in their own e2e suites, all passing:
  - issue-detail 25, including "Done: update posted." after the re-read;
  - engagement-planning 22;
  - minutes 26 and minutes-end 18;
  - delivery-release 22;
  - income-schedule 28;
  - weekly 25 and weekly-returned-received 17;
  - workspace 37, including the W-2008 reconcile;
  - response 16, clients 16 and finance-month-end 24.

### Commands
- `cd frontend && E2E_PORT=4976 MOCK_PORT=4977 npx playwright test e2e/payments.spec.ts e2e/workspace.spec.ts e2e/weekly-returned-received.spec.ts e2e/minutes-end.spec.ts e2e/response.spec.ts e2e/clients.spec.ts e2e/finance-month-end.spec.ts e2e/weekly.spec.ts e2e/minutes.spec.ts e2e/issue-detail.spec.ts e2e/engagement-planning.spec.ts e2e/delivery-release.spec.ts e2e/income-schedule.spec.ts`: **307 passed**. Payments 31.
- `npx vitest run tests/payments.test.tsx tests/payment-reminder.test.tsx tests/payments-mock.test.ts tests/mock-contract.test.ts tests/workspace-step.test.tsx tests/weekly.test.tsx tests/minutes.test.tsx tests/minutes-end.test.tsx tests/issue-detail.test.tsx`: **584 passed**.
- `npx vitest run tests/engagement-planning.test.tsx tests/income-schedule.test.tsx tests/release-gates.test.tsx tests/response.test.tsx tests/workspace.test.tsx tests/workspace-mock.test.ts tests/weekly-mock.test.ts tests/delivery-release-mock.test.ts`: **238 passed**.
- Spec greps:
  - AC1: no board string in the F-41 files. The hits are comments in files that predate this feature.
  - AC7, AC12 and AC20: empty.
  - AC4: the one `Number(` in `model.ts:108` reads a month index from `period` for a label, not an amount.
- Cleanup: I stopped only my own PIDs (mock 93102, app 93542). `frontend/test-results` is deleted, nothing is listening on 4974 to 4977, and the worktree is clean.

## Findings
1. QA-2-1 | non-blocking | low | frontend | When a send that sends fails with a 5xx, a network failure or a 500 (W-3804), the page shows the frame's notice "We couldn’t confirm this step. Check the page before trying again." Spec line 128 and AC16 ask for "We are checking what happened. Nothing was sent again." This deviation is not recorded in any build.md. The meaning is safe: no success words appear, and Send is locked in the session. But "before trying again" invites a retry the page itself refuses. Expected: record it as a deviation from F-17's shared text, or route the wording to UX. Actual: `useWorkspaceStep.ts` `default:` branch → `failed` notice, rendered by the frame.

## Verified
- UI-2-1 | verified | At 390 on the live build, "Open the reminder draft" measures 151.6×44.0, and every list target is at least 44px.
- UI-2-2 | verified | `.ws-attachment` has one paperclip `svg`, contains no `a`, and shows "INV-0391.pdf" and "Uploaded · 84 KB" at both widths. axe is clean. W-3812 shows no attachment.
- UX-2-1 | verified | After the uncertain sends on W-3803 and W-3804, and on W-3805 and W-3806, the subtitle reads "…couldn't be confirmed. Nothing is sent again until a person confirms what happened." After Not now the page reads "This draft is set aside." / "Nothing was sent. The draft is kept." The old sentence is absent.
- UX-2-3 | verified | The Edit form, inline at 1440 and in the Drawer at 390, submits with "Save draft" and has no "Edit" button inside it. On W-2209 the weekly form keeps its own submit label and posts `send_to_tola`.

## Notes
- These are recorded deviations from round 1, confirmed live; they are not findings:
  - a send carries no `inputs` key (the schema makes it optional);
  - W-3802's per-recipient word is F-28's "Received", not "Delivered";
  - TECH-1-2: a hung send never times out.
- The contract mock accepts a second send while delivery is uncertain if a new key arrives after a reload during a hang or a routed failure. In the browser, the lock holds only within the session, or when the backend marks the item uncertain. The real guard is the backend (BACKEND-HANDOFF priority 1), and it must be proved before any live provider is used.
