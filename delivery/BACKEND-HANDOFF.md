# Backend handoff: what the UI needs from the API (15 Nov 2026)

For: the backend developer. From: the frontend delivery work on branch `dlv-00-delivery-setup`.

This pack tells you, for every one of the 59 approved screens, what the screen does, which
operations and fields it reads and writes, which guards each write needs, and where the v7
contract has to change. Nothing here invents a business rule: where a screen needs a value PSL
has not decided, the decision id is named and the screen stays held.

## How to read this pack

| File | What it holds |
|---|---|
| this file | the overview, the cross-cutting changes in priority order, and the PSL decisions |
| [backend-handoff/built-screens-and-open-questions.md](backend-handoff/built-screens-and-open-questions.md) | Part 1: the screens already built on the contract mock (route, operations, mock fixtures, PR) and the behaviour the frontend relies on. Part 2: the 45 open questions raised so far (BQ-1..BQ-45) |
| [backend-handoff/gaps-a-project-setup.md](backend-handoff/gaps-a-project-setup.md) | Assistant, document review, project tabs, report, milestones, issue detail, Setup (delegation, roles, payroll fields, costing rule), sign-in, staff accounts |
| [backend-handoff/gaps-b-rfp-planning.md](backend-handoff/gaps-b-rfp-planning.md) | Log an RFP, assign the PM, RFP response, costing sheet, submission, engagement, planning |
| [backend-handoff/gaps-c-client-lines.md](backend-handoff/gaps-c-client-lines.md) | Weekly update (returned, received), minutes, change request, emergency change, escalation, leadership report |
| [backend-handoff/gaps-d-delivery.md](backend-handoff/gaps-d-delivery.md) | Retrospective, delivery overview, release gates, go-live, hypercare, archive, handover to Support, closure |
| [backend-handoff/gaps-e-finance-payroll.md](backend-handoff/gaps-e-finance-payroll.md) | Decision variants, Finance Start work drawers, payroll import/matching/corrections/run, payments, payment reminder |
| [backend-handoff/gaps-f-finance-workspaces.md](backend-handoff/gaps-f-finance-workspaces.md) | Management accounts, schedules, fixed assets, cash forecast, BU totals, ledger sources |

Each screen section has the same shape: what it does, proposed route, reads, writes and guards,
agent work, what v7 already covers, gaps (`G-…`, each marked additive or breaking and blocking or
nice-to-have), and questions. Gap ids are stable; please answer against them.

Where to see the screens: the approved boards are in `design/canvas/project/` (main canvas) and
`design/canvas/finance/project/` (Finance and Payroll canvas). Built screens run locally with
`cd frontend && npm run dev -- -p 3000` (contract mock on 4010); routes are in Part 1.

## Where things stand

- **Contract:** v7 (`architecture/packages/v7/openapi.json`, `endpoints.csv`, `model.json`) is a
  proposal, additive over v6. Many of its decisions are still `proposed`; the frontend builds
  against them on the mock only, and you may change or refuse any field.
- **Built on the mock and merged (F-01..F-18, follow-ups):** My work, work item and its line
  workspace frame, decision page, Start work (core lines), all exceptions, projects list and
  journey, overview and factory floor, record a response / SOW signature, RFP team input and
  outcome, month-end, Setup rules, alerts and notification settings.
- **Being built now:** Clients (SCR-35), Setup templates (SCR-34), Weekly update part 1 (SCR-25),
  and a frame change so line work items are laid out as the line boards draw them.
- **Designed, not built (46 screens):** everything in the gap files. The gap check found about
  **170 blocking and 150 nice-to-have gaps**; most blocking ones repeat across screens and are
  covered by the ten changes below.

## The changes that unblock the most screens (in priority order)

1. **Safety and correctness of writes** (BQ-1..BQ-16). Server-side refusal of a resend while an
   external effect is uncertain; idempotency keys looked up before revision and grant, same
   status on replay, a reused key with a different body refused; one fixed order of checks
   (authentication, permission, key, revision, body); idempotency on E-RESPONSE and the
   revision-only writes; 422 `fields[]` on every write. Needed before any real send is switched on. Also: every cited record in a client-bound report must be visible to this person for this case and week, and E-LINE-OPTIONS limited to person, tenant and case (F-21 SEC-1-2); approving sends exactly the version that was reviewed.
2. **Workspace step fields carry the current value** on editable fields, not only display fields
   (prefilled drafts, accept-with-edit, cover letters, payment reminders, saved cites).
   SCR-25, 26, 27, 32, 40 and the F-17 frame.
3. **Per-step decision options**: which verdicts a step offers and their labels and consequences
   (Approve / Return / Reject / Withdraw differ by line; "Escalate", "Keep owed", "Approve an
   exception"). G-C-1, SCR-03 variants, SCR-50, SCR-51, SCR-57, SCR-58.
4. **Links from a workspace** (`workspace.links[]` or similar): where "Open actions", "Open the
   report", "Raise an escalation", "Ask Tola" go, with prefill. G-44-1..4, SCR-28, SCR-30, SCR-31.
5. **Recording for people who don't log in**: who it is recorded for, when they decided, an
   attestation; several signers in one step (client and PM on go-live). SCR-31, SCR-45, SCR-48,
   SCR-50.
6. **Per-recipient and per-item reconcile**: one uncertain recipient among several must not force a
   whole-item resend (INV-RESEND). G-C-5, SCR-47 (per file), SCR-53, SCR-56.
7. **Internal report delivery**: no integration exists for sending management accounts, the cash
   forecast, BU totals or the leadership report to internal and group recipients (I-ALERTS forbids
   amounts; I-CLIENT-MESSAGES is client-only). Suggested new decision: D-REPORT-DELIVERY. G-C-7.
8. **Option lists per work item**: E-LINE-OPTIONS keyed by line and field only; owner pickers and
   cite pickers need `work_id`. SCR-25, SCR-28.
9. **Unknown amounts with a known part**: "₦7.3M + Unknown" needs a known part plus `has_unknown`
   (as month-end's `cash_received_detail`). SCR-20, SCR-56. Never return 0 for unknown.
10. **Missing records and operations**: mark a milestone complete (blocks invoicing from a
    milestone, SCR-19/38); a structured document read (SCR-08); payroll file intake (SCR-09);
    payroll correction (SCR-37); client creation and a pre-sale case (SCR-23, 24, 41); a section
    page read for long tables (SCR-26); meeting, action and decision records (SCR-28); hypercare
    observations and a scheduled evaluation (SCR-46); Finance confirmation of closure (SCR-49).

## Waiting on PSL (do not build the rule; the screens stay held)

| Decision | Holds |
|---|---|
| D-SIGNIN | sign-in, account set-up, sign-out (SCR-17, account menu) |
| D-ADMIN-AUTHORITY | roles and staff accounts (SCR-13, SCR-21), several Setup values |
| D-PAYROLL-VISIBILITY | payroll field visibility and every payroll row (SCR-09, 13, 18, 37, 56, 57, 59) |
| D-COSTING-RULE | costing rule and costing sheet (SCR-39, SCR-27) |
| D-CHANGE-DECIDERS | change request decisions (SCR-31) |
| D-RECEIPT-ALLOCATION | recording a payment, forecast actuals (SCR-20, SCR-56) |
| D-DECISION-VARIANTS | payment exception, CEO costing, CTO emergency decisions (SCR-03, SCR-27, SCR-50) |
| D-RETURN | Return and Reject behaviour on most review steps |
| D-ALERT-PROVIDERS | WhatsApp and email sending, internal requests to people without a login |
| D-SPEECH-INPUT | "Speak your request" in the assistant (SCR-05) |

Also unset with no decision id yet (named in the gap files): hypercare window and criteria, closure
Finance confirmer, handover review, costing adjuster and limits, the weekly report's week-end rule,
Finance Setup values (reviewers, preparers, recipients, inclusion rules).

## Board corrections found (for the design engineer, not the backend)

SCR-27 draws four approvals where D-APPROVAL-ORDER has three; SCR-49 still says "Head of PMO";
SCR-17 shows a record reference before sign-in; SCR-04's management accounts drawer shows a
control total of ₦0.00 for "leave blank if unknown"; SCR-57 counts disagree (6 BUs vs 4 rows,
7 recipients vs 6); the CEO's name differs between SCR-03 and SCR-59; the retrospective board names
a Lagoon Health owner on a Sabi Market project; SCR-55/57 show "Withdraw approval" before any
approval. These are listed so nobody builds the API around them.

## How to answer

Reply per gap id (`G-…`) or question id (`BQ-…`): accept, change (say how) or refuse. Line keys in
the gap files (`management_accounts`, `delivery_release`, …) are suggestions; your names win. When
an answer changes v7, the frontend repoints its mock and types to the new version in one task.
