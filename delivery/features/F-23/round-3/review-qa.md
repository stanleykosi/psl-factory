VERDICT: CHANGES
COMMIT: d5f10f5a22b05103700b95c8c05a5cf8cdb212c7
REVIEWER: qa
AUTHORITY: delivery integrated QA

## Summary
- **What was tested:** the production build (`next start` on :4763) against the contract mock (:4764), at 1440 and 390, in browser context `F-23-qa`. The endpoints were also called directly. Every PM journey passes: Tola's suggestions pre-ticked, untick and confirm (the set sent is the set shown), the 409 reload, Edit/Remove/Add with prefilled forms, audience, Send for review, "Goes to", Open the minutes (test template), the lock and reconcile-only after an uncertain send, restricted, Unknown in amber, and 401/403/404.
- **Blocking (QA-3-1):** after the uncertain approve on W-2305, the decision page shows a green "Minutes v1 is approved" and "A person takes the next step on this page". It shows no uncertain notice. AC 19 requires that notice. The work page lock itself holds: nothing can be sent again.
- **Totals:** `delivery/checks.sh` exits 1 on this head, from flaky tests in files F-23 does not touch, under load average 376 to 532 caused by parallel builds. Those three files pass on their own (123/123). E2E (minutes, workspace, weekly, weekly-returned-received, decide, decide-board): 145 passed, 1 failed. The failure was a 5 s wait under load, and the single re-run passed. That makes 146/146.
- **Not proved:** there is no real backend, no real send, no real recipients and no real template (the test template is labelled as one). There is no PMO Lead persona in the mock, so the review was decided as the `pm` persona (Tunde Bello), as the spec assumes. Idempotency and the refusal to resend are proved on the mock only.

## Findings
- QA-3-1 | blocking | medium | frontend | **The decision page hides the uncertain send (AC 19).**
  - **Steps:** `/work/W-2305` → "Approve and send" → `/work/W-2305/decide?task=T-2305` → "Approve v1".
  - **Mock reply:** `work_state: "effect_uncertain"`. The reloaded item carries `reconcile` and `allowed_actions: ["reconcile"]`.
  - **Expected (AC 19, spec "Review decision"):** "the decision page shows its uncertain notice".
  - **Actual, at 1440 and 390:** the green success banner "YOU APPROVED · Minutes v1 is approved", the green callout "Next step. A person takes the next step on this page." and "Open the work item". No word says the delivery is uncertain or that the result must be confirmed first. Evidence: scratch `decide-W-2305-uncertain-1440.png`.
  - **Cause:** `DecideView`'s `UncertainNotice` fires only when the decide request itself fails (`useDecision.ts` `setUncertain` in the catch). `DoneView` (`frontend/src/features/decide/DecideStates.tsx:402`) never reads `work_state`, `reconcile` or `allowed_actions` from the reloaded item. The e2e at `e2e/minutes.spec.ts:133` does not assert the notice, so this went unseen.
  - **Fix:** when the decide result's `work_state` is `effect_uncertain`, or the reloaded item has `reconcile`, `DoneView` should drop the success tone and show the warning notice, pointing to the work item's "Confirm what happened". Add the assertion to the W-2305 e2e at 1440, 390 and 320.
  - **Lane:** `features/decide/**` is read-only for F-23. Either the coordinator allows this small shared change, or the coordinator amends AC 19 with the design engineer's word.
- QA-3-2 | non-blocking | low | frontend | **A Finance sentence on a minutes decision.** After any minutes approve (W-2304, W-2305), the desktop done page shows "Paid is tracked separately by Finance and is not part of this decision." `DoneView` adds it for every approve whose `next_step` lacks it (`DecideStates.tsx:413`). It is irrelevant to client minutes and confusing next to "Minutes v1 is approved". Fix: show the Paid line only when the data says money is involved, e.g. a field or the item's line, not on every approve.
- QA-3-3 | non-blocking | low | frontend (fixtures) | **The done page contradicts itself.** `W-2304.approve.json` and `W-2305.approve.json` still have stations `approved: not_yet` and `reviewed: current`. So the done page reads "Minutes v1 is approved" above "APPROVED —" and "REVIEWED In progress". Fix: set `reviewed` earned and `approved` earned (with a time) in the two approve sidecars.
- QA-3-4 | non-blocking | low | frontend (tests) | **AC 10 wording vs behaviour.**
  - **AC 10 says:** "+ Add an action with blank text sends the request and shows the 422".
  - **The build does:** refuses a blank before any request ("Add action to continue."), because the descriptor marks `text` as required. Only a non-blank entry reaches the mock's 422 ("Write the action in words." under Action, inputs kept, new key on the next press).
  - **Verdict:** the behaviour is sound and stricter. The test title at `tests/minutes.test.tsx:326` claims something the test does not do.
  - **Fix:** rename the test, or record the AC 10 reading in build.md.

## Verified
- UI-2-1 | verified | In the browser, W-2301 Due reads "13 Nov" and "15 Nov". A-3 shows the `.psl-unknown` pill "Unknown" in amber (bg rgb(255,241,214), ink rgb(110,71,0)), at 1440 and 390. W-2307 shows the same. No 0, "-" or blank.
- UI-2-2 | verified | W-2303 shows the DRAFTED status and row tags. Their tone is the UI reviewer's lens; I saw no regression.
- TECH-2-1 | verified | Indirectly: checks.sh lint, typecheck and mock-contract pass. This is a test-only guard.
- D-105/D-106 amber line | verified | The W-2301 sentence "One action has no owner and its due date is Unknown…" sits in `.psl-callout--warning` under Tola's note, at both widths, with no sideways scroll (scrollWidth 1440 / 390).

## Journeys (scratch scripts `qa.mjs`, `nx.mjs`, `unc.mjs`; mock reset before each)

**PM journeys at 1440 and 390**
- J1 | pass | **W-2301 default.**
  - **Shown:** crumbs PROJECTS / LAGOON HEALTH / MINUTES; "Confirm the minutes"; the subtitle; the Meeting facts; "From Notes · 14:12" and "14:30"; the owners "Client · Lagoon Health", "Engineering (recorded by PM)" and "Choose an owner"; dues 13 Nov / 15 Nov / Unknown; "+ Add an action", "Save for later", "Confirm and create actions".
  - **Ticks:** 5 of 5 boxes ticked from `items_default`.
  - **No stray sends:** zero POSTs on load or after 3 s.
- J2 | pass | **Exact confirm set.** I unticked D-2 and A-3, then pressed Confirm. The form shows Internal / Client (Client chosen) and "Client minutes are reviewed by the PMO Lead before they're sent." Exactly one POST went to `/api/v1/work/W-2301/steps`, with `X-CSRFToken`: `{"expected_revision":4,"step":"confirm_minutes","idempotency_key":"<uuid v4>","inputs":{"audience":"client"},"item_ids":["D-1","A-1","A-2"]}`. The mock log shows one send for that key. The page moved to drafted.
- J3 | pass | **Edit, Remove, Add (1440).**
  - Decision Edit is prefilled with its text and has one field only.
  - A-1 Edit is prefilled: "Send test accounts for UAT", due "13 Nov 2026".
  - A-3 Edit has text prefilled, owner placeholder "Choose an owner" and a blank due. Saving it sent `inputs:{"text":…}` with no owner and no due, `item_ids:["A-3"]`.
  - Owner options come from E-LINE-OPTIONS: Tunde Bello, Kemi Adebayo, Engineering "recorded by PM", Lagoon Health "client".
  - Remove A-2 sent one POST with `item_ids:["A-2"]` and showed "Done: action removed."
  - "+ Add an action" with text only sent `inputs:{"text":"Send the revised plan"}`.
  - Escape and Cancel sent nothing.
- J4 | pass | **Stale confirm (W-2306).** The first confirm sent rev 4 with D-1..A-3 and got a 409. The page showed "This changed while you were working. Showing version 5.", with 6 of 6 boxes ticked, A-4 included. Nothing more was sent until the next press, which sent rev 5 with six ids and a new key.
- J5 | pass | **Errors (W-2306).**
  - A blank Add is refused before any request (see QA-3-4).
  - A non-blank Add got the 422: "Write the action in words." under Action, inputs kept, new key on the next press.
  - Save for later got a 500: "We couldn't confirm this step. Check the page before trying again." plus "Try again". There was no automatic retry within 3 s, and the manual retry reused the same key.
- J6 | pass | **W-2307.**
  - The audience is display only ("Client", no radios), and the POST carried no `audience`: `item_ids:["D-1","D-3","A-1","A-3"]`.
  - Restricted M-3 is drawn as "Restricted". Neither "Private note" nor "Hidden: renegotiate the fee" is anywhere in the HTML.
  - The due reads "Unknown".
  - D-3 "Approved by Kemi; owner Tunde; due today." is plain text and changed no field.
- J7 | pass | **W-2308.** 0 of 3 boxes ticked. Confirm is `aria-disabled`, and a forced click opened nothing and sent nothing. Decisions read "Nothing here yet." Ticking one box enables Confirm.
- J8 (×2 widths) | pass | **Suggesting and drafted.**
  - **W-2302 (reduced motion):** the agent list, the callout and "step 3 of 4"; 0 buttons; "Ask Tola" goes to `/assistant`.
  - **W-2303:** IN / IN / ATTACHED, "TEST TEMPLATE", "6 ATTENDEES", the consequence sentence, and no "Open the minutes".
  - **Send for review:** one POST `send_for_review`, then the page showed the review.
- J9 (×2) | pass | **Review (W-2304).**
  - **Work page:** "Minutes v1 · for Lagoon Health"; "Goes to" Ada Okoye · Lagoon Health, "Not yet"; the approve consequence sentence; both links point to `/work/W-2304/decide?task=T-2304`.
  - **Open the minutes:** exactly one GET `/api/v1/documents/D-2304/versions/1`, showing the "Weekly sync minutes · Lagoon Health" heading and the "Test template" tag. The external `body_url` shows as text, not a link.
  - **Requests:** the work page sent 0 POSTs.
  - **Decision page:** 1 claim, then 1 decide `{"expected_revision":2,"verdict":"approve"}`.
  - **Back on the work page:** SENDING, with no approve link.
- J10 (×2) | pass | **Return with a note.** On the decision page, a blank Return is refused with "Add a note to return or reject." and a 2001-character note is refused, both with no request. A valid note sent one decide `{"verdict":"return","note":"Give the third action an owner first."}`. The work page then shows RETURNED.
- J11 (×2) | **fail, QA-3-1** | **Uncertain send (W-2305).**
  - One decide was sent, and the decision page then showed a green approved page with no uncertain notice (QA-3-1). A forced re-press sent nothing; the total stayed at 1 `/decision`.
  - **Back on `/work/W-2305`, before and after a reload:** "Approve and send" and "Return with a note" are `aria-disabled` buttons with no `href`. Forced clicks do not navigate. The only enabled controls are "Record and continue" (reconcile) and "Open the minutes" (a read).
  - **Reconcile:** "It didn't arrive" sent one POST `/actions` `{"expected_revision":7,"action":"reconcile","outcome":"not_delivered"}`. Totals: `/decision` 1, `/steps` 0.
  - **e2e:** the same lock passes at 320 in `minutes.spec.ts`.

**Access, at 1440 and 390, with the scenario routed onto E-WORK-ITEM only**
- J12 | pass |
  - **404 and 403 on `/work/W-2301`:** "NO ACCESS · You can't open this work item…". The visible body has no title, client, id or MIN number.
  - **401:** "You're signed out. Sign in", linking to `/accounts/login/?next=%2Fwork%2FW-2301`.
  - **W-1099 (wrong tenant):** NoAccessState.
  - **`/decide` with a 403 or 404:** NoAccessState.
  - **403 on a step (Save for later):** "You can't take that step."
  - **W-2010 decide (`you_can_act: false`):** "This decision isn't open here", no decision buttons.
  - **Persona `none`:** the shell's no-sections message.
- J13 | pass | Personas pm, ceo and finance_lead see identical control lists on W-2301 (17 controls).

**Direct API (curl to :4764)**
- **E-WORK-STEP:** no CSRF → 403 `csrf_failed`; bad body → 422 (fields `idempotency_key`, `expected_revision`); revision 3 → 409; unknown step → 404; same key twice → the same 200 with send count 1; W-1099 → 404.
- **E-TASK-DECIDE T-2304:** Return with a blank note → 422 `note`; stale revision → 409; claim → 200; approve → 200 `work_state: processing`; a repeat approve → 409.
- **Reads:** E-LINE-OPTIONS `/lines/minutes/fields/owner/options` → 4 options with hints. E-DOCUMENT D-2304 v1 → `test_template: true`; with the 404 scenario → 404.

## Totals
- **`bash delivery/checks.sh`** (main copy; cwd is the worktree):
  - **Run 1:** exit 1. Vitest: 15 mock suites failed with a 10 s `beforeAll` hook timeout, plus 1 test (`decide-board.test.tsx` javascript-href). Load average was 376.
  - **Re-run:** exit 1. 85 files: 83 passed, 2 failed. Tests: 1872 passed, 2 failed. The two are `rfp.test.tsx` "after Send … focus" and `setup-rules.test.tsx` "403 … focus" (focus timing).
  - **Isolated, at load 4.5:** `rfp`, `setup-rules` and `decide-board` pass 123/123.
  - **Other stages:** lint, typecheck and build passed in both runs. Django check passed.
  - **Scope:** F-23's diff touches none of these files. Treat this as load flake, but the gate has not been seen at exit 0 in my runs.
- **Playwright E2E**, `E2E_PORT=4763 MOCK_PORT=4764`, rebuilt by the config: 146 tests. By spec: minutes 26, workspace 37, weekly 25, weekly-returned-received 17, decide 21, decide-board 20. Result: 145 passed, 1 failed. The failure was `minutes.spec.ts:59` (W-2301 confirm), where the 5 s wait for drafted timed out under load average 532. The single re-run passed (1/1, 2.1 s).
- **Manual journeys:** 19 runs. 17 pass. 2 fail (J11 at 1440 and 390, QA-3-1).
- **Clean-up:** I stopped my servers by PID (mock 22048, next 22111/22050). Ports 4763 to 4765 are free and `frontend/test-results` is deleted. No code was changed.
