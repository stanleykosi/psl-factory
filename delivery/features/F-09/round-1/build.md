STATUS: READY
COMMIT: 4efaee8910bfe52304b9f253e66d96689f03862b
BUILDER: builder
LANE: full

## Summary
- New page `/work/<id>/respond?task=<task id>` (SCR-16): a PM records who responded, when, what they did, which version and (when the API lists more than one) how it arrived, uploads proof first, ticks the attestation and presses Record once. Every option comes from `tasks[].response`; nothing comes from `/me`. A `sow_signature` variant has its own Signature panel.
- Safety on the write: proof uploads one file at a time and carries each returned `case_revision`. The claim runs only when `claim_required` is true. A synchronous lock means one E-RESPONSE per press, and nothing retries by itself. A 409 keeps everything entered and reloads. A network or 5xx error re-reads the item and never resends; if that read also fails, Record stays off and Try again only reads.
- The success view is filled from the 200 (`recorded`, `next`), and anything missing comes from one reload. Absent r2 fields are left out, with no stand-in board text.
- Work item (SCR-02), with exactly two edits to `WorkItemOverview.tsx`: the "Record the client's response" / "...signature" entry link, and the reconcile panel ("Confirm what happened"). The panel shows only with `reconcile` plus `allowed_actions` containing `reconcile`, and it sends one E-WORK-ACTION, after which the page reloads.
- Contract mock `mock/response.mjs` checks requests and replies against v7, with fixtures W-1601..W-1609 and sidecars under `mock/fixtures/response/`. The base's v4 checks are unchanged and still pass.
- **Continuation (not yet gated):** `origin/dlv-00-delivery-setup` is merged in (df8e82c, no conflicts), bringing the frame's phone back-link slot (PR #17, D-23/D-28). The page now calls `usePhoneBack` ("← Queue" on the form, "← SOW" on the SOW form, "← Work item" on success and any other state) and draws no back bar of its own, so the phone bar matches the SCR-16 boards; the board's bar reference (REL-0077 / SOW-0207) sits at the right of the title row, because the slot has no reference place. The SOW phone form keeps the board's rows in place (note and attestation follow "What happens next"), and phone pills, chip, alert and top spacing follow the boards. Desktop is unchanged except that the proof card's second line is 18px high, as the board draws it (desktop SOW 90.6 → 92.5).

## Changes
- `frontend/src/app/work/[id]/respond/page.tsx`: the server page. Title "Record a response · PSL Factory"; reads `params` and `?task=` the same way `decide/page.tsx` does.
- `frontend/src/features/response/contract.ts`: local v7 types (`TaskResponse`, `Reconcile`, `ResponseWorkItem`, the upload, response and work-action bodies and results). Every r2 field is optional.
- `frontend/src/features/response/api.ts`: the only API module (`getWorkItem`, `uploadEvidence`, `claimTask`, `recordResponse`, `workAction`, `asResponseItem`). **The one commented widening cast is `const v7 = api as unknown as Client<ResponsePaths>`.** Remove it once the client is on v7 (F-13).
- `frontend/src/features/response/useResponse.ts`: the page flow (load, claim, record, the 403/409/422/uncertain/unconfirmed handling, recheck). `useEvidenceUpload.ts`: upload one file per choice, carry the case revision, per-chip errors, Try again that reloads before it uploads. `ProofField.tsx`: three board layouts (drop area with chips, phone button, SOW card).
- `frontend/src/features/response/ResponseForm.tsx` (client_response and sow_signature forms, agent aside), `ResponseView.tsx` (page states, crumb, phone back bar, success, not-open), `ReconcilePanel.tsx`, `ResponseEntryLink.tsx`, `labels.ts`, `icons.tsx`, `reload.ts` (`reloadPage()`), `usePhone.ts`, `index.ts` and `response.css`. The CSS uses tokens only.
- `frontend/mock/response.mjs`: `RESPONSE_OPENAPI_PATH` (**the single v7 constant**; remove it with the cast once the mock reads v7), `RESPONSE_OPERATIONS`, `responseRoute`, `resetResponses`. Validators are compiled once with `ajv/dist/2020` and `ajv-formats`. Checks run in this order: scenario (including `record-then-fail`), CSRF, persona `none`, record, body, rules, revisions, grant, success. Every reply is validated against v7 before it is sent.
- `frontend/mock/fixtures/response/work/W-1601..W-1609.json` (served items) and `frontend/mock/fixtures/response/*.json` (sidecars `W-1601/1602/1605/1606.recorded` and `W-1603.delivered|not_delivered|unknown`). All are `sample: true` and valid against v7.
- **Shared edits for the integration owner to merge:**
  - `frontend/mock/server.mjs`, three additive edits:
    - (a) `readWorkFixtures` also reads `fixtures/response/work/*.json` into the same `work` map;
    - (b) one branch before the 501 check sends `RESPONSE_OPERATIONS` to `responseRoute`;
    - (c) `/__mock/reset` also calls `resetResponses()`.
    `M1_OPERATIONS` and `OPENAPI_PATH` are unchanged.
  - `frontend/src/features/work-item/WorkItemOverview.tsx`, the two allowed edits:
    - in `TaskPanels`, a task with `responseOf(task)` that you can act on gets `<ResponseEntryLink>` in place of "Open the decision";
    - one `<ReconcilePanel id item={asResponseItem(item)} />` mount after the left `work-column`.
    `NextStep` is untouched.
- Continuation commits efe0c8e and 4efaee8:
  - `ResponseView.tsx`: `usePhoneBack({ label, href })` called once, before any early return; `BackBar` removed; `PhoneReference` puts the reference beside the phone h1 in a `.resp-titlerow`.
  - `ResponseForm.tsx`: on the phone the SOW form puts When alone, Proof alone, then "What happens next", Note and the attestation (desktop rows unchanged).
  - `response.css`: `.resp-backbar` styles removed; `.resp-titlerow`/`.resp-phoneref`; phone-only: 14px content top, 52px pills with the board's radio inset, 8px chip padding, 14px alert, SOW "What they did" gap 12px and 42px segments; `.resp-card__meta` line-height 18px.
  - `tests/response.test.tsx` and `e2e/response.spec.ts`: the phone back-link checks now find the link in `.psl-phonebar` by its frame name ("Back to Queue" / "Back to SOW" / "Back to Work item"), check its text "← …" and href, that it is the only "← " on the page and that Menu is gone; the reference is checked in `.resp-phoneref`.
- Tests: `frontend/tests/response.test.tsx` (50 component tests), `frontend/tests/response-mock.test.ts` (32 mock-against-v7 tests), `frontend/e2e/response.spec.ts` (16 Playwright and axe tests).

Decisions taken inside the spec (for review):
- The mock's case revision belongs to the case: an upload moves every served item in that case forward through `overrides`. W-1608 shares case C-1601, so `T-1608 → 403` can be reached with valid proof.
- A sidecar whose `recorded` has a `summary` is board (r2) data, and its 200 carries `revision`, `recorded` and `next`. W-1606's sidecar has no summary, so its 200 is the bare `{task_id, work_state}` and its reload carries only `recorded.by` and `.at`.
- The proof control is a real `<button>` ("Add another file" / "Take a photo or choose a file" / "Choose the signed copy") that opens a hidden `<input type="file">` with no `capture`. This matches the board's button role.
- On the phone, the client form shows its picker only before the first file, as the phone board does.
- A response task with a variant this page doesn't record gets no entry link (and the not-open page).
- The success heading uses the station that was current when Record was pressed. If the page is opened on an already-recorded task, it uses the loaded item's current station.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] **Entry button.** Component test "entry from the work item": W-1601 links to `/work/W-1601/respond?task=T-1601` with no "Open the decision"; W-1608 shows neither; W-1201 keeps "Open the decision". W-1602 shows "Record the client’s signature". The e2e test follows the link.
2. [x] **Default form shows only returned options.** Component tests check the crumb "QUEUE / PREPARE FOR RELEASE / REL-0077 · STATION 3 OF 5", the h1 and intro, the single preselected responder, exactly 3 unchecked radios, the version text, no channel control, the hint, the attestation, disabled Record, and the Tola aside (`/agents/tola.png`, both lines). W-1605 starts on "Choose…" with Email / Letter / In person. An added action is offered, a removed one is not, and an action without a label is not offered. The `finance_lead` persona sees the same options.
3. [x] **Validation.** Component test: the board alert line shows, a click on the disabled Record sends no request, the line stays with proof but no tick, and it goes away with proof and tick. W-1609 never enables Record.
4. [x] **Proof first, case revision carried.** Component test: upload 1 has `case_revision` 4 and CSRF `mock-csrf-pm`; upload 2 has 5; the record has `evidence_id` EV-…-1, `evidence_ids` [EV-…-2] and `case_revision` 6.
5. [x] **Record body.** Component test: exactly one POST with the exact body from the spec and the CSRF header; no note/team/what/estimate keys; a typed note is sent trimmed.
6. [x] **Claim first.** Component test: the call order is evidence, claim `{expected_revision:3}`, response with `expected_revision` 4. W-1601 sends no claim. A claim 409 sends no response. A claim network error shows "We couldn’t get this ready. Try again." and sends no response.
7. [x] **One record on a double press.** Component test with a deferred reply: one E-RESPONSE, the button reads "Recording…" and is disabled, and the form has `aria-busy="true"`.
8. [x] **Success.** Component test: the exact eyebrow, h1 and status sentence, both `next` lines, the correction line, "Back to the work item", no form controls, and one reload. At 390 the frame's phone bar shows "← Work item" (to `/work/W-1601`, the only back link, no Menu), REL-0077 sits beside the h1, and "Back to my queue" is pinned at the bottom (component test and e2e).
9. [x] **Absent fields left out (W-1606).** Component tests: no intro, aside or hint, and none of the board sentences. Success reads exactly "Response recorded. Recorded by Tunde Bello at 15:04." from the reload.
10. [x] **SOW signature.** Component tests: the crumb (only PROJECTS is a link, to `/projects`), "Signature", "SOW-0207 v1 · Tamarind Loans · sent 18 Dec 10:30", the note line, the signer, Signed / Asked for changes / Declined, the what-happens-next line, "Record signature" and the aside intro. "Declined" sends `rejected`. At 390 the h1 is "SOW signature", the frame's phone bar shows "← SOW" (to `/work/W-1602`), SOW-0207 sits beside the h1 and there is no aside. The client form's phone bar shows "← Queue" (to `/my-work`).
11. [x] **Errors on record.** Component tests: 422 shows the problem callout, keeps entries and sends no second POST; 409 shows the warning, one GET, keeps entries and proof, clears choices the task no longer offers, and shows success if the reload is already recorded; 403 does one GET, and W-1608 is then not open; 403 on a still-open task keeps the controls; 401 gives a sign-in link with `next` = `/work/W-1601/respond?task=T-1601`; item 404 shows NoAccessState with no id or title; 500 shows the error card and Try again.
12. [x] **Uncertain effect.** Component tests: recorded reload shows the warning plus success with one POST; open reload brings Record back with no POST; failed reload keeps Record off and Try again sends only a GET. e2e: `record-then-fail` on E-RESPONSE leads to the warning plus the success view, with exactly 1 send.
13. [x] **Reconcile panel.** Component tests on W-1603 (finance_lead): the heading, the checks sentence, the three option texts, the button, the footer, and the panel in `.work-columns`. At 390 the warning callout shows. W-1607 shows two options with no "Allow …" and no resend_note.
14. [x] **Reconcile only with the grant.** Component test: W-1604 and W-1601 show no panel and send nothing. The boundary test (`grep roles|destinations src/features/response`) finds nothing.
15. [x] **Reconcile write.** Component tests: "It arrived" stays disabled until the `delivery_receipt` upload succeeds, then a double press sends one POST with the exact body and CSRF, and `reloadPage` is called once. "It didn’t arrive" sends no evidence. A 409 shows "Reload the work item" with no second POST. A network error shows "We couldn’t confirm your answer…" with no second POST. 403/422 show the message and 401 a sign-in link. The grep `resend|deliver` on `api.ts` finds nothing.
16. [x] **Mock against v7.** `npx vitest run tests/response-mock.test.ts`: 32 passed. This covers every fixture against v7 and `sample:true`, every reply against v7, and all the listed 422/409/403/404/501/csrf/scenario/reset/claim cases.
17. [x] **Base v4 checks unchanged.** `npx vitest run tests/mock-contract.test.ts tests/api-schema-drift.test.ts tests/mock-decide.test.ts` passes with no edits to those files. `git diff origin/dlv-00-delivery-setup HEAD -- architecture frontend/src/api frontend/src/shell` is empty: F-09 changes none of them (the only shell changes since 92d029b are the base's own PR #17 slot, merged in). No `fixtures/work/W-16*` file exists (tested). The only casts are in `api.ts` (tested).
18. [x] **Accessibility and layout.** `E2E_PORT=4401 MOCK_PORT=4402 npx playwright test e2e/response.spec.ts`: 16 passed. axe finds no WCAG 2.2 AA violations for the five states at 1440 and 390. At 390, Record and "Record and continue" are in the viewport, at least 44px tall, and scrollWidth is 390 or less. Tab order runs Who → When → actions → Version → Note → proof button → attestation → Record, each with a 2px focus ring. Reduced motion leaves no running animations. Both radio groups are named.
19. [ ] **Design fidelity: desktop and phone success pass; three SCR-16 phone boards and SCR-02 do not.** Re-run after the slot merge with `round-1/fidelity/_driver/runall.sh` (the tool's `fidelity.mjs` plus an `--actions` hook running `act.mjs`, which fills the board values) against `MOCK_PORT=4402 npm run dev -- -p 4401`, mock reset before each board. Reports and `scores.txt` are in `round-1/fidelity/`. Coverage is 100% with the 36 exception requests in `round-1/fidelity/exception-requests.json` on all 12 boards; none is approved.

    | Board | Width | Before slot | Now | Result |
    |---|---|---|---|---|
    | SCR-16-desktop | 1440 | 95.1 | 95.1 | PASS |
    | SCR-16-desktop-validation | 1440 | 96.2 | 96.2 | PASS |
    | SCR-16-desktop-success | 1440 | 94.4 | 94.4 | PASS |
    | SCR-16-desktop-sow-signed | 1440 | 90.6 | 92.5 | PASS |
    | SCR-16-mobile | 390 | 66.8 | 80.3 | FAIL (visual) |
    | SCR-16-mobile-validation | 390 | 52.4 | 70.5 | FAIL (visual) |
    | SCR-16-mobile-success | 390 | 77.8 | 95.4 | PASS |
    | SCR-16-mobile-sow-signed | 390 | 74.0 | 89.0 | FAIL (visual, 1 point) |
    | SCR-02-desktop-awaiting-reconciliation | 1440 | 56.4 | 58.8 | FAIL (F-03's page) |
    | SCR-02-mobile-awaiting-reconciliation | 390 | 59.1 | 59.1 | FAIL (F-03's page) |
    | SCR-02-desktop-waiting | 1440 | 48.5 | 50.9 | FAIL (F-03's page) |
    | SCR-02-mobile-waiting | 390 | 52.7 | 52.7 | FAIL (F-03's page) |

    - **What still holds the phone boards down:** fields the spec requires that the boards don't draw. SCR-16-mobile and -validation draw no "When they responded" and no Note; the spec keeps both, in its own phone order (summary, When, actions, Proof, note, attestation, alert; spec section 6 and Assumptions), and they push every later row down by about 170px. SCR-16-mobile also draws no "What they did" or "Proof" labels while -validation does; the page keeps both labels in both states. On SCR-16-mobile-sow-signed every board row now lines up to the pixel (Document to "What happens next"); the remaining point is the Note and attestation below them, which make the page 905px tall, so the pinned Record bar lands lower in the full-page capture, and the board's bar reference, which sits beside the h1 because the frame slot has no reference place.
    - **Exception requests after the slot:** the old "← Queue" request (frame bar, D-08) is replaced. "← Queue", "← Work item" and "← SOW" are now drawn by the slot in the board's place, but the frame names the link "Back to …" for screen readers and the tool matches on that name, so each stays as a request with that reason. No other request was covered by the slot; every one of the 36 is still matched by a missing board element in this run.
    - **SCR-02 boards** measure F-03's work item page (D-25/D-26), reported and not rebuilt. F-09's reconcile panel and entry button line up.
    - **Proposed exceptions, as the spec's Assumptions list them:**
      - Note field on every form (on desktop it shares the version / When row so the board's rows don't move; on the SOW phone it follows the board's rows);
      - the SOW attestation, placed beside the proof card (after the board's rows on the phone);
      - "When they responded" stays on the phone;
      - no action is preselected;
      - STATION 3 OF 5 (the board says 2);
      - the phone summary line uses the full version label "Patient app · build 2.4.0";
      - the channel select appears only with 2 or more channels;
      - the frame's Start work / More ways to start;
      - the board's static "20 Dec 2026, 14:10" is a datetime input on the page;
      - the phone validation line is `role="alert"`;
      - the phone reference (REL-0077 / SOW-0207) beside the h1 instead of in the bar, until the frame slot offers a reference place (a frame change, outside F-09's lane).
20. [x] **Gate.** `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exits 0: Django check, npm ci, lint, typecheck, vitest (16 files, 408 tests) and next build.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-09 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 at 4efaee8 (lint, typecheck, 16 files / 408 unit tests, build compiled).
- `cd frontend && E2E_PORT=4401 MOCK_PORT=4402 npx playwright test`: 100 passed at 4efaee8, including the 16 in `response.spec.ts` and the base's frame back-link test.
- `npx vitest run tests/response.test.tsx`: 50 passed after the slot adoption.
- Fidelity ran against `MOCK_PORT=4402 npm run dev -- -p 4401`, with the mock reset before each board; scores are in the table above and `round-1/fidelity/scores.txt`. The servers on 4401 and 4402 have been stopped, and `frontend/test-results` and the scratch fidelity runs have been deleted.
- All results come from the contract mock only. No real provider or live integration was used, and nothing is sent to anyone.

## Blocked
Not blocked.
