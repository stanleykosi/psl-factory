DECISION: READY
RISK: high
SURFACES: ui, api, security, auth, external-messaging, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-107B is part 2 of SCR-57 (BU totals): the 6 boards `SCR-57-{desktop,mobile}-{publish,receipts,verified}`. It covers publishing the approved totals to the CEO and BU heads, recipient receipts, and the verified result. Part 1 (F-107) covers the 8 boards up to the approved result.
- The earlier F-44 block (D-PAYROLL-VISIBILITY, plus G-C-7 and G-C-8 on internal report delivery and recipient receipts) is resolved for build by D-187 (LD-Q1 "Build on the API") and D-185. The page shows what API 1.25.0 serves each person and hides any board figure the API does not serve to that person (D-182 rule). Backend answers E-26, E-27, E-28 and E-30 govern publishing and recipient views.
- Waits, not blockers: F-107 must be on main (this part reuses its panel, model and review code), as must F-85 and F-87 (the line adapter and the `Actions` slot). The coordinator holds the builder until then.
- I did not run `design.py check` (this role has no shell). The client approval and the D-173/D-181 exceptions in `design/review.json` are taken as recorded in the lane D context.
- The merge goes to the design engineer's merge batch (high risk).

## Scope
Outcome: a Finance person with publish authority sends the approved BU totals to the CEO and BU heads. Each recipient sees only their own approved view and confirms receipt. Finance sees the verified result only when the server says so.

In (6 boards): `SCR-57-{desktop,mobile}-{publish,receipts,verified}`. Task: FE-FIN-BU.
- Publish: `POST /work/{id}/business-units` with `action: publish {expected_revision, case_revision}`. The control shows only when the served `can_publish` is true and the result is complete and approved. A held result never shows it (held belongs to F-107).
- Receipts: a recipient confirms receipt with `POST /work/{id}/aggregate-receipt {publication_id}`. Finance reads receipt progress from `publication_id`, `receipt_id`, `receipt_ids[]`. Draw only what these serve.
- Verified: drawn only when `verified_at` is non-null. An agent or job claim is not "verified". The board's negative states come from the served fields only.
- Cancel-after-publish: drawn only if a served action or field exists in API 1.25.0 for it. Otherwise hide it and say so in build.md. Use no invented action.
- The "Sent. This is shown on the next screen." note that F-107 draws is replaced here by the real publish, receipts and verified states.
- Recipient view (`recipient_only`): the reduced view from F-107 plus the receipt confirmation control, nothing else.

Binding for the spec:
- Authority comes from the server (`can_publish`, `recipient_only`, `review_subjects[]`). The UI infers no role and counts nothing.
- Hide, never invent: recipient counts ("6 BU heads", "7 recipients"), staff counts and group sizes the API does not serve to that person, the BU publisher rule, and any named recipient the API does not serve. Do not resolve G-57-4 (6 vs 4 BUs, 7 vs 6 recipients) by picking a board number. Build to live data.
- Publish and receipt are external messaging. The in-app delivery carries totals only. Any alert, email or WhatsApp copy comes from what the server sends. This page composes no message and puts no amount in an alert (I-ALERTS).
- Send the writes through F-87's `useWorkCommand` and `makeCommand`, one write at a time, with a press lock and an uncertain lock after a timeout or 5xx. Re-read before offering a retry, and never auto-resend a publish or a receipt. Revision tokens and the idempotency key never go inside `inputs`.
- Money is the served decimal string with the served `currency`. Unknown shows "Unknown", never 0. No sums or percentages are computed in the page.
- 403 and 404 look the same ("This record is unavailable."). No names, staff IDs or individual pay appear in any fixture or the DOM. Add canary keys to the mock as F-107 does.
- Mock ids and `frontend/mock/finance*` changes: use a new work id range and name any change under `mock/finance*` in build.md for lane B.
- Disclosure proof against live Django (Finance publisher, a BU recipient, a person with no access) is needed, as in F-107 criterion 12.

Out: the first 8 boards (F-107); Event mode (no board); starting a run (SCR-04); payroll import and run (F-108/F-110); `prepare_rule` and `restart` forms; Setup editing of disclosure rules or minimum group size; backend, OpenAPI, and `frontend/src/features/workspace` and `work-item` (lane C).

## Risk
High: publishing sends payroll-derived money aggregates to people outside Finance (the CEO and BU heads). A wrong recipient, a premature publish or a small-group leak cannot be undone, and a double publish or double receipt is an uncertain effect. Surfaces are ui and api (`business-units` publish and `aggregate-receipt`), security and auth (per-recipient views with server-decided authority), external-messaging (delivery to the CEO and BU heads), and product-decision (D-187 chose to build on the API's disclosure, and PSL can still overrule D-PAYROLL-VISIBILITY). Files: `frontend/src/features/finance/business-units/` (from F-107). Payments is not ticked because nothing is invoiced, paid or posted.
