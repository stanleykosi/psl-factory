STATUS: READY
COMMIT: 356656654596e6bc7295f4cdca4f80a88d4ce2e5
BUILDER: builder
LANE: full

## Summary
- SCR-51 part 1 is built on the F-17 line workspace for `line_key: "escalation"`: `/work/W-3601` (investigating), `W-3602` (decide), `W-3603` (not escalated), `W-3604` (draft), plus W-3605 to W-3609. Contract mock only.
- **Nothing reaches the client in part 1.** No message is sent, emailed or delivered to Lagoon Health or anyone outside PSL. Message v1 is Tola's draft, shown as returned. "Send for review" only hands it to the PMO Lead inside the app. No fixture step sets `sends`. A test over every fixture, sidecar and notice finds no "sent to", "was sent", "has been sent", "delivered", "received" or "This sends to the client" (one exception: the shared F-16 uncertain notice says "Nothing was sent again.", see Findings below).
- The decision is taken in place with F-33's `InlineDecide` over `useDecision`, unchanged. Controls come only from `tasks[].you_can_act` and `required_role`; nothing reads `/me`. No state is shown before the re-read; an uncertain decide reads "result not confirmed" and RESULT NOT CONFIRMED.
- Code change is three small edits: the `escalation` line joins F-33's visible agent card rule (`drawsAgentCard` in `Workspace.tsx`, used by `WorkItemOverview.tsx`), and the phone back link goes to the project for the escalation (`WorkItemView.tsx`). No CSS, no shared file other than those.
- Fidelity: second run (final exceptions file) gives 100% coverage after exceptions on all 8 boards; visual 90.1 on desktop-investigating and 76.8 to 86.1 on the other seven, each with a waiver (pending design engineer). First run kept as `scores-first-run.txt`.
- Coordinator decisions applied: `InlineDecide` now names who was asked, only when the response sends `asked` (additive; no change when absent); the footer time-only is an exception; the board-string criterion excludes F-16's eyebrow; the missing `inputs: {}` is a recorded spec deviation.

## Changes
- `frontend/src/features/workspace/Workspace.tsx`: `ESCALATION_LINE` and exported `drawsAgentCard(lineKey, status)` (income while working, escalation while working or done); the two `agentSide` lines use it.
- `frontend/src/features/work-item/WorkItemOverview.tsx`: the screen-reader copy of the agent card follows `drawsAgentCard`.
- `frontend/src/features/workspace/InlineDecide.tsx`: in the cannot-act branch, draws `task.asked` (`name · role`, comma separated) only when present. Test in `escalation.test.tsx` (present and absent).
- `frontend/src/features/work-item/WorkItemView.tsx`: phone bar "← Project" for the `escalation` line.
- `frontend/mock/fixtures/work/W-3601.json` to `W-3609.json`, sidecars `W-3602.approve.json`, `W-3602.reject.json`, `W-3604.steps.json`, `W-3604.next.json`, `W-3607.approve.json`. Tasks T-3601 to T-3607 and T-3610.
- `frontend/tests/escalation.test.tsx` (26 component tests), `frontend/tests/escalation-mock.test.ts` (8), `frontend/e2e/escalation.spec.ts` (30).
- `frontend/tests/mock-contract.test.ts` and `frontend/tests/income-schedule-mock.test.ts`: two existing allow-lists widened for W-36xx (links on W-36xx; the `verdict` overlay on W-27xx and W-36xx). Existing assertions otherwise unchanged.
- `delivery/BACKEND-HANDOFF.md`: section "Added during F-39: escalation (19 Nov)".
- Factory files (project folder): `delivery/features/F-39/fidelity-exceptions.json`, `round-1/fidelity/` (`run.sh`, 8 reports, `scores.txt`).
- No change to `src/api`, `src/features/decide`, `proposals.ts`, `src/shell`, `mock/server.mjs`, `mock/workspace.mjs`, any existing fixture, `apps`, `architecture`, `design` or protected paths.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Four states from data (criterion corrected by the coordinator: the board-string grep excludes F-16's pre-existing `NOT YOUR DECISION` eyebrow): `tests/escalation.test.tsx` "four states from data" (status label and tone, facts, card, panel, quote, Message v1, Next, links) and a test that walks `src` for the board strings. The spec's literal `grep -rn "...YOUR DECISION..." frontend/src` is not empty: it hits F-16's existing `NOT YOUR DECISION` eyebrow in `DecideStates.tsx:35,57` (shared, unchanged). With that eyebrow excluded no board string is in `src`. Pages seen in the fidelity run at 1440 and 390.
2. [x] Tola's work is shown: W-3601 card shows Tola, WORKING, "step 3 of 4", the four steps with sources, a footer "Started <time>" and "Ask Tola" (href `/assistant`), no decide control. W-3604 shows DONE and the three details. W-3602 and W-3603 draw no visible card. A changed `source` changes only that text. Note: the footer reads the time only ("Started 11:00" as the shared F-33 card writes it), not "13 Nov 11:00" (Conflicts 7).
3. [x] Unknown is never 0: W-3606 shows "Unknown" for Delays and Already asked the client; no 0, empty or dash.
4. [x] The page counts and dates nothing: modified-copy tests change "3 TIMES" and "15 DAYS LATE" and only that text moves. `git diff -U0 frontend/src | grep -nE "parseFloat|Number\(|\.reduce\(|new Date\("` returns nothing.
5. [x] Sample-marked: all nine fixtures show SAMPLE DATA with the label on; `sample: false` does not.
6. [x] Controls only from `you_can_act` and `required_role`: tested with `pm`, `finance_lead`, `ceo` and a source check for `useMe`. W-3601, W-3603 and W-3605 show no decide button; W-3605 shows the `not_your_role` copy and "Kemi Adebayo · PMO Lead" from `asked` (shown only when `asked` is sent; a test removes it and the name goes), and sends no claim.
7. [x] Escalate: one claim to `/api/v1/tasks/T-3602/claim`, one decision `{verdict: "approve", expected_revision: 1}` with CSRF, valid against the generated schema, double press sends one, MESSAGE DRAFTED from the re-read (component and e2e request log).
8. [x] Don't escalate needs a note: empty, blank and over 2000 send nothing; message announced, focus on the note; with a note one `reject` with the trimmed note; NOT ESCALATED with the quote and "Back to the issue" to `/work/W-3609` (e2e follows the link to ISS-0241). At 390 it opens the full-height Drawer.
9. [x] No success before the re-read: a 200 with a re-read still serving the decide shows neither MESSAGE DRAFTED nor NOT ESCALATED.
10. [x] Uncertain decide: W-3607 returns `work_state: effect_uncertain`, page shows "Escalation ESC-0012: result not confirmed" and RESULT NOT CONFIRMED, never drafted or escalated. A 500 and a network failure re-read first, show the notice; one POST after 60 s of fake time. e2e uses a routed abort.
11. [x] Refusals: 403 read-only view; 409 stale view keeps the note, no resend; 422 message under the note (component tests; `escalation-mock.test.ts`).
12. [x] Send for review (spec deviation accepted by the coordinator: no `inputs: {}`, the field is optional in the contract and the shared hook is unchanged): one POST `/api/v1/work/W-3604/steps` with CSRF, `expected_revision: 2`, `step: "send_for_review"` and a UUID key; a retry after a 500 reuses the key; WAITING FOR REVIEW only from the re-read, with no Approve/Send/Return control. **Difference:** the shared step writer sends no `inputs` key for a step without fields (the generated request schema accepts that), so `inputs: {}` is not in the body. The test accepts absent or `{}`.
13. [x] W-3608: Send for review is unavailable with the returned reason, nothing is posted, no reviewer named.
14. [x] Nothing says sent to the client: component test over W-3601 to W-3609 and the sidecars; `grep -n '"sends"' frontend/mock/fixtures/work/W-36*` returns nothing. The shared uncertain notice's "Nothing was sent again." is stripped in that test (F-16 text, not this feature's).
15. [x] Access: 401 on decide shows signed-out with `next=/work/W-3602`; 403 and 404 look the same with no title/fact/message; e2e covers the 403 not-open view.
16. [x] Frame: crumbs as returned, tab bar marks none current (e2e), phone bar "← Project" to `/projects/P-0101` (frame draws the accessible name "Back to Project") with ESC-0012. F-30 issue and F-33 income suites unchanged and green.
17. [x] Phone: one column, pinned bar (computed `fixed`), Escape and Cancel close the Drawer and return focus, no sideways scroll, every control at least 44 by 44 (e2e at 390; the frame's History link excluded as in F-33).
18. [x] Fidelity: 100% coverage after exceptions on all 8 boards (second run). Visual: desktop-investigating 90.1; the others 76.8 to 86.1 (at least 70), each with a visual waiver. Every exception/waiver is "builder proposal, pending design engineer" and maps to a Conflicts number.
19. [x] Accessibility: axe (wcag2a/aa, 21a/aa, 22aa) at 1440 and 390 on W-3601 to W-3604 and W-3608, the open Drawer, the note error, the uncertain notice, the not-open view; reduced motion test for the WORKING pulse.
20. [x] Tokens and components only: no CSS was added; no local copy of a shared component.
21. [x] Mock matches the contract: `tests/escalation-mock.test.ts` (fixtures and sidecars schema-valid with `verdict` and `links` stripped; claim then approve serves the approve sidecar; reject without a note 422; stale 409; W-3605 403; W-3607 `effect_uncertain`; the W-3604 step serves `.next`; reset clears).
22. [x] Contract not extended: see Changes. Overlay fields are reused ones only (`steps[].verdict`, `workspace.links` kinds `assistant` and `work`).
23. [x] Existing tests green: `checks.sh` exit 0 (109 files, 2480 tests); e2e passed (below).
24. [x] build.md evidence: this file. Nothing reaches the client in part 1.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` at commit 35665665 under the shared lock (load $2 under 14): exit 0, 109 files, 2480 tests passed.
- `cd frontend && E2E_PORT=4938 MOCK_PORT=4939 npx playwright test e2e/escalation.spec.ts e2e/workspace.spec.ts e2e/income-schedule.spec.ts`: 95 passed (3.7 min), `timezoneId: 'Africa/Lagos'`. (Earlier, at 19305e78, the same plus `e2e/issue-detail.spec.ts` gave 120 passed; `frontend/test-results` deleted after each run.)
- Fidelity: two runs of `round-1/fidelity/run.sh`, shared tool unmodified, production build (`API_ORIGIN=http://127.0.0.1:4936 FRAME_FIXTURES=1`, app 4937, mock 4936, persona `pm`); servers stopped by PID. The first run's scores are in `scores-first-run.txt`. The second run used the final exceptions file (footer exception reworded "shared agent card shows time only"). Scores (coverage / with exceptions / visual):

| Board | Coverage | With exceptions | Visual |
|---|---|---|---|
| SCR-51-desktop-investigating 1440 | 75 | 100 | 90.1 |
| SCR-51-desktop-decide 1440 | 71 | 100 | 77.3 |
| SCR-51-desktop-not-escalated 1440 | 84.6 | 100 | 78.6 |
| SCR-51-desktop-draft 1440 | 78.1 | 100 | 76.8 |
| SCR-51-mobile-investigating 390 | 50 | 100 | 86.1 |
| SCR-51-mobile-decide 390 | 66.7 | 100 | 82.3 |
| SCR-51-mobile-not-escalated 390 | 40 | 100 | 79.2 |
| SCR-51-mobile-draft 390 | 55.6 | 100 | 81.2 |

- In the first run 9 exceptions (marked `added_after_run: true`) were added after seeing its `unexcepted` list; the second run confirms them.
- All exceptions and waivers carry `approved_by: "builder proposal, pending design engineer"`. Each maps to a Conflicts number: 2 (note label), 6 (phone wording), 7 (agent card title, head, footer), 9 (crumbs, tab bar, phone bar), 12 (frame items: Overview, Setup, Kemi Adebayo name, "Tunde Bello · PMO"), and one frame item without a Conflicts number (SAMPLE DATA, design decision 14 Nov (c)). Visual waivers: seven boards measured 76.8 to 86.1 (at least 70), citing the shared frame (D-99, D-110). Desktop-investigating is 90.1, no waiver needed.
- The UI reviewer should check the "misplaced" items in the reports (title, tab labels, Next panel and its link sit at different vertical positions than the boards). I did not change the shared frame.

## Overlay and backend list
- Reused, not new: `workspace.steps[].verdict` (F-33) and `workspace.links[]` kinds `assistant` and `work` (X-LINKS, F-28/F-32). Nothing added.
- Recorded in `delivery/BACKEND-HANDOFF.md`, not built: X-VERDICTS `tasks[].decision.verdicts[]` and that "Don't escalate" is `reject` closing as NOT ESCALATED (G-SCR51-2); `escalations` in the register enums (G-SCR51-4); `action_id`/`issue` in `cites` (G-SCR51-5); the issue link (G-SCR51-6); internal notes that skip review (G-SCR51-1); recipients from contact records (G-SCR51-3, part 2); `agent.finished_at` and an agent card title; no idempotency key on E-TASK-DECIDE.

## Held list
- Whether "Don't escalate" tells the person who raised it; whether the PMO Lead may edit Message v1 (no edit built); which internal notes skip review; who reviews client messages (no policy slot; W-3608 shows the hold with sample wording and names nobody); per-verdict words (built from F-33's step proposal).
- Part 2 (review, received, any client send, recipients), parts 3 and 4 (SCR-50), CTO pre-authorisation.

## Findings for the coordinator and design engineer (no code changed)
- `useWorkspaceStep` omits `inputs` for a step without fields: spec deviation from AC 12 (`inputs: {}`), accepted by the coordinator; the shared hook is unchanged.
- F-16's `UncertainNotice` contains "Nothing was sent again.", which matches the AC 14 phrase "was sent"; it is about the decision write, not the client. I removed the sentence from the W-3607 fixture's `next_step`.
- The footer's "Started <time>" is time-only; the boards write "Started 13 Nov 11:00". Listed as an exception (shared agent card shows time only), pending the design engineer.
- The spec's `grep` for board strings in `src` is corrected to exclude F-16's `NOT YOUR DECISION` eyebrow.
- Wording not in the spec: the review task title "Review the escalation message" (T-3610) and the sample task basis lines are mine, sample text.

## Blocked
Not blocked.
