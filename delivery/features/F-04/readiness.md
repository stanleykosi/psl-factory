DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, payments, contract-change, product-decision
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-04 is FE-DECIDE in architecture v3 (R-DECIDE; acceptance A-DECIDE and A-STALE). Its only dependency, T-FRONTEND-SHELL, is done (F-01, a41d472). It has no decision gates (validation.json `"FE-DECIDE": []`), and the client approved SCR-03 on 13 Nov 2026 (design/review.json, both canvases).
- Blocker: the approved contract cannot feed the approved screen. The boards show the amount, the basis, the recipient, what changed, the earlier approvers, the preparer's reviewer and the payment-exception figures. E-WORK-ITEM and E-TASK-* carry none of these, and every schema is `additionalProperties: false`. To build to the boards, the builder would have to invent money figures and approvers, which C-FRONTEND and AGENTS.md forbid.
- The payment-exception board's choices are "Keep owed / Exception / Reject". The E-TASK-DECIDE verdict list is `approve | return | reject | revoke`, so the board cannot be submitted through the contract as written.
- It is also too big for one PR. The eight board pairs mix one standard decision flow with three line-specific variants (short payment, CEO final costing, CTO emergency). Proposed split below.
- Risk is high: approvals of invoices and costings (money), a payment-exception decision, a stale-version concurrency path and separation of duties, all on a one-tap phone action that is hard to undo.

## Findings
- PMO-0-1 | blocking | high | backend | Contract gap. SCR-03 needs the amount, basis, recipient and what changed for the version being decided (design/screens.md:94 says "the exact version, amount and basis from contract terms, recipient, what changed, who may decide"; board design/canvas/project/SCR-03-mobile.dc.html shows Amount ₦4,250,000.00, Basis "Contract stage 2 of 4", the recipient email and Changed "PO number"). E-WORK-ITEM (architecture/packages/v3/openapi.json:719-966) offers only `tasks[{id, kind, title, required_role, you_can_act, revision}]`, stations, facts, agent steps and next_step. No endpoint returns the decision content. Expected: an architecture revision that adds a decision view, either on E-WORK-ITEM's task or as a task read endpoint, covering the version label, amounts (with `unknown`), basis, recipient, changes since the last version, the approval chain with earlier approvals, and a reason when you cannot act.
- PMO-0-2 | blocking | high | backend | "Who may decide" is backend-owned but not exposed. The CEO costing board (SCR-03-mobile-ceo-costing.dc.html) shows "PM · Tunde Bello · approved 08 Nov", "PMO Lead · approved 09 Nov", "Yours is the last approval" and "STEP 3 of 4". The own board (design/canvas/finance/project/SCR-03-mobile-own.dc.html) shows "Ada Okafor has been asked to review it". The contract carries only `required_role` and a boolean `you_can_act`, so the frontend cannot tell "not yours", "you prepared this" and "already decided" apart without guessing, and cannot name approvers. D-APPROVAL-ORDER r1 (PM, then PMO Lead, then CEO) must come from the API, not be hard-coded.
- PMO-0-3 | blocking | high | backend | Payment-exception verdicts do not map to the contract. The board's "Keep owed / Exception / Reject" plus Reason, and its INVOICED/RECEIVED/OWED/RULE "Not set" figures (SCR-03-mobile-payment-exception.dc.html), have no counterpart in the E-TASK-DECIDE request enum (`approve, return, reject, revoke`; openapi.json:1729-1737) or in any response. AGENTS.md requires that payment exceptions need configured human authority and never erase debt. Expected: the architecture states which verdict and fields this decision sends, or moves it to E-WORK-ACTION or E-EXCEPTIONS (FE-M2).
- PMO-0-4 | non-blocking | medium | integration | Parallel-lane collision. The mock serves one fixture per operation (frontend/mock/server.mjs:76,98). The SCR-03 states need several work items and tasks keyed by id, and that same E-WORK-ITEM.json and server.mjs are in F-03's path. Expected: the coordinator assigns one owner for per-id fixture routing in server.mjs before both lanes start.
- PMO-0-5 | non-blocking | medium | frontend | QA-3-2, carried from F-01. The mock drains write bodies without validating them (server.mjs:79-80). F-04 is the first feature that writes, so its tests need the mock, or a test-side check, to reject bodies that break the E-TASK-CLAIM and E-TASK-DECIDE schemas: missing `expected_revision`, an unknown verdict, extra properties. Otherwise a wrong body passes under test and only fails at FE-CONNECT-1.

## Scope
**Proposed split.** The spec writer must not start either part until its gate below clears.

**F-04a: standard decision panel and phone action bar** (FE-DECIDE core; A-DECIDE, A-STALE)
- Outcome: from an alert or row link, an eligible person opens one task on a work item, sees the exact version and what it contains, and claims it (E-TASK-CLAIM with `expected_revision`). They approve, return or reject it (E-TASK-DECIDE; a note is required for return, reject and withdraw) with the CSRF header, and see the result from the response (`verdict`, `decided_by`, `decided_at`, `work_state`).
- States: default, done/submitted, not-yours, own, stale-version (409, then reload the work item and show the newer version; no automatic retry), plus 401, 403, 404 and 422 through the F-01 error mapping. Desktop panel and phone action bar at 390px and 1440px. Sample labelling throughout.
- The UI shows only what the API returns. It must not invent approvers, approval order, eligibility or amounts. Unknown values are shown as unknown, never as zero.
- Gate: PMO-0-1 and PMO-0-2 closed by an approved architecture revision (v4) and the frontend client regenerated from it.

**F-04b: line-specific decision variants**
- CEO final costing (approval chain from the API, per D-APPROVAL-ORDER), CTO emergency, and short-payment exception.
- Gate: F-04a merged and PMO-0-3 settled in the architecture. If the short payment moves to E-WORK-ACTION or E-EXCEPTIONS, it joins FE-M2 instead.

**Out (both):** the work item page, stations and history (F-03), My work queues (F-02), the notification centre (FE-M4), backend and `apps/api` work, the real API (FE-CONNECT-1), and what "return" does on each line (D-RETURN, backend-owned; the frontend only sends `return` with a note).

**Ownership (coordinator's proposal, accepted):** the decision route (e.g. `src/app/work/[id]/decide/**`), `src/features/decide/**`, and the mock fixtures E-TASK-CLAIM.json and E-TASK-DECIDE.json. Change `src/shell/**`, `src/api/**` and `mock/server.mjs` only where necessary and minimally, with per-id fixture routing agreed with F-03 (PMO-0-4).

## Risk
High:
- The screen is where people approve invoices and costings and decide short payments (money). It enforces "act only on the current version" (INV-REVISION, 409 recovery: concurrency). It reflects separation of duties ("Preparer cannot decide own work", REC-TASK).
- A wrong label or a stale amount on a one-tap phone approval is hard to undo.

Surfaces:
- `ui`: the SCR-03 boards.
- `api`: the E-TASK-CLAIM and E-TASK-DECIDE writes.
- `security`: CSRF on writes, and not leaking actions the person may not take.
- `payments`: the short-payment exception.
- `contract-change`: PMO-0-1 to PMO-0-3 need openapi.json changes.
- `product-decision`: how the board's payment-exception choices map to recorded outcomes. That decision belongs to the business owner with the backend developer.

## Notes
- PRODUCT-ACCEPTANCE is `not-required` because the work conforms to the approved SCR-03 boards. If the v4 contract forces different copy, fields or choices from the boards, it becomes `required`.
- Nothing here needs a client answer from me. The next step is an architecture revision by the backend developer and architecture owner, with the design engineer confirming the fields match the boards.
- frontend/mock/server.mjs:13 still reads `architecture/packages/v2-reviewed/openapi.json`. v3 left every E-* endpoint unchanged (impact.json), so that is harmless today, but a v4 contract change must repoint it.
- D-RETURN (r2, open) is a recorded working assumption for the frontend. It does not block F-04a because the frontend only sends the verdict.
- I could not run `design.py check` because my role is read-only. The coordinator's design gate should confirm it.

## Questions
None. NOT-READY on an architecture gap, not a client question.
