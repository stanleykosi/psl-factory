VERDICT: CHANGES
COMMIT: 06b4c0e93bbc3083cea431c2f022c1e267486f24
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (UI-only feature: shared next build on 4111 against the contract mock on 4112)

## Summary
- I tested the shared build at http://localhost:4111 (next-server, cwd `f-11/frontend`, `.next/BUILD_ID` built 08:09, after the head commit at 08:03) with the contract mock at http://127.0.0.1:4112. I reset the mock before and after every state-changing journey. All 15 tests in `e2e/setup.spec.ts` pass against it (temporary scratchpad config, since deleted).
- Almost everything behaves as specified, checked both by direct API calls and in the browser:
  - all three rule views, and counts that come only from the count fields;
  - a first save at `expected_revision: 0` (one PUT, CSRF, the exact body with `reason` and `evidence_id`, then v1, the badge and banner at 7, focus on the status message);
  - a real two-tab 409, and the stale and invalid save cookies;
  - all three uncertain-result branches, plus a 404 on save and a 401 on save;
  - a double click sending one PUT;
  - Proof with and without `proof_case`, and a 422 on upload;
  - per-row editor gating, with admin and finance_lead giving identical markup;
  - pm and none blocked with no rules request;
  - phones read-only at 390 even with editable data;
  - keyboard paths.
- One blocking defect. When a 403 on save takes away the last editable row (the "wrong user" case: the right is withdrawn while the person is editing), the whole "Set a rule" panel disappears. The API message is never shown, the person's ticks and Why are thrown away without explanation, and focus falls to the page body.
- What remains unproved: no real backend. T-SETUP, `proof_case`, the `cursor` parameter and `expected_revision` minimum 0 are proposals the mock implements. A real tenant boundary isn't tested (the mock has no tenants; per-persona isolation of saves was checked instead). There was no real evidence store, and no live CSRF/session (mock tokens only).

## Findings
- QA-1-1 | blocking | medium | frontend | A 403 on save that leaves no editable row hides the 403 message. Steps: as admin, open `/setup/rules` at 1440. Then, with the page still open, set `psl_mock_setup=readonly` (the right is withdrawn). Tick PMO Lead, type a Why and click "Save as version 1". Expected (spec, PUT responses table, 403 row): "Show the API message in the alert and re-read the list (the row will normally lose its editor)", with focus on the callout. Actual: the PUT returns 403 and the list is re-read. Because `editable.length` is now 0, `RulesView` unmounts `SetRulePanel`, and the alert holding "Your role does not allow this." goes with it. `main` contains no such text, the only `role=alert` on the page is Next's empty route announcer, and focus is on `body`. The ticks and Why vanish with no explanation. The same applies on Finance when a group's only editable row loses its right (the panel only renders while `editable.length > 0`). The unit test "403 shows the message and reloads; the row loses its editor" (tests/setup-rules.test.tsx:387) only covers the case where other rows stay editable. When I routed a 403 while the data stayed editable, the message showed with focus on the alert, so the gap is only the unmount. Paths: frontend/src/features/setup/RulesView.tsx:106-108, frontend/src/features/setup/FinanceRulesView.tsx:111-126 (gating), frontend/src/features/setup/SetRulePanel.tsx:111 (the message lives in panel state). Expected fix: keep the outcome message visible after the editor goes away, for example by lifting the notice into the view or showing a page-level `role="alert"` callout that takes focus. Add an e2e or unit test with every row losing `can_change`.
- QA-1-2 | non-blocking | low | integration | `/__mock/reset` does not reset the evidence id counter. The first upload after a reset answered `evidence_id: "EV-2"` (and `EV-4` later in a session), so ids depend on earlier runs. The case revision counter does reset (`case_revision` 1 is accepted again). This is harmless to the UI but makes evidence ids non-deterministic across test runs. Path: frontend/mock/evidence.mjs (counter is outside `resetSetup`).

## Verified
None (round 1).

## Evidence
Setup: `curl -X POST http://127.0.0.1:4112/__mock/reset` gave 204 before and after each journey. Nothing was started or stopped. The scratchpad scripts, results and screenshot are deleted, and the worktree is clean.

**E2E against the shared build**
- `cd frontend && MOCK_PORT=4112 npx playwright test --config <scratchpad>/pw.config.mjs`, using baseURL http://localhost:4111, testMatch `setup.spec.ts` and no webServer.
- Result: 15 passed (46.9s). This covers AC 1, 2, 5, 8, 10, 11, 14, 16-21 and 24, including axe at 1440/390, the keyboard test and the 401 sign-in link.

**Direct API calls (curl through 4111 `/api/v1`)**
- GET `/setup/rules`:
  - admin 200 and finance_lead 200; pm 403 and none 403;
  - admin: 10 items, `not_set_count` 8, `roles_missing_count` 2;
  - `area=finance`: 25 items, count 25. `area=delivery`: 5 items, count 4. `area=bogus`: 0 items, no count;
  - `psl_mock_setup=forbidden` as admin: 403 forbidden.
- PUT `presale.rfp_assigner`:
  - CSRF: no CSRF header gives 403 `csrf_failed`. The finance_lead token sent as admin gives 403 `csrf_failed`;
  - personas and editability: pm and none with their own tokens get 403 forbidden. The readonly scenario gets 403. The `can_change:false` row `finance.short_payments` gets 403, and so does the link row `presale.costing_rule`;
  - invalid input: an unknown component gives 404. `expected_revision` -1 and "0" give 422 "Check these fields: expected_revision.". The role `admin` (not in the options) gives 422 `value.roles`;
  - wrong revision: `expected_revision` 1 on a rev-0 row gives 409 `stale_revision`. A GET afterwards shows the row still `set:false`, rev 0, count 8 (nothing changed);
  - first save: `expected_revision` 0 gives 200 `{revision:1}`. The GET shows `set:true`, rev 1, "PMO Lead", `effective_from` 2026-11-14T00:00+01:00, `holds_work:false`, `selected ['pmo_lead']`, count 7;
  - replaying the identical PUT gives 409, so there is no duplicate version;
  - finance_lead still sees rev 0 and count 8, so saves are kept per persona;
  - the save cookies: `invalid` gives 422 "Check these fields: reason, starts." and `stale` gives 409.
- POST `/cases/C-SETUP-1/evidence`:
  - no CSRF gives 403 `csrf_failed`, and pm gives 403;
  - admin at `case_revision` 1 gives 200, with a sha256 equal to `shasum -a 256` of the content and `case_revision` 2;
  - the same request again gives 409;
  - case C-NOPE gives 404, and a body missing fields gives 422 naming `content_base64` and `case_revision`.

**Browser journeys (Playwright chromium, 1440x900 unless stated)**
- J1, admin, first save and Proof:
  - `/setup` lands on `/setup/rules`. The picker holds exactly the 4 editable rows. The costing link row and the read-only rows are absent;
  - "Who may record an RFP outcome" has no `proof_case`: the drop reads "Proof can’t be attached here yet.", with `aria-disabled="true"` and no file input;
  - "Who may assign an RFP to a PM" starts with no ticks. Two uploads go to `/cases/C-SETUP-1/evidence` with kind `rule_proof` and CSRF, at `case_revision` 1 then 2. The box then reads "proof2.bin Uploaded · 3 KB";
  - by keyboard (Space on PMO Lead, then Tab moves through the next two checkboxes to Starts, type the Why, Enter on Save), one PUT is sent: `{"expected_revision":0,"value":{"roles":["pmo_lead"]},"starts":"2026-11-14","reason":"QA first save","evidence_id":"EV-4"}` with `X-CSRFToken: mock-csrf-admin`. The Why was trimmed;
  - "Saved as version 1." appears with focus on the `role=status` callout. The row reads "PMO Lead v1 · since 14 Nov" without HOLDS WORK. The Rules badge reads 7 and the banner "7 rules aren’t set yet". The button reads "Save as version 2" and Why is cleared.
- J1, real concurrency: a second tab saved v2 (PMO Lead, CEO). The first tab then ticked PMO, typed a Why and saved at rev 1. Result: one PUT and one GET; the alert reads "Someone changed this since you opened it…"; the row shows "PMO Lead, CEO v2"; the ticks were reset to the reloaded selection (PMO unticked); Why is cleared; the button reads "Save as version 3".
- J2, uncertain, PUT aborted (network): the requests were GET, PUT, GET (one re-read). The message reads "We couldn’t confirm the save. Nothing new is shown for this rule, so you can save again.". The ticks and Why "net fail" were kept and Save stayed enabled. No resend happened in 2s; the next click sent the 2nd PUT, which returned 200.
- J3, uncertain, the PUT reached the mock and then a routed 500 came back: the message reads "This rule changed. Check the version shown before saving again.". Why is cleared, the ticks equal the reloaded selection, the row shows v1, the button reads "Save as version 2", and there was 1 PUT.
- J4, uncertain with a failed re-read: "We couldn’t check whether the save went through. Reload the page before saving again.". Save is disabled and the rows stay. Picking another rule re-enables Save.
- J5:
  - 404 on save (routed) plus a double click: one PUT and one re-read; the alert reads "We could not find that record.";
  - 401 on save: SignedOutState with the link `/accounts/login/?next=%2Fsetup%2Frules`;
  - 403 with the data still editable (routed): the alert message is shown, focus is on the alert and the Why is kept;
  - 403 with the right withdrawn (readonly): see QA-1-1.
- J6, upload answered 422 (routed): the file input gets `aria-invalid="true"` and "Check these fields: content_base64." shows. Save still worked, and the body had no `evidence_id`.
- J7, personas on `/setup/rules`:
  - admin and finance_lead: the same h1, badges and 4-item picker, and identical `.setup-desktop` markup length (5727). No `/me` role effect;
  - pm: "This section isn’t open to your role. Go to My work", with 0 setup requests and no rule names;
  - none: "No sections are open to your role yet…", with 0 setup requests.
- J8, phone at 390x844, admin, desktop (editable) data:
  - rules shows "Rules · 8 not set", finance "Finance rules" and delivery "Delivery rules";
  - no visible input, select or button on any of the three, `scrollWidth` 390, and no writes;
  - 40 Tab presses never put focus on a hidden desktop control.
- J9, Finance as finance_lead: Enter on "Set BU totals rules" sets `aria-expanded` to true and opens one panel limited to "Who reviews BU totals". Saving sent `{"expected_revision":0,"value":{"roles":["finance_lead"]},"starts":"2026-11-14"}` with `mock-csrf-finance_lead` and returned v1. The callout then read "24 values are Not set…". Enter again collapsed it (`aria-expanded` false).

## Notes
- The prior non-blocking findings (SEC-1-1, TECH-1-1 to TECH-1-4) were not retested as findings. QA-1-1 is a different path from TECH-1-1.
