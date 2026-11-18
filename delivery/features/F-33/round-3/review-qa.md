VERDICT: PASS
REVIEWER: qa
COMMIT: d20fd9b2ccee7be267936cc2758358989ecdedbb
AUTHORITY: delivery integrated QA

## Summary
- **What ran.** I made my own production build in the worktree (`API_ORIGIN=http://127.0.0.1:4886 FRAME_FIXTURES=1 npm run build && npx next start -p 4887`) over the contract mock (`MOCK_PORT=4886 node mock/server.mjs`). On it I ran an independent Playwright suite (65 tests, 1440 and 390, Africa/Lagos) and a 4-test follow-up. I also called the mock directly with curl. Then I stopped 4886 and 4887 by PID and ran the spec's e2e set with `E2E_PORT=4888 MOCK_PORT=4889`, plus the issue, document-review and weekly e2e: 173 passed in 7.3 min. The targeted vitest run had 8 files and 544 tests, all passing.
- **Result.** Every journey in the brief passes at both widths:
  - the four states, and the hold with no reviewer named;
  - approve, return and reject in place, with claim, CSRF and `expected_revision`;
  - the note rule;
  - W-2712 uncertain on all three verdicts;
  - 409, 422, 500, network failure, and 401, 403 and 404 on both read and decide;
  - amounts exactly as returned, and Unknown never shown as 0;
  - 44px targets on the phone and no sideways scroll;
  - axe at both widths (40 scans, 0 violations).
  - The other lines are unchanged.
- **What is NOT proved.**
  - There is no backend. Everything ran against the contract mock, so these are mock results, not live integration evidence.
  - There is no real Finance policy. `finance.income_schedules.reviewer`, `.income_detail` and `.inventory` are NOT SET. Every fixture is sample data, and no real reviewer exists. Separation of duties is only the fixture's `you_can_act`/`cannot_act_reason`, never a server rule.
  - The `steps[].verdict` overlay (G-C-1) is a proposal the real backend may refuse.
  - "Wrong tenant" cannot be exercised, because the mock has no tenant concept. Wrong user is covered by the personas and by `you_can_act` false.
  - E-TASK-DECIDE has no idempotency key (a backend item carried from round 1). A resend after a lost response is stopped only by the revision check (409) and the frontend never resending.
  - The SAMPLE DATA tag is hidden in this build by design (`NEXT_PUBLIC_SHOW_SAMPLE_LABEL` unset, 14 Nov decision), so AC 5 was proved only by the component test.
- **Scratch evidence.** All under `/private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/qa-f33/`:
  - `spec/qa.spec.ts`, `spec/qa2.spec.ts`
  - `qa-run3.log` (64 of 65 passed: the 1 failure is my own selector, see the month-end journey), `qa2.log` (4 of 4)
  - `e2e.log` (173 passed), `vitest.log` (544 passed)
- **Housekeeping.** The worktree's `frontend/.next` is now the e2e build (API origin 4889). The shared review copy needs its own rebuild before it is restarted. I deleted `frontend/test-results`.

## Journeys
Unless a line says otherwise, each was run at 1440 and at 390 on :4887/:4886, with persona `finance_lead` and `POST /__mock/reset` before each test.

1. **Four states, W-2701 to W-2704** (plus W-2705, W-2706, W-2707 and W-2712), on `/work/<id>`.
   - Each page has one h1. Every fixture string appears verbatim in `document.body.innerText`: title, status label, section titles, item labels, values, tags and `next`. The missing list was `[]` on all 8 pages at both widths.
   - There is no "12.4M" and no "₦0". scrollWidth is within the viewport, and axe is clean.
   - W-2701, W-2703, W-2704, W-2705 and W-2706 sent zero `/tasks/` POSTs.
   - The board-string grep on `frontend/src` (the AC 1 and AC 16 patterns) returns nothing.
2. **Amounts as returned.**
   - W-2702 reads "₦12,400,000.00" exactly at both widths.
   - I changed the read with `page.route`, then checked each result:

     | Amount sent | Page shows |
     |---|---|
     | `"12400000.10"` | "₦12,400,000.10" |
     | `"98765432109876543.21"` | "₦98,765,432,109,876,543.21" (beyond float precision, so no float is used) |
     | `"0.00"` | "₦0.00" (a real zero is shown as sent) |

   - On W-2707 the report line and Detail rows both read "Unknown", with no "₦0", no "0.00" and no dash.
   - `git diff -U0 d9ca6f97..HEAD -- frontend/src | grep -E "parseFloat|Number\(|\.reduce\(|compactAmount"` returns nothing.
3. **Approve on W-2702.**
   - Request log, from a double-click on "Approve schedule": `POST /api/v1/tasks/T-2702/claim {"expected_revision":1}`, then exactly one `POST /api/v1/tasks/T-2702/decision {"expected_revision":1,"verdict":"approve"}`. Both carry `X-CSRFToken: mock-csrf-finance_lead`, with no note and no extra keys.
   - The status becomes VERIFIED only after the re-read serves `W-2702.approve.json`, and no decide button remains.
   - Test double: the decide answered 200, but I kept serving the review fixture on the re-read. The status stays "AWAITING FINANCE DECISION" and no "Verified" appears. The only new line is the `VERDICT_WORDS` notice "Schedule v1 is approved", which the spec allows on a 200. No control is offered (see QA-3-1).
4. **Return and reject on W-2702.** On the phone this is the Drawer.
   - **Empty note:** nothing is sent. "Add a note to return it." or "Add a note to reject it." shows under the field, with `aria-invalid="true"` and `aria-describedby` set to the message. Focus moves to the note. axe is clean.
   - **Whitespace-only note:** the same message, and nothing is sent.
   - **2001 characters:** "Keep the note to 2000 characters or fewer." and nothing is sent. Zero decision POSTs before a valid note.
   - **Valid note:** I typed `"   Row 12 is a reclassification, not a disaggregation.  "`. It sent one POST: `{"verdict":"return"|"reject","note":"Row 12 is a reclassification, not a disaggregation.","expected_revision":1}` (trimmed). The re-read shows "RETURNED · CORRECT AND RESUBMIT" or "REJECTED".
   - **Phone Drawer:** Escape and Cancel each close it and return focus to the opening button ("Return with a note" or "Reject"). The open Drawer is axe clean.
5. **Reviewer not set (W-2706).**
   - The page shows "SETUP NEEDED", "Who reviews schedules · NOT SET" and its `next` sentence.
   - There is no Decide panel, no "Decide ·" heading and no button, and zero `/tasks/` POSTs.
   - `main` contains neither "Ada Okafor" nor "Schedules reviewer", and the whole body has no "Schedules reviewer". The only "Ada Okafor" on the page is the signed-in persona in the shell top bar, not a reviewer.
6. **No control when you_can_act is false.**
   - W-2705 shows "You prepared Schedule v1, so someone else must review it." with 0 decide buttons.
   - W-2708 shows the `not_your_role` copy with 0 buttons.
   - Zero claim or decide POSTs across W-2705, W-2706 and W-2708.
   - Personas `ceo` and `pm` on W-2702 draw the same three buttons, so the controls come from `you_can_act` only. `InlineDecide.tsx` has no `useMe` or `/me`.
   - W-2709 draws only `['Approve schedule','Return with a note']`. W-2711 draws no revoke or post button. W-2710 draws the link `/work/W-2710/decide?task=T-2710`.
7. **W-2712, effect_uncertain on approve, return and reject.** The lines that appear after the press are the same for all three verdicts at both widths:
   - "DECISION NOT CONFIRMED"
   - "Next step. We are checking whether the decision was recorded. Nothing is sent again."
   - "Schedule v1: result not confirmed"
   - "We are checking what happened. Nothing was sent again. Reload"
   - The frame's "See all exceptions" (UX-2-1, carried).

   None of the new lines matches `approved|returned|rejected|verified`. No decide button remains. Pressing Reload sends nothing more: exactly 1 decision POST in total. axe is clean.

   I then fully reloaded the page. It still shows "DECISION NOT CONFIRMED", the milestones still read APPROVED/VERIFIED "Not yet", there are 0 decide buttons, and the POSTs are still claim plus 1 decision.

   I also called the mock directly with curl:

   | Request | Answer |
   |---|---|
   | First decide | 200 `work_state: effect_uncertain` |
   | Second decide, same revision | 409 `stale_revision` |
   | Second decide, revision 2 | 403 `forbidden` |
   | Re-read | `effect_uncertain`, `you_can_act: false`, `already_decided` |

8. **Decide errors on W-2702.** Each failure was injected on the first decision POST only.

   | Failure | How injected | What the page shows | Status after | Note field | axe |
   |---|---|---|---|---|---|
   | 409 | `X-Mock-Scenario: 409` | "This review changed while you were reading it, so nothing was recorded. Review the latest". After "Review the latest" the note is still "Keep this note." | unchanged | kept | clean |
   | 422 | `X-Mock-Scenario: 422` | "Check the highlighted fields and try again." On the phone the Drawer stays open. | unchanged | `aria-invalid="true"`, note kept | not run |
   | 500 | `route.fulfill` 500 | "We couldn't confirm your decision. We've reloaded this item so you can see whether it was recorded." | AWAITING FINANCE DECISION | not checked | clean |
   | Network | `route.abort('failed')` | Same sentence as 500 | AWAITING FINANCE DECISION | not checked | clean |
   | 401 | `X-Mock-Scenario: 401` | Signed-out view "You're signed out. Sign in" | not checked | not checked | not run |
   | 403 | `X-Mock-Scenario: 403` | Read-only "This decision needs a Schedules reviewer. You can't approve, return or reject it." | not checked | not checked | not run |

   In every case: no success words, and exactly 1 decision POST, so nothing was resent automatically.

   The same rules, straight to the mock with curl:

   | Request | Answer |
   |---|---|
   | Return with no note | 422 `note` |
   | Reject with a blank note | 422 `note` |
   | Extra key `amount` | 422 |
   | `revoke` | 422 |
   | No CSRF token | 403 `csrf_failed` |
   | The pm persona's CSRF token on a finance_lead session | 403 `csrf_failed` |
   | T-2705 decide | 403 |
   | Unknown task | 404 |

9. **Read access: 401, 403, 404 and persona `none` on `/work/W-2702`.**
   - 401 gives the signed-out view with the link `/accounts/login/?next=%2Fwork%2FW-2702`.
   - 403, 404 and persona `none` give the same "NO ACCESS · You can't open this work item".
   - In all four, `page.content()` contains none of these: "Income detail", "12,400,000", "SCH-0021", "BISI ADE", "Service revenue", "Schedules reviewer", "Approve schedule".
   - The only API calls were `/me`, the item read and `/notifications`. axe is clean on the not-open view.
10. **Correct and resubmit (W-2703).**
    - The choice offers three options (Disaggregation, Reclassification, Additive) with 0 checked.
    - Submitting with no choice sends nothing and shows "Add row 12 relationship to continue."
    - Then I chose Reclassification, with the first POST forced to 500. The page shows "We couldn't confirm this step. Check the page before trying again." and never "resubmitted".
    - Try again sends a second POST with the same `idempotency_key` (UUID v4 shape), and with `expected_revision: 4`, `step: "correct_and_resubmit"`, `inputs.row_12_relationship: "reclassification"` and CSRF.
    - The re-read shows "You prepared Schedule v1, so someone else must review it."
11. **Phone at 390.**
    - The Decide bar has `position: fixed` and shows the three step labels.
    - There is no sideways scroll on W-2701, W-2702, W-2703, W-2704, W-2706 or W-2712.
    - Every button, link, radio and tab this feature adds is at least 44 by 44. Only two shell or frame controls are smaller:
      - the skip link "Skip to main content" (129x21), which is the shell's and visible only on focus;
      - the frame's History link (42x24), already routed to a frame follow-up as UI-2-7.
12. **Other lines unchanged** (1440 and 390):

    | Item | Status | Callouts | Agent footer |
    |---|---|---|---|
    | W-2901 "Lagoon Health · Statement of work" | ACTION NEEDED | warning `work-next`, info `ws-agentnote` | none |
    | W-2411 "Login fails on older Android phones" | FIX IN TESTING | info, info | none |
    | W-2209 "Weekly client report · 5–11 Nov" | RETURNED TO YOU | warning, warning | none |

    These match the UI reviewer's round-3 reading.
    - **Month-end:** `/finance/month-end?period=2026-10` has a link to `/work/W-1603` at 1440. At 390 my check failed only because my text selector hit the hidden desktop table. The month-end e2e covers the phone cards and the W-1603 link and passed.
    - **Contract paths:** `git diff --stat d9ca6f97..HEAD` shows no change under `src/api`, `src/features/decide`, `src/shell`, `mock/server.mjs`, `mock/workspace.mjs`, `mock/fixtures/response`, `mock/fixtures/finance` or `E-MONTH-END.json`.
13. **Spec e2e and vitest.**
    - `cd frontend && E2E_PORT=4888 MOCK_PORT=4889 npx playwright test e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/finance-month-end.spec.ts e2e/issue-detail.spec.ts e2e/document-review.spec.ts e2e/weekly.spec.ts`: 173 passed (7.3m), 0 failed, 0 flaky.
    - `npx vitest run tests/income-schedule.test.tsx tests/income-schedule-mock.test.ts tests/mock-contract.test.ts tests/response-mock.test.ts tests/finance-month-end.test.tsx tests/workspace.test.tsx tests/decide.test.tsx tests/document-review.test.tsx`: 8 files, 544 passed.
    - Load was 7 to 16 during the runs, under the limit of 20.

## Findings
1. QA-3-1 | non-blocking | low | frontend | The test double is a decide that answers 200 while the re-read still serves the review state.
   - What happens: the panel says "Schedule v1 is approved" while the status stays "AWAITING FINANCE DECISION". No control is offered and nothing says Verified, so AC 9 and the Writes contract are met. The spec allows the `VERDICT_WORDS` heading on a 200.
   - Why it matters: a real backend that is slow to show the decision would put an approval notice next to an awaiting status.
   - Suggestion: for product acceptance, consider wording the 200 notice as recorded, not as an outcome, when the re-read state has not moved. Path: `frontend/src/features/workspace/InlineDecide.tsx` `confirmed` and `onDecided`.

## Verified
- QA request (W-2712) | verified | `/work/W-2712` shows `effect_uncertain` in a browser on approve, return and reject at 1440 and 390. It never reads as success, before or after a full reload. One decision POST is sent and no second one is possible from the page. The mock answers a second decide with 409 (same revision) or 403 (new revision).
- TECH-2-1 | verified | Journeys 7 and 8: each decide shows only its own outcome or "result not confirmed"; no earlier "done" notice sits beside it.
- UI-2-1, UI-2-2, UI-2-3, UX-2-2 | verified, browser lens only |
  - W-2703 draws the problem callout and the other lines' callouts are unchanged (journey 12).
  - One Ask Chidi link sits in the agent footer and is 44px tall at 390.
  - The note label reads "Note (needed to return or reject)".
  - The Reject consequence on W-2702 is the fixture's text.

## Notes
- Mock behaviour, not product: with persona `none`, `GET /api/v1/work/W-2702` on the mock answers 200 with the full item. The frontend still shows the not-open view and leaks nothing, because it gates on `/me`. The real backend must refuse the read itself.
- Instruction-like text in evidence: none found.
