VERDICT: PASS
COMMIT: df180ca0716d9a70e19bc82f5df57cce37e99aeb
REVIEWER: reviewer-qa
AUTHORITY: integrated QA

## Summary
- I tested the shared production build at http://localhost:4631 against the mock at http://127.0.0.1:4632. The build is from the worktree `f-16/frontend`, built at 21:44 after head df180ca (committed 21:34), and the tree is clean. I reset the mock (`POST /__mock/reset`) before and after every journey that changes data. I used headless Playwright from the worktree's node_modules with a scratchpad config and no webServer. The project was named `f-16-qa`, the timezone was Africa/Lagos, and I did not start or stop any server.
- **The decide behaviour is unchanged.** Each action sent exactly one claim and one decide, both with the `/me` CSRF token and `expected_revision`. Approve sends no note unless one is typed. Return and reject send nothing until a non-blank note is given. The note is capped at 2000. A 409 shows the stale view with one reload and no retry. An uncertain effect gets one reload and no resend. A 422 shows the server message and keeps the note. A 403 on decide reloads the item and shows it read-only. A 409 on claim goes to the stale view with no decide. `useDecision.ts`, `format.ts`, `DecidePanel` handlers, `src/api`, `src/shell`, `src/features/work-item`, `mock/server.mjs`, `tests/decide.test.tsx` and `e2e/decide.spec.ts` have no diff against base 6282bb2. The only DecidePanel change is a class name.
- Full Playwright suite against the build: 288 passed, 5 failed. None of the 5 is in decide, decide-board, work-item or work-item-board: those specs passed 21, 20, 23 and 39 tests. One failure is the environment: `frame.spec.ts:260` opens `/frame-fixtures/phone-back`, which returns 404 because the shared server runs without `FRAME_FIXTURES=1`, as F-15 QA also found. The other four (`overview.spec.ts:126`, `projects.spec.ts:152/199/421`) also fail on base sources, as F-15 round 1 build.md recorded. Base has since fixed them (PR #25), and F-16 picks the fix up when it merges base. F-16 touches none of those files.
- Axe (wcag2a/2aa/21a/21aa/22aa) found 0 violations, with no sideways scroll, at 390 and 1440 on these pages: default W-1901, done, stale W-1902, not-yours W-1903, own W-1904, no-access (403 and 404), the 401 signed-out view, the 500 error card and the work item page W-1201.
- Not proved here: this is UI against the contract mock, not the Django backend. Wrong user and wrong tenant are proved only as far as the mock enforces fixture eligibility (`you_can_act`) and CSRF. No real provider is involved. The fixture-only PROPOSAL fields (queue, agent, comment) have no live source yet.

## Findings
None.

Known and non-blocking, not re-raised: UI-2-1. On phone done, the Paid sentence shows twice: once in the next-step card and once as its own line (`qa-evidence/done-390.jpg`). On desktop it shows once (measured count 1 at 1440, 2 at 390).

## Verified
- UX-1-1 | verified | After Approve on W-1901, `document.activeElement` is the H1 "Invoice v2 for Lagoon Health is approved" at 1440 and 390. Exactly one `role="status"` element reads "Your decision was recorded.". On stale W-1902, focus moves to the stale heading (H2) at both widths.
- UX-1-2 | verified | Each view has one h1 "Decision" inside `main`: the 500 card (route returns 500 for `GET /api/v1/work/W-1901`) and the 401 view (route returns 401 for the item only). With the 401 scenario cookie, `/me` also returns 401 and the frame-level signed-out view shows instead. That view has no page h1, but it is frame-owned and unchanged. Its sign-in link keeps `next`.
- UI-1-1 | verified (behaviour only) | The done next-step card shows Chidi's done pose on the blue surface (`qa-evidence/done-390.jpg`, `done-1440.jpg`). Fidelity scoring is the UI lens.
- UI-1-2 | verified (behaviour only) | On phone stale, the agent note sits inside the VERSION 3 · CURRENT card, with the Amount in mono and small "unchanged"/"changed" marks (`qa-evidence/stale-390.jpg`).
- Paid twice on desktop done | verified | The 1440 done page has 1 visible "Paid is tracked separately" sentence.

## Evidence
Command (worktree `frontend/`): `npx playwright test -c <scratchpad>/qa.config.ts`. The config had the journey spec, baseURL :4631 and no webServer. Result: 25 passed, 2 failed. Both failures were my own over-strict regex on the not-yours alert line. The page reads "Ada Okafor (Finance Lead) was alerted at 12 Nov 10:42 by WhatsApp and email" because the fixture time is not today, which is `formatClock` behaviour unchanged from F-14. I re-probed both widths: the copy, the disabled comment box and zero writes all hold. Log: `qa-evidence/qa-journeys.txt`.

- **Default W-1901** (1440 and 390). On load: 1 `POST /api/v1/tasks/T-1901/claim` with body `{"expected_revision":2}` and `x-csrftoken` equal to the `/me` token. Approve v2 with no note: 1 `POST .../T-1901/decision` with body `{"expected_revision":2,"verdict":"approve"}` and the same CSRF. The done page shows "Next decision · 2 of 3" linking to `/work/W-1201/decide?task=T-1201`, plus "Open the work item" and "Back to my work". The YOU APPROVED banner is green.
- **Note rules** (W-1201):
  - Approve with the note "PO number checked" sends `note` once.
  - Return and Reject, with an empty or blank note, send 0 decides, show "Add a note to return or reject." and focus the textarea.
  - With the note "Wrong PO", each sends exactly one decide `{verdict, expected_revision:2, note}`. The h1 reads "Invoice v2 was returned" / "was rejected" with no success banner.
  - The note is `maxlength=2000`: typing 2005 characters leaves 2000 and the counter reads "2000 / 2000".
  - With the 422 scenario cookie: 1 decide, the alert "Check the highlighted fields and try again.", and the note is kept.
- **Stale W-1902.** Approve sends 1 decide, which gets a 409. That is followed by exactly 1 `GET /api/v1/work/W-1902`. The page shows VERSION 2 · REPLACED and VERSION 3 · CURRENT with changed/unchanged marks. No second decide is sent. "Review version 3" claims `{"expected_revision":5}`, after the first claim `{"expected_revision":4}`, and enables Approve v3. The decide count stays 1.
- **Uncertain effects** (W-1201):
  - The route lets the decide reach the mock and then answers 502. Requests: claim, decision, then 1 GET of the item. There is no resend. The reloaded page shows "We couldn’t confirm your decision…" and the ALREADY DECIDED view, with Approve gone (`qa-evidence/uncertain-recorded-1440.jpg`).
  - Network abort: 1 decide and 1 reload.
  - Decide and reload both fail: Approve, Return and Reject are all disabled. Try again sends no decide (the count stays 1).
- **Other failure paths.**
  - 403 on decide: 1 decide, 1 reload, then the read-only "NOT YOUR DECISION" view with 0 Approve buttons.
  - 409 on claim: the stale view after 1 reload, with 0 decides.
- **Not-yours W-1903** (1440 and 390):
  - No Approve, Return or Reject buttons.
  - The page shows "NOT YOUR DECISION", "This decision needs a Finance Lead." and the alert line above.
  - The textarea and "Add comment" are `disabled`, and "Comments aren’t available yet." is linked by `aria-describedby`. A forced click on both, plus typing, sent 0 non-GET requests and 0 claims.
- **Own W-1904** (both widths): no controls and 0 writes.
- **Wrong user and authority** (direct API against the mock):
  - pm persona decides on T-1903: `403 {"code":"forbidden","message":"Your role does not allow this."}`.
  - Decide without CSRF: 403. Decide with `expected_revision:1`: 409.
  - In the UI, eligibility comes from the fixture, not `/me`. The ceo persona on W-1901 gets 1 Approve. The pm persona on W-1903 gets 0.
- **No access.** With the item routed to 403 or 404, the page shows the one h1 "You can’t open this work item" (40px at 1440, 26px at 390) and the phone bar "← Queue". INV-0412 and Lagoon do not appear, and there are 0 writes. The 403 scenario cookie (which affects `/me` too) gives the frame's "Your account can’t use PSL Factory." view.
- **500 then retry.** The error card reads "We couldn’t load this decision. Your work is safe; nothing was changed." There is no claim while it shows. Try again loads the item, sends 1 claim and 0 decides, and enables Approve v2. Both widths.
- **Unknown amounts.**
  - W-1202 reads "Amount | Unknown", with no ₦0.
  - W-1901 with the amount set to `{unknown:true}` in transit: "Unknown" shows, with no ₦0 and no ₦4,250,000.
- **F-14 seam.** `/work/W-1201` at 1440 and 390 shows ₦4,250,000.00, 0 writes and 0 axe violations. The decision link `/work/W-1201/decide?task=T-1201` navigates. `src/features/work-item/**` has no diff. `work-item.spec.ts` passed 23 tests and `work-item-board.spec.ts` passed 39.
- **Full suite.** Command: `MOCK_PORT=4632 npx playwright test -c <scratchpad>/pw.config.ts` (testDir is the worktree `e2e`, baseURL :4631). Result: 288 passed and 5 failed (listed above). Re-running only the failures (`--last-failed`) gave the same 5. Scratch configs, `test-results` and probe scripts were deleted. The mock was reset afterwards (204).

## Notes
- For the integration owner, as F-15 QA already noted: start the shared review server with `FRAME_FIXTURES=1` so that `frame.spec.ts:260` can run against it.
- F-16 is not yet on the current base. Base has the F-15 bookkeeping and the e2e fix PR #25. Spec criterion 21 asks for the 390 e2e and axe run to be repeated after F-15's shell merges.
- The done banner time comes from the mock's `decided_at`, so it shows the real current time, while the facts strip shows the fixture's "10:47". This is mock behaviour and is unchanged from F-04.
