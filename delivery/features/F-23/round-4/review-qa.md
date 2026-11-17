VERDICT: PASS
COMMIT: 778e868137d79b0b808b55c5c994c7345613d586
REVIEWER: qa
AUTHORITY: delivery integrated QA

## Summary
- **What I ran:** the production build (`next start` :4763) against the contract mock (:4764), in browser context `F-23-qa`. This head is the round-4 fix plus the dlv-00 merge with F-26.
- **QA-3-1 is fixed live.** After an uncertain approve on W-2305, the decision page is titled "Minutes v1: result not confirmed", with "NOT CONFIRMED" above it and the uncertain notice in an alert. It has no approved banner, no "Next step", no Paid line and no "Your decision was recorded". This holds at 1440, 390 and 320.
- **A normal approve (W-2304) is unchanged.** It still shows the green "Minutes v1 is approved".
- **The round-3 journey smoke** (19 runs plus 12 access checks) all pass on this head.
- **Not proved:** there is no real backend, send, recipients or template (it is a test template). There is no PMO Lead persona in the mock, so decisions were taken as the `pm` persona, as the spec assumes. Idempotency and the refusal to resend are proved on the mock only.

## Verified
- QA-3-1 | verified | `/work/W-2305` → "Approve and send" → `/work/W-2305/decide?task=T-2305` → "Approve v1". Result at 1440, 390 and 320:
  - **Heading:** h1 "Minutes v1: result not confirmed" under the eyebrow "NOT CONFIRMED · hh:mm".
  - **Notice:** `role=alert` "We couldn't confirm your decision. We've reloaded this item so you can see whether it was recorded."
  - **Absent:** 0 success banners or callouts, no "Next step", no "Paid is tracked separately", no "is approved", and no "Your decision was recorded" status.
  - **Requests and controls:** exactly 1 `/decision` POST. No decision buttons remain. "Open the work item" is present.
  - **Layout:** scrollWidth equals the viewport. Screenshots are in the scratch folder: `r4-W-2305-{1440,390,320}.png`.
  - **Work page:** back on `/work/W-2305`, still locked before and after a reload. Approve and Return are `aria-disabled` with no href. Reconcile is the only action and sends 1 `/actions`, with `/steps` at 0.
  - **Control case:** W-2304, whose approve answers `processing`, still shows "Minutes v1 is approved" with the recorded status.
  - **e2e:** `minutes.spec.ts` W-2305 at 1440, 390 and 320 now asserts the notice, and passes.
- QA-3-3 | verified | The done pages now agree with their headings.
  - **W-2304:** DRAFTED Earned, REVIEWED Earned 10 Nov 17:05, APPROVED Earned 10 Nov 17:05, SENT "Not yet", under "Minutes v1 is approved".
  - **W-2305:** APPROVED Earned and SENT Unknown, under "result not confirmed".
- QA-3-4 | verified | The test title at `tests/minutes.test.tsx:326` now says a blank is refused before any request and typed text reaches the 422. Live, W-2306 behaves that way:
  - A blank Add sends 0 requests and shows "Add action to continue.".
  - Typed text gets the 422 "Write the action in words." under Action, and the next press uses a new key.

## Smoke of the round-3 journeys (scratch `qa.mjs`, `nx.mjs`): 19/19 runs pass, 12/12 access checks pass
- **J1/J2 at 1440 and 390:** W-2301 starts with 5/5 boxes ticked. Unticking D-2 and A-3 and confirming sent one POST with `item_ids:["D-1","A-1","A-2"]`, `inputs:{audience:"client"}`, revision 4, CSRF and a UUID key. The mock counted one send.
- **J3:** Edit forms open prefilled. A blank owner or due is left out. Remove sends `item_ids:["A-2"]`. Add with text only sends `inputs:{text}`.
- **J4:** a 409 reloads to version 5 with 6/6 ticked, and the next press sends a new key at revision 5.
- **J5:** the 422 path as above. A 500 offers "Try again" with the same key and no automatic retry.
- **J6:** W-2307 shows the audience as display only, the restricted item as "Restricted" with no hidden strings, and Unknown due. The notes text "Approved by Kemi; owner Tunde; due today." grants nothing.
- **J7:** W-2308 starts unticked. Confirm is `aria-disabled` and sends nothing. The empty section reads "Nothing here yet.".
- **J8 at both widths:** W-2302 has nothing to press. W-2303 shows TEST TEMPLATE, and Send for review sends 1 POST and opens the review.
- **J9 at both widths:** "Goes to" lists Ada Okoye with "Not yet". "Open the minutes" makes 1 GET and shows the "Test template" tag. The work page sends 0 POSTs. The decide page sends 1 claim and 1 approve.
- **J10 at both widths:** blank and over-long notes are refused before any request, and a valid note sends one return.
- **J11 at both widths:** passes, including the uncertain notice above.
- **J12:** 401, 403 and 404 on the work page and on the decide page, and W-1099 (no access), show the right states with no leak at 1440 and 390. A 403 on a step shows "You can't take that step."; a task the user can't act on offers no decision.
- **J13:** personas pm, ceo and finance_lead see identical controls.

## Totals
- **checks.sh:** I accept the coordinator's run on this head (`round-4/merge-checks.log`: vitest 88/88 files, 1952/1952 tests, build complete). On this head I re-ran `decide`, `minutes`, `minutes-mock` and `mock-contract`: 369/369 passed.
- **E2E, existing run** (`round-4/merge-e2e.log`): 116 passed — decide-board 20, decide 21, minutes 26, money 12, workspace 37.
- **E2E, my run** (`E2E_PORT=4763 MOCK_PORT=4764`, rebuilt by the config): minutes, weekly and weekly-returned-received, 68/68 passed. I added the weekly specs because the merged evidence lacked them and they share the workspace and decide code.
- **Manual:** 19/19 journeys, 12/12 access checks and 5 QA-3-1/QA-3-3 runs (W-2305 at 3 widths, W-2304 at 2) all pass.
- **Clean-up:** servers stopped by PID (mock 47034, next 47036). Ports 4763 to 4765 are free and `frontend/test-results` is deleted. No code was changed.

## Findings
- QA-4-1 | non-blocking | low | frontend | **The uncertain notice blames the wrong thing.**
  - **Shown:** on the uncertain done view, the notice says "We couldn't confirm your decision…" while the facts strip shows APPROVED Earned and SENT Unknown.
  - **Problem:** the decision was recorded; what is uncertain is the send. A reader may think the approval itself is in doubt, and nothing on this page names the next move.
  - **Fix:** for the `work_state`/`reconcile` case, say the delivery could not be confirmed and point to "Confirm what happened" on the work item. Keep the current sentence for a failed decide request.
- QA-3-2 | non-blocking | low | frontend | Still open, as a follow-up by instruction: "Paid is tracked separately by Finance…" still shows on a normal minutes approve (W-2304, at 1440 and 390). It is gone from the uncertain view.
