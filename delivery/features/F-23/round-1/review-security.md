VERDICT: PASS
COMMIT: d5046515521bca99b4b7de220c4d524838cfff1f
REVIEWER: reviewer-security
AUTHORITY: delivery security review

## Summary
- Nothing Tola suggests is sent before the PM presses "Confirm and create actions". Pre-ticks come only from the step's `items_default`. The set sent is the set ticked at submit, and the server stays the authority (E-WORK-STEP, `expected_revision`, idempotency key).
- Decision links (`task_id`) now follow the page lock. While a write is in flight, after an uncertain send or after a failed refresh, they render as an `aria-disabled` button with no `href` and no handler. On W-2305 the only action is reconcile, and nothing is sent again.
- Notes text is shown as escaped plain text and sets no owner, due date, audience or approval. Owners come from E-LINE-OPTIONS. Nothing is read from `/me`. No `dangerouslySetInnerHTML`, no new dependency and no secrets in the diff.
- The E-DOCUMENT panel shows the "Test template" tag only when the document says `test_template`. `body_url` is a link only when `isAppPath` accepts it, and `//`, `\` and `javascript:` are never links. A 403 or 404 shows no title.
- Mock only. build.md states the D-LINE-WORKSPACE limits and names the server-side refusal of a resend (SEC-5-C1) as unimplemented backend work.

## Findings
- SEC-1-1 | non-blocking | low | frontend | Defence in depth for "the set sent is the set shown". At `frontend/src/features/workspace/Workspace.tsx:194-197`, `ticked`, `tickedFor` and `liveIds` skip restricted items (`it.restricted`) but not restricted sections. `Sections.tsx:441-460` draws a restricted section as its label only. So if a backend ever returned rows inside a `restricted: true` section, with the confirm step and `items_default: "checked"`, their ids would be sent in `item_ids` without being on screen. Rows in that section would also count towards the `cross` test at `Workspace.tsx:99`. The contract text at `schema.d.ts:1692` says restricted sections carry no rows, so today's data cannot trigger this. Expected: a section that is not drawn adds nothing to the confirm set. Fix: skip `section.restricted === true` in `ticked`/`tickedFor` (and in the `cross` count), and add one component test with a restricted section that has rows.

## Verified
None (round 1).

## Notes
- No AC 19 bypass found. `StepControl` (`Steps.tsx:56-67`) returns the disabled button before building the `href`. `off` includes `flow.allLocked`, which is true when `awaitingReconcile` (`item.reconcile` or `effect_uncertain`). `useWorkspaceStep.submit` refuses any step while that lock holds. Going straight to `/work/W-2305/decide?task=T-2305` reaches the F-16 page, and there the `.approve.json` task has `you_can_act: false`, `cannot_act_reason: "already_decided"`. The real guarantee still depends on the backend refusing a resend while delivery is uncertain (SEC-5-C1), and build.md records that.
- Item-scope steps now send `item_ids: [that item]` (`Workspace.tsx:203`). This narrows what a step acts on, which helps safety. The changed F-17 assertion is a contract question for the coordinator, not a security one.
- If everything is unticked while the confirm form is open, nothing is sent (`Workspace.tsx:182`). After a 409 reload the form stays open, and nothing is sent until the PM presses again with a new key and the new revision.
- `Links.tsx:66` prints a non-app `body_url` as plain text. That is safe from XSS. A real backend that returned a presigned storage URL would show its query string, but only to someone already allowed to read the document. When E-DOCUMENT is built, consider serving the body through an app path.
- `WorkspaceLinks` in the read-only `Workspace` view (`Workspace.tsx:393`) gets no `page`, so a 401 on the document read shows "We couldn't open the minutes" instead of the signed-out callout. This is UX, not exposure.
- The mock E-DOCUMENT answers D-2304 v1 for every persona and 501 for any other document. It is mock only and does not stand for the real access check.
- Pre-existing: the checkbox `aria-label` uses `item.text`. Restricted items render separately and are excluded from ticks.
