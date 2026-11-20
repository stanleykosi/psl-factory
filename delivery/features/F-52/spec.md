# F-52 Follow-up batch A: fixes on merged screens

Tasks: FE-FOLLOWUPS-1 (coordinator-defined follow-up batch). No new endpoint; contract mock only. Screens: SCR-54 (income schedule), SCR-52 (leadership report), SCR-51 (escalation), SCR-26 (RFP response record), the shared header. The design check passes under EXCEPTION D-89 (as for every feature since 15 Nov).

## Rules
Authority only from `you_can_act`. Nothing invented. Wording comes from data or existing labels, except the one new F-35 next-step sentence below. Every change is scoped to its line or the shared header, and other lines' tests stay green.

## Acceptance criteria
1. On the income schedule line (F-33), after a decide answered 200, the page says the version is approved only when the re-read shows the decided state. While the re-read still serves the review, it shows the neutral "result not confirmed" wording F-45 uses, and never "approved" or "verified". — verify: component test that fails on the old code.
2. On the income schedule line, a real two-reviewer sequence through the mock (the task closes, then the second reviewer's decide gets a 409) leaves a lasting stale notice and the unsent note, with no decide buttons. — verify: test.
3. On the leadership report line (F-35), the stale notice adds one sentence telling the reviewer what to do next ("Read the current version above; nothing was recorded for you."), and focus moves to the notice when it appears. — verify: test for the text and `document.activeElement`.
4. The escalation mock serves W-3602's send-for-review step answer (fixture), so "Send for review" completes and the re-read shows the next state. — verify: mock test plus an e2e or component test.
5. The response mock answers `POST /api/v1/tasks/T-3401/response` with `team_input` (no 501), so F-37's "Record team input" completes with proof on the mock. — verify: mock test plus a component test of the completed state.
6. The shared header's History link is at least 44 by 44 px at 390. Desktop is unchanged. — verify: e2e measuring `getBoundingClientRect` on two lines.
7. tests/rfp-intake-mock.test.ts no longer fails on ECONNRESET in beforeEach (a retry or `Connection: close`), and the file passes 5 runs in a row. — verify: the runs.
8. No other line's behaviour changes. checks.sh passes, and the e2e for income-schedule, leadership-report, escalation, rfp-requirements and one more line passes. — verify: checks and e2e.

## Out of scope
F-49's empty-submit check (batch B, after F-51). F-35's notice surviving a reload (needs backend state). F-43's tags on NOT SET facts (accepted under D-124).
