VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 5fd62b4c65d9c80c66ebf0f6e3dd37bb0ddb8dc0
AUTHORITY: delivery security review

## Summary
- The source change is small: one `scheduleLine()` helper (`frontend/src/features/workspace/labels.ts:69-72`) adds `fixed_assets` to the income line's existing frame branches in `Workspace.tsx` and `WorkItemOverview.tsx`. There is no new write path, endpoint, dependency or HTML sink.
- Decide runs only through F-33's reviewed `InlineDecide`/`useDecision`. Buttons need `task.you_can_act === true` and a ready claim (`InlineDecide.tsx:125-127`). The request is `{verdict, note?, expected_revision}` with `X-CSRFToken`, one write at a time, a re-read after an uncertain result and no automatic resend. Tests check that a double press sends one POST (`tests/asset-schedule.test.tsx:342-388`, `:493-553`).
- The holds (W-3907/3908/3909) carry `tasks: []` and no steps, name no reviewer or role, and tests show no control and zero POSTs. The panel title and basis come from the backend's `required_role` and `decision.basis`, and nothing reads `/me`.
- 401 leads to the signed-out page with `next=/work/<id>`. 403 and 404 on read look the same and show no title, cost or asset name. Persona `none` makes no further call (`tests/asset-schedule.test.tsx:554-604`).
- Returned text renders as React text nodes (no `dangerouslySetInnerHTML` in the workspace, decide or work-item features). The proof cite has only an `evidence_id`, so it renders as text. `RefView` links only `isAppPath` targets (`Sections.tsx:64-74`). The fixtures have no URLs, emails, tokens or secrets. The explain-dates step (G-55-1) is not built, so it sends nothing.

## Findings
None.

## Notes
- Non-blocking, from before this change: E-TASK-DECIDE has no idempotency key in v7 (F-33 PMO-3-1). Double-decide protection rests on `expected_revision` plus one write per press. A server-side idempotency key is still the backend's to add before live money approvals.
- Non-blocking: the claim that asset values stay out of Chidi's context (G-55-6) is a section `note` from data. The guarantee is the backend's and is not proven by this mock-only feature.
- Non-blocking: the `fixed_assets` phone CSS uses `content: attr(data-label)`. The value is the column label from data and is drawn as text, so it cannot inject anything.
- Test edits in `tests/mock-contract.test.ts` and `tests/income-schedule-mock.test.ts` only widen the allow-lists to W-39xx. No assertion is weakened.
