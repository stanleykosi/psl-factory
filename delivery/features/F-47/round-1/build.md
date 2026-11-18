STATUS: READY
COMMIT: 438c350fe7fe79233604f2293b6812d10df6c1ee
BUILDER: builder
LANE: full

## Summary
- The Start work drawer's Proof box now works on minutes and change (PM lines) and on two new Finance lines, income schedules and ledger sources. A chosen file uploads at once to the line's case. The card reads "Uploaded · <size>" only once the backend returns an `evidence_id`, and only those ids go with the start.
- The case and revision come only from the line (fixed case) or from the chosen project. Each upload carries the revision the last one returned, and the start sends the last one. Start stays off while any file is uploading or has failed. A 409 on an upload or a start re-reads where the revision came from and keeps everything typed.
- There is no size or type rule in the browser and nothing comes from `/me` or roles. File names and backend messages render as plain text. 403 and 404 on an upload look the same.
- The mock has a start-work branch for uploads, a revision map that E-LINES, E-LINE-OPTIONS and E-WORK-START share, the two Finance lines with their options, `W-4401`/`W-4402`, and the `upload_uncertain`/`start_uncertain` fixtures. Contract mock only.
- All 14 spec Conflicts are built as the spec recommends, PROVISIONALLY under D-114. Every exception and waiver reads "builder proposal, pending design engineer".

## Changes
- `frontend/src/features/start-work/intake.ts`: `evidence` is now a rendered and sent kind. New `uploadable()`. `startableHere` refuses a required evidence field only when it has no `evidence_kind` or is `restricted`. `buildIntake(fields, values, proof)` sends the confirmed ids: the last one, or all of them in order when the field is `multiple`.
- `frontend/src/features/start-work/StartProof.tsx` (new): hosts `useEvidenceUpload` and `ProofField` (`card` layout, "Choose a file"; `drop` when `multiple`), modelled on StepForm's EvidenceField. It is keyed by case, so another project starts it again empty. It shows F-05's disabled dashed box "Choose the project first." until there is a case. It follows the form's revision (`sync`) and reports ids, busy, failed and revision to the form. On 403 or 404 it drops the file and raises one drawer notice. It is wrapped in a disabled `fieldset role="presentation"` while the start is sent or uncertain.
- `frontend/src/features/start-work/useStartWork.ts`: holds proof state, `proofRevision` and `sendCase`. Start is held while proof is busy or failed. On a project change it drops the proof and shows the Conflicts 4 line. `rereadCase()` is the upload hook's re-read (E-LINES for a fixed case, E-LINE-OPTIONS for a project). A start's 409 resets to the re-read revision. 401 from an upload leads to signed-out. The 422 for `proof` now shows inline.
- `frontend/src/features/start-work/LineForm.tsx`: evidence fields render `StartProof`. The Project control is read-only while an upload runs, and Start is gated on `proofHeld`.
- `frontend/src/features/start-work/IntakeField.tsx`: removed the old "Proof upload comes next" box and the evidence label exception.
- `frontend/src/features/start-work/labels.ts`: adds "Start schedule", "Record source", the Conflicts 4 line and the shared 403/404 sentence.
- `frontend/src/features/start-work/start-work.css`: Proof label weight 600 (the board's) scoped to `.sw-prooffield`. On phones the "×", "Choose a file" and Try again are 44 px via `--control-md`, scoped to the drawer.
- `frontend/mock/start-work.mjs`: new `ownsUpload()` and `upload()`. Checks run in this order: schema 422, case the line starts on (else 404), revision 409, then empty or `.exe` 422. On success it adds 1 to the revision and returns `EV-SW-<case>-<n>` and the sha256. The revision map (`persona:case_id`) is read by E-LINES, E-LINE-OPTIONS and the start. A start's evidence must be an id issued on the same case for the same persona. Adds the uncertain fixtures. `reset()` clears everything. `WORK_IDS` gains W-4401/W-4402.
- Fixtures: `lines.finance_lead.json` gains the two lines. New `options/mapping_run.json`, `options/continues.json`, `work/W-4401.json` and `work/W-4402.json`.
- `frontend/tests/start-work-proof.test.tsx` (32 tests) and `frontend/tests/start-work-proof-mock.test.ts` (17 tests) are new.
- `frontend/e2e/start-work-proof.spec.ts` (new, 14 tests at 1440 and 390).
- `delivery/BACKEND-HANDOFF.md`: adds "## Added during F-47: Start work proof upload (19 Nov)".

### Allowed edits outside the lane
1. `frontend/mock/server.mjs`: one dispatch branch before the F-09 response branch. A non-`C-SETUP-*` upload whose `kind` is a Start work line's `evidence_kind` for the persona gets the M1 scenario and CSRF handling and goes to `start-work.mjs`. **I also changed one existing line**: the start-work call now passes `cookies`, which `start_uncertain` needs. That goes beyond the spec's "one dispatch branch".
2. `frontend/mock/fixtures/me.finance_lead.json`: `startable_lines` gains `income_schedules` and `ledger_sources`.
3. `frontend/src/features/response/useEvidenceUpload.ts`: one additive guard. A 200 without a non-empty string `evidence_id` is marked failed ("Couldn't upload. Try again.", retryable), and its revision is not taken.

### Places where the spec and the schema disagree (schema followed)
- The spec asks for `sample: true` on the two new lines. The E-LINES line item is `additionalProperties: false` with no `sample`, so it is left out; the options and work items do carry `sample: true`.
- The spec asks for `line_key` on W-4401/W-4402. E-WORK-ITEM has no `line_key`, so it is left out; `case_id` is kept.

### F-05 assertions rewritten (Conflicts 13), old then new
- `tests/start-work-intake.test.ts` "never sends an evidence, money or unknown field": old, evidence is never sent. New, evidence is sent only from the confirmed ids (last one, or all if `multiple`), never from typed values or when the field has no kind or is restricted.
- `tests/start-work-intake.test.ts` shownFields/startableHere: old, the evidence field is "drawn disabled" and any required evidence can't start. New, the same field is the Proof box, a required evidence field with `evidence_kind` can start, and one with no kind or restricted can't.
- `tests/start-work.test.tsx` "optional evidence drawn disabled": old, "Proof upload comes next" with `aria-disabled` and no button. New, a Proof group with an enabled "Choose a file" button, and nothing is sent for it.
- `tests/start-work.test.tsx` 422 boxes: old, the proof problem sits in its own box and the `.sw-proof` box has no error. New, the problem sits under the Proof fieldset (the same order of boxes).
- `e2e/start-work.spec.ts:160-168`: old, "Proof upload comes next". New, "Choose the project first." The label selector also reads `[data-field] > .resp-field > .psl-label`.
- **Not listed in Conflicts 13, but forced by the new lines:** in `tests/start-work.test.tsx` the finance_lead chooser count goes from 1 to 3, and in `tests/start-work-mock.test.ts:101` the finance_lead keys go from `['invoice']` to `['invoice','income_schedules','ledger_sources']`. `tests/start-work-mock.test.ts:105-117` (the ceo's evidence fields) stays unchanged and green, because the ceo is not served the Finance lines.

### Mock-only fields and cookies
`_personas` on the new options (stripped before serving). Cookie `psl_mock_start_work` = `upload_uncertain` | `start_uncertain`, applied once per reset per persona. Mock ids are `EV-SW-<case_id>-<n>`.

### Builder choices (pending design engineer)
- On 403 or 404 from an upload, the file is taken off the form and the drawer shows "You can't add proof to this item." once. This keeps the two cases identical on screen (criterion 9), because F-09's hook puts the 403 sentence in the card but gives a 404 none. The 403 case is found by matching the hook's own sentence.
- A `restricted` evidence field draws the disabled dashed box "Proof can't be uploaded for this item." (F-09's sentence), with no picker.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] The four drawers draw their fields from data: component test "draw their fields, Proof box and button words from data"; e2e at 1440 and 390. `grep -rn "SCH-INC\|QB-JE\|MR-0044\|income_detail_oct\|weekly-sync-notes" frontend/src` returns nothing.
2. [x] Project first: component tests show "Choose the project first.", zero upload POSTs and no button before the choice, then "Choose a file" enabled. Ledger and schedules show the button at once.
3. [x] Uploaded only when the backend says so: one POST to `/cases/C-0101/evidence` with CSRF, exactly 4 keys, valid against the request schema, `case_revision: 6`. The card reads "Uploading…" until a deferred answer, then "Uploaded · 38 KB". A 200 without `evidence_id` reads "Not uploaded", and the start sends no proof. e2e request log at both widths.
4. [x] Revision chaining: ledger uploads send 2 then 3, and the start sends 4 with the second id. With `multiple`, both ids go in order. A file chosen while one uploads is not sent. Mock test checks the same.
5. [x] Start lands on W-1403, W-1405, W-4401 and W-4402. A double press sends one start. The key is the one made at drawer open, and no `randomUUID` call happens during the upload (component test `it.each`). e2e `dblclick` gives one start and lands.
6. [x] Start is held while an upload runs or any card is failed: component and e2e tests. Try again and remove both free it.
7. [x] Removing a file sends no request, the start leaves the id out, and no "deleted" appears; `grep -rn "deleted" frontend/src/features/start-work` returns nothing.
8. [x] Project change (persona ceo): the card goes, the status line shows, the next upload goes to C-0102 at revision 3, the start sends C-0102 rev 4 with only the new id, and Project is disabled during the upload. e2e checks it too.
9. [x] Upload errors: 403 and 404 give an identical drawer `textContent`; 401 shows signed-out; 422 shows the `.exe` sample and a scenario message word for word; 409 re-reads E-LINES (fixed) or E-LINE-OPTIONS (project) and keeps values; 500 or network shows "Couldn't upload. Try again." with no resend after 60 s (fake timers); Try again re-reads first, then uploads once.
10. [x] Uncertain upload: component, mock and e2e tests show "Not uploaded", Try again (revisions 2 then 3), and a start with only `EV-SW-C-FIN-LEDGER-2` at rev 4 that gets 201.
11. [x] Start 409 keeps the card and resends with the re-read revision and a new key. `start_uncertain` shows "Check again" plus the My work line and the picker locked; Check again sends an identical body and key, lands, and `mock.started.size` is 1. e2e checks it too.
12. [x] Wrong record: mock tests cover another case, another persona and an id never issued, each answering 422 with the message. Component test: the message sits under Proof with one `[data-field="proof"]`. finance_lead upload to C-0102 answers 404 (mock test), and the drawer's 404 sentence is covered by criterion 9.
13. [x] Access: persona `none` gets no radios and no Proof group. Wrong CSRF gives the refusal and no "Uploaded" (component); missing or wrong CSRF answers 403 (mock). 401 on E-LINES, upload or start shows signed-out with `next=%2Fmy-work`. 403 and 404 on start read "You can't start this here."
14. [x] Plain text: an `<img src=x onerror=alert(1)>.pdf` name renders as text and `querySelector('img')` is null. A `<b>bold</b>` 422 shows as text with no `<b>`. The dialog has no `<a>` after upload. There is no `accept` or `capture`. `git diff -U0 frontend/src | grep -nE "PROOF_TYPES|PROOF_MAX_BYTES|accept=|\.size *[<>]"` returns nothing.
15. [x] Unknown never 0: a fixed line without `case_revision` can't start here and sends nothing. An upload 200 without `case_revision` leads to a start with 2 (the last known), and a 0-byte file never reads "0 KB". The same lines file served to pm, ceo and finance_lead gives identical Proof box HTML. The grep `useMe\|/api/v1/me\|roles` matches only `useMemo` and F-05's existing LineChooser comment; no new code reads `/me` or roles.
16. [x] Phone (e2e at 390): the bottom sheet; "×", "Choose a file", Try again, Start, segments and pickers are all ≥ 44×44; the sheet body has no sideways scroll; Escape closes and focus returns to "+ Start".
17. [x] Fidelity: one run of 8 boards (below). Coverage after exceptions is 100% on all 8. Visual is ≥ 90 on the two Finance desktop boards. The other 6 are waived per board under D-83 and Conflicts 14 (all ≥ 70).
18. [x] Accessibility: axe (wcag2a/2aa/21a/21aa/22aa) is clean at 1440 and 390 for empty and uploaded on all four drawers, and for uploading, failed, 422-under-Proof and Check again (ledger) and project-changed (minutes). The Proof group is named "Proof", the file input is labelled by it, and the project-changed line is `role="status"`. "Uploading…" and "Uploaded" are text.
19. [x] Tokens only: the CSS diff adds no hex, rgb, hsl or raw px (44 px comes from `--control-md`). There is no copy of ProofField, useEvidenceUpload or any `@/components` export.
20. [x] Mock matches the contract: `tests/start-work-proof-mock.test.ts` checks schema-valid lines, options, W-4401/2 and upload 200/409/422; F-09 (C-1601 gives `EV-C-1601-1`) and C-SETUP routing are unchanged; `/me` equals E-LINES for all personas; reset restores 6, 3 and 2.
21. [x] Contract not extended: no change to `src/api`, `src/components`, `src/shell`, `response.mjs`, `evidence.mjs`, `setup.mjs`, `architecture`, `design`, `openapi.json` or protected paths. In `src/features/response`, only the `useEvidenceUpload.ts` guard changed. `server.mjs` has the branch plus `cookies` on one existing line (listed above).
22. [x] Existing tests green: `delivery/checks.sh` passed, and the e2e passed (below).
23. [x] This file.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-47 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (run under `.checks.lock` with load below 14) exited 0. The Django check found no issues; lint and typecheck were clean; vitest gave **102 files, 2317 tests passed**; the production build succeeded.
- `cd frontend && E2E_PORT=4942 MOCK_PORT=4943 npx playwright test e2e/start-work-proof.spec.ts e2e/start-work.spec.ts e2e/response.spec.ts e2e/workspace.spec.ts` gave **73 passed, 4 failed**. All 4 failures were my new phone tests: they used the desktop selector `.psl-drawer__body` where the phone sheet's is `.psl-sheet__body`. I fixed the selector (commit 438c350f) and re-ran `e2e/start-work-proof.spec.ts` alone: **14 passed**. `frontend/test-results` was deleted after each run.
- Targeted runs during the build: `npx vitest run tests/start-work-proof.test.tsx` gave 32 passed; `tests/start-work-proof-mock.test.ts` 17 passed; `tests/start-work.test.tsx tests/start-work-mock.test.ts` 90 passed; `tests/start-work-intake.test.ts` 12 passed.

## Fidelity
Production build `API_ORIGIN=http://127.0.0.1:4940 FRAME_FIXTURES=1 npm run build && npx next start -p 4941`, mock on 4940, `POST /__mock/reset` before each board. Driver, run script and reports are in `round-1/fidelity/` (`_driver/act.mjs`, `_driver/run.sh`, `_driver/fid-driver.mjs`).

**About the run count:** the first invocation called the shared `fidelity.mjs` directly. That tool has no `--actions`, so it captured the bare My work page with no drawer open. Those results did not measure the feature and were deleted. The scored run used `_driver/fid-driver.mjs`, which is the shared tool plus F-05's actions hook.

| Board | Coverage | With exceptions (as run, then with "Done 28") | Visual | Result |
|---|---|---|---|---|
| SCR-04-desktop-minutes-1440 | 73.7 | 100 | 89.3 | waived (D-83) |
| SCR-04-desktop-change-1440 | 71.1 | 100 | 86.3 | waived (D-83) |
| SCR-04-desktop-schedules-1440 | 86.8 | 97.4, then 100 | 95.8 | ≥ 90 |
| SCR-04-desktop-ledger-1440 | 84.2 | 97.4, then 100 | 96.1 | ≥ 90 |
| SCR-04-mobile-minutes-390 | 69.2 | 100 | 78.6 | waived (D-83) |
| SCR-04-mobile-change-390 | 61.5 | 100 | 81.0 | waived (D-83) |
| SCR-04-mobile-schedules-390 | 61.5 | 100 | 75.3 | waived (D-83) |
| SCR-04-mobile-ledger-390 | 53.8 | 100 | 84.9 | waived (D-83) |

- The only open item in the run was the My work tab "Done 28" under the scrim on the two Finance desktop boards. I added it as a Conflicts 8 exception afterwards and recomputed coverage from each `report.json` with the tool's own role and name matching, without another run.
- The fidelity check flagged no item inside any drawer as missing.
- `fidelity-exceptions.json` has 30 exceptions (Conflicts 7, 8 and 9) and 6 visual waivers, one per board, each naming that board's own gaps. All read "builder proposal, pending design engineer".

## Blocked
None.

## Open for the design engineer (D-114, provisional)
All 14 Conflicts are built as recommended and need sign-off, in particular: 1 (ProofField card), 2 ("×"), 3 (empty and waiting states), 4 (project change drops the proof), 5 (Start held), 6 (no `next`), 7 (Finance lines for the Finance persona only), and the 6 visual waivers.

Backend items are in BACKEND-HANDOFF.md (F-47 section): the Finance cases and their revision source, evidence kind names, limits as 422, duplicate-by-sha256, one revision per case, `next` and who may start.

Held, from the spec's "What is sent": Finance runs may wait in `setup_needed`; F-47B (fixed assets, cash forecast); F-47C (management accounts and `money`); payroll and business-unit drawers.
