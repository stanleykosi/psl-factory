VERDICT: PASS
COMMIT: 2075d4aa29aa4d09b9adc118b4955ad7e5c29af3
REVIEWER: qa
AUTHORITY: delivery integrated QA

## Summary
- I tested the real frontend (`next build` with `API_ORIGIN=http://127.0.0.1:4776`, then `next start -p 4777`) against the contract mock (`MOCK_PORT=4776 node mock/server.mjs`). The browser session was F-24-qa, run with Playwright Chromium in the Africa/Lagos timezone at 1440 and 390, as `pm`, `finance_lead`, `admin` and `none`. I also called the endpoints directly. 59 live checks were run: all pass after I fixed 7 errors in my own script (listed under Notes). None of those was a product defect.
- Every journey in the brief passed at this head:
  - pick an agent and ask
  - watch it work: polls at 5.0 s and stops when the run ends
  - read the answer with its steps and sources
  - "Start this invoice": the normal drawer opens prefilled, and the person presses start
  - second start gets a 409 and the thread is re-read
  - restricted source, Unknown amount, uncertain send and uncertain start
  - 401, 403 and 404, and another person's conversation
  - the phone "Open INV-0415" footer sits at the bottom of the screen
- Product checks:
  - A person starts every work item. No start request was sent before the person pressed start, and the assistant itself sent nothing.
  - No control offers approve, send or pay. The only control with "send" in its name is the composer's Send button for the message.
  - The mic is aria-disabled. Click, Enter and Space change nothing and send nothing. Spies on the speech APIs recorded 0 calls.
- Totals:
  - `bash delivery/checks.sh` exit 0: Django check clean, lint 0 warnings, tsc clean, 82 test files and 1779 tests passed, build OK.
  - `E2E_PORT=4777 MOCK_PORT=4776 npx playwright test e2e/assistant.spec.ts e2e/start-work.spec.ts`: 34 passed (24 assistant, 10 start-work) in 56.7 s.
- Still unproved (contract mock only, per spec Limits):
  - There is no real backend or agent. Every answer is fixture text or labelled sample text.
  - The link from a draft to its work item, the 409 on a second start and the prevention of a double send are simulated by the mock (G-SCR05-1 and G-SCR05-3 are still open).
  - No alert is sent when a working conversation ends (G-SCR05-7).
  - The `/work/W-1401` page I reached after the start is the existing fixture work item. Its body shows INV-0420 · Lagoon Health, not INV-0415, because the mock does not create a real item.

## Journeys
Unless a row says otherwise, the commands are the two scratch drivers (`qa.mjs` and `qa-f24-r3b.mjs`) run against 4777/4776, with `POST /__mock/reset` before each journey.

| # | Journey | Result | Evidence |
|---|---|---|---|
| 1 | PM default, 1440 | pass | h1 "Hi Tunde, I'm Tola. What should we get moving?"; Talk to: Tola · PMO, Chidi · Finance, Zainab · HR, with Tola pressed; the "Message Tola" composer; side panel "Tola is ready."; 5 conversation rows under TODAY plus "+ New request" |
| 2 | PM default, 390 | pass | same h1; agent row Tola/Chidi/Zainab; "5 earlier" opens a bottom sheet with 5 links |
| 3 | Finance Lead, Chidi only (1440 and 390) | pass | `/assistant?agent=tola`: the only textbox is "Message Chidi", and no Tola text appears |
| 4 | Admin, no agents (1440 and 390) | pass | "No agents are available to you."; 0 textboxes; 0 POSTs |
| 4b | `none` persona | pass | the frame says "No sections are open to your role yet." because `me.none` has no assistant destination; 0 textboxes; 0 POSTs |
| 5 | Ask from the home | pass | Shift+Enter keeps "Line one\nline two". Enter, then a second Enter, sent exactly `POST /assistant/conversations {"agent":"tola"}` and `POST .../CV-N1/messages {"text":"Line one\nline two"}`, both with `x-csrftoken: mock-csrf-pm`. Mock log: `E-CONVERSATION-NEW:200, E-MESSAGE:200`. The page landed on `/assistant/CV-N1` with the sample answer |
| 6 | Blank text, 4,001 characters, "+ New request" | pass | Send is disabled for blank text. 4,001 characters shows "Keep it under 4,000 characters." and the log stays at 2. "+ New request" posts nothing |
| 7 | Watch it work (CV-2405, 1440) | pass | "WORKING · STEP 3 OF 5" and "Tola is working on it. You can leave; you'll be alerted." 4 GETs, 5.0 s apart. 0 GETs in the 16 s after "answered". The sentence disappears and the list is re-read. Assistant log 0 (opening and polling write nothing) |
| 8 | Hidden tab | pass | `visibilityState` forced to hidden: 1 GET in 11.5 s. Visible again: a GET follows at once |
| 9 | Reload keeps the state (390) | pass | after a reload: "Tola · PMO agent · step 4 of 5 … WORKING"; step 3 is not shown |
| 10 | Thread CV-2401 (1440 and 390) | pass | in this order: ask, "Chidi · Finance agent", hand-off note, "3 STEPS · DONE" with references, answer, MILESTONE · HB-M2, draft title, "DRAFTED · NOT REVIEWED", "₦6,800,000.00 (contract stage 2 of 3)", "Invoice · TEST TEMPLATE", "Finance review by a Finance Lead", "Start this invoice". No control matches approve, pay, send to/for, edit draft or attach. Side panel: "Chidi has a draft ready for you to check." |
| 11 | Restricted source (CV-2403) | pass | sources: link "GO-LIVE · GLV-0087" → `/work/W-1005`, plain "DELIVERY JOB · 10:02", and a plain "Restricted" span. "FINANCE MEMO" and "0042" are not in the page HTML |
| 12 | Unknown amount (CV-2406, 1440 and 390) | pass | "Amount Unknown". No ₦0 and no blank |
| 13 | Start this invoice, 1440 | pass | The drawer shows Project "Harmattan Bank · mobile onboarding" and Completed milestone "Milestone 2 · beta signed 30 Oct". 0 POSTs in the 4.5 s before the press. 1 POST `{"line":"invoice","case_id":"C-0102","case_revision":3,"intake":{"project":"P-0102","milestone":"M-0202"},"idempotency_key":…}` with CSRF. The page stays on `/assistant/CV-2401`. "Started INV-0415." has focus. "Open the work item" links to `/work/W-1401`. The start button is gone. The list shows "Started · INV-0415". The side panel reads "Chidi answered from records you can see." A reload keeps all of this |
| 14 | Start this invoice, 390 | pass | same prefill, 1 POST and started state |
| 15 | Phone footer, live (TECH-3-1) | pass | `.as__open` bottom equals the viewport height in every case: 844 at 390×844 (scrollY 197), 844 scrolled to the top, 844 scrolled to the bottom, and 640 at 390×640. `href=/work/W-1401`. No composer textbox. Screenshot checked |
| 16 | Second start | pass | The stale tab gets `409 {"code":"draft_already_started"}` through the drawer. After Close, the thread re-reads, shows "Started INV-0415." and the button is gone. A direct POST with a new key also gets 409. Repeating the same key replays the 201, so there is no second item. A POST with no CSRF gets 403. A start with no draft read falls through to the pinned billing-contact 422 |
| 17 | Uncertain start: request aborted before reaching the mock, and reply lost after the mock answered | pass | Start work's own "We couldn't confirm the start…" notice. 1 POST in 7 s (no automatic resend). Assistant log 0. The person's "Check again" re-sends with the same key and the started line appears |
| 18 | Uncertain send (TECH-1-1) | pass | "Same words" delivered once. Sending identical text again with the request aborted shows "We couldn't confirm that was sent." with "Try again". The text is kept. No resend in 10 s, and the mock log shows a single E-MESSAGE. The person's "Try again" delivers it once. When the mock received the message but the reply was lost, the re-read finds it, the text is cleared and nothing is resent |
| 19 | Send hooks `[500]`, `[422]`, `[409]` | pass | One POST each, and the text is kept. `[500]`: "We couldn't confirm that was sent." with Try again. `[422]`: the mock's message. `[409]`: "This conversation changed. Showing the latest." |
| 20 | 401, 403 and 404 on the conversation read (header scenario on that request only) | pass | 401: signed-out callout linking to `/accounts/login/?next=%2Fassistant%2FCV-2401`. 403 and 404: "We could not find that conversation." with no thread content. On the list read: 401 shows the signed-out callout with `next=%2Fassistant`; 403 and 404 show "Couldn't load your conversations" with Try again |
| 21 | Another person's conversation | pass | `finance_lead` opening CV-2401 and CV-N1, and `pm` opening CV-2411 and CV-2499, all see "We could not find that conversation." with no title leaked. API as `pm`: GET CV-2411 → 404 and POST a message → 404. The pm list does not include CV-2411 |
| 22 | API refusals | pass | `finance_lead` creating a Tola conversation → 403 "That agent is not available to you." An extra `idempotency_key` field → 422 naming it. No CSRF → 403 |
| 23 | A draft the person can't start | pass | `finance_lead` on CV-2411: "Start this report" opens a drawer reading "You can't start this here.", with 0 comboboxes and no start button. CV-2402 has no start button |
| 24 | Mentions | pass | Opening the picker sends no request. Typing "harm" sends exactly one GET `?q=harm`, which returns 3 items with SAMPLE DATA. The chip is "@Harmattan Bank · mobile onboarding" with "Remove @Harmattan Bank · mobile onboarding". The sent body carries `mentions:[{"kind":"project","id":"P-0102"}]`. After the chip is removed, the body is `{"text":"No mention now"}` |
| 25 | Held mic | pass | `aria-disabled="true"`, 44px, tooltip "Not available yet". Click, Enter and Space leave the text, composer, URL and button unchanged, with 0 POSTs. Spies on `SpeechRecognition`, `webkitSpeechRecognition` and `getUserMedia` recorded 0 calls. `grep -rn "SpeechRecognition\|getUserMedia\|webkitSpeech" frontend/src` finds 0 lines. The phone composer has no mic (as on the boards) |
| 26 | All requests local | pass | browser hosts: `localhost:4777` only |
| 27 | Static checks | pass | No `dangerouslySetInnerHTML` or `innerHTML` in the assistant code or the 4 new components. The only "roles" in `features/assistant` is a comment. Approve/send/pay words appear only in the agents-cannot sentences and code comments |

## Findings
- QA-3-1 | non-blocking | low | frontend | Second start (stale tab), `frontend/src/features/start-work/LineForm.tsx:60` "stale" notice | After `409 draft_already_started`, the drawer says "This project changed since you opened the form. We've loaded the latest version; check your entries and press start again." and turns the start button back on. Pressing it again just gets another 409 (seen live: replies `[409,409]`). The thread behind the drawer has already re-read, and Close shows the started line. The spec allows "the drawer's existing message", so this is not a spec break. But the drawer invites a start that can never succeed, and the backend's own "This draft was already started." is never shown. Fix (later, with G-SCR05-1): when the 409 code is `draft_already_started`, show the returned message and offer only Close (or close the drawer and let the thread's started line speak).

## Verified
- UI-2-1 | verified | Live at 390×844 and 390×640, after the start and scrolled to the top and to the bottom: the `.as__open` footer's bottom equals `window.innerHeight` exactly. "Open INV-0415" links to `/work/W-1401`, and the composer is gone.
- UX-2-1 | verified | Live at 390: the "5 earlier" button exists and opens the bottom sheet with the 5 conversations. The underline itself was checked by the UI and UX reviews.
- UI-2-2 | verified (no QA impact) | Change to the exceptions file only. No runtime behaviour to retest.
- TECH-1-1 | verified | Live: after "Same words" was delivered, an identical send that was lost was not shown as delivered. The page showed the unsure line and "Try again", kept the text, and made no automatic resend. When the reply was lost after the mock had stored the message, the re-read was correctly treated as delivered.
- TECH-3-1 | verified live (the assertion is still loose) | The footer is exactly at the bottom of the screen in all 4 measurements, so the code is correct. The e2e check `> 844 - 4` would still pass if the footer were pushed off-screen. The technical reviewer's fix stands as a non-blocking test-quality item.

## Notes
- Round-3 impact assessment: the diff is assistant.css (the phone `.as__open` dock), shell.css (`.shell-phonenote--action` underline), one e2e assertion and the exceptions file. Every other journey was re-run live on this head regardless, so nothing is carried forward unretested.
- The mock serves the restricted source's label ("FINANCE MEMO · 0042") in the E-CONVERSATION body, and the frontend drops it before rendering. Whether a real backend may send it at all is the open INV-RESTRICTED question. This is not a frontend defect.
- 7 FAIL lines in my first run were errors in my own script, each corrected and re-run:
  - the list count included the "+ New request" link
  - the frame's "Start work" button was mistaken for a draft button
  - the chip name has an "@" prefix
  - the mention items are buttons, not options
  - a cookie scenario also broke E-ME, so I re-ran it as a header on the conversation request only
- Servers I started (mock PID 99263; `npx next start` PID 99265 and its child 99299) were stopped by PID. Ports 4776 and 4777 are free. `frontend/test-results` was deleted. The worktree is clean at 2075d4aa. Disk: 4.5 GB free before and after.
