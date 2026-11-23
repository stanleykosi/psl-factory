# Payment reminder: Finance prepares, schedules, sends or sets aside the reminder for one invoice, live

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas under the recorded exception in `design/review.json`; screens: SCR-32 (boards `SCR-32-desktop`, `SCR-32-mobile` in `design/canvas/finance/project/`).

## Summary
- SCR-32 moves from the v7 work-scoped page (`/work/W-3801`, F-41) to an invoice-scoped page on live `GET/POST /projects/{case_id}/invoices/{issue_id}/reminder`. The Payments page links to it through each row's `reminder_url`.
- The page shows only live facts: invoice reference, amount owed, due date, recipient, subject and message, attachment, history, hold reason, follow-up timing. Anything the API does not supply is hidden (see Contract, "Hidden").
- Actions are exactly the five of E-12: `send` (optional `scheduled_for`), `set_aside`, `cancel_schedule`, `check_mailbox`, `confirm`. Each carries the draft `revision`. An uncertain delivery is settled by `check_mailbox` or `confirm`, never by sending again.
- High risk (client-facing message about money owed; merge goes to the design engineer's batch). Client acceptance required.
- Build-start wait, not a blocker: the shared line adapter (F-85, lane C, PR #101) is not on main. The coordinator holds the builder until it merges. This spec follows `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.

## Context
Lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d`, frontend in `frontend/`.
- Today: the reminder is a v7 work line drawn by `frontend/src/features/workspace/*` (`Workspace.tsx`, `StepForm.tsx`, `Steps.tsx`, `Sections.tsx`) from `frontend/mock/workspace.mjs`. Live has no payment-reminder work line (`screens-e-finance-payroll.md`, SCR-32).
- Payments page: `frontend/src/features/finance/payments/PaymentsView.tsx` (+ `model.ts`, `usePayments.ts`). It links "Open the reminder draft" through `workHref(note.workId)`. Live `GET /payments` items carry `case_id`, `issue_id` (nullable), `reminder_url` (nullable), `has_reminder_draft`, `status`, `owed`, `reference`.
- App routes: `frontend/src/app/finance/payments` exists; there is no reminder route.
- Live types: `frontend/src/api/live-schema.d.ts` (operations `reminders_detail`, `reminders_draft`, `reminders_command`, `reminders_rule_options`); client `frontend/src/api/client.ts`, errors `frontend/src/api/errors.ts`.
- Backend answers: E-12 (action values), E-13 (interval, earliest date, waiting for receipt) in `/Users/Hunchoo/psl-factory/delivery/connect/backend-answers.md`.

## Contract

### Route
`/finance/payments/[caseId]/invoices/[issueId]/reminder` (new, under `frontend/src/app/finance/payments/`). `caseId` is the uuid and `issueId` the integer from the Payments row. A non-integer `issueId` or non-uuid `caseId` shows the not-found state without calling the API.

### Payments link
In `PaymentsView.tsx`, a row whose `reminder_url` is non-null and whose `issue_id` and `case_id` are present links to the route above. The link text is the existing one ("Open the reminder draft" when `has_reminder_draft`, else "Prepare a reminder"; if the existing board wording differs, keep the board's). A row with `reminder_url: null` or `issue_id: null` draws no link. The link is built from `case_id` and `issue_id`, never by parsing `reminder_url`.

### Read: `GET /projects/{case_id}/invoices/{issue_id}/reminder` (200)
Fields used: `revision`, `issue_id`, `reference`, `balance{due_date|null, currency, amount_basis, owed}`, `recipient{id,name,email}|null`, `suggested_subject`, `suggested_message`, `mode|null` (`manual_evidence|synthetic_mailbox`), `hold|null`, `timing{minimum_days_between, earliest_date|null, awaiting_receipt}|null`, `can_prepare`, `can_schedule`, `can_confirm`, `history[{id, number, subject, message, set_aside, attachment_url|null, mailbox_download_url|null, dispatch{id, mode, scheduled_for|null, receipt{id, reference, delivered, recorded_at}|null}|null}]`, `attachments[{id,label}]`, `receipt_proofs[{id,label}]`.
Errors: 401 sign-in, 403 "You do not have access to this invoice", 404 not found, 5xx/503 retry; messages come from the `Error` body (`code`, `message`, `fields[]`); the page writes no policy wording of its own.
Permission and tenant: server-side per case and grant. The page never infers access from the URL and never reads another case's invoice.

### Write 1, save the draft: `POST .../reminder` (201)
Body `{revision, subject (1..180), message (1..10000), attachment_id|null, attachment_checked}`. `revision` is the read's `revision`. Response is the draft `{id, number, subject, message, set_aside, attachment_url, mailbox_download_url, dispatch}`. After 201 the page re-reads. Shown only when `can_prepare` is true. 409 means the draft changed: show the server message and re-read, keeping the person's typed text visible in the form. 422 `fields[]` show under the matching field.

### Write 2, actions: `POST .../reminder/actions` (200)
One request per press; the button is disabled until the response arrives (no double send). Body by action, exactly:
- `send` `{action, draft_id, revision, scheduled_for?}`. `draft_id` is the latest history item that is not `set_aside` and has `dispatch: null`. `scheduled_for` is sent only when "Schedule" is used and `can_schedule` is true; it is an ISO date-time chosen by the person.
- `set_aside` `{action, draft_id, revision, reason (1..1000)}`. Reason is required in the form.
- `cancel_schedule` `{action, dispatch_id, revision}`, offered only for a dispatch with `scheduled_for` set and `receipt: null`.
- `check_mailbox` `{action, dispatch_id}`, offered only when the dispatch `mode` is `synthetic_mailbox` and `receipt` is null.
- `confirm` `{action, dispatch_id, revision, evidence_id, delivered, reference (1..160)}`, offered only when `can_confirm` is true. `evidence_id` is chosen from `receipt_proofs[]`; the form never lets a person type an id.
Response `{revision, dispatch|null, receipt|null}`; after 200 the page re-reads and draws from the re-read, not the response. Errors as above. 409 stale revision: re-read and say "This reminder changed. Check it and try again." A failed or timed-out `send` is never retried by the page: it re-reads and, if the dispatch exists without a receipt, the person sees the Delivery block and uses `check_mailbox` or `confirm`.
`revision` is held from the latest read and sent as given; an unknown (missing) revision disables the actions.

### Rules context: `GET /setup/{case_id}/payment-reminder-rules`
Read only, used only to show the interval when `timing` is null and to nothing else. If this read is 403 or fails, the page ignores it. No POST to this route (Setup owns it).

### Screen states
- Loading: skeleton for the invoice facts and message.
- Not found / no access / error: message from the server with "Try again" (error) or a link back to Payments.
- Hold: `hold` non-null: a notice with the `hold` text verbatim; Send, Schedule and Edit are disabled; nothing is sent. `recipient: null`: "No recipient is set up for this invoice" and Send disabled.
- Empty (no draft yet, `history` empty): shows `suggested_subject` and `suggested_message` in the editor; "Save draft" if `can_prepare`, else read-only.
- Draft ready (latest history item without dispatch): subject, message, attachment, buttons Send reminder, Schedule (if `can_schedule`), Edit, Not now. The line "This sends to the client." sits under Send.
- Scheduled: dispatch with `scheduled_for` and no receipt: "Scheduled for {date-time}" and Cancel schedule.
- Sent, delivery not confirmed: dispatch present, receipt null, `scheduled_for` null or past: "Delivery not confirmed yet", with Check mailbox (synthetic) or Record delivery (`confirm`, if `can_confirm`).
- Delivered / not delivered: `receipt.delivered` true "Delivered" or false "Not delivered", with `reference` and `recorded_at`.
- Set aside: `set_aside: true` item reads "Set aside, nothing was sent".
- Follow-up: from `timing`: "Follow-up interval: {minimum_days_between} days"; "Earliest follow-up: {earliest_date}" only when non-null; "Waiting for the original receipt" only when `awaiting_receipt` is true. `timing: null` shows nothing.
- Dispatch block (Question 1, option a): `mode` as "Manual evidence" or "Synthetic mailbox" and the scheduled send time sit in the dispatch status block beside the send action.

### Hidden (D-182), not replaced by a default
- "Overdue by N days" and the subject text "is 21 days overdue" computed in the browser: not drawn; only `due_date` is shown. The page does not edit the server's suggested text.
- "Last payment": not drawn.
- "Reminders sent: None yet": drawn only as a count of `history` items that have a `dispatch`; with an empty history the row is "None yet" because the read is complete; otherwise the row is hidden.
- The "7 days" sentence: replaced by the API `timing` values above; never a hard-coded number.
- "Copy: Kunle Ade (PM)": the API has no copy recipient; not drawn.
- "Uploaded · 84 KB": `attachments[]` has only `label`; drawn as the label (a link to `history[].attachment_url` for sent drafts).
Unknown money stays unknown: `owed` is shown as given with `currency`; a missing or null value reads "Unknown", never 0.

### Fixture examples (mock at 4991 must serve these, live-shaped)
1. Ready draft: `reference "INV-0391"`, `balance {due_date "2026-10-22", currency "NGN", amount_basis "outstanding", owed "6800000.00"}`, recipient set, `hold null`, `can_prepare true`, `can_schedule true`, `can_confirm false`, `history []`, one attachment.
2. Held: `hold "No sender is configured for reminders"`, `can_prepare false`.
3. Scheduled: history item with `dispatch {id 5, mode "synthetic_mailbox", scheduled_for "2026-11-30T09:00:00Z", receipt null}`.
4. Sent, not confirmed: dispatch without receipt, `can_confirm true`, two `receipt_proofs`.
5. Delivered: dispatch with receipt `{delivered true}`; `timing {minimum_days_between 7, earliest_date "2026-12-07", awaiting_receipt false}` (fixture values only).
6. Errors: 403, 404, 409 on save and on action, 422 with `fields`.

## Lanes
- Frontend lane (owner of everything here): `frontend/src/app/finance/payments/[caseId]/invoices/[issueId]/reminder/**`, a new `frontend/src/features/finance/reminder/**` (view, `useReminder.ts`, `model.ts`, the F-85 line adapter mapping for the reminder in `reminderAdapter.ts`, css), the link change in `frontend/src/features/finance/payments/PaymentsView.tsx` and `model.ts`, `frontend/mock/invoices.mjs` or a new `frontend/mock/reminders.mjs` registered in `frontend/mock/server.mjs`, tests under `frontend/src/**` and `frontend/e2e/payment-reminder*.spec.ts`.
- Backend lane: none. The API 1.24.0 is used as is; any contract defect is raised to the integration owner.
- Integration owner: lane D coordinator. Shared files: `frontend/src/features/workspace/*` (lane C; not changed here: a needed change is named as a dependency on lane C), `frontend/src/api/*` (shared; limited to live types and error mapping if missing), `frontend/mock/server.mjs` (one registration line).
- The old v7 reminder (`payment_reminder` line, W-38xx fixtures) is left in place for the other mock screens unless nothing else uses it; removing it is not required.

## Acceptance criteria
Checks use Next at 4990, mock at 4991, Django at 8030.
1. From Payments, a row with `reminder_url` links to `/finance/payments/{case_id}/invoices/{issue_id}/reminder`; a row with `reminder_url: null` or `issue_id: null` shows no link — verify: unit test on `PaymentsView`/`model.ts`; e2e click-through at 4990.
2. The page shows the live reference, `owed` with `currency`, `due_date`, recipient name and email, subject and message — verify: e2e on fixture 1; a `owed` of null shows "Unknown", never 0.
3. The page draws no "Overdue by", no "Last payment", no "7 days" text and no "Copy:" line — verify: e2e text absence on fixtures 1 and 5; grep `frontend/src/features/finance/reminder` for `days overdue` and `7 days` returns nothing.
4. Saving the draft posts `{revision, subject, message, attachment_id, attachment_checked}` with the read's `revision`, then re-reads — verify: unit/e2e request assertion on the mock; a 409 shows the server message and keeps the typed text; a 422 field error shows under its field.
5. Send posts `{action:"send", draft_id, revision}` once per press; a second press while pending sends nothing — verify: e2e counts one request on a double click.
6. Schedule posts `scheduled_for` as an ISO date-time and appears only when `can_schedule` is true — verify: e2e with fixture 1 and a fixture with `can_schedule:false`.
7. Not now requires a reason (1..1000 chars); an empty reason blocks the request; success shows "Set aside, nothing was sent" — verify: e2e.
8. Cancel schedule is offered only for a scheduled dispatch with no receipt and posts `{action:"cancel_schedule", dispatch_id, revision}` — verify: e2e on fixture 3.
9. Check mailbox is offered only for a `synthetic_mailbox` dispatch with no receipt and posts `{action:"check_mailbox", dispatch_id}`; Record delivery posts `confirm` with `evidence_id` chosen from `receipt_proofs`, `delivered`, `reference` and is offered only when `can_confirm` is true — verify: e2e on fixture 4 and a fixture with `can_confirm:false`.
10. After a failed or timed-out send (mock returns 503 once, then the read shows the dispatch), the page does not offer a new Send for that draft and shows "Delivery not confirmed yet" with Check mailbox or Record delivery — verify: e2e.
11. `hold` text is shown verbatim and Send, Schedule, Edit are disabled while it is set; `recipient: null` also disables Send — verify: e2e on fixture 2.
12. `timing` values drive the follow-up lines; `earliest_date: null` hides that line; `awaiting_receipt: true` shows "Waiting for the original receipt"; `timing: null` shows no follow-up line — verify: unit test on `model.ts`.
13. `mode` and the scheduled send time show in the dispatch block — verify: e2e on fixture 3.
14. Negative: 403, 404 and 5xx each show their own state with the server message; a malformed `issueId` or `caseId` shows not-found with no API call — verify: e2e, request log.
15. Negative: a user without access to the case sees no draft text and no action buttons; the mock returns 403 for the wrong user and the page keeps no earlier data on screen — verify: e2e persona switch.
16. No request goes to `POST /setup/{case_id}/payment-reminder-rules` and `src/features/workspace` has no changed file — verify: `git diff --stat origin/main -- frontend/src/features/workspace` is empty (or only F-85 files already on main); request log.
17. Phone width (390) shows the same facts and actions in one column with no horizontal scroll — verify: e2e at 390.
18. Against Django at 8030 with the live adapter, the read of one seeded invoice renders and the save and send actions return 201 and 200 — verify: manual run recorded in the build notes; the mock is the CI evidence.
19. Unit tests cover `model.ts` mapping (state selection, hold, timing, unknown money) and the action body builders, including that a missing `revision` disables actions — verify: `vitest` on `frontend/src/features/finance/reminder`.

## Out of scope
- The rules write (`POST /setup/.../payment-reminder-rules`), the rules screen, who may send, who is copied.
- Any change to `frontend/src/features/workspace` (lane C).
- Recording a payment, short-payment decisions, payment allocation (other features).
- Any blind resend, auto-retry of `send`, or automatic second reminder.
- Computing days overdue, last payment or totals in the browser; editing the server's suggested text beyond what the person types.
- A copy-to-PM recipient, a "Download PDF" control, or upload of a new attachment.
- Removing the v7 mock reminder line.

## Assumptions
- Route shape `/finance/payments/{caseId}/invoices/{issueId}/reminder`: no route is specified; it sits under the Payments area the person came from.
- `draft_id` for send and set aside is the latest history item that is not set aside and has no dispatch: the contract names `draft_id` but not how to pick it.
- A dispatch with `receipt: null` and no `scheduled_for` (or one in the past) is "Delivery not confirmed yet": the API has no explicit uncertain flag; this never offers a resend.
- "Reminders sent" is derived by counting history items with a dispatch, shown only when history is complete; the contract gives no count field.
- Error text comes from the server `message`; 409 gets a fixed "changed, check and try again" fallback only when the body has no message.
- `receipt_proofs[]` is the only source of `evidence_id` choices, as `{id,label}`; upload of new proof is not part of this feature.
- The rules read is optional context and never blocks the page.
- Payments link wording: kept from the existing view; the board's text wins on a clash.

## Questions
1. Where should `mode` and the scheduled send time appear, given the boards do not draw them? Options: (a) Recommended: in the dispatch status block beside the send action; (b) in the history list only. The builder follows (a).
2. The boards draw "Copy: Kunle Ade (PM)", "Overdue by 21 days", "Reminders sent: None yet / Last payment: None", "Uploaded · 84 KB" and Chidi's "7 days" sentence; the API supplies none of them. Options: (a) Recommended: hide each (D-182) and show the API `timing` lines instead; (b) draw them as "Unknown". Context: option (b) puts words on a client-facing money screen that the API cannot back.
3. The boards show one fixed "Send reminder / Edit / Not now" row. Live adds Schedule, Cancel schedule, Check mailbox and Record delivery, and a hold notice, which no board draws. Options: (a) Recommended: add them as secondary buttons and a notice in the existing action row and delivery area, using library components; (b) hold them until new boards are drawn. Context: without (a) the live flow cannot reach a scheduled or uncertain state.
4. "Not now" needs a reason (API requires 1..1000 chars) and the boards draw no reason field. Options: (a) Recommended: an inline reason field opened by Not now; (b) a modal. Context: either adds an element the board omits.

## Conflicts with the boards
- SCR-32 desktop and mobile: removed "Copy: Kunle Ade (PM)", "Overdue by", "Last payment", the "Uploaded · 84 KB" size and the "7 days" sentence (no data). Added: Schedule, Cancel schedule, Check mailbox, Record delivery, reason field for Not now, hold notice, dispatch block with mode and send time, follow-up lines. Recommendations are in Questions 1 to 4.
- The mobile board shows a shortened summary and one button; this spec follows the same one-column full content as F-41 did (D-111); recommend keeping that.
