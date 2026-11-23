DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Connects the already-built SCR-03 Decision desk (default boards) to live API 1.22.0, task FE-CONNECT-1. It is one outcome and one PR.
- Five boards: default, done, not-yours, stale (main canvas) and own (Finance canvas). That is within the 8-board limit, so no split is needed.
- The D-180 push (delivery/connect/LANES.md) is the recorded exception for connecting built screens. Its limit is conformance to the approved boards, with no new authority or approvers.
- Open backend questions A-18 to A-22 do not block the work. Build on the best reading of the contract and flag each one.
- Several design parts have no live source, so the client must see how they are handled.

## Scope
Outcome: a person with a decision waiting opens it on SCR-03 (`/work/[id]/decide?task=`, `src/features/decide/*`, plus `workspace/InlineDecide.tsx`). They read the live task, its evidence and what is asked. They record approve, return or reject through the live API. The result is shown from the record.

In scope, per the connection map (delivery/connect/screens-a-frame-core.md, "SCR-03 · Decision"):
- `GET /tasks/{id}`: `invoice_packet`, `recipient_change`, `review_evidence[]`, and `task{role, can_claim, can_decide, claimed_by_you, verdicts[]}`. Task ids are integers.
- `POST /tasks/{id}/claim` with `{expected_revision}`.
- `POST /tasks/{id}/decision` with `{expected_revision, verdict: approve|return|reject, evidence_id (required, int), note (required key)}`. The page adds an evidence picker. There is no `revoke`, and no `decided_by` or `decided_at` in the reply.
- `POST /tasks/{id}/comments` with `{revision, body}`, for the not-yours board.
- Decided history from `GET /work/{id}/history?kind=decision`, for the done board.
- Stale handling: reload on a revision conflict.
- Task list from `GET /work?queue=decisions`.

Out:
- The payment-exception, ceo-costing and cto-emergency variants (FE-DECIDE-VARIANTS).
- The `/work/{id}/reviews` and `/role-work` packets, unless a default board already uses them.

Rules for the builder:
- A-18: do not pre-select evidence on a guess. Require the person to choose one item, and block submit until they do. Flag the question.
- A-19 and A-21: do not invent the approval chain, the "why you cannot decide" sentence, the basis line, the change list or the preparer name. Hide these parts, or show them as not available (unknown is not zero). Derive "cannot decide" only from `can_decide` and `claimed_by_you`, with no invented reason text.
- A-20: do not offer revoke on tasks.
- A-22: take the page to open from `tasks[].url`. Do not hard-code the route.
- No invented approvers or authority. The server decides who can act, and the page never infers it.
- The pager "decision 2 of 5" is not supported (BQ-23), so drop it or fill it from the live list only.

## Risk
Medium. The change is one screen, but it sits on a contract change: required evidence and note, no revoke, and reshaped task reads. It also writes a business decision (approval of an invoice or accounting review) with revision-conflict handling. Several design parts are removed because the live API cannot fill them, so the client must accept the result as a changed flow (product-decision). No data or migration work is involved, and the backend is not touched. Verification is contained: five boards and a mockable API.
