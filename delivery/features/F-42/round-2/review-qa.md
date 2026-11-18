VERDICT: PASS
REVIEWER: qa
COMMIT: 8d59b2422e06f960853993435c2935b7b9805046
AUTHORITY: delivery integrated QA

## Summary
- I ran a production build of 8779c5f3 (`API_ORIGIN=http://127.0.0.1:4982 FRAME_FIXTURES=1 npm run build`, then `npx next start -p 4983`) against the contract mock (`MOCK_PORT=4982 node mock/server.mjs`). I signed in as finance_lead, and also as ceo, pm and none. A Playwright driver used the browser's own request log, timezone Africa/Lagos, at 1440 and 390. Driver: /private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/qa-f42/qa.mjs. Logs: run1.log and run2.log in the same folder. I also called the endpoints directly with curl.
- **Spec journeys pass end to end.**
  - The four states, and approve, return and reject in place on both reviews.
  - The note rule, the CSRF header and `expected_revision`, and one decision on a double press.
  - The waiting state that replaces the explain-dates step, and the three holds.
  - Unknown cost, the uncertain-decide fixture, and the 409, 422, 5xx, network, 401 and 403 answers.
  - Access with no leak, costs digit for digit, the phone Drawer and pinned bar, and axe at both widths.
- **Claims per page view:**
  - W-3902 claims exactly one (T-3902) and W-3903 exactly one (T-3903, never T-3931).
  - Zero claims on W-3901, W-3904, W-3905, W-3906, W-3907, W-3908, W-3909 and W-3912, on a reload of a decided item, and for any task with `you_can_act: false`.
  - The only other claim is after a 409, when the person presses "Review the latest", which re-claims at the current revision.
- **Income line (W-2701..W-2704) unchanged:**
  - Status, claims, no sideways scroll and axe all match the fixtures at both widths. `data-line` is `income_schedules`.
  - Vitest income-schedule, income-schedule-mock, asset-schedule and asset-schedule-mock: 4 files, 100 tests passed (run after waiting for load under 20).
- **Not proved:**
  - No real backend or Django service ran; everything is the contract mock. Claim, decide, the uncertain effect and the access refusals are mock behaviour, and 401/403/404/409/422 were forced with the mock's `X-Mock-Scenario` header.
  - Real separation of duties, tenant scoping and reviewer policy were not tested: `finance.asset_schedule.*` and F07 are NOT SET, and only the sample "PPE reviewer" fixtures exist.
  - E-TASK-DECIDE has no idempotency key (F-33 PMO-3-1). A double press is held to one by the client and `expected_revision` only.
  - The explain-dates step (G-55-1) is not built, so only its waiting placeholder was exercised.
  - The SAMPLE DATA tag is off in this build by design (it needs `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1`), so it was not seen on the page.
  - I did not run the repo e2e (`e2e/asset-schedule.spec.ts`), fidelity or checks.sh.

## Journeys
Each journey below ran at 1440 and at 390 unless it says otherwise. The mock was reset (`POST /__mock/reset` → 204) before each journey.

**1. The four states, /work/W-3901..W-3904: pass at both widths**
- Status labels as returned: "CHIDI INVESTIGATING", "AWAITING FINANCE DECISION" (W-3902 and W-3903) and "PROCESSING".
- Every section title, fact label and value, table cell, money cell and `next` sentence in the fixture is on the page.
- One h1 per page, no sideways scroll (`scrollWidth <= innerWidth`), and axe (wcag2a/2aa/21a/21aa/22aa) returns `[]`.
- W-3901:
  - The agent card shows Chidi, WORKING, "Started 10:05", "PPE_REGISTER_OCT.XLSX · 64 ASSETS", "PPE-0005", "VALUES NOT READ" and the "never reads asset values" note.
  - "Ask Chidi" has href `/assistant`.
  - No claim or decision is sent.
- W-3904: no claim or decision is sent.

**2. Register review, approve, then date review, approve: pass at both widths**
- W-3902:
  - Exactly one claim, `POST /api/v1/tasks/T-3902/claim` `{"expected_revision":1}`, with `X-CSRFToken: mock-csrf-finance_lead`.
  - A double click plus a third click on "Approve register" sends one `POST /api/v1/tasks/T-3902/decision` with body `{"expected_revision":1,"verdict":"approve"}`: no note and no extra keys.
  - The re-read draws "WAITING FOR DATE EXPLANATIONS", the notice "October register is approved", and "Waiting for someone to explain the 3 unclear in-service dates and attach the proof. The date review starts after that."
  - Afterwards there are no decide buttons, no file input and no explain or upload control (G-55-1 is held).
  - A reload sends no further claim.
- W-3903:
  - One Decide panel, and one claim (T-3903 only; nothing for T-3931).
  - The proof row reads "asset-dates-explanation.pdf" with "Uploaded · 64 KB" and is not a link.
  - The basis "Approve the explained dates. Depreciation starts from these dates." is shown as returned.
  - A double click on "Approve dates" sends one T-3903 decision, `{"expected_revision":1,"verdict":"approve"}`.
  - The re-read shows "PROCESSING" and "REGISTER · APPROVED", and the notice "October in-service dates is approved".
- Writes for the whole journey, in order: claim T-3902, decision T-3902, claim T-3903, decision T-3903.

**3. Return and reject, on W-3902 (T-3902) and W-3903 (T-3903): all 8 runs pass at both widths**
- Desktop uses the side panel; phone uses the bar and the full-height Drawer.
- An empty note sends nothing. "Add a note to return it." (or "…reject it.") appears, the textarea gets focus, `aria-invalid="true"` and `aria-describedby` point at the message, and axe is clean with the error shown (with the Drawer open on phone).
- A note of only spaces sends nothing. A 2001-character note shows "Keep the note to 2000 characters or fewer." and sends nothing.
- A valid note sends one POST, `{"verdict":"return"|"reject","note":"The Hilux sale proof is missing; attach it.","expected_revision":1}`, trimmed, with the CSRF header.
- The re-read shows "RETURNED" (with the sidecar's quote) or "REJECTED". There is no "Correct and resubmit" and no decide buttons afterwards.

**4. Holds, W-3907, W-3908, W-3909: pass**
- Each shows "SETUP NEEDED", the "Why it's held" fact ("Who reviews assets", "Register rules" or "Calculation rules") with "NOT SET", and the `next` sentence as returned.
- `main` has no buttons at all: no Decide panel and no "See all exceptions" (UX-1-1).
- No "PPE reviewer", "Decide ·", "Ada Okafor" or "Bisi Ade" appears in main.
- W-3909 shows no PROCESSING, no "REGISTER · APPROVED" and no ₦ figure.
- Zero task POSTs, no sideways scroll, and axe is clean at both widths.
- At 390, the one target under 44px is the frame's History link (QA-2-1).

**5. Unknown cost, W-3910: pass at both widths**
- The Toyota Hilux row reads "Toyota Hilux · A-0388 Disposed 20 Oct Unknown".
- There is no ₦0, 0.00 or dash, and "₦14,000,000.00" is absent.
- The other costs read "₦8,400,000.00" and "₦3,150,000.00".

**6. Uncertain decide, W-3911: pass for approve, return and reject at both widths**
- Each verdict shows "October register: result not confirmed" and the backend's "DECISION NOT CONFIRMED".
- No "is approved", "returned" or "rejected" appears. The only "APPROVED" on the page is the lifecycle label, whose value is "Not yet".
- Axe is clean. Exactly one decision is sent, and still one after 4 s idle and a reload.
- After a reload the page still shows DECISION NOT CONFIRMED with no decide button.
- The direct call `POST /tasks/T-3911/decision` answers 200 with `work_state: effect_uncertain`.

**7. Decide failures on W-3902: pass at both widths**
- The failures were forced with a routed `X-Mock-Scenario`, or with `route.fulfill(500)` / `route.abort('failed')`.
- **409:**
  - The stale view "This review changed while you were reading it, so nothing was recorded. Review the latest" appears, with no resend.
  - After "Review the latest", the textarea still holds "Keep this note.". That press sends a new claim; the decision count stays 1.
- **422:** "Check the highlighted fields and try again." (the mock's 422 body) appears under the note, the note is kept, and the status is unchanged.
- **500 and network:**
  - The page re-reads the item; there are 4 GETs of `/api/v1/work/W-3902` by the end.
  - It shows "We couldn't confirm your decision. We've reloaded this item so you can see whether it was recorded." and no success wording.
  - Axe is clean. There is exactly one decision POST, including after 62 s of waiting in the network case.
- **403:** "This decision needs a PPE reviewer. You can't approve, return or reject it." with no success wording.
- **401:** the page shows signed out, with sign-in href `/accounts/login/?next=%2Fwork%2FW-3902`.

**8. Read access on W-3902: pass at both widths**
- **401:** "You're signed out. Sign in".
- **403 and 404:** the same "NO ACCESS · You can't open this work item" view (see QA-2-3 for one earlier exception at 390). Axe is clean.
- **500:** "ERROR · COULDN'T LOAD … Try again", and Try again then loads the item.
- No title, PPE-0006, cost, asset name or "Register changes" appears in any of these, and no task POST is sent.
- **Persona none:** "No sections are open to your role yet." with zero `/api/v1/work/` calls.

**9. Cannot act, at 1440: pass**
- W-3905 shows "You prepared October register, so someone else must review it."
- W-3912 shows "You prepared October in-service dates…".
- W-3906 shows "This decision needs a PPE reviewer. You can read it, but you can't approve, return or reject it."
- W-3901 and W-3904 have no review to act on.
- None of these pages has a decide button, and none sends a task POST, even after typing in any textarea.
- Direct calls: claim and decide on T-3905 → 403, and decide on the decided T-3931 → 403.

**10. Personas ceo and pm, W-3902: pass**
- Both get the same three buttons ("Approve register", "Return with a note", "Reject") and one claim.

**11. Costs exactly as returned: pass**
- Default page text matches the fixture digit for digit at both widths: "₦8,400,000.00", "₦14,000,000.00", "₦3,150,000.00".
- With the response rewritten to `"14000000.10"`, the page shows "₦14,000,000.10" and no "₦14,000,000.00", at both widths, with no short "M" form.

**12. Phone, 390**
- The Decide bar is `position: fixed` and holds the step labels.
- "Return with a note" and "Reject" open a 390×844 Drawer. Escape and Cancel close it and return focus to the opening button.
- There is no sideways scroll on any page tested.
- 44px targets: every control except the frame's History link (QA-2-1). The skip link is off-screen at y=-34 and only appears on focus.

**13. Direct API checks (curl against :4982)**
- A claim without the CSRF header gets 403 `csrf_failed`.
- Return with no note gets 422, and reject with a blank note gets 422.
- An extra body key (`amount`) gets 422.
- A repeat approve after a decided approve gets 409 `stale_revision`.

**14. Income line, F-33: pass at both widths**
- W-2701..W-2704 show their fixture status labels and `data-line="income_schedules"`.
- Claims equal the tasks with `you_can_act: true`.
- No sideways scroll, and axe is clean.
- F-42's only change to an F-33 test widens one fixture-name regex from `^W-27` to `^W-(27|39)` (tests/income-schedule-mock.test.ts:106). The W-2706 assertions are unchanged.

## Findings
- QA-2-1 | non-blocking | low | frontend | The frame's "History" link is under the project's 44px phone rule. Expected: at least 44 by 44 px (D-92c). Actual: 42×24 at 390 on every F-42 page and on F-33's W-2702. It still passes WCAG 2.2 AA target size (24px). It is shared F-17 frame code (`frontend/src/features/work-item/work-item.css:406`, `WorkItemView.tsx:151`), outside this feature's lane, and the builder's e2e excludes it explicitly (`e2e/asset-schedule.spec.ts:220`). It needs a frame-wide fix.
- QA-2-2 | non-blocking | low | frontend | On the proof row, the file name is moved first with CSS `order: -1` (`frontend/src/features/workspace/workspace.css:282`), so the DOM order is "Uploaded · 64 KB" and then "asset-dates-explanation.pdf". A screen reader reads the detail before the file name. Expected: the reading order matches the visual order, with the file name first in the DOM.
- QA-2-3 | non-blocking | low | integration | Once, in run1 at 390, a forced 404 read showed "ERROR · COULDN'T LOAD … Reference unexpected_response" instead of the NO ACCESS view. That was at load average about 300. It did not recur in 4 later tries at 390 or in any try at 1440. No title, cost or asset leaked. I'm recording it as possible flakiness of the proxy or client under load, not as a defect.

## Verified
- UX-1-1 | verified | On the real stack, `main` on W-3907, W-3908 and W-3909 has no buttons and no "See all exceptions", at 1440 and 390. Income pages W-2701..W-2704 are unaffected.
- UX-1-2 | verified | After "Approve register" on W-3902, the re-read shows "Waiting for someone to explain the 3 unclear in-service dates and attach the proof. The date review starts after that.", with no decide control.
- UI-1-1 | verified | The W-3903 page text has "asset-dates-explanation.pdf" with "Uploaded · 64 KB", and the file name is not a link. I did not judge the visual style; the UI review covered it. The reading order is noted in QA-2-2.
- TECH-1-1 | carried | The fixture facts change is confirmed by the technical review. On the W-3911 pages I saw the lifecycle "APPROVED" stay "Not yet".

## Update for head 8d59b242 (diff c972854d..8d59b242)

- The head moved only by merging dlv-00 (F-47 Start work proof upload, F-41 payments list and reminder, test fix #65). Frontend diff re-read at Workspace.tsx, Sections.tsx, workspace.css, workspace.mjs, proposals.ts and the mock-contract lists.
- F-42 decide in place, holds, proof row and money rules are intact; F-41 reminder line, phone Drawer and attachment row and F-33 income line are intact; the proof row and attachment row stay distinct; no assertion was loosened (the only edit is the sample:false case for W-3813).
- Vitest on asset-schedule, income-schedule, payments, payment-reminder, workspace and mock-contract files: 11 test files passed (586 tests). checks.sh 2655 and e2e 142 passed on this head.

Verdict unchanged.
