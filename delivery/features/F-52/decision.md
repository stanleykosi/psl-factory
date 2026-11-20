RECOMMENDATION: ESCALATE
COMMIT: 7fa112fbc1c004292685163cfe2e8a25ad525c54
APPROVER: approver

## Summary
- F-52 is follow-up batch A: seven small fixes on already-merged screens (income schedule, leadership report, escalation, RFP response mock, shared History link, one flaky test).
- Gate, technical, UX, UI, QA and PMO acceptance all PASS on this head, with no blocking finding.
- Risk is medium with surfaces ui and contract-change; the merge policy auto-merges low risk only and lists contract-change as always human.
- Three changes alter what people read or tap: the income "approved" timing, the new F-35 notice sentence with focus, and the 44px History link.
- No fidelity run was done, because only a tap target changed.

## Why
The work is sound and evidenced, and I would merge it, but policy sends medium risk with a contract-change surface to a human. Product acceptance of the wording and focus changes is required by readiness.

## Acceptance criteria
1. Income "approved" only after the re-read: met, a test that fails on the old code, and UX saw it live.
2. Two-reviewer stale 409 on income: met, test in income-schedule.test.tsx.
3. Leadership stale notice sentence and focus: met, test on text and activeElement, confirmed live.
4. Escalation W-3602 send-for-review: met, mock test and component test; UX completed it live.
5. T-3401 team_input on the response mock: met, mock test and component test; UX completed it live.
6. History link at least 44 by 44 at 390: met, e2e and UX measurement; desktop unchanged.
7. rfp-intake-mock ECONNRESET: met, 8 runs in a row passed.
8. No other line changes: met, checks.sh exit 0 and 146 e2e passed; I spot-checked Workspace.tsx, where the changes are keyed to the lines.

## For the human
Please sign:
1. The F-35 stale notice sentence "Read the current version above; nothing was recorded for you." UX-1-1 notes "above" is wrong (the current version sits below the notice) and "nothing was recorded" repeats. Accept it, or give new wording.
2. The focus change: focus moves to the notice when it appears, on the leadership report line only.
3. The income line now says "approved" only after the re-read confirms it; until then it shows "result not confirmed", matching the ledger line (F-45). This closes the F-33/F-45 difference.
4. The History link size: 44 by 44 on phones, desktop unchanged (no fidelity run).
5. Product acceptance (required).

Before the PR, the coordinator notes that operation_ids is empty: none, no new endpoint.

Files:
- /Users/Hunchoo/psl-factory/delivery/features/F-52/round-1/review-ux.md
- /Users/Hunchoo/psl-factory/delivery/features/F-52/round-1/acceptance-pmo.md
- /Users/Hunchoo/psl-factory/delivery/features/F-52/round-1/build.md
