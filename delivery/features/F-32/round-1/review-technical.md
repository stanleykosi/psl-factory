VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 9f594712fb1c9a7ac4283d41d121707c4f96d45f
AUTHORITY: delivery technical review

## Summary
- The Delivery tab, the `work` link kind and the new Steps.tsx rule match the spec and the D-113 recommendations. No generated type is changed.
- The Steps.tsx rule (a step with `task_id` links only when that task has `you_can_act`) is safe for existing lines. `StepControl` has one caller, and it passes `item.tasks`. I scanned every `mock/fixtures/work/*.json`. The only task-linked steps that are now unavailable are W-2305.approve, which is a done task, and the deliberate W-2504, W-2505 and W-2506 cases. W-2009 already has a `disabled_reason`.
- Authority comes only from `tasks[].you_can_act`, `cannot_act_reason` and `required_role`. Nothing is read from `/me`. Release ready comes only from the returned status.
- Unknown is never 0. A row with no gate shows "Unknown" and a missing date reads Unknown, not blank.
- No assertion is loosened. Every edit to existing tests either adds "Delivery" at index 1 and shifts the later indexes, or follows F-29 Documents. I ran release-gates, workspace and delivery-overview: 73 passed.

## Findings
1. TECH-1-1 | non-blocking | low | frontend | frontend/src/features/workspace/Steps.tsx:66 A task that is present but not actionable and has no `decision` shows the generic "This decision isn't open to you here." It drops `cannot_act_reason`, which is the only authority text the response gave. Expected: use the reason where one exists. Actual: the generic sentence. This is not a defect on the current fixtures.
2. TECH-1-2 | non-blocking | low | frontend | frontend/tests/mock-contract.test.ts:647 The F-23 guard was widened from `/^W-23/` to `/^W-2[35]/`. This is a legitimate follow-on (W-2501 and W-2503 carry links), but it also admits W-24xx and W-25xx files. Expected: `/^W-(23|2501|2503)/`. Actual: `/^W-2[35]/`, which is slightly broader than needed.

## Verified
- Test edits checked one by one:
  - projects-journey.test.tsx: tab lists gain Delivery, and the keyboard End and ArrowRight indexes shift from 5 to 6.
  - workspace.test.tsx and issue-detail.test.tsx: the tab list and hrefs gain Delivery.
  - mock-contract.test.ts: the `project_tab` enum gains `delivery`, and a `work` link schema is added.
  - mock-projects.test.ts: PROPOSAL keys are stripped before the schema check, so the generated-schema validation still runs on the rest.
  - e2e/projects.spec.ts: the tab arrays gain Delivery. The stale Documents case now checks the F-29 list ("Statement of work", tab index 3) and returns to the journey through the first tab, because "Open the journey" was a coming-next control that F-29 removed.
- Not run: the e2e specs (Playwright, no servers). I judged them by reading the diff.
