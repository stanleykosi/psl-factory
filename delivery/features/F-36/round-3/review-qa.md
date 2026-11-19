VERDICT: PASS
REVIEWER: qa
COMMIT: ba1ee621c715fa9ca4cfdbd22cf22f2620028305
AUTHORITY: delivery integrated QA

## Summary
- Tested a production build of the worktree frontend (`API_ORIGIN=http://127.0.0.1:4990 FRAME_FIXTURES=1 npm run build && npx next start -p 4991`) against the contract mock on 4990 (`MOCK_PORT=4990 node mock/server.mjs`). I signed in as `psl_mock_persona=pmo_lead` and drove Playwright Chromium at 1440 and 390. The script was `qa4.cjs` and its output is `qa-run4.txt`, both in `/private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/qa-f36/`. It ran 123 checks: 115 passed and 8 failed. All 8 failures came from my script, not the product (details under Journeys).
- QA-2-1 is fixed. When the server refuses "You are assigning as", the proof, or both with a 422, the panel shows:
  - its own words under the right field;
  - a "1 thing to fix" or "2 things to fix" summary whose links go to those fields;
  - focus on the first named field, with every entry kept;
  - no raw field names, at both widths.
- QA-2-3 is fixed. "Nothing was changed." appears once on the item-read error card.
- The regression pass is clean: assign success, 409, uncertain, written-then-500 and the phone layout. `E2E_PORT=4992 MOCK_PORT=4993 npx playwright test e2e/rfp-assign.spec.ts`: 24 passed. `test-results` deleted, my servers stopped.
- Not proved (unchanged from round 2):
  - real backend authority, candidate rule, tenant isolation and overlay fields (mock only);
  - real alert sending and real evidence storage;
  - the 60-second single-POST rule (unit test only);
  - screen readers, and browsers other than Chromium.
  QA-2-2 (37px summary links on the phone) stays open in the shared component. It now also applies to the new role and proof summary links.

## Journeys
**422 on the role (W-3302, real mock; the outgoing body was rewritten to `acting_role: "cfo"`)**
- The server answered 422 `{"code":"invalid","message":"Check these fields: acting_role.","fields":[{"name":"acting_role","message":"Check acting_role."}]}`.
- The panel shows "1 thing to fix · Choose a role you may assign as.", with the same words under "You are assigning as".
- No "Check these fields", `acting_role` or "cfo" text appears.
- The summary link goes to `#assign-pm-role`, and clicking it focuses the role list.
- After the reply, focus is on `#assign-pm-role`.
- Tunde Bello, CEO, the uploaded file chip and the note "kept note" are all kept.
- Axe is clean. Same result at 1440 and 390, with no sideways scroll (390 of 390).

**422 on the proof (W-3302, `evidence_id: "EV-NOPE"` after a real upload)**
- The panel shows "1 thing to fix · Remove the file, or add it again.", with the same words under the proof.
- The link goes to `#assign-pm-proof`, and focus is on the proof block.
- Entries and the chip are kept, there are no raw names, and axe is clean at both widths.

**422 on both**
- The panel shows "2 things to fix" with both links, in order role then proof. Each link focuses its field.
- Focus starts on the role list, entries are kept, there are no raw names, and axe is clean at both widths.

**422 on the role shown as plain text (W-3301, a routed 422 with message "Check these fields: acting_role." and the field message "RAW-BACKEND acting")**
- The panel shows its own words under the plain-text "PMO Lead" row and a linked summary to `#assign-pm-role-text`, with focus there.
- There is no raw text, the note is kept, and axe is clean at both widths.

**Item read 500 (QA-2-3)**
- The card reads "We couldn’t load this item. Nothing was changed. / Retry". The sentence appears once, there is no form, and axe is clean at both widths.

**Regression**
- Assigning on W-3302 with CEO and the proof at 1440 and 390:
  - a double click sends one POST with `{"expected_revision":1,"person_id":"P-0007","acting_role":"ceo","evidence_id":"EV-C-3302-1","case_revision":2}` and `X-CSRFToken: mock-csrf-pmo_lead`;
  - the notice reads "TL-RFP-2026-014 is now with Tunde Bello." and the panel closes;
  - at 390, every target is at least 44px after the upload, there is no sideways scroll and axe is clean.
- 409 (`psl_mock_assign=stale`):
  - the panel shows "This changed while you were working. Showing version 2.", Sola Martins stays chosen and there are no success words;
  - the retry sends `expected_revision: 2` and succeeds.
- Uncertain (`psl_mock_assign=uncertain`, 1440 and 390):
  - the panel shows "Not confirmed" and "Try again", the entries are kept, there are no success words and nothing is resent within 3.5 s;
  - "Try again" sends exactly one more POST;
  - at 390 every target is at least 44px, and axe is clean.
- W-3306 shows "Assigned to Tunde Bello" and "Not confirmed at first; confirmed after reading it again."
- e2e `rfp-assign.spec.ts`: 24 of 24 passed, including the builder's new 422-on-both, focus and axe test.

**Script failures (mine, not the product)**
- 4 failures: my "focus moved off the button" check treated the role list, which is a button element (`#assign-pm-role`), as the "Assign PM" button. The "focus on first named field" check passed in the same runs.
- 4 failures: my phone check was meant to skip the summary links but missed them because their names were cut short. They are the known 37px QA-2-2 links ("Choose a role you may assign as." 206x37, "Remove the file, or add it again." 197x37). Every other target was at least 44px.

**Carried forward from round 2 (impact assessment)**
- Round 3 changed only `AssignPmDrawer.tsx`, `rfp-assign.test.tsx` and `e2e/rfp-assign.spec.ts` (`git diff --stat 5e14a6ad 4f53c9f1`).
- The drawer change touches only:
  - how it handles a 422 that names the role or the proof (summary, words under the field, focus);
  - the ids on the role and proof blocks;
  - the error card's text.
- It does not touch the list, how the panel opens or closes, the PM options, the "What happens next" wording, the access views (401, 403, 404, W-1099), the network and 502 handling, the no-`assign` items, W-3304, or F-30's W-2413 and F-31's W-2601.
- Those round-2 results stand. The e2e suite and the regression pass above re-cover the shared paths.

## Findings
None.

QA-2-2 (non-blocking, shared `ValidationSummary` link height on the phone) is still open outside this lane. It now also covers the role and proof summary links.

## Verified
- QA-2-1 | verified | The real mock's 422 on `acting_role`, on `evidence_id` and on both (W-3302), and a routed 422 on the plain-text role (W-3301), at 1440 and 390, gave the same result: own words under the field, a "N thing(s) to fix" summary with working links (`#assign-pm-role`, `#assign-pm-proof`, `#assign-pm-role-text`), focus on the first named field, PM, role, file and note kept, no "Check these fields" or raw names, and axe clean. e2e 24 of 24 passed.
- QA-2-3 | verified | An item-read 500 on W-3301 shows "Nothing was changed." exactly once ("We couldn’t load this item. Nothing was changed. / Retry") at 1440 and 390, and axe is clean.
