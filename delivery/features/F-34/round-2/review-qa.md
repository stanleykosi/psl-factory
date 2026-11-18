VERDICT: CHANGES
REVIEWER: qa
COMMIT: e3928527335e9963daedccf798e736ff53e1ee8b
AUTHORITY: delivery integrated QA

## Summary
- I ran a production build of e3928527 (`API_ORIGIN=http://127.0.0.1:4978 FRAME_FIXTURES=1 npm run build && npx next start -p 4979`) against the contract mock on 4978, as persona `pm` (and `finance_lead`, `ceo`, `none` where noted). I drove it with a Playwright script (78 checks), plus direct calls to the mock. Then I stopped my own PIDs (app 32167/32264, mock 31782) and reset the mock.
- Spec e2e set (`E2E_PORT=4980 MOCK_PORT=4981 npx playwright test e2e/delivery-hypercare.spec.ts e2e/delivery-release.spec.ts e2e/workspace.spec.ts`): 80 passed (hypercare 21, release 22, workspace 37). Targeted vitest (hypercare, delivery-hypercare-mock, mock-contract, delivery-release-mock, delivery-overview, workspace-step, engagement-planning): 7 files, 500 passed. `frontend/test-results` deleted.
- Every success and failure journey in the spec behaves correctly. Nothing says "Done" before the re-read, there is no double send, and entries are kept. 401/403/404 do not leak. Unknown is never 0. axe is clean at 1440 and 390, with no sideways scroll.
- One blocking problem. At 390 the proof chip's "×" (remove file) button is 24×24px in the record and observation forms. Spec AC16 and D-92c require 44px, and the feature's e2e skips that button with `:not(.resp-chip__remove)`.
- **Not proved.** Everything runs on the contract mock only. Nothing is deployed, evaluated or qualified. The default and qualified pages are fixture sample data, and D11 (window and criteria) is still open. No real backend checks the evidence id, enforces the idempotency promise or decides access per record: the mock accepted a step whose `evidence_ids` held an unknown id. The unknown-id case (W-3199) cannot be shown on the mock, which serves its default item W-1001 for any id it doesn't know. A real 404 was shown only through the scenario header. Fidelity was not re-scored by me.

## Journeys
Script: /private/tmp/claude-501/-Users-Hunchoo--claude-spares-spare-2d2Z3S/0986a60c-391e-48d6-b2da-79de8713a755/scratchpad/qa-f34/qa.mjs (final run qa-run4.txt). Debug drives: dbg.mjs, dbg2.mjs and dbg3.mjs in the same folder.

1. **Delivery tab → W-3101.** On `/projects/P-0101/delivery`, the Hypercare row and its sub-nav entry both link to `/work/W-3101`. Clicking opens HYP-0062 "day 10 of 30", and Back returns to the tab. Every other link is unchanged: Release and Release gates go to W-2503, Go-live to W-2510, and the tabs are as before. Pass.
2. **Default window and criteria, as returned (W-3101).** The page shows "Hypercare · day 10 of 30", the observations table (ISS-0301 "Open · owner set", OBS-0012 "Noted", Incidents "None") and "30 days · from Setup". It shows the three criteria, each with one "Met" and no "Done" beside it (UI-1-1), the returned Next sentence and "Log an observation". There is no "qualified" text. Pass.
3. **Setup-needed hold (W-3103).** The page shows "Hypercare can't be evaluated…" and keeps the observations. `.ws button` and `main button` are both empty. There is no criteria row, MET, Log or Record. "Open Setup › Rules" goes to `/setup/rules/delivery`. I then changed the GET response with `page.route`. With the links removed, with area `nowhere`, and with an unknown kind, no `/setup` anchor is drawn. Pass.
4. **Qualified only from verified (W-3104, W-3110).** W-3104 shows "Hypercare qualified" and the verified note, with `psl-callout--success`. It has no "Agent working" (UX-1-1), and "See what closure needs" goes to `/work/W-3120`, which opens. On W-3110, where Tola's "Mark hypercare qualified" step is done, there is no qualified banner and no closure link. A copy of W-3104 with tone `person` and state `processing` draws `--info`/`--warning`, not success. Pass.
5. **Record the release (W-3102).**
   - Version "Build 1.0.0" and Environment "Production · Lagoon Health" are pre-filled.
   - Submitting blank shows "Add released on to continue." and "Add proof to continue." With the date but no proof, the proof message shows. Nothing is sent in either case.
   - After the upload, "Add proof to continue." is gone (UX-1-2).
   - One upload is sent: `POST /api/v1/cases/P-0101/evidence`, `kind: deployment_log`, `case_revision: 2`, `X-CSRFToken: mock-csrf-pm`.
   - Then one step: `record_release`, `expected_revision: 1`, inputs `{version, released_at: "2026-04-01T21:00:00.000Z", environment}`, `evidence_ids: ["EV-P-0101-1"]`, an idempotency key and CSRF.
   - I held the re-read GET for 3 s. During that time the page still showed "Hypercare · release not recorded", with no "Done:" and no hold. Once released, the hold ("Setup needed") and "Done: Record release." appeared together.
   - `/__mock/workspace-log` shows one send. No step buttons remain afterwards.

   Pass.
6. **Log an observation (W-3101).**
   - Blank sends nothing and shows the field message.
   - Text with a proof sends one upload (`kind: hypercare_observation`) and one `log_observation` with `inputs.what` and `evidence_ids`.
   - Text alone sends one write with no `evidence_ids`.
   - The re-read shows OBS-0013 and the Done notice.

   Pass.
7. **Failure fixtures.** In each run I first changed Version to "Build 1.0.1-qa".
   - W-3105 (500, nothing written): the failed message shows, there is no Done, and the page still reads "release not recorded". The form keeps "Build 1.0.1-qa". "Try again" posts the same key, and the mock log shows one send for it. Pass.
   - W-3106 (written, then 500): the failed message shows and there is no Done. The re-read shows the hold. One send, and no step control is left. Pass.
   - W-3107 (effect uncertain): "We are checking what happened. Nothing was sent again." shows. Record release is `aria-disabled` with "Confirm what happened first." No Done, and nothing reads recorded. Pass.
   - W-3108 (409): "This changed while you were working. Showing version 2." The form is kept with "Build 1.0.1-qa" and the file chip, and there is no Done. Pass.
   - W-3112 (observation written, then 500): the failed message shows, OBS-0013 appears from the re-read, there is no Done, and there is one send. Pass.
   - Network abort on the step (e2e): the failed message shows, there is no Done, and the record stays. Pass.
8. **Invalid and refused input.** I added `X-Mock-Scenario` to the step POST only.
   - 422: "Check the highlighted fields…" and the form is kept.
   - 403: "You can't take that step." and a re-read.
   - 404: the no-access view.
   - 401: the signed-out view.
   - Upload answered 500: "Couldn't upload. Try again." and no step is sent.

   Direct calls to the mock:
   - an upload as persona `none` gets 403;
   - a step with no CSRF gets 403 `csrf_failed`;
   - `record_release` on W-3103, where it is not offered, gets 404 "That step is not offered on this item."

   Pass.
9. **Read access.**
   - With `X-Mock-Scenario` 401 on the GET of W-3101, the page shows "You're signed out", and Sign in goes to `/accounts/login/?next=%2Fwork%2FW-3101`.
   - With 403 and with 404, the page shows the same "You can't open this work item" text.
   - None of the three shows HYP-0062, Lagoon, ISS-/OBS- or Hypercare in `innerText` or `textContent`. Each makes only one work GET (plus `/me` and notifications).

   Pass. W-1099, the mock's no-access id, is axe-clean at both widths. W-3199 could not be tested (see Summary).
10. **Unknown never 0 (W-3111).** The Incidents row reads "— · Incidents · Unknown", the Window tag reads "Unknown", and the page has 3 "Unknown". None of them shows None, 0 or blank. Pass.
11. **Controls only from the response.** `pm`, `finance_lead` and `ceo` see the same single control on W-3101. On W-3109, "Log an observation" is `aria-disabled`, with `aria-describedby` set to "Only the project's PM logs observations.". Pressing it opens no form. Pass.
12. **Phone and axe.**
   - At 1440 and 390, W-3101, 3102, 3103, 3104, 3109, 3111 and W-3199 have no axe violations (wcag2a/aa, 21a/aa, 22aa). `scrollWidth` is at most `innerWidth`.
   - The record and observation forms are also axe-clean at both widths when open with a file chip, with no sideways scroll.
   - Every feature control (buttons, inputs, Setup and closure links) is at least 44px at 390.
   - Two items are under 44px. The chip's "×" ("Remove release-1.0.0-log.pdf") is 24×24 (QA-2-1). The frame's "History" link is 24px (QA-2-2).
13. **F-32 and other lines unchanged.**
   - W-2502 (REL-0091) renders "Your decision", the checked list and "Approve for release" / "Return with a note".
   - The delivery-release e2e passed 22 of 22, and the workspace e2e 37 of 37.
   - Other lines after the StepForm change: on W-2604 (register engagement), a blank submit shows "Add plan evidence to continue.". The upload clears only that message, and nothing is sent until submit. workspace-step and engagement-planning vitest are green.

## Findings
1. QA-2-1 | blocking | medium | frontend | **The proof chip's remove button is too small on a phone.** At 390, the "×" on an uploaded file in the Record release form (W-3102) and the Log an observation form (W-3101) measures 24×24px. Spec AC16 and D-92c require every form control, "including the open record form and the proof control", to be at least 44px. The rule `.resp-chip__remove { min-width: 24px; min-height: 24px }` (src/features/response/response.css:77) is raised to 44px only inside `.cmp-panel` (src/features/workspace/workspace.css:252), and the step form is `.ws-form` (StepForm.tsx:288). The feature's e2e hides the gap: `form.locator('button:not(.resp-chip__remove), …')` at frontend/e2e/delivery-hypercare.spec.ts:82. Expected: add `.ws-form .resp-chip__remove { min-width: var(--control-phone); min-height: var(--control-phone); }` (phone width, or always), and drop the `:not(.resp-chip__remove)` exclusion so the e2e measures it.
2. QA-2-2 | non-blocking | low | frontend | **The frame's "History" link is 24px tall at 390.** It is on every work item, W-2502 included (WorkItemView.tsx:152). It was already there before this feature (round-1 UI notes) and is not inside the feature's e2e locator. It belongs in a frame pass.
3. QA-2-3 | non-blocking | low | integration | **Spec AC15's unknown id `/work/W-3199` can't be proved on the mock.** `GET /api/v1/work/W-3199` returns 200 with the default item W-1001 (INV-0412), per the server.mjs:8-9 default-fixture rule. The page then draws W-1001 under the W-3199 URL. No-access was proved with W-1099 and with the 403/404 scenario. The real backend must answer 404 for an unknown or other-tenant id, and that is unproved.
4. QA-2-4 | non-blocking | low | backend | **The mock does not check a step's evidence ids.** A direct `POST /api/v1/work/W-3102/steps` with `evidence_ids: ["EV-nope"]` returned 200 `done`. The real backend must reject unknown or foreign evidence ids. Record this in BACKEND-HANDOFF alongside G-46-1.

## Verified
- UI-1-1 | verified | W-3101 criteria section innerText: "Window 30 DAYS · FROM SETUP / No open high-severity issues MET / No unresolved incidents MET / Medium issues have an owner MET". No DONE.
- UI-1-2 | verified | tone exceptions are present in fidelity-exceptions.json. The page draws the returned tone, and no src mapping was added (round-2 src diff is StepForm.tsx only).
- UX-1-1 | verified | W-3104 at 1440 has no "Agent working" and the success callout.
- UX-1-2 | verified | on W-3102, "Add proof to continue." shows before the upload and is gone once it completes. On another line, W-2604, only the evidence message clears.
- UX-1-4 | verified | recorded in BACKEND-HANDOFF. The page draws the Setup link only when it is returned (journey 3).
