DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, external-messaging
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-89 is now only the weekly report writes, which is one reviewable PR: `POST /work/{id}/weekly-report` action `correct` and `POST /work/{id}/reviews` kind `document` (approve, return, reject). release_invoice moved to F-90, which removes the money write that made the first pass NOT-READY.
- D-182 accepted LC-Q1..LC-Q9, so no client question blocks the work. Design approval rests on the recorded exception in design/review.json, which allows delivery on the current design version. The exception limits apply, and I did not re-run `design.py check`.
- F-85 (adapter, panel read) and F-87 (controls, shared write locking) are build-order dependencies. The spec may cite them, but the build cannot merge before them.
- Gaps to close in the spec: `feature.json` still has no operation ids, acceptance criteria or baseline. The spec writer must fill them in, or the coordinator must record the bounded exception on the feature. I did not verify architecture or decision approval status in this pass.
- Open wording point: the screens doc (SCR-25) names the review field `verdict`, while the coordinator brief says `decision`. The spec writer must take the field name from contracts/psl-factory.openapi.json 1.22.0 `reviews_review` and not from either note.

## Scope
Binding for the spec writer. Task FE-CONNECT-1, screen SCR-25 (screens-c-rfp-planning-reports.md), plus DC-1..DC-5 where the screens touch these writes. Never invent a business rule, an approver or who may act. Unknown stays unknown, never 0.

In:
- `POST /work/{id}/weekly-report` with `action:"correct"` {expected_revision, case_revision, parts, reason}, only when the readback says `can_correct`. This is the "Edit after return" step.
- `POST /work/{id}/reviews` kind `document` {version_id, decision/verdict approve|return|reject, note}. Take `version_id` from `weekly-report` -> `document_version_id`. Show the controls only when the API offers them. The frontend does not decide who may review.
- All writes go through the F-85 adapter and the F-87 write locking: press lock, uncertain lock after a timeout or 5xx (no retry until reconciled), fresh idempotency key per attempt, revision tokens sent as given, and a 409 reloads the item.
- Show no content the API does not serve: no returned-note text, no cite labels, no assembled text beyond `document_version_id`. Per LC-Q1, hide what the backend does not supply. The `weekly-report` panel key is C-20: build on it and flag it.

Out:
- release_invoice (`POST /work/{id}/actions`), which is F-90.
- Weekly report intake and start (F-86), reconcile, resume, cancel and background (F-87), corrections and coordination retry (DC-1..DC-5 features), new endpoints or states, and any backend change.

## Risk
Medium. There are two writes through one shared lock and idempotency contract (contract-change). An approve or return of a weekly report reaches the client (external-messaging). A retry before reconcile would repeat that effect, so the F-87 uncertain-lock rule is the main test target. There is no data migration, no money, and no new identity or approver rule in the frontend, because the API decides what is offered. Product acceptance is required because the client sees a changed review and edit flow.
