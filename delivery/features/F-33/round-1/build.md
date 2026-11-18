STATUS: READY
COMMIT: 552c91602c0dc6e3d1e089517c3cb4bc19e9fcfd
BUILDER: builder
LANE: full

## Summary
- SCH-0021 "Income detail · October" now opens on the F-17 line workspace in four board states: investigating (W-2701), review (W-2702), returned (W-2703) and verified (W-2704). There are 7 more fixtures: you prepared it, reviewer not set (the hold), unknown amount, not your role, two verdicts, no verdict, malformed verdict.
- The review is decided in place. A new `InlineDecide` panel ("Decide · <required_role>") is driven by the `steps[].verdict` overlay and writes through the existing F-16 `useDecision` (claim once, then decide). Buttons appear only while `tasks[].you_can_act` is true. Return and reject need a note, which is checked before any request. On a phone the buttons are pinned in a bar, and Return and Reject open the full-height Drawer.
- Money rules:
  - every amount is the backend's decimal string, formatted as returned;
  - the page computes no total, count, difference or short form ("₦12.4M" is not drawn);
  - an unknown amount or count reads "Unknown", never 0.
- "Verified" appears only when the re-read item says `state: verified` with the `verified` tone. The W-2706 hold has no controls, sends no writes and names no reviewer.
- Correct and resubmit uses the existing E-WORK-STEP flow. On a phone it opens the Drawer, and the re-read item shows the schedule back in review with the "prepared by you" reason.

## Changes
- `frontend/src/features/workspace/InlineDecide.tsx` (new): the Decide panel over `useDecision`.
  - Note label: "Note (needed to return or reject)", naming only the verdicts this panel offers that need a note.
  - Note messages: "Add a note to return it." / "Add a note to reject it." / over 2000 characters, checked before any request.
  - Claim states: pending, failed and invalid.
  - Error views: 409 shows the stale view with "Review the latest"; 403 shows the read-only view using `cannotActCopy`; an unconfirmed write shows the unconfirmed view; 5xx or network shows `UncertainNotice`.
  - Losing access (401/403/404) hands over to `page.onAccessLost`.
  - After each settled outcome the page re-reads once. A 200 gives the `VERDICT_WORDS` notice ("Schedule v1 is approved").
  - Phone: buttons pinned in a bar that measures its own height; Return and Reject open the Drawer with Cancel; focus goes back to the opener.
- `proposals.ts`: `stepVerdict(step)` returns approve|return|reject. It returns `undefined` when the step has no `task_id` or no verdict (the existing link stays) and `null` for any other value (the step is not drawn).
- `Workspace.tsx`:
  - Workspace steps with a valid verdict go to `InlineDecide`, one panel per `task_id`. Steps with an invalid verdict are not drawn. Everything else is unchanged.
  - The done notice is held in the page's existing live region, so it survives the re-read.
  - Income line only: the station row in the main column on desktop (`MiniStationBar` with "Station n of 5 · Name" on a phone), and the working agent's `AgentCard` plus "Started 11:20" in the side column.
  - The phone Drawer for step forms now covers the income line too.
- `workspace.css`: additive rules, tokens only.
- `Sections.tsx` (shared; defect fix): a `figures` item's returned `tag` was dropped. It is now drawn beside the value ("2" then the CHIDI CHECKING tag, in agent style). No existing fixture has a tag on a figures item.
- `work-item/WorkItemOverview.tsx` (outside the listed lane; income line only, two small edits):
  1. A task with `cannot_act_reason: already_decided` and no step gets no "Only a … can decide" card. Without this, the verified and decided pages drew an unboarded panel above the workspace.
  2. The screen-reader-only copies of the station track (desktop) and of the working agent card are not drawn, because the workspace now draws them visibly. This avoids reading them twice.
- Fixtures `frontend/mock/fixtures/work/W-2701…W-2711.json`:
  - `W-2702.approve|return|reject.json` sidecars: each one revision higher, with the task `already_decided`.
  - `W-2703.steps.json` (200 done with a message) and `W-2703.next.json` (back in review, `prepared_by_you`).
  - There is no `W-2702.next.json`. Every fixture is `sample: true`. No existing fixture changed.
- Tests:
  - `tests/income-schedule.test.tsx` (28 tests).
  - `tests/income-schedule-mock.test.ts` (7 tests).
  - `tests/mock-contract.test.ts`: strips `steps[].verdict` (only on a step with a `task_id`), and allows the `links` overlay on `W-2701.json`.
  - `e2e/income-schedule.spec.ts` (28 tests).
- `delivery/BACKEND-HANDOFF.md`: new section "Added during F-33: income schedules (18 Nov)".
- Factory files in the project folder: `delivery/features/F-33/fidelity-exceptions.json` and `round-1/fidelity/` (`run.sh`, 8 reports, `scores.txt`).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Four states from data: component tests for W-2701…W-2704 (status label and tone, stations, sections, agent card, quote, facts, Next). A test walks `src` for the board strings, and the spec grep returns nothing. Pages seen at 1440 and 390 in the fidelity run and in screenshots.
2. [x] Amounts as returned: "₦12,400,000.00" at desktop and phone (matchMedia stub), with no "12.4M". A copy with "12400000.10" shows "₦12,400,000.10". The e2e checks this at both widths.
3. [x] Computes nothing: modified copies tested ("30 ROWS" leaves the section title unchanged; "1 OF 2" and a changed `next` change only that text). `git diff -U0 d9ca6f97 -- frontend/src | grep -nE "parseFloat|Number\(|\.reduce\(|compactAmount"` returns nothing.
4. [x] Unknown: on W-2707 the report line and Detail rows read "Unknown". There is no "₦0" or "0.00", and no fact value cell is empty, "-" or "—".
5. [x] Sample: with `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1`, all 11 fixtures show SAMPLE DATA and a `sample: false` copy does not.
6. [x] W-2706 hold: SETUP NEEDED, "Who reviews schedules" NOT SET, the `next` sentence. No Decide panel, no button, zero POSTs. `main` contains neither "Ada Okafor" nor "Schedules reviewer". (Ada Okafor appears only in the shell's signed-in name.)
7. [x] Controls: W-2702 shows the three buttons under "Decide · Schedules reviewer". W-2709 shows Approve and Return only. W-2711 draws neither `revoke` nor `post`. W-2710 is the link to `/work/W-2710/decide?task=T-2710`. W-2705 and W-2708 show their reason, no button and no claim. Personas finance_lead, ceo and pm see the same controls. `InlineDecide.tsx` has no `useMe` or `/me`.
8. [x] Agent: Chidi's steps, sources, WORKING (agent tag) and CHIDI CHECKING (agent tone) are drawn, with no decide control and no "none" wording. "Ask Chidi" links to `/assistant`.
9. [x] Verified only from the response: W-2704 shows VERIFIED from its status. Approve shows VERIFIED only after the re-read serves the approve sidecar. With a 200 decide and a re-read still in review, the status and notices never say Verified. No Export or Withdraw button.
10. [x] Approve: one claim to `/api/v1/tasks/T-2702/claim`, then exactly one decision `{verdict: "approve", expected_revision: 1}`. It validates against the v7 request schema, carries `X-CSRFToken`, and a double press sends one. Shown in a component test and in the e2e request log (dblclick sends one claim and one decision).
11. [x] Note rule: empty, blank and over-2000 notes send nothing. The message sits under the field with `aria-invalid` and is described by the field, and focus moves to the note. With a note, one POST with the trimmed note. The return and reject re-reads draw RETURNED and REJECTED.
12. [x] No write when the person cannot act: the e2e request log is empty across W-2705, W-2706 and W-2708 at 1440 and 390.
13. [x] Refusals: 403 shows the read-only view with the re-read reason and no "approved". 409 shows the stale view and keeps the note; the next press after "Review the latest" sends `expected_revision: 2`. 422 puts the backend message under the note. The mock test shows 409 for a stale revision and 403 for W-2705/W-2708.
14. [x] Uncertain decide: for a 500 and for a network failure, the decision is followed first by a GET of the item, then `UncertainNotice` shows, with no "approved/returned/rejected/verified". After 60 s of fake time there is still one decision POST. The e2e aborts the decide route and checks the same.
15. [x] Correct and resubmit: a required Segmented choice of three with nothing selected. An empty submit sends nothing. A 500 then Try again reuses the same UUID key. The body validates against the v7 step schema with CSRF and `expected_revision: 4`. On 200 the re-read shows the `prepared_by_you` copy. "resubmitted" is never shown. It also works on the `W-2702.return` sidecar. e2e at both widths (Drawer on phone).
16. [x] No D-RETURN wording: the quote and the consequence are shown as returned, and the grep for "backend only waits|every return" in `frontend/src` returns nothing.
17. [x] Access: 401 on decide shows sign-in with `next=%2Fwork%2FW-2702`. 403 and 404 on read look the same, with no title or amount. Persona `none` gets the shell's not-open state with zero work reads and zero POSTs. The e2e checks that the 403 view is axe-clean.
18. [x] Phone: one column. The Decide bar is `position: fixed` with the three step labels. Return, Reject and Correct and resubmit open the Drawer. Escape and Cancel return focus to the button. There is no sideways scroll. All controls are at least 44×44, except the frame's History link (42×24, F-17 `.work-linehistory`, not this feature's code) — see Open.
19. [x] Fidelity: 100% coverage with exceptions on all 8 boards. Visual scores are 72.9–87.8, so all 8 have board-level waivers citing D-83 (all ≥ 70). Each of the 18 exceptions has role, name, category, reason, a Conflicts number (`conflicts`) and `approved_by`. None covers a value the data supplies (they cover frame items, AgentCard layout, the decide-panel wording calls, the form opening on press, and items held to part 2).
20. [x] Accessibility: axe (wcag2a/2aa/21a/21aa/22aa) is clean at 1440 and 390 on W-2701…W-2706, on the open Drawer, the note error, the uncertain notice and the not-open view. The agent card has no animation under `reducedMotion: 'reduce'`.
21. [x] Tokens and components: the diff adds no `#hex`, `rgb(`, `hsl(` or raw px in `workspace.css`. `Button`, `Drawer`, `TextArea`, `Callout`, `Loading` and `MiniStationBar` are imported from `@/components`.
22. [x] Mock: `income-schedule-mock.test.ts` checks:
    - schema validity with the overlay stripped;
    - claim then approve serves the approve sidecar, and a repeat decide is 409;
    - return with no note or a blank note is 422; return and reject serve their sidecars;
    - a stale revision is 409; decide on W-2705/W-2708 is 403;
    - the W-2703 step serves its next sidecar;
    - reset clears.
23. [x] Contract not extended: `git diff --stat d9ca6f97` shows nothing under `src/api`, `src/features/decide`, `src/shell`, `mock/server.mjs`, `mock/workspace.mjs`, `fixtures/response`, `fixtures/finance`, `E-MONTH-END.json`, `apps`, `architecture`, `design` or the protected paths. No existing fixture is modified or deleted. Overlay proposals are listed below.
24. [x] Existing tests green: `delivery/checks.sh` passes (2303 tests). The listed must-stay-green files pass, as does the e2e command under Lanes (105 passed).
25. [x] This file.

### Overlay proposals and backend items (also in BACKEND-HANDOFF)
- `workspace.steps[].verdict` (G-C-1); inline placement, with no field (G-C-2). `money.display_short` is not built.
- Questions for the backend:
  - G-54-3: the initial value for Row 12, and whose value it would be.
  - D-RETURN: does a return create the preparer's task?
  - G-C-3: the `setup_needed` shape and the Setup link.
  - The state and view names used for each state.
  - G-C-4: "Ask Chidi" context.
  - Readiness questions 1–4.
- Held because a decision is open: who reviews schedules, the income detail and inventory rules (all NOT SET), D-RETURN, and which verdicts a review offers.
- Held to part 2: the held board and duplicate settlement, Export (G-54-5), Withdraw (`revoke`), and the inventory kind.
- Mock seam option (b): W-2701…W-2704 are opened directly. The month-end row and W-1603 are unchanged.

## Validation
- `cd frontend && npx vitest run tests/income-schedule.test.tsx`: 28 passed.
- `npx vitest run tests/income-schedule-mock.test.ts`: 7 passed. `tests/mock-contract.test.ts`: 297 passed.
- `npx vitest run` on the Context list plus issue-detail, work-item, work-item-board, minutes and minutes-end: 16 files, 609 passed (before the last two edits). After the edits, the affected subset was rerun: 7 files, 491 passed.
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh`, run under the shared lock at commit 552c916's tree: exit 0. Django check reported no issues; lint, typecheck and build succeeded; 102 files and 2303 tests passed. No load flakes.
- `cd frontend && E2E_PORT=4881 MOCK_PORT=4880 npx playwright test e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/finance-month-end.spec.ts`: 105 passed (3.6 min). Ports 4880/4881 are the caller's. Earlier runs had fixed failures in my own spec: the 403 test now routes only the item read, and the frame's History link is excluded and reported.
- Fidelity: production build with `API_ORIGIN=http://127.0.0.1:4880 FRAME_FIXTURES=1 npm run build && next start -p 4881`, mock on 4880, persona finance_lead, `round-1/fidelity/run.sh`. Scores (coverage / with exceptions / visual):

| Board | Coverage | With exceptions | Visual |
|---|---|---|---|
| SCR-54-desktop-investigating 1440 | 83.3 | 100 | 87.8 |
| SCR-54-desktop-review 1440 | 86.1 | 100 | 76.6 |
| SCR-54-desktop-returned 1440 | 75 | 100 | 72.9 |
| SCR-54-desktop-verified 1440 | 87.1 | 100 | 75.9 |
| SCR-54-mobile-investigating 390 | 77.8 | 100 | 84.7 |
| SCR-54-mobile-review 390 | 75 | 100 | 80.5 |
| SCR-54-mobile-returned 390 | 71.4 | 100 | 83.2 |
| SCR-54-mobile-verified 390 | 66.7 | 100 | 85.1 |

  - About the run count (D-64): I ran one probe with no exceptions into the scratchpad to find the missing items and draft exceptions. I then fixed the stations and agent card, which were hidden from the extractor by aria-hidden.
  - The first recorded run served stale W-2703 fixtures because the mock was started before I regenerated them. I restarted the mock and the run was redone. The table above is that rerun, the only one kept.
  - What the waivers cover: the shared frame (page width, top bar, crumbs, taller station boxes with a status line, bold fact labels), the correction form opening on press, the D-RETURN note not drawn, and the part-2 buttons.

## Open
- The frame's phone "History" link (`.work-linehistory`, F-17) is 42×24, under 44×44. It is on every line workspace, is not this feature's code, and is left for the frame owner.
- `WorkItemOverview.tsx` is outside the listed lane (two income-line-only edits, explained under Changes). The coordinator should confirm or move them.
- Every exception and all 8 visual waivers are "builder proposal, pending design engineer". The agent card reads "step 4 of 4" while the board reads "step 3 of 4": AgentCard counts the next unfinished step. This is listed under Conflicts 15.
- Integration: `Workspace.tsx`, `proposals.ts`, `workspace.css` and `mock-contract.test.ts` are likely touched by F-31 and F-32 too.
