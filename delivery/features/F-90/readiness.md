DECISION: READY
RISK: high
SURFACES: ui, api, payments, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- One observable outcome: a person with the server's offer releases an invoice from the work item, and the screen shows pending, done or uncertain without ever repeating the release.
- The split from F-89 removes the earlier size problem. This is one write (`POST /work/{id}/actions` `action:'release_invoice'` -> 202) plus the invoice states SCR-02 shows around it.
- No product question blocks it. LC-Q1..LC-Q9 were accepted in D-182, and the server decides who may release (403/409/422), so the frontend invents no rule.
- Design approval rests on the recorded exception in `design/review.json` (13 Nov client approval of version 1794581312-b166 still covers the invoice states; only the design engineer's upload-concept change since then awaits PSL approval). That exception is bounded, so I count it. Not run in this pass: `design.py check`, the architecture approval status and the decision statuses. The feature record has no baseline, operation ids or acceptance criteria, so the spec writer must cite them, or the coordinator must record the exception limits on the record.
- Build order, not a readiness blocker: F-85 (adapter, read-only work item) and F-87 (shared write locking, `useWorkCommand`, "Check what happened") merge first. If either is unmerged when the build starts, the builder waits and does not rebuild them here.

## Scope
Binding for the spec writer. Task FE-CONNECT-1. Never invent who may release, amounts, conditions or references. Unknown stays unknown, never 0.

In:
- The release control on the work item, shown only when `GET /work/{id}` `actions[]` contains `release_invoice`. Hidden otherwise, with no disabled placeholder inventing a reason.
- `POST /work/{id}/actions` `{expected_revision, action:'release_invoice'}` with `expected_revision` sent as read. Check `contracts/psl-factory.openapi.json` 1.22.0 for any further required body field, including the idempotency key, and send exactly what it asks for.
- Writes go through the F-85 adapter and F-87 locking. The press lock disables the control at once. A fresh idempotency key per attempt. After a timeout or 5xx the uncertain lock applies, with no retry until F-87's "Check what happened" (reconcile) settles it. A 202 moves the item to a pending state and the page polls as SCR-02 already does for `state==='processing'`. A 409 reloads the item. A 403 or 422 shows the server's message. Unknown outcomes are never shown as success.
- The invoice states on SCR-02 for what surrounds the control: the invoice readback `GET /projects/{case_id}/billing-invoices/{invoice_id}` (`reference, version, issued_at, delivered_at, currency, amount, paid, owed`) when the panel `invoice` is present. Values the API does not return render as unknown, not 0 and not invented.
- Tests with the real adapter against mocked responses: offered and not offered, 202, 409, 403, 422, timeout, 5xx, and a second press during the lock.

Out:
- Weekly report correct and document review (F-89), reconcile and other F-87 controls, resume, cancel, background, invoice information, milestone proof, draft stop, corrections and coordination retry (other DC features), amounts or conditions of release the API does not supply, and any backend, contract or new-state change.
- Client-side decisions about who may release, a client-side "are you sure" amount line, and a retry button for an uncertain release.

## Risk
High: the release moves money and cannot be undone. A stale revision or a retry before reconcile would repeat the effect, which AGENTS.md forbids, and the server's 403/409/422 are the only authority. Surfaces: ui (control and states), api (`POST /work/{id}/actions`), payments (invoice release), security (permission comes only from `actions[]` and server errors), contract-change (relies on the F-85 adapter and F-87 lock contract). The change is small and has no migration, so one PR is sized right, but the payments and security reviewers are mandatory. Client acceptance is required because the release is a new live action (SCR-02 "new in live").
