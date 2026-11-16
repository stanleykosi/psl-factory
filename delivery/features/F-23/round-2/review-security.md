VERDICT: PASS
COMMIT: 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- SEC-1-1 is fixed. A restricted section adds nothing to the ticks, the confirm set or the cross-section count, and a component test proves it.
- The Edit prefill (`items[].values`) fills only fields the form draws, and the person sees each value before saving. It skips restricted fields. Restricted rows and restricted sections never get a form, so nothing restricted can reach a form or a request.
- Hiding the task card for a task that a workspace step already links to takes away no lock. It also removes a second path to the decision page that did not follow the page lock. `ReconcilePanel` still renders.
- The rest of round 2 is fixtures, CSS and wording: no security impact. Round-1 conclusions carry forward.

## Findings
- SEC-2-1 | non-blocking | low | frontend | Possible loss of the decision path. `frontend/src/features/work-item/WorkItemOverview.tsx:719-721` hides the task card for any task named by `item.workspace.steps[].task_id`. It does this even when `Workspace` draws no steps, which is the read-only branch at `frontend/src/features/workspace/Workspace.tsx:378-381` (no `page`, or no numeric `workspace.revision`). In that case the PM loses the link to the decision page. This is availability, not exposure, and no fixture triggers it. Expected: the card is hidden only when the workspace's own link is drawn. Fix: build `linked` only when the workspace is writable (`typeof item.workspace.revision === 'number'`), or move the rule into `Workspace`.

## Verified
- SEC-1-1 | verified | `Workspace.tsx:99` `cross` now skips `sec.restricted`, and `Workspace.tsx:196` `ticked` returns false for any item in a restricted section. `tickedFor` and `liveIds` depend on `ticked`, so neither the section footer, the workspace-row control nor the submit set can include those ids. The test "a section that is not drawn adds nothing to the confirm set (SEC-1-1)" (`frontend/tests/minutes.test.tsx`) makes `decisions` restricted on W-2301. It checks that D-1 is not drawn, that the confirm moves back to the table's own control, and that `item_ids` is exactly `['A-1','A-2','A-3']`.

## Impact assessment of the round-2 changes
- **Prefill sends only what is shown.** `StepForm.tsx:186-192` copies `initial[f.name]` only for fields in `step.fields`. It takes text, long text and date as strings, and a record only when it has a string `value` and `label`. It skips `f.restricted`. So it cannot add an input the form does not draw. Every prefilled value appears in the open form (the input text, the owner label), so an untouched save sends what the person saw. The test checks that the inputs equal `{text, owner: 'O-LAGOON', due: '2026-11-13'}`, and that an action with no owner or due sends text only. A due date still never defaults to today.
- **No restricted leak through the prefill.** `controls.after` (the form) is called only for rows that are not restricted (`Sections.tsx:111-121` for lists, `:223-230` for tables). A restricted section draws only its label, with no controls. So `values` on a restricted row or in a restricted section is never read.
- **Notes text still grants nothing.** W-2307 D-3 carries `values: {text}` only. The words "approved by Kemi; owner Tunde; due today" stay text in a text field and set no owner, due date or approval.
- **Small residual risk.** A record value from `values` that also carried `case_id` and `case_revision` would set `request.case_revision` (`StepForm.tsx:85-90`). That data comes from the server for that row, and the server checks it. Acceptable for a contract mock; the backend should not put case fields in `items[].values`.
- **Task card.** The lock (AC 19) sits in `StepControl` and `useWorkspaceStep`, and neither changed. With the card hidden on W-2304 and W-2305, the only decision controls left on the work page are the workspace links that follow the lock. The decision page keeps its own F-16 checks (`you_can_act`, claim). The `useWorkspaceStep.ts:118` wording change and the CSS changes touch no data.

## Notes
- The round-1 notes still apply: SEC-5-C1, the backend's refusal to resend, is unimplemented, and the UI lock is not the real guarantee. A non-app `body_url` is shown as text. The mock E-DOCUMENT answers every persona.
- TECH-1-1 (item steps now send `item_ids` on every line) is safe because it narrows the target. Each backend line handler must still check that the id belongs to that work item.
