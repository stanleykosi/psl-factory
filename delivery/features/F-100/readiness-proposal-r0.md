DECISION: NOT-READY
RISK: high
SURFACES: ui, api, external-messaging, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Connect SCR-32 (payment reminder, built in F-41 on the v7 mock) to live API 1.24.0, keyed by invoice. The backend answers E-12 and E-13 settle the action values and follow-up interval.
- Blocked on a dependency: the shared line adapter and workspace frame (F-85, lane C, PR #101) is not on main. Lane D features must not change that frame. Start once F-85 merges.
- High risk: the reminder is a client-facing message about money owed. It carries an attachment, scheduling and delivery reconciliation.
- Client acceptance is required, because the flow changes from work-scoped to invoice-scoped and adds scheduling and delivery-check behaviour.
- I did not find the approved architecture package or design/review.json for this feature in the folder, and I did not run `design.py check`. Confirm those gates when F-85 lands. Lane D context says SCR-32 boards exist.

## Scope
Outcome: Finance staff open a payment reminder for one invoice, see the live invoice and debt facts, and prepare, schedule, send, set aside or confirm the reminder through the live API.

Task: FE-CONNECT-1. Screen: SCR-32 only.

Endpoints:
- `GET/POST /projects/{case_id}/invoices/{issue_id}/reminder`
- `POST /projects/{case_id}/invoices/{issue_id}/reminder/actions`
- `GET /setup/{case_id}/payment-reminder-rules` (read only)
- `GET /payments` (the link into the reminder)

In:
- A page keyed by invoice instead of work id.
- Reads: `reference`, `balance{due_date, currency, amount_basis, owed}`, `recipient|null`, `suggested_subject`, `suggested_message`, `history[]`, `attachments[]`, `dispatch{mode, scheduled_for, receipt}`, `hold`, `can_prepare`, `can_schedule`, `can_confirm`.
- Draft save: `POST .../reminder {revision, subject, message, attachment_id, attachment_checked}`.
- Actions, which per E-12 are exactly `send` (optional `scheduled_for`), `set_aside`, `cancel_schedule`, `check_mailbox` and `confirm` (`{dispatch_id, evidence_id, delivered, reference}`).
- Show `hold` as the reason sending is stopped.
- Show the follow-up interval and earliest follow-up date from the reminders read (E-13). Show "waiting for original receipt" where the API says so.

Out:
- The rules-setting write (`POST /setup/.../payment-reminder-rules`). It belongs to Setup.
- Any change to `src/features/workspace` (lane C).

Hidden, per the D-182 rule, with a stated note:
- "Overdue by N days". Only `due_date` is supplied.
- "Last payment".
- Any hard-coded "7 days" sentence. Use only the API values.

Unknown amounts or rule values stay unknown, never 0. Do not invent approvers, attempt counts or amounts. Show `mode` (manual evidence or synthetic mailbox) and the scheduled send time; the design does not draw them yet. This is a presentation question for the batch: where they appear.

## Risk
High. The feature sends a client-facing message about money owed, so a wrong amount, recipient or duplicate send is hard to undo. It also covers scheduling, an uncertain-delivery reconcile path (`confirm`) and a contract move from work-scoped to invoice-scoped. Per lane D rules, external client messages are high risk, and merge goes to the design engineer's merge batch. Every send must go through the live action with the draft `revision`. A retry after an uncertain dispatch must go through `confirm` or `check_mailbox`, never a blind resend.

## Questions
None blocking. Resubmit for readiness once F-85 (PR #101) is merged to main.
