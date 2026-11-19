VERDICT: CHANGES
REVIEWER: qa
COMMIT: 5e14a6ada5bd803586a0ced36e05176e8f84f66c
AUTHORITY: delivery integrated QA

## Summary
- Tested on a production build of the real frontend (`API_ORIGIN=http://127.0.0.1:4990 FRAME_FIXTURES=1 npm run build && npx next start -p 4991`) against the contract mock on 4990, as `psl_mock_persona=pmo_lead`, in browser session `F-36-qa` (Playwright Chromium, timezone Africa/Lagos). Three scripts ran 113 checks in total and 101 passed. Of the 12 failures, 6 came from my own setup and 6 are product problems: 4 runs hit the blocking QA-2-1 and 2 hit the minor QA-2-2.
- Blocking (QA-2-1): when the backend refuses "You are assigning as" or the proof with a 422, the panel shows the mock's raw sentence "Check these fields: acting_role." (or "evidence_id"). There is no "things to fix" summary and focus stays on "Assign PM". The messages under each field are the page's own words, and the person's entries are kept. A 422 on the PM or the note works correctly: summary, own words, focus moved, entries kept.
- Everything else asked for passed:
  - the panel over the list, with nobody pre-chosen;
  - the proof upload, and "What happens next" exactly as returned;
  - a double press sends one POST, with the CSRF token and the right revision;
  - 409, 5xx, network and uncertain results, with the read-back line still there after 17 s;
  - an item without `assign` has no control;
  - 401, 403 and 404 leak no names;
  - 390 phone targets, including the chip "×" at 48x48, with no sideways scroll;
  - axe at both widths;
  - F-30's W-2413 and F-31's W-2601 behave as before.
- Tests: targeted vitest 13 files, 746 tests passed. Playwright (`E2E_PORT=4992 MOCK_PORT=4993`) on rfp-assign, my-work, issue-detail, response and engagement-planning: 101 passed. `test-results` deleted, my servers stopped.
- Not proved:
  - a real backend's assign authority, candidate rule, tenant isolation and the G-24-1, G-24-2 and G-24-3 overlay fields (mock only);
  - real alert sending (nothing is sent);
  - real evidence storage;
  - the 60-second "only one POST" rule (unit test only);
  - VoiceOver or TalkBack;
  - browsers other than Chromium;
  - fidelity, which was not re-run (the builder's run stands, and the phone waiver is still waiting for the design engineer's signature).

## Journeys
Scripts are in `/private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/qa-f36/`: `qa.cjs`, `qa2.cjs` and `qa3.cjs`. The outputs are `qa-run1.txt`, `qa-run2.txt`, `qa-run3.txt` and `e2e.log`. The mock was reset before each journey. Request bodies were captured from the browser's own requests, and the mock's log was read from `GET /__mock/workspace-log`.

**Opening the panel (1440)**
- `/my-work?queue=unassigned` shows "Unassigned 6".
- Pressing "Tamarind Loans · loan origination RFP" opens `/my-work?queue=unassigned&assign=W-3302`. The tab list stays drawn behind the panel.
- The eyebrow reads "TAMARIND LOANS · TL-RFP-2026-014". The PM list shows "Choose a PM".
- The options are exactly Tunde Bello "PMO · 2 RFPs in progress", Sola Martins "PMO · 1 RFP in progress" and Ife Okoro "PMO" (no "0").
- Escape, Cancel and "×" each close the panel. Focus goes back to the row link, and no POST is sent.
- No `/me` read was added: the only `/me` read is the shell's. A grep of the diff under rfp, my-work and workspace finds no `/me`, `useMe` or `roles` read.

**W-3302: proof and returned wording**
- "What happens next" is the returned summary and agent sentence word for word.
- The role list is exactly ["PMO Lead", "CEO"], with PMO Lead chosen. I chose CEO.
- The file upload sent one POST to `/api/v1/cases/C-3302/evidence` with `kind: assignment_proof` and `case_revision: 1`. The chip shows "Uploaded · 18 KB".
- A scripted double click on "Assign PM" sent one POST with `X-CSRFToken: mock-csrf-pmo_lead` and the body `{"expected_revision":1,"person_id":"P-0007","acting_role":"ceo","evidence_id":"EV-C-3302-1","case_revision":2}`.
- The notice "TL-RFP-2026-014 is now with Tunde Bello." appeared and the panel closed. The mock log shows `[W-3302, 200, written]`.

**W-3301: the typed request only**
- The panel shows "3 people can prepare RFPs here", "PMO Lead" as plain text and no Proof field. The fixed "What happens next" sentence names no WhatsApp, email or Tola.
- With the note "  please start Monday  ", the body was exactly `{"expected_revision":1,"person_id":"P-0007","note":"please start Monday"}`.
- After assigning, the count went from 6 to 5, the row is gone, focus is on the Unassigned tab, and axe is clean.

**409 (`psl_mock_assign=stale`)**
- The panel shows "This changed while you were working. Showing version 2." Sola Martins stays chosen and there are no success words.
- With the cookie cleared, the next press sent `expected_revision: 2` and succeeded with "is now with Sola Martins".

**422 (`psl_mock_assign=invalid`, person_id)**
- The summary reads "1 thing to fix · Choose a PM from the list to continue.", with the same sentence under the field. The entries are kept and axe is clean.

**422 on the overlay fields**
- I rewrote the outgoing body so the real mock answers its own 422 (`acting_role: "cfo"`, or `evidence_id: "EV-NOPE"`).
- The panel shows "Check these fields: acting_role." (or "evidence_id"), no summary, and focus on the "Assign PM" button. The page's own words appear under each field, and the entries are kept. This happens at both widths. See QA-2-1.

**5xx with nothing written (`psl_mock_assign=uncertain`)**
- The panel shows "Not confirmed: We couldn't confirm the PM was assigned…" and "Try again", with the entries kept. There are no "is now with" or "Assigned to" words, and axe is clean.
- No resend happened in the next 3 s.
- "Try again" sent exactly one more POST (2 in total).

**Network failure and a 502 (routed)**
- A connection reset, or a 502 with an HTML body, gives the same "Not confirmed" state, with "Try again", the entries kept and no success words.

**W-3306: written, then 500**
- The panel shows "Assigned to Tunde Bello" and "Not confirmed at first; confirmed after reading it again.", with no form and one POST.
- After 17 s, past the 15 s list poll, both lines are still there. The mock log shows `[W-3306, 500, written]`.
- Closing the panel re-reads the list, and the row is gone.

**No `assign`**
- `?assign=W-3305` goes to `/work/W-3305`, with no "Assign PM" or "Set an owner" control.
- W-3304 shows "No one can prepare RFPs here yet." with no list and no "Assign PM". Axe is clean.

**Access (no names leaked)**
- Item read:
  - W-1099 shows "You can't open this item." and "Close", with no client, RFP, person or fixture name, and no second item read. Axe is clean.
  - A routed 403 or 404 on the W-3301 read shows the same view with no further call.
  - A routed 401 shows "You're signed out." with the link `/accounts/login/?next=%2Fmy-work%3Fqueue%3Dunassigned%26assign%3DW-3301`.
  - A routed 500 shows "We couldn't load this item." with Retry and no form. Axe is clean.
- The write:
  - A routed 403 on the POST shows the not-open view with no names.
  - A routed 401 shows the signed-out state with `next` pointing back to the panel URL.
  - Neither shows success words.
- Persona `pm` keeps "Only Leads can see unassigned work."

**Phone (390)**
- The W-3302 subline reads "Tamarind Loans · TL-RFP-2026-014".
- Every button, link, input and list in the panel is at least 44px, before and after the upload. The chip "×" ("Remove assignment-email.eml") is 48x48.
- There is no sideways scroll on the document (390 of 390) or the panel (390 of 390).
- "Assign PM" is pinned at the bottom, 358 of 390 wide.
- A double click sent one POST, and the notice appeared.
- W-3301, W-3304, the uncertain state and W-1099 meet the 44px rule and do not scroll sideways.
- In the 422 and empty-submit states, the summary's links are 37px tall. See QA-2-2.

**Axe**
- No violations (wcag2a, 2aa, 21a, 21aa, 22aa).
- Desktop: W-3301, W-3302 before and after upload, W-3304, the 422 state, the uncertain state, W-1099, the item-read 500 and the list after success.
- Phone: W-3302 before and after upload, W-3301, W-3304, the 422 state, the uncertain state, W-1099 and the list after success.

**F-30 and F-31 unchanged (persona `pm`)**
- On W-2413, "Set an owner", then Engineering, then "Set owner" gives "Owner set: Engineering". The body is `{"expected_revision":2,"person_id":"T-ENG"}`, with no added keys.
- On W-2601, "Confirm PM" gives "PM confirmed: Sola Martins".

**Automated runs**
- Vitest: `npx vitest run tests/rfp-assign.test.tsx tests/rfp-assign-mock.test.ts tests/mock-contract.test.ts tests/issue-detail.test.tsx tests/issue-assign-mock.test.ts tests/workspace.test.tsx tests/my-work.test.tsx tests/my-work-model.test.ts tests/mock-work-list.test.ts tests/response.test.tsx tests/response-mock.test.ts`: 11 files, 680 tests passed. `tests/engagement-planning*.ts(x)`: 2 files, 66 passed.
- Playwright: `E2E_PORT=4992 MOCK_PORT=4993 npx playwright test e2e/rfp-assign.spec.ts e2e/my-work.spec.ts e2e/issue-detail.spec.ts e2e/response.spec.ts e2e/engagement-planning.spec.ts`: 101 passed in 6.3 minutes (rfp-assign 23, my-work 15, issue-detail 25, response 16, engagement-planning 22).

**Failures from my own setup (not product)**
- The `psl_mock_scenario` cookie fails every request, including the shell's `/me`. That made my first 401, 403 and 404 runs test the shell, not the panel. I re-ran them with a route on the item read only, and they passed (above).
- My first routed 422 sent `fields` as an object, not the contract's array.
- Spec criterion 12 names W-3399 as a 404. The mock serves its default fixture for unknown ids (an invoice, `/work/W-3399`). The prompt names W-1099 as the no-access id, and W-1099 passes.

## Findings
- QA-2-1 | blocking | medium | frontend | A 422 on "You are assigning as" or the proof shows the backend's raw sentence and skips the summary and focus. Expected (spec Contract, 422, and the prompt's "frontend wording"): the page's own words, a top summary and focus on the first named field. Actual (real mock 422 on `acting_role: "cfo"` or `evidence_id: "EV-NOPE"`, at 1440 and 390): a Callout "Check these fields: acting_role." (or "evidence_id"), so the PMO Lead sees a field key, no "things to fix" summary, and focus stays on "Assign PM". The messages under each field are correct, and the entries are kept. Cause: `AssignPmDrawer.tsx:145` passes `result.message` back to `AssignForm`. `AssignForm.tsx:115` shows that message whenever neither `person_id` nor `note` is named, and only focuses those two fields. Fix: when the 422 names `acting_role` or `evidence_id`, drop the backend message, add those fields to the summary, and focus the role list or the proof field. Then add a test where the mock refuses each field.
- QA-2-2 | non-blocking | low | frontend | The summary's links in the phone sheet are 37px tall: "Choose a PM to continue." 158x37 and "Add a note to continue." 145x37 on W-3303, and "Choose a PM from the list to continue." 237x37 after a 422. D-92c and D-95 ask for 44px on standalone links. This passes WCAG 2.5.8 (24px). The links come from the shared `src/components/ValidationSummary.tsx`, which is read-only for this lane, and F-30's W-2411 summary links are 18px tall today. Route it as a fix to the shared component, not to F-36.
- QA-2-3 | non-blocking | low | frontend | When the item read returns a 500, the problem card says "Nothing was changed." twice: once in its title "We couldn't load this item. Nothing was changed." and again in its body. Cause: `AssignPmDrawer.tsx:43` and `:173-174`. Remove one.

## Verified
- UI-1-1 | verified | The desktop eyebrow `innerText` is "TAMARIND LOANS · TL-RFP-2026-014". The phone subline is "Tamarind Loans · TL-RFP-2026-014". The e2e computed-style test passed.
- UI-1-2 | verified | The e2e "head, footer and next block" test passed: Cancel is at least 48px tall and the Assign PM to Cancel width ratio is between 1.6 and 2.2.
- UI-1-3 | verified | The `.rfp-assign__next` top border is not 0px (e2e). The text matched the returned sentences.
- UX-1-1 | reopen | The messages under the fields are the page's own for all four fields. For `acting_role` and `evidence_id`, the raw backend summary "Check these fields: acting_role." is still shown at the top (QA-2-1).
- UX-1-2 | verified | Axe is clean on the panel at both widths, and the panel reads as the labelled dialog "Assign accountable PM".
- UX-1-3 | verified | On W-3306, "Not confirmed at first; confirmed after reading it again." shows under "Assigned to Tunde Bello" and is still there 17 s later.
