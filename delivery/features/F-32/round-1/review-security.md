VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 9f594712fb1c9a7ac4283d41d121707c4f96d45f
AUTHORITY: delivery security review

## Summary
- Decision links in `Steps.tsx` are enabled only when the matching `tasks[]` entry exists with `you_can_act` truthy. A missing task, missing `tasks`, missing `you_can_act` or `false` all render an `aria-disabled` button with no href and no click handler. Nothing reads /me, persona or role text. The page-lock `off` rule still applies after that check.
- The new `work` link kind accepts only `work_id` that matches `RECORD_ID` (`^[A-Za-z0-9][A-Za-z0-9._-]*$`). That excludes `/`, `:`, `..` and a leading `javascript:`. The href is always `/work/<id>`, so there is no open redirect and no scheme URL. Delivery row links use the same pattern plus `encodeURIComponent`.
- All returned text (labels, titles, notes, reasons) renders as React text nodes. There is no `dangerouslySetInnerHTML` and no href is built from free text.
- The change adds no write path. The decision still happens on the unchanged F-16 page, which keeps its CSRF header and idempotency. "Release ready" comes only from the re-read `workspace.status`. The mock approve fixture is labelled contract-mock only.
- 401, 403 and 404 handling is untouched. The only new reason text is `cannotActCopy`, which uses `required_role` and generic copy, never ids.

## Findings
None.

## Notes
- Non-blocking: when `cannot_act_reason` is `prepared_by_you`, the reason line shows `task.decision.version.label`. It is backend data for a task the person can already read, so there is no new leak.
- Non-blocking: the frontend check is advisory. The backend must enforce role and tenant on the decide action, and release authority is still held (Conflicts 2). Already recorded in BACKEND-HANDOFF.
