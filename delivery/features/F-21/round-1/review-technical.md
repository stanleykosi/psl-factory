VERDICT: PASS
COMMIT: 0036fe0ae4ee5811edd8976e0afaebe310552f44
REVIEWER: reviewer-technical
AUTHORITY: delegated technical review

## Summary
- Mounts on the F-17 workspace renderer: no weekly route, page or renderer. The only src changes by F-21 are in StepForm.tsx and Sections.tsx, both general. Other workspace diffs (Workspace.tsx, useWorkspaceStep.ts, workspace.css, the removed `role=alert` summary) come from the merged frame and F-17 follow-up commits, not F-21.
- Frame changes are safe for F-17 lines. Prefill applies only to unrestricted text/long_text fields that carry a `value`. Escape is skipped only when the target is inside `.sw-picker__pop`, and the picker's search box sits inside it. The 422 dedupe uses a Set. The checklist tag only draws when `tag` is present.
- Uncertain-send lock intact: W-2205 `approve_send` returns `effect_uncertain`, and the next item carries `reconcile`. Weekly tests cover reconcile only, no resend and locked-on-reload. F-17 `workspace-step` tests pass unchanged.
- Re-ran weekly, weekly-mock, mock-contract and workspace-step vitest: 290 passed. Fixtures W-2201..W-2208 are checked against the E-WORK-ITEM 200 schema without stripping. Nothing built for returned or received.

## Findings
- TECH-1-1 | non-blocking | low | builder | Mock hook is scoped narrowly: `STEP_RECORD_FIELDS` is keyed on `weekly_report` and the four cite names, and `optionsField` falls back to it only after the intake lookup. Existing lines are unaffected. Records options and panel references agree by design. Backend must serve these through E-LINE-OPTIONS (already listed in build.md).
- TECH-1-2 | non-blocking | low | builder | The new frame behaviours (text prefill, Escape inside a picker, 422 sentence told once, checklist `tag`) are tested only through `weekly.test.tsx` and e2e, not in the F-17 `workspace*.test.tsx` files. A future F-17 change could break them without a generic test failing. Consider a small generic test.
- TECH-1-3 | non-blocking | low | builder | W-2204's mock `approve_send` 200 message reads "Lagoon Health received v1: emailed 12 Nov 15:10 to 2 contacts. Verified on the mock only." It is mock text and labelled as such, and no received page is drawn. The word "received" is close to the unbuilt received board, so keep it clearly sample.
- TECH-1-4 | non-blocking | low | builder | The build.md claim "No assertion removed or loosened" is imprecise. The two weekly assertions (subtitle and status) were rewritten in commit 0036fe0a after the D-73 header move. The justification holds: exact text is still checked and a place check (outside `.ws`) was added. The `workspace.test.tsx` header changes and the `workspace-step` line 217 and 281 changes are not F-21's (merged frame and F-17 follow-up work). F-17's region driver was not re-run, as the builder said.
- TECH-1-5 | non-blocking | low | design engineer | Open for the backend: whether the real 422 names a whole-form field (`parts`) as in W-2202 (D-74), and the idempotency promise stays unbuilt. Both are listed in build.md. The exceptions are the two D-85 items and the D-83 waivers, to be signed by the coordinator.

## Verified
- Idempotency and revisions: the step request carries a UUID key, `expected_revision` equal to `workspace.revision`, and CSRF, with no client retry and a new key after 409/422. Asserted in the weekly tests and the mock tests (repeated key replay, wrong revision 409, bad body 422).
- Contract: the generated types and `src/api` are not touched. The W-2208 `task_id` step is a link only and sends nothing.
