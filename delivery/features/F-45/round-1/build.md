STATUS: READY
COMMIT: af1d1c8d3629b577c4baeebb4eae025c6a511397
BUILDER: builder
LANE: full

## Summary
- LED-0052 "QuickBooks journal JE-7741 · October" works on the shared Finance line layout. It has four board states: investigating, observe, review and verified (W-4201 to W-4204). There are also holds, refusals and uncertain fixtures (W-4205 to W-4213). Every fixture is sample data, there is no amount anywhere, and nothing is read from or sent to QuickBooks.
- Recording what you found goes through F-17's step form. The choice is the shared Select with nothing pre-chosen, and Proof is required. The upload goes to C-LED-0052 with `kind: ledger_observation`, then one step is sent. Review is F-33's InlineDecide with approve and reject only, and "Verified" appears only after the re-read.
- Change to shared code (scoped): a stale 409 on decide used to make the panel vanish and lose the typed note. Now, on the ledger line, the page keeps the stale sentence and "Your note wasn't sent: …" once the re-read closes the task.
- F-47 merged first, so F-45 points the ledger start's landing at W-4201 (spec Lanes, AC 23).
- Fidelity: 100% coverage after the proposed exceptions on all 8 boards. After the coordinator's second run, visual is 76.4 to 91 (desktop review went from 68.7 to 81.2). No floor exception is needed now. 7 waivers are builder proposals.
- Coordinator decisions (same round): (1) on the ledger line, the "approved" wording appears only when the re-read has moved on; otherwise the page says "LED-0052 v1: result not confirmed". The test failed first. (2) Ledger-scoped station and fact styling lifted desktop review above 70.

## Changes
- `frontend/src/features/workspace/labels.ts`: adds `ledger_sources` to F-42's `SCHEDULE_LINES` (stations in the workspace, agent card beside, phone Drawer, stopped-station banner, no card for a decided task).
- `frontend/src/features/work-item/WorkItemOverview.tsx`: no "See all exceptions" button on ledger holds (`setup_needed` is an exception state). Policy holds show no controls, as F-42 does for fixed assets.
- `frontend/src/features/workspace/InlineDecide.tsx`: a required `onStale(note)` callback plus `DECIDE_TEXT.noteNotSent`. The hunk is byte-identical to F-39 45ae7b66 and F-35 971bf73a.
- `frontend/src/features/workspace/Workspace.tsx` (coordinator decision 1): on the ledger line, `onDecided` records its `taskId`. If the re-read still offers that task's verdicts, a settled notice becomes `DECIDE_TEXT.notConfirmed(<version label>)`, never the VERDICT_WORDS heading. Other lines pass `onDecided` unchanged.
- `frontend/src/features/workspace/workspace.css` (coordinator decision 2): on `.ws[data-line="ledger_sources"]` only, using tokens only. Stations are drawn as the boards draw them: number and name, 13px sans 600, no minimum height, with the status word visually hidden but still read by screen readers. Fact labels are in body weight.
- `frontend/src/features/workspace/Workspace.tsx`: keeps `staleDecide` and shows the stale callout with the unsent note once the task's panel is gone. It is gated on `line_key === 'ledger_sources'` (new `LEDGER_LINE` constant). Otherwise it is the same as F-35/F-39's Workspace hunk.
- `frontend/mock/fixtures/work/W-4201…W-4213` plus sidecars: `.next` (4202, 4208, 4213), `.steps` (4202, 4208, 4213), `.approve`/`.reject` (4203, 4212). There is no `.next` on any review fixture.
- `frontend/mock/start-work.mjs`: `WORK_IDS.ledger_sources` changes from W-4402 to W-4201. W-4402 stays as a fixture because `start-work-proof-mock.test.ts` reads it.
- Tests:
  - `tests/ledger-source.test.tsx`: 47 component tests.
  - `tests/ledger-source-mock.test.ts`: 18 tests against the real mock.
  - `e2e/ledger-source.spec.ts`: 37 tests at 1440 and 390.
  - `tests/mock-contract.test.ts`: adds W-4201 and W-4211 to the links allowlist, plus an F-45 block.
  - `tests/income-schedule-mock.test.ts`: the verdict allowlist regex changes from `27|39` to `27|39|42`, as F-42 did.
  - F-47 landing assertions changed from W-4402 to W-4201 in `tests/start-work-proof*.ts(x)` and `e2e/start-work-proof.spec.ts`.
- `delivery/BACKEND-HANDOFF.md`: new "Added during F-45" section.
- Feature folder:
  - `fidelity-exceptions.json`: 27 exceptions and 8 visual waivers, all "builder proposal, pending design engineer".
  - `round-1/fidelity/`: `run.sh`, `drive-states.mjs`, `serve-frozen.mjs`, `frozen/`, `scores.txt` and the 8 reports.
- No change to `mock/response.mjs`, `server.mjs` or `workspace.mjs`, any existing fixture, `src/api|decide|response|start-work|shell|components`, `StepForm`, `Steps` or `proposals.ts`.

## Fixes
- COORD-1-1 | 65ddbf68 | Ledger line: "<label> is approved/rejected" only when the re-read no longer offers the task; otherwise "result not confirmed". The test `a 200 whose re-read still serves the review never says Verified or approved` failed before the change (1 failed) and passes after. The approve-to-verified test now also asserts "LED-0052 v1 is approved". F-33's income line is unchanged: `income-schedule.test.tsx` passes, including its "Schedule v1 is approved" assertion.
- COORD-1-2 | 7a92f667 | Desktop review visual went from 68.7 to 81.2 through ledger-scoped station and fact styling, with one more fidelity run (`round-1/fidelity-2/`). The floor exception is dropped.
- (test robustness) | 4dba97ab | The e2e and the fidelity driver wait for "Uploading…" to clear before recording. The W-4213 e2e had failed once in 2 of 9 runs because it submitted mid-upload.

## Spec against merged F-33 (and dlv-00 since d20fd9b2): differences
1. **Line predicate.** The spec asks for a new `FINANCE_BOARD_LINES` set. F-42 had already merged that set as `SCHEDULE_LINES`/`scheduleLine`, used at every branch: `bannerTone`, `inDrawer`, `schedule`, `Workspace()`, and WorkItemOverview `:704`/`:729`. I added `ledger_sources` to it and did not create a second set. The spec's line references (`INCOME_LINE :105`, `:181`, `:643`) no longer exist.
2. **InlineDecide.** The merged version matches what the spec quotes: `DECIDE_TEXT.needed` ("Note (needed to reject)"), a claim on load only when `you_can_act`, the "Getting this review ready…" line, the phone Drawer for verdicts that need a note, and the stale panel with "Review the latest". It also has the stale-409 gap. That gap is fixed here, scoped (see Summary and Pending).
3. **`stepVerdict`.** Unchanged from d20fd9b2: `undefined` means no proposal, `null` means the value is not drawn, and the values are approve, return and reject.
4. **`steps[].verdict` overlay strip.** It is generic in `mock-contract.test.ts`. The regex allowlist in `income-schedule-mock.test.ts` named only W-27/W-39, so I extended it to W-42. The links allowlist in `mock-contract.test.ts` also needed W-4201 and W-4211.
5. **Reviewer-not-set hold.** The W-2706 shape is unchanged and reused for W-4205. However, merged WorkItemOverview drew "See all exceptions" on `setup_needed` for every line except issue and fixed assets, so I excluded `ledger_sources`.
6. **Upload seam.** F-31, not F-34 or F-45, already merged the step-evidence grant in `response.mjs`, so F-45 changes nothing there. That grant does not check the step's `disabled_reason`, which the spec asked for. On the mock, the W-4210 capturer could still upload to C-LED-0052. The page sends nothing (tested), and this is flagged for the backend in the handoff.
7. **AC 9 wording conflict.** After a decide 200 and a successful re-read, merged InlineDecide says "<label> is approved" even when the re-read still serves the review, and F-33's test asserts this. **Resolved for the ledger line (coordinator decision):** Workspace downgrades the notice to "result not confirmed" while the re-read still offers the task. InlineDecide is unchanged. The income line keeps F-33's behaviour, recorded as a coordinator follow-up.
8. **Agent card.** It reads "step 4 of 4" from the steps sent (3 done), where the board says "step 3 of 4". It also has no title. This is exception Conflicts 14.
9. **F-47** merged before F-45, so the repoint is F-45's (done). **Ports:** I used 4955 (app) and 4954 (mock) as instructed, not the spec's 4970/4971.

## Stale-409 approach
- The InlineDecide hunk is identical to F-39 45ae7b66 and F-35 971bf73a. It records the note the decide carried and calls `onStale(note)` on a 409.
- The Workspace hunk is F-35's, with one extra gate: `workspace.line_key === LEDGER_LINE`. The behaviour on every other line is unchanged.
- When the re-read closes the task (another reviewer decided), the panel goes. The page then shows "This review changed while you were reading it, so nothing was recorded." and "Your note wasn't sent: “…”". It sends nothing on its own.
- When the task survives, InlineDecide's own stale view keeps the note, and a new press carries the new revision.
- Tests:
  - three component tests (desktop, approve race, phone Drawer), which fail on the old code (3/3 failed with the src changes stashed);
  - an e2e test with two tabs at 1440 and 390.
- When F-35 or F-39 merges, the coordinator keeps their general hunk and drops the ledger gate.

## Acceptance criteria
1. [x] Four states from data: component tests for W-4201 to W-4204, and the e2e at 1440 and 390. The board-string grep on `frontend/src` returns nothing.
2. [x] No amount: a component test renders all 13 items and 7 sidecars (no ₦, no NGN, no digit groups). The mock test checks every fixture file. The changed-fact test passes. The diff grep for parseFloat, `Number(`, `.reduce(` and compactAmount returns nothing.
3. [x] W-4211 Treatment reads "Unknown". The third step reads "✓Done: Checked where it came from", with no source.
4. [x] SAMPLE DATA shows on all 13 fixtures with NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1. A copy with `sample: false` shows none.
5. [x] W-4205: status, fact and next are as returned, with no button, link or POST. Neither "Ada Okafor" (in `main`; the shell's signed-in name is outside it) nor "Ledger reviewer" appears. No Setup control appears on any fixture.
6. [x] W-4208 Unknown sends one step with `inputs.found: "unknown"` and re-reads to CHECK HELD (station 3 stopped, facts, next, no control). A double whose re-read is still observe shows no hold.
7. [x] Controls:
   - W-4203 shows the buttons, basis, consequence and "Note (needed to reject)", with no Return.
   - W-4206 and W-4207 show their copy, with no button and no claim.
   - W-4210 is inert with its reason.
   - finance_lead, ceo and pm see the same controls on all 13.
   - The `/me`/`is_you`/`prepared_by` diff grep returns nothing.
8. [x] W-4201 agent card: WORKING, sources and "Started 15:12" in the side column; Ask Chidi links to /assistant. In the e2e, every request stays on the app origin, and the API calls go only to `/api/v1/`.
9. [x] VERIFIED only from the re-read, and W-4204 has no control. A 200 whose re-read is still the review never says Verified or approved ("LED-0052 v1: result not confirmed").
10. [x] Observation:
    - The form validates both fields, is announced, and puts focus on the Select.
    - The upload carries `kind`, `case_revision` 4 and CSRF, and it is schema-valid.
    - Exactly one step is sent with exactly five keys and a UUID key; a double press sends one.
    - The re-read shows the `prepared_by_you` copy.
    - Nothing says "recorded" before the re-read (pending-read test).
11. [x] Upload failures:
    - A 5xx shows the problem and sends no step.
    - A 409 re-reads, and the next upload carries case_revision 6.
    - "×" leaves Proof empty and nothing is sent.
    - 403 shows a message.
    - The mock refuses persona none (403), a wrong kind (422) and a stale revision (409).
    - `response-mock.test.ts` passes unchanged.
12. [x] Reject: empty, blank and over-2000 notes are refused before sending, with focus on the note and aria-invalid/describedby. With a note, one POST is sent with the trimmed note, and the page shows REJECTED with no Correct step. Approve sends `{verdict: approve, expected_revision: 1}` after one claim to T-4203. Covered by component and e2e tests.
13. [x] The e2e presses every button on W-4201, W-4204 to W-4207, W-4209 and W-4210: zero POSTs at both widths.
14. [x] 403 on decide shows the read-only copy, and on the step "You can't take that step." A 409 on decide keeps the note and the new press carries revision 2. A 409 on the step keeps the choice and the proof and sends nothing more. A 422 shows under the field and under the note.
15. [x] W-4212 approve and reject show CHECKING and "result not confirmed". A 500 or network error re-reads first and shows UncertainNotice, and after 60 s with fake timers there is still one POST. The e2e routed abort passes.
16. [x] W-4213: the re-read comes first, then `STEP_TEXT.failed`, never "Observation recorded.". The mock log shows one applied step, and a retry with the same key is a replay.
17. [x] 401 on the read, the decide and the step all go to sign-in with `next`. 403 and 404 render identical text, with no title, fact or agent step. Persona none makes no further call.
18. [x] Phone: the step form opens in the Drawer with the Select and the file input. Cancel and Escape return focus. The Decide bar is fixed. There is no sideways scroll. Every target is at least 44 px, including the chip "×" after an upload (e2e).
19. [x] Fidelity on a production build, with observe driven: the first run plus the one extra run the coordinator authorised. Coverage after the proposed exceptions is 100% on all 8. Visual is 76.4 to 91, with 7 D-83 waivers proposed and no board under 70.
20. [x] Axe is clean at 1440 and 390 on W-4201 to W-4205 and W-4209, the open form with an upload, field errors, the note error, the Drawer, the uncertain notice and the not-open view. The agent tag does not animate under reduced motion.
21. [x] No hex, rgb or hsl added, no CSS changed, and no local component copies.
22. [x] `tests/ledger-source-mock.test.ts` covers schema, sample and line, upload then step for W-4202 and W-4208, claim then approve, reject 422, stale 409, W-4206 403, W-4212 uncertain, and reset.
23. [x] `git diff --stat origin/dlv-00-delivery-setup...HEAD` touches none of the protected or shared paths. The exception is the allowed F-47 repoint (`mock/start-work.mjs`, one line). `response.mjs` is unchanged. The overlay fields are listed below.
24. [x] checks.sh passes. The full e2e (below) passes.
25. [x] This file.

## Validation
- `delivery/checks.sh`, run under the shared lock at 4dba97ab: Django check clean; lint, typecheck and build ok; vitest 120 files and 2882 tests passed; exit 0.
- `cd frontend && npx vitest run tests/ledger-source.test.tsx tests/ledger-source-mock.test.ts tests/mock-contract.test.ts tests/income-schedule-mock.test.ts tests/start-work-proof*.ts*`: all passed (47, 18, 343 and 144 tests).
- `cd frontend && E2E_PORT=4955 MOCK_PORT=4954 npx playwright test e2e/ledger-source.spec.ts e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/start-work-proof.spec.ts e2e/asset-schedule.spec.ts`: 164 passed (7.9 m) at 4dba97ab, exit 0.
- Fidelity: `round-1/fidelity/run.sh live`, then `node drive-states.mjs` (log: "no step sent"), then `run.sh frozen`. The app was the production build on 4955 with FRAME_FIXTURES=1, the mock on 4954 and the frozen pages on 4956. All servers are stopped and `test-results` is deleted.

## Fidelity
| board | coverage | after exceptions | visual, run 1 (`fidelity/`) | visual, run 2 (`fidelity-2/`) |
|---|---|---|---|---|
| desktop-investigating 1440 | 86.7 | 100 | 80.1 | **91** (passes, no waiver) |
| desktop-review 1440 | 88.2 | 100 | 68.7 | **81.2** |
| desktop-verified 1440 | 89.3 | 96.4 in run → 100 | 74.1 | 80.5 |
| desktop-observe 1440 (driven) | 81.8 | 100 | 71.8 | 76.4 |
| mobile-investigating 390 | 77.8 | 100 | 83.2 | 83.0 |
| mobile-review 390 | 85.7 | 100 | 82.9 | 83.4 |
| mobile-verified 390 | 80 | 100 | 75.9 | 78.2 |
| mobile-observe 390 (driven) | 83.3 | 100 | 77.8 | 77.8 |

- **Run 2** is the single extra run the coordinator authorised, with the same driver and boards (log: "no step sent").
- **Desktop verified:** the only element left is the board's unnamed side column. The spec sends the re-check sentence as an untitled `text` section, which the shared workspace draws in the main column. The `layout` exception (Conflicts 13) proposes, as Option B, that the backend send it as `workspace.next`. That exception now has `name: ""`, because the tool matches an unnamed area by role and empty name; it showed as "(side panel)" and did not match, so it was still counted. Coverage after exceptions is recomputed from `report.json` against the final file: 100. I did not run fidelity again.
- **Exceptions by Conflicts number:**
  - 3: the answers in the closed Select.
  - 7: the note label and "What happens next:".
  - 8: the phone titles.
  - 9: Many, Observed, FOUND, Reference, RECORDED, Posted.
  - 10: "Look up JE-7741 in QuickBooks".
  - 11: "Uploaded · 310 KB".
  - 12: crumbs, ← My work, and the Bisi and Chuka names.
  - 13: the side column.
  - 14: the agent card's title and role line.
  - SAMPLE DATA: design decision 14 Nov (c) and D-92.
- **Remaining gaps:** the shared frame (top bar, crumbs as a list, History link, page width), taller shared fact rows, the shared TextArea height, and the components listed in each waiver.

## Contract proposals (mock only)
- `line_key: "ledger_sources"`.
- The view names: investigating, observe, review, verified, rejected, check_held, setup_needed and effect_uncertain.
- `steps[].verdict` (approve/reject; F-33 G-C-1).
- `workspace.links[]` assistant (X-LINKS).
- The step `record_observation` with field `found` (found, not_found, unknown, more_than_one) and field `proof` (`evidence_kind: "ledger_observation"`).
- One case per source, `C-LED-0052`.
- No value the boards show is missing from an endpoint.
- Backend items are in BACKEND-HANDOFF:
  - G-58-3 and G-58-4;
  - three separate people;
  - the `setup_needed` shape;
  - G-C-1 and G-C-4;
  - G-58-5;
  - which case holds the proof;
  - upload grant against `disabled_reason`;
  - no QuickBooks reads;
  - claim on load;
  - no idempotency key on decide.

## Held (from "What is sent")
- All three ledger policy values are NOT SET.
- Separation of the three people (G-58-4).
- What Unknown or More than one does (G-58-3).
- The verdict set (G-C-1).
- "Ask Chidi" context (G-C-4).
- The re-check (G-58-5).
- Part 2: duplicate (G-58-1), Correct with `continues` (G-58-2, G-C-6), Open LED-0049 (G-C-3) and the rejected board.

## Pending
- Design engineer:
  - sign the 27 exceptions and 7 D-83 waivers (no floor exception now);
  - decide the verified side note: keep it in main, or have the backend send it as `next`;
  - review the ledger-scoped station style (status word kept for screen readers only, as the boards draw it).
- Coordinator follow-up: the income line (F-33) still shows "<label> is approved" when a re-read has not moved on.
- Coordinator: when F-35 or F-39 merges, reconcile the stale hunk (keep the general one and drop the `LEDGER_LINE` gate). F-42, F-43 and the line set are integration items. F-47's landing now points to W-4201.
- Product acceptance (required).

## Blocked
None.
