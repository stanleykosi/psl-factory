DECISION: READY
RISK: high
SURFACES: ui, api, external-messaging, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Connect SCR-32 (payment reminder, built in F-41 on the v7 mock) to live API 1.24.0, keyed by invoice. Backend answers E-12 and E-13 settle the action values and the follow-up interval.
- Build-start wait, not a blocker: the shared line adapter and workspace frame (F-85, lane C, PR #101) is not on main. Under the lane D rule the coordinator holds the builder until F-85 merges. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- High risk: the reminder is a client-facing message about money owed, with an attachment, scheduling and delivery reconciliation. Merge goes to the design engineer's merge batch.
- Client acceptance is required: the flow changes from work-scoped to invoice-scoped and adds scheduling and delivery-check behaviour.
- Architecture and design approval are covered by the v9 package and the 13 Nov client design approval (lane D context). I did not re-run `design.py check` in this re-run.

## Scope
Outcome: Finance staff open a payment reminder for one invoice, see the live invoice and debt facts, and prepare, schedule, send, set aside or confirm the reminder through the live API.

Task: FE-CONNECT-1. Screen: SCR-32 only.

Endpoints:
- `GET/POST /projects/{case_id}/invoices/{issue_id}/reminder`
- `POST /projects/{case_id}/invoices/{issue_id}/reminder/actions`
- `GET /setup/{case_id}/payment-reminder-rules` (read only)
- `GET /payments` (the link into the reminder)

In:
- A page keyed by invoice instead of work id. This feature builds its own adapter mapping in its folder and does not change the shared frame.
- Reads: `reference`, `balance{due_date, currency, amount_basis, owed}`, `recipient|null`, `suggested_subject`, `suggested_message`, `history[]`, `attachments[]`, `dispatch{mode, scheduled_for, receipt}`, `hold`, `can_prepare`, `can_schedule`, `can_confirm`.
- Draft save: `POST .../reminder {revision, subject, message, attachment_id, attachment_checked}`.
- Actions, exactly per E-12: `send` (optional `scheduled_for`), `set_aside`, `cancel_schedule`, `check_mailbox`, `confirm` (`{dispatch_id, evidence_id, delivered, reference}`).
- Show `hold` as the reason sending is stopped.
- Show the follow-up interval and earliest follow-up date from the reminders read (E-13). Show "waiting for original receipt" where the API says so.

Out:
- The rules-setting write (`POST /setup/.../payment-reminder-rules`); it belongs to Setup.
- Any change to `src/features/workspace` (lane C). A needed frame change is named as a dependency on lane C.

Hidden per the D-182 rule, with a stated note in the spec:
- "Overdue by N days" (only `due_date` is supplied).
- "Last payment".
- Any hard-coded "7 days" sentence; use only API values.

Unknown amounts or rule values stay unknown, never 0. Do not invent approvers, attempt counts or amounts. Show `mode` (manual evidence or synthetic mailbox) and the scheduled send time. The design does not draw these; the placement is a presentation question for the batch, and the builder uses the best reading and flags it.

## Risk
High. The feature sends a client-facing message about money owed, so a wrong amount, recipient or duplicate send is hard to undo. It also covers scheduling, an uncertain-delivery reconcile path (`confirm`) and a contract move from work-scoped to invoice-scoped. Every send must go through the live action with the draft `revision`. A retry after an uncertain dispatch must go through `confirm` or `check_mailbox`, never a blind resend.

## Questions
None blocking.

1. Where should `mode` (manual evidence or synthetic mailbox) and the scheduled send time appear on SCR-32, given the boards do not draw them?
   - (a) Recommended: in the dispatch status block beside the send action.
   - (b) In the history list only.
   - Context: the API supplies both and the boards omit them; the builder follows (a) until answered.
