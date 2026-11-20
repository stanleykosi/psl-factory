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
   (prefilled drafts, accept-with-edit, cover letters, payment reminders, saved cites). For `records` fields this means a list of `{value,label}` as `value`, so a saved draft's cited records come back (F-21 UX-1-1); and confirm whether a step write that omits a cites field keeps the saved cites.
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

## Added during F-21 (15 Nov)

- **Reconcile after an uncertain send** (`POST /work/{id}/actions`, reconcile): the mock does not answer it yet (501), so what the work item looks like after "It didn't arrive" or "It arrived" is recorded is untested on any stack. Please define the reply and the next state (F-21 QA-3-1).
- **Unknown work id must be 404.** The mock serves a default item for any unknown id; the real API must answer 404 for an unknown or other-tenant id, and the frontend shows no client, title or id then (F-21 QA-3-2).
- **Cited records:** see priority 1 and 2 above (list-valued `value` for `records` fields; whether an omitted cites field keeps the saved cites; scope every cite to person, case and week).
- **Which record the weekly timeline cites:** the board shows MIN-0141 (minutes); the sample data cites MTG-0140 (weekly sync). PSL/backend to decide.

## Added during design-system conformance (16 Nov)

- **Projects list rows need an open/closed state** (E-PROJECTS, D-PROJECTS-VIEW). D-94: a closed project's missing next milestone shows "—", an open one's shows "Unknown". Rows carry no open/closed field today (`additionalProperties: false`), so on "All I can see" a closed project still shows Unknown. Additive: a `closed` boolean or lifecycle state per row.
- **Overview chips need `status.tone`** for waiting, uncertain and stopped work. The page never infers colour from text (F-08); without the tone, "Effect uncertain" can't show amber.

## Added during F-22: weekly report returned and received (16 Nov)

Screens: SCR-25 returned and received (W-2209 to W-2214 on the mock). All additive proposals; the backend may rename or refuse.

- **Toned banner** (`workspace.banner {tone, text}`): the boards draw an amber "returned" banner and a green "received" banner. Today the page shows the return note as an amber callout and the received sentence as a row with a green "Verified" tag only when every delivery is confirmed (D-97). Green must never show unless every delivery is confirmed.
- **Per-recipient receipt record**: each client recipient needs its own delivery state (`delivered | uncertain | unknown | failed`), a time (or none: the page shows "Time unknown"), the backend's own tag text (e.g. DELIVERED, Bounced) and the channel. Today `recipients` rows carry a tag and a receipt word; the "Approved" row is an item with no receipt. Uncertain must never read as received; reconcile is per recipient (priority 6).
- **Step submit label** (`steps[].submit_label`): "Edit your update" reuses the `send_to_tola` step; the form's heading and button need their own label.
- **Return note and returner**: where the PMO Lead's return note, who returned it and when are carried; whether a returned item also offers `save_draft` (the board shows one button).
- **Next line for failed or unknown delivery**: `workspace.next` lines tell the PM what happens next; please send one for a failed or unknown delivery too (F-22 UX-1-1).
- **Saved cites in step fields**: `value` as a list of `{value,label}` on `records` fields (priority 2), so "Edit your update" opens with the saved cites (F-22 QA-2-1; the mock carries this and the contract test strips it).
- **Uncertain item without reconcile**: the page now locks every step whenever an item is `effect_uncertain`, with or without `reconcile`, and says "We are checking what happened. Nothing was sent again." Please always send `reconcile` with an uncertain item, and define the reconcile reply (still 501 on the mock, F-21 note; W-2212).
- **Unknown work id is 404** (F-21 note): still served a default item by the mock (F-22 QA-2-2).
- **Limits**: D-RETURN (what Return creates and how v2 is numbered) and D-ALERT-PROVIDERS (real delivery confirmations) are open; the frontend shows only what the data says and claims no real delivery.

## Added during F-24: the assistant (16 Nov)

Screens: SCR-05 default, working, thread, draft-started (`/assistant`, `/assistant/[conversationId]`). Everything runs on the contract mock (`frontend/mock/assistant.mjs`, CV-2401..2406, CV-2411, CV-2499); no real agent, provider or backend answers. Full gap list: [gaps-a-project-setup.md](backend-handoff/gaps-a-project-setup.md) G-SCR05-1..8.

- **Link a draft to its work item** (G-SCR05-1, blocking for real use): optional `source:{conversation_id, message_id}` on E-WORK-START and a stable `message_id` on messages, so one draft starts at most one work item.
- **Second start of the same draft**: the mock answers 409 `{code: "draft_already_started", message: "This draft was already started.", work_id, reference}`. Please confirm the shape. Today the Start work drawer shows its generic "changed, press start again" text and re-enables start (F-24 QA-3-1); with the confirmed shape the page will show the backend's message and offer only Close.
- **Idempotency on assistant writes** (G-SCR05-3, blocking): `idempotency_key` on E-CONVERSATION-NEW and E-MESSAGE. Until then the page uses a click lock, never retries on its own, and re-reads the conversation before offering "Try again".
- **Started state**: `draft.started {work_id, reference}` exists; please add `draft.started.note` (the board's "now at its first review station" sentence) and a `started` status word for the conversation list, or confirm the list should derive it from `draft.started`.
- **Restricted sources** (INV-RESTRICTED): the mock sends a restricted source's label and the frontend drops it, showing only "Restricted". The real API should not send the label at all.
- **Edit draft** (G-SCR05-2), **mentions echo and milestone/meeting kinds** (G-SCR05-4), **an alert when a working conversation ends** (G-SCR05-7: the page says "You can leave; you'll be alerted"), backend-owned agent copy and status words: see the gap file.
- **Speech input** stays held by D-SPEECH-INPUT: the microphone is drawn but does nothing.

## Added during F-26: the project Money tab (17 Nov)

Screen: SCR-12 (`/projects/{caseId}/money`), read-only, on the contract mock (`frontend/mock/money.mjs`; D-PROJECT-TAB-ROWS is still proposed; nothing released). Gap ids G-SCR12-1..4 are in [gaps-a-project-setup.md](backend-handoff/gaps-a-project-setup.md).

- **Source details** (G-SCR12-1): add `component`, `version`, `rule_version` and `case_id` to `source_details[]`. Until then the panel shows what is sent and no version line.
- **Figure context for the assistant** (G-SCR12-2): E-CONVERSATION-NEW needs a figure context. Until then "Ask me about any figure here" is a plain link to `/assistant`.
- **Rows with no figure** (G-SCR12-3): a row without `figure_id` shows "No source recorded" and its amount is not a link. Please document this case.
- **`as_of` on E-REPORT figures**: the page shows E-PROJECT-TAB's `as_of`; figures need their own.
- **`finance_tracks`**: the page reads "Finance tracks" and infers nothing. Please say whether it means "not shown to this person".
- **Who may read the Money tab**: per record. 403 or 404 for PMO? A 404 must reveal no stage names. Today a refused read shows "You can't see this project's money." (D-108) and no stage or amount.
- **Optional display fields**: report title and eyebrow (the page writes no title of its own).
- **"—" versus Unknown**: paid `not_due` shows "—"; an absent `paid` shows "Unknown", so an unknown paid state must be sent as `paid.status: unknown`, never by leaving it out. An absent `invoice`/`invoice_status` shows "—", meaning no invoice yet. Please confirm.
- **Money rules the page relies on**: amounts as decimal strings (never numbers); no totals are drawn; invoice and paid are separate; a report figure whose value differs from the row shows both with "These figures differ".

## Added during F-27: Setup delegation (17 Nov)

Screen: SCR-13 delegation (`/setup/delegation`), on the contract mock (`frontend/mock/delegations.mjs`). Held: D05 (identity delegation), D-ADMIN-AUTHORITY, D-DELEGATION-VIEW (proposed). Contract mock only, nothing released. Gap ids G-SCR13A-1..6 are in [gaps-a-project-setup.md](backend-handoff/gaps-a-project-setup.md); the items below supersede its older text where they differ.

- **G-SCR13A-1..6** (all proposals, unconfirmed): `from_person_id` and `from_options[]`; `delegate_options[].for_person_id`; end-early; `delegation_id` returned; authority-ceiling enforcement; tab counts.
- **From semantics**: an absent `from_person_id` means the caller. The page sends it whenever From comes from `from_options[]`, including a single option (F-27 SEC-1-1). The older "optional, defaults to the caller" note and the spec's "two or more choices" rule are superseded.
- **To pairing**: when `for_person_id` is present, To lists only delegates paired with the From shown; with no From list, only unpaired delegates (SEC-1-2). The backend still decides.
- **List-level `can_add`**: absent or false means no add control. Today only per-row `can_change` exists.
- **First delegation**: v7's E-DELEGATION body requires `expected_revision` ≥ 1, but a list's `revision` can be 0. Please allow 0 (the mock does).
- **422 `fields[]`** with names `from_person_id`, `delegate`, `authority`, `starts`, `ends`, `reason`; the page labels them "From", "To", "Authority", "Starts", "Ends", "Reason".
- **Uncertain add**: on an unconfirmed write the page re-reads the list; if the revision moved it offers only "Start again", so a second press can't duplicate. Please make a replayed PUT with the same body answer 409, as the mock does.
- **The two board sentences** ("Only people who already hold the same role are listed", "Delegating can't give anyone authority they don't already have") are shown as drawn (D-103). The backend must enforce both.
- **Mock question** (F-27 TECH-1-1): in the readonly scenario the mock refuses with 422 before its "no `can_add` → 403" check. Which should the real API return?
- **Open**: project-scoped delegation; what happens to claimed tasks when a delegation ends; optional `delegate_hint`/`note`.

## Added during F-23: the minutes line (17 Nov)

Screens: SCR-28 default, suggesting, drafted, review (work item line workspace, fixtures W-2301..W-2308). Contract mock only (D-LINE-WORKSPACE proposed); the template is a test template; a real client send is gated by D-ALERT-PROVIDERS; idempotency and the no-resend lock are proved on the mock only. Gap ids G-SCR28-* are in [gaps-c-client-lines.md](backend-handoff/gaps-c-client-lines.md).

- **Pre-ticked suggestions** (`steps[].items_default: "checked"`): Tola's suggested decisions and actions arrive ticked; one Confirm sends `item_ids` for exactly the set shown (kept decisions and remaining actions), with `expected_revision` and an idempotency key. Nothing suggested becomes a decision or action until confirmed.
- **Item steps send their item** (`item_ids: [id]` on every line's item-scope step, e.g. Edit/Remove). Each line's handler must accept or ignore it.
- **Edit prefill** (`items[].values`): the row's current text, owner and due, so Edit opens with them; a field the PM clears is left out of the request.
- **Board date format** (`columns[].date_format: "day_month"`): "13 Nov" in the Due column; an unknown due is `{unknown: true}` (amber Unknown), never a date or blank.
- **Toned agent-note lines** (`agent_note.warn_lines: [indexes]`): lines that ask the PM to act show as an amber warning (D-105). Flags by index; nothing matches on words.
- **Links from a workspace** (`workspace.links[]`, `link.action_id`): "Ask Tola", "Open the minutes".
- **Document read** (E-DOCUMENT): `test_template: true` shows a "Test template" tag.
- **Meeting, action and decision records**: their own records with ids, owners, due, status (priority 10).
- **Owner options per work item**: E-LINE-OPTIONS needs `work_id` (priority 8); options may carry a `hint` with `recorded_by_pm` / `outside_party`.
- **Approve and Return** go through the decision page (claim; Return needs a note). After an uncertain approve, the page shows "result not confirmed" and the work item offers only reconcile (QA-3-1); please define the reconcile reply (W-2305).
- **Open**: G-SCR28-5 (audience change after drafting), G-SCR28-7 (when actions are created), G-SCR28-8 (recipients from client records), G-SCR28-9 (meeting notes are untrusted input), D-RETURN.
- **Wording asks**: the shared decision copy "Paid is tracked separately by Finance" shows on minutes approves (QA-3-2); "Approve and send" on the work page vs "Approve v1" on the decision page (UX-1-3).

## Added during F-25: project tabs — Milestones, Registers, Actions (17 Nov)

Screens: SCR-38 (default, changed), SCR-11, SCR-29 (`/projects/{caseId}/milestones|registers|actions`), read-only, on the contract mock (`frontend/mock/project-tabs.mjs`; D-PROJECT-TAB-ROWS proposed; nothing released). Documents stays "coming next" (no approved list board). Gap ids are in [gaps-a-project-setup.md](backend-handoff/gaps-a-project-setup.md).

- **Invoice status label** (G-SCR38-1): `milestones[].invoice.status_label`. Until then the cell shows the reference with the standard state word ("INV-0412 · Waiting"); a missing or unknown state reads "Unknown".
- **Mark milestone complete** (G-SCR38-2, G-SCR19-2): `milestone_id`, `reference`, `can_complete`, `cannot_complete_reason`. The button is left out until the backend decides who may complete (D-104); FE-MILESTONE-COMPLETE builds it.
- **Change amount note** (G-SCR38-3): `contract_amount_note` or `changes[].amount_note` ("Unknown until a SOW amendment is signed"); the page builds "+ the change · change amount Unknown" from data and never sums a milestone with its change.
- **Filters** (G-SCR11-1, G-SCR29-1): severity, state and owner filters with options as `filters:[{key, options}]`. Today only search is offered and "Filter" is left out (D-104).
- **Row shapes** (G-SCR11-2): confirm Changes, Emergencies and RFPs share the register row shape.
- **`state_key`** on register and action rows if states are to be coloured; today `state` is display text only.
- **Owner/due edit** (G-SCR29-2): the board sentence implies one, but there is no operation; design to keep or drop.
- **Questions**: is `age_seconds` computed at response time (a closed issue's age shows "Unknown" until a not-applicable signal exists); which `paid.status` the board's "—" maps to; tab reads must hide figures and names on 403/404 (the page shows one "No access" panel and no row text).
- **Money rules relied on**: Unknown is never 0; completion, invoice and paid are separate facts; amounts as decimal strings.
- **Also for F-25** (PMO): `summary.note` for the change sentence; a proposal for an "age does not apply" signal on closed issues; do `summary` counts reflect the `q` search?; what `finance_tracks` means for this person (shown as "Tracked by Finance"); does an absent `paid` mean nothing recorded?; please confirm the two static sentences (the SCR-11 footer rule and the SCR-38 footer); ask design for the other registers' columns; the paid labels are frontend wording for now. Limits: D-PROJECT-TAB-ROWS is proposed, the backend may change or refuse any field, there is no backend yet, and the Documents tab row shape is unsettled.

## Added during F-28: the minutes line, finished (17 Nov)

Screens: SCR-28 filed internal and published (work item `view: "internal"` / `"published"`, fixtures W-2309..W-2314). Contract mock only (D-LINE-WORKSPACE proposed): nothing is sent, filed or created; a real client send is gated by D-ALERT-PROVIDERS; the template is a test template. The frame draws only what the reloaded work item returns and adds no rule.

- **Link kind `project_tab`** (G-SCR28-3): `workspace.links[]` target `{kind: "project_tab", tab, case_id}`; "Open actions" goes to `/projects/{case_id}/actions`. Drawn only for a known tab and a valid case id. `link.action_id` (per-action link) is recorded, not built.
- **Receipts are per person** (G-SCR25-1): `recipients[].receipt` is the only delivery evidence. Only `received` may read Received. A person on a channel with no `receipt` reads "Unknown". The returned sentence and tag ("delivery confirmed", Delivered) are drawn as returned: the backend must only return a confirmed sentence and a verified tone when every recipient is `received`; the frame does not check.
- **Created actions table**: columns action, owner, due (date or `{unknown: true}`), state (tag). An action with no owner returns the owner cell "No owner yet" and the tag "OWNER NEEDED" (tone `person`); OPEN is tone `uncertain`. The frame guesses nothing from text.
- **Audience skips review** (no decision id): internal minutes end filed with no review; which audiences skip it is the backend's.
- **Open**: G-SCR28-6 (action, decision, meeting records), G-SCR28-7 (actions created at confirm or at approval), where internal minutes are filed, D-RETURN, server-side refusal of a resend while delivery is uncertain (SEC-5-C1), the idempotency promise, and the project tab counts on the tab bar.
- **Owner assignment** (W-2313 only): an item step `assign_owner` on an OWNER NEEDED action, through E-WORK-STEP and E-LINE-OPTIONS `minutes/owner`. No board draws it; keep or drop.

## Added during F-29: document review (17 Nov)

Screen: SCR-08 (`/projects/{caseId}/documents/{documentId}?v=<version>`, 4 boards) and a read-only Documents tab list. Contract mock only (`frontend/mock/documents.mjs`, overlay `frontend/mock/proposals/document-review.json`; nothing released). Fixtures are sample data: SOW-0198 (D-2901), Lagoon Health, COST-0140, Kemi Adebayo, Tola. Gap ids G-SCR08-1..8 are in [gaps-a-project-setup.md](backend-handoff/gaps-a-project-setup.md).

- **E-DOCUMENT additive fields** (all optional; absent means the part is left out or reads Unknown, never invented): `case_id`, `project_title`, `reference` (G-SCR08-6); `sections[] {key, heading, text, changed_since?, notes?[{agent, text, cites?[{label, reference}]}]}` (G-SCR08-1, -2); `checks[] {key, label, status: done|held|blocked|unknown, detail?, cite?}` computed by the backend, shown in the order sent (G-SCR08-3); `audience {label}`, `review {role_label, work_id, task_id}`, `drafted_by {agent, from[]}` (G-SCR08-5); `returned {by, role, at, note?}` (G-SCR08-7).
- **Plain text only**: `sections[].text` and notes are plain text (paragraphs on blank lines); the page never renders markup. `body_url` is a link only, never fetched or embedded.
- **Version in the URL**: the page reads `?v=` and never guesses the latest; a document that names another `case_id` or version than the address is shown as not open. Approval on one version is never shown on another.
- **Review = one decision task** on `review.work_id` / `review.task_id`; Approve and Return use the existing claim and decision writes with `expected_revision`, a return needs a note (max 2000). Approve says "Not sent to the client": the page never claims a send. The re-read of the work item chain step (`status: approved`, `person`, `decided_at`) is what the confirmation shows.
- **Returned note** (G-SCR08-7): send `returned.note` only to a person who may read it; otherwise omit it and the page says "The note isn't shown to you." Alternative the page does not yet read: `tasks[].decision.chain.steps[].note`.
- **Not built (asked)**: "Ask Tola to draft v3" and "Edit as v3" are drawn disabled with "Not available yet" (G-SCR08-8: no operation drafts or saves a version); version history and Compare (G-SCR08-4); a "who reviews" rule beyond `review.role_label` and `you_can_act`.
- **Tola's note on the returned state** is read from the work item `workspace.agent_note.lines`, not the document.
- **Documents tab**: E-PROJECT-TAB `documents[]` (`document_id, title, version, status, test_template, work_id`); a row links to the review only when it carries a `work_id`. `tab_counts.documents` should equal the rows the person may see.
- **Questions**: should `status` text for a returned or approved version come from the document or the task? Does a returned document keep its task (the page stops claiming once `returned` is sent)? Board sentence "Approval on v2 is not carried over" is shown as written; please enforce it.

## Added during F-30: issue detail (17 Nov)

Screens: SCR-30 (default, overdue, no owner, verified; `/work/W-2411..W-2414`), the issue's work item on the line workspace, contract mock only (D-LINE-WORKSPACE proposed; nothing released). Gap ids G-SCR30-* are in [gaps-a-project-setup.md](backend-handoff/gaps-a-project-setup.md).

- **Raise an escalation** (G-SCR30-1, blocks the real start): a step `steps[].starts_line: {line_key, prefill}`. The page only opens Start work on that line, prefilled for the person to check; the escalation starts only when the person presses Start work's own button and the backend answers. v7 steps cannot start a line today.
- **Set an owner** (G-SCR30-3, blocks the real write): E-WORK-ASSIGN takes a `person_id` of someone with a login. The boards' owners are teams (no login, 13 Nov decision). Mock overlay `assign.candidates[].kind: 'person' | 'team' | 'outside_party'`; the page words a team or outside party as "Team" or "Outside party" after the role and `hint` (the backend may word this itself). `assign` sits at the top of the work item, beside `workspace`. No idempotency key on this operation: the page sends once per press and, after a 5xx or network failure, re-reads before offering the form again; please say whether a repeat assignment of the same person is harmless.
- **Record a reply** (G-SCR30-4): a workspace step `record_reply` with one required long text `reply`; the "(recorded by PM)" words come from the timeline item the backend returns, never from the page.
- **Reminder receipts** (G-SCR30-5): `receipt: uncertain` and `channel` on a timeline item for a reminder to a no-login team. The page shows the receipt word as returned and does not offer "send again" while the item is uncertain or a reconcile is present.
- **Links** (G-SCR30-2, optional): `workspace.links[]` for "Open the issue register". Until then the read-only item draws the link from `context.project.case_id`.
- **Lead sentences and agent note**: "Engineering hasn't acknowledged...", "Tola can't follow this issue up: it has no owner", the verified sentence and the owner-update note ("closing needs QA and the PM") are drawn exactly as returned, as an untitled `text` section note (the green banner when `workspace.status.tone` is `verified`) or a step `consequence`. The page composes none of them.
- **Questions** (`gaps-a-project-setup.md`): who posts the owner update (a person with a login, or the PM on the owner's behalf); confirm no step changes severity or state (closing needs QA and the PM, in the register); one work item per issue, with `reference` = ISS-xxxx. Also: the project tab bar on the issue page has no counts (E-WORK-ITEM carries no `tab_counts`) and marks no tab current (the response does not say which tab an issue belongs to).
- **Wording that is the frontend's, not a rule**: "Owner set: <assigned_to>", "No one can be chosen yet.", "Not recorded", "Open the issue register".

## Added during F-31: engagement and planning (18 Nov)

Screens: SCR-41 (engagement, `/work/W-2601`, register `W-2602`) and SCR-42 (planning `/work/W-2603`, record department input), 8 boards, line workspace on E-WORK-ITEM. Contract mock only (D-LINE-WORKSPACE proposed; nothing released). Gap ids G-41-1 to -7 and G-42-1 to -8 (`delivery/backend-handoff/gaps-b-rfp-planning.md`). On the mock nothing is sent to anyone: no department request goes out, no project or planning line is created, and no file leaves the machine.

- **Confirm PM through E-WORK-ASSIGN** (G-41-1, blocks the real write): proposed `assign.default_person_id` (must be one of `assign.candidates`) and `assign.default_hint`. When valid the form is drawn open with that person chosen, labelled with `assign.role`, button "Confirm <role>", notice "PM confirmed: <assigned_to>" when the role is "PM". Otherwise F-30's closed "Set an owner". No idempotency key on the typed body.
- **Register the engagement** (G-41-4, G-41-5, G-41-6): E-WORK-STEP `register_engagement` with an evidence field `plan_evidence` (kind `plan`), `start_date` and `client_contact` (both optional). Needed: where plan evidence lives before the project exists (the mock uploads it to the engagement item's own case); a 200 `created[] {kind, case_id?, work_id?, reference, line?}` and a reconcile path for a half-done registration (the page links to the project and planning item only from cites the re-read returns); where the client project contact is stored and whether it is required. The backend task should be rated high.
- **Planning rows** (G-42-1, G-42-2, G-42-4): proposed `items[].team_key` (the team a row's record step is for), `teams[].disabled_reason` (not offered in the form) and `teams[].asked_at` (not read). Estimates are plain text cells; a `quantity {value?, unit, unknown}` cell would let the browser format them. "Record input" is an item step whose `task_id` names the planning item's `team_input` task; the page opens F-18's form in a Drawer only when that task is in `tasks[]` with `you_can_act` and `response.variant: team_input`. "Who receives this?" is an item step with `disabled_reason: "Not available yet"` until Setup has a receiver rule and a link target.
- **Text with money in a cell** (G-41-3): a text-column cell may carry `text` and a typed `money`; the page draws "text · amount". Two amounts (awarded and costing) are two rows by source; the browser compares nothing.
- **Held for PSL** (no decision id): who sends department requests (G-42-3, Tola's "Sent requests … EMAIL · 08 DEC" is shown only as a checklist line, never as a receipt); whether pricing always reruns after planning (G-42-5); who accepts readiness and what makes planning verified (G-42-6, "Prepare readiness" is drawn disabled with its returned reason); whether the engagement asks again for a PM (G-41-2).
- **Mock only, not a proposal**: a step script may carry `serve` (another fixture served under the item's id); the E-EVIDENCE-UPLOAD mock accepts a workspace step's evidence kind; a one-team input on a task that stays open for other teams answers `recorded {by, at, summary, proof_count}` without marking the task recorded.
- **Questions**: should a planning item's status label ("PLANNING · 2 OF 5 IN") be the backend's text (the page counts nothing)? Does the record 200 need `recorded` on every call, or only the last? Should a 403 on the record write ever leave the item readable?
- **Wording that is the frontend's, not a rule**: "Confirm PM", "PM confirmed: <name>", "Recorded under your name: <summary>, <time>".

## Added during F-32: delivery tab and release gates (18 Nov)

Screens: SCR-43 (`/projects/{caseId}/delivery`) and SCR-44 (`/work/{id}`, line key `delivery_release`; default, decision and ready boards). Contract mock only (`frontend/mock/fixtures/work/W-2501..W-2510`, the `delivery` keys in `fixtures/projects/P-0101.json`, overlay `frontend/mock/proposals/delivery-release.json`). Nothing is released or deployed, no authority is configured, and every "release ready", "approved" and "Kemi Adebayo" is fixture text. Gap ids G-43-*, G-44-* are in [gaps-d-delivery.md](backend-handoff/gaps-d-delivery.md).

- **Authority only from the task**: the release decision is a decision task on the release work item. The page draws Approve and Return only when `tasks[]` holds the task a step names with `you_can_act: true`; otherwise the step is unavailable and says why (`cannot_act_reason`, `required_role`). This is a general frame rule (every step with a `task_id`), also used by F-33. Nothing is read from `/me`.
- **Release ready only from the response**: the work page shows "Release ready" only when the re-read item says so (`workspace.status.tone: verified`). An agent step "Mark release ready" that is `done` shows nothing (INV-AGENT): please set verified only after the recorded decision and a deterministic factory check. The mock's approve goes straight to the ready item (`W-2502.approve.json`), skipping readiness (part 2).
- **E-PROJECT proposals (all optional)**: `delivery[].reference` string, `delivery[].at {date?, unknown}`, `delivery[].detail` string (G-43-2); `delivery[].short_title` (G-F32-1, sub-nav label; falls back to `title`); `delivery_agent {agent, title?, status, finished_at?, steps[{text, status, source?, at?}]}` (G-43-3; absent or malformed falls back to `agent_summary`); `delivery_summary.note` (G-43-5, the line-order sentence; the page composes none). Tags take their tone only from `delivery[].gate.tone`. Rows link only through `work_id`.
- **E-WORK-ITEM proposal**: `workspace.links[]` kind `work`, `{key, label, target: {kind: "work", work_id}}` (G-44-2), a link to another work item, drawn only for a valid id ("Open go-live").
- **Recorded, not built**: G-43-1 `delivery_summary {reference, done, total}` (the browser never counts rows), G-43-4 `next_action`, G-43-6 (how the factory opens each next delivery line; no Start control), G-44-1 `workspace.notices[]`, G-44-3 `context` on E-CONVERSATION-NEW ("Ask Tola" sends none), G-44-4 `agent.finished_at` (the page reads the section `as_of`).
- **Questions for PSL** (`gaps-d-delivery.md:47-50, 67-73`): is the gate a "Planning decision" or a "Release decision" (the boards say both; planning and costing must finish before the SOW is signed); who holds release authority (D-ROLE-PMO lists closure, commercial approvals and escalations, not release); does Reject apply to a release (the F-16 page offers it; the boards draw Approve and Return); how is a delivery row the person may not open shown.

## Added during F-33: income schedules (18 Nov)

Screen: SCR-54 part 1 (investigating, review, returned, verified; `/work/W-2701..W-2704`), the income schedule's work item on the line workspace (`line_key: "income_schedules"`), contract mock only (D-LINE-WORKSPACE proposed; nothing is posted, exported or sent). Fixtures W-2701..W-2711 are sample data (SCH-0021, Bisi Ade, Ada Okafor, Chidi). Gap ids G-C-*, G-54-* are in [gaps-f-finance-workspaces.md](backend-handoff/gaps-f-finance-workspaces.md).

- **Decide in place** (G-C-1, G-C-2): a mock overlay `workspace.steps[].verdict: "approve" | "return" | "reject"` on a step that carries `task_id`. Each such step is one button in a "Decide · <required_role>" panel, labelled with the step's `label`, and the write is the existing E-TASK-CLAIM (once per task revision, only while `you_can_act`) then E-TASK-DECIDE `{verdict, note?, expected_revision}`. No verdict means the existing link to the decision page; any other value (`revoke`, `post`) is not drawn. The backend may refuse any verdict; its 403 or 422 is shown. Please say which verdicts a schedule review offers, and whether the step list or the task should carry them.
- **No idempotency key on E-TASK-DECIDE** (security review SEC-1, carried from F-16): the decide write sends `{verdict, note?, expected_revision}` with no key. A double press, a retry after a 5xx or a network failure, and a reload after `effect_uncertain` are stopped only by the claim plus `expected_revision`. The backend must refuse a second decide at the same revision (409) and must not apply a decision twice; please say whether E-TASK-DECIDE should take an `idempotency_key`, as E-WORK-STEP does. The page never resends a decision on its own.
- **Buttons only from `tasks[].you_can_act`**; otherwise the page shows the `cannot_act_reason` copy (`prepared_by_you`, `not_your_role`, `already_decided`) and sends nothing. The page reads no role, person or `prepared_by` rule and never reads `/me` for this. Separation of duties is the backend's.
- **Wording from the backend**: the panel's basis sentence is `tasks[].decision.basis` as returned ("…You didn't prepare it, so you can review it." is the backend's sentence, not the page's); the approve step's `consequence` ("Approving doesn't post anything…"); status labels, facts, figures, the reviewer's quote (an untitled `text` section `note`) and `next` lines. Only the note label ("Note (needed to return or reject)") and its messages are the frontend's.
- **Money**: the report line is a facts item `money {amount: "12400000.00", currency, unknown}`; the page formats the decimal string as returned and computes no total, count, difference or short form. "₦12.4M" (phone board) is not drawn: no endpoint supplies a short amount (proposal, not built: `money.display_short`). Unknown amounts and missing counts read "Unknown", never 0.
- **Counts are text**: "Income detail · 38 rows", "31 ROWS", "2 OF 2", "THESE 38 ROWS ONLY" and "the 7 additive and reclassification rows" are backend text in typed sections and `next`; the page never counts rows.
- **Who reviews schedules is NOT SET** (`finance.income_schedules.reviewer`): fixture W-2706 is the proposed hold, `state: setup_needed`, status "SETUP NEEDED" (`stopped`), a facts row "Who reviews schedules · NOT SET", a `next` sentence naming Setup in words, `tasks: []`, no steps and no reviewer anywhere. Please confirm this shape and the Setup link (G-C-3). `income_detail` and `inventory` rules are NOT SET too; the real review cannot start.
- **D-RETURN (open)**: built on the working assumption that a return gives the preparer a "Correct and resubmit" step: an E-WORK-STEP `correct_and_resubmit` with one required `choice` field `row_12_relationship` (disaggregation, reclassification, additive). Nothing is pre-selected (G-54-3: whose value would an initial value be?). Does a return create the preparer's task, and what are the real correction fields (they wait on the Income detail rules)?
- **Decided tasks**: after approve, return or reject the sidecars keep the task with `you_can_act: false`, `cannot_act_reason: already_decided` and one revision higher. On this line the frame no longer draws a "who can decide" card for a decided task with no step; the workspace says what it became. Verified is shown only from `state: verified` and the `verified` status tone.
- **State and view names used** (please confirm): investigating `processing`/`view: investigating`; review `action_needed`/`review`; returned `action_needed`/`returned`; verified `verified`/`verified`; rejected `cancelled`/`rejected` with status "REJECTED" (no board says what a rejected schedule becomes); held `setup_needed`/`setup_needed`.
- **Ask Chidi** (G-C-4): the existing `workspace.links[]` `assistant` link to `/assistant`, with no work-item context.
- **Held to part 2**: the held board and duplicate settlement (G-54-1, G-54-2), Export as an adjustment (G-54-5), Withdraw approval (`revoke`, G-54-4), the inventory kind (G-54-6).

## Added during F-35: leadership report (19 Nov)

Screen: SCR-52 part 1 (drafting, review, tuesday, received; `/work/W-3201..W-3204`), the leadership report's work item on the line workspace (`line_key: "leadership_report"`), contract mock only (D-LINE-WORKSPACE proposed). Nothing is emailed, messaged or delivered to anyone; no receipt is recorded by the page; nothing posts to E-WORK-ACTION. Fixtures W-3201..W-3212 are sample data (Tola, Ifeoma Nwosu, Sola Martins, the four audience roles). Gap ids G-SCR52-1 to -7 are in [gaps-c-client-lines.md](backend-handoff/gaps-c-client-lines.md) (lines 134-149).

- **Approve and send, decided in place**: reuses F-33's overlay `workspace.steps[].verdict` (`approve`, `return` only on this line) on steps that carry `task_id`; the writes are the existing E-TASK-CLAIM then E-TASK-DECIDE `{verdict, note?, expected_revision}`. Approving is what sends the exact version to the audience, so the backend must make the send part of the recorded decision's effect, refuse a second decide at the same revision (409) and never deliver twice (E-TASK-DECIDE still has no idempotency key, F-33 SEC-1). The approve step carries no `sends: true` on the mock: the shared step text for `sends` is "This sends to the client.", which is wrong for an internal report; the basis sentence says what approving does. **Contract rule asked (TECH-1-1, SEC-1-2):** whenever a step sets `sends: true`, the backend also sends that step's `consequence` as a sentence naming who receives it (for example "Approving sends this exact version to the leadership audience."). Without it the shared frontend fallback says "This sends to the client.", which is wrong for an internal report. Once confirmed, the fixtures will carry `sends: true` with that sentence. (Frontend follow-up outside this lane: the shared fallback in `Steps.tsx` should not name the client on a line it does not know.)
- **Who reviews and who receives are NOT SET** (Setup values, no decision id): W-3207 is the proposed hold, `state: setup_needed`, status "SETUP NEEDED" (`stopped`), station 3 `stopped`, a facts row "Leadership reviewer · NOT SET", a `next` sentence naming Setup › Rules in words, `tasks: []`, no steps, no `required_role` and no reviewer anywhere. Please confirm this shape. The review fixtures' `required_role: "Leadership reviewer"`, the reviewer's name and the four audience roles are sample data.
- **Sent, delivered and received only from the item** (G-SCR52-6): after approve the re-read is `processing`, status "SENT · CHECKING DELIVERIES" (`agent`), a `recipients` section with one row per audience role, each `receipt: not_yet`. One delivery not confirmed is `effect_uncertain`, status "SENT · DELIVERY NOT CONFIRMED" (`uncertain`), the row `receipt: uncertain` with tag "CHECKING" (`uncertain`, drawn amber). "Received by every recipient" is only `state: verified` with that status. The page never reads `uncertain` as received and offers no resend. Needed: who confirms an uncertain internal delivery and in what words (no `reconcile` or `allowed_actions` is sent on this line in part 1, so the client-worded ReconcilePanel never shows); whether a recipient row should carry `at` for an uncertain delivery (the page shows "Time unknown").
- **Tuesday reports go out without review** (rule held for PSL): W-3203 is `waiting`, status "PUBLISHED · NO REVIEW" (`verified`), a note sentence and `next` line from the backend. The schema has no "not applicable" fact status, so `reviewed` and `approved` are `not_yet`; please add one for lines with no review step.
- **Coverage and visibility** (G-SCR52-3, SEC-1-1): whose visibility builds a cross-project report is open. The proposal is the viewer's own, everywhere in the item: the figures, the agent's step text and sources (W-3210 cites "3 PROJECTS · 24 MEETINGS · 7 ISSUES" and no escalation id when 3 of 5 are visible), and the sentences. A left-out project may appear only as a count. Its records, ids, meeting or issue counts and its name must never reach the response. In addition: the figures section's `coverage` says how many projects are left out ("2 projects are left out because you can't see them.") and never names them; the drafting note is backend text. Every figure is a `value` string ("5 OF 5", "3", "2"); the page counts and sums nothing (G-SCR52-4). An unknown figure has no `value` and reads "Unknown". Please keep "invoices verified" apart from paid in E-REPORT.
- **Send for leadership review** (only where offered): E-WORK-STEP `send_for_review` with `applies_to: workspace`, no `inputs`; the page sends no reviewer or audience. A 200 `done` re-reads to the review with `cannot_act_reason: prepared_by_you` (G-SCR52-7, already typed). A 200 `effect_uncertain` (W-3212) shows the shared checking notice and sends nothing again. Please say whether a person sends the draft or Tola hands it over by itself.
- **Decided tasks**: after approve or return the sidecars keep the task with `you_can_act: false`, `cannot_act_reason: already_decided`, one revision higher; on this line (as on the income line) no "who can decide" card is drawn for a decided task with no step.
- **State and view names used** (please confirm): drafting `processing`/`drafting`; draft ready `action_needed`/`drafting`; review `action_needed`/`review`; returned `processing`/`returned`; sent `processing` or `effect_uncertain`/`sent`; tuesday `waiting`/`tuesday`; received `verified`/`received`; held `setup_needed`/`setup_needed`. Crumbs Overview / Leadership reports / reference from `workspace.context.crumbs`; no `context.project`, no `case_id`.
- **Ask Tola**: the existing `workspace.links[]` `assistant` link to `/assistant`, with no work-item context.
- **Held to part 2 or later**: the setup boards and "Start the report" (G-SCR52-1, G-SCR52-2); a report page, "Open the full report" / "Open the report", the Overview reports list and `X-LINKS` kind `report` (G-SCR52-5); the delivery channel (D-REPORT-DELIVERY suggested, D-ALERT-PROVIDERS open).
- **Wording that is the frontend's, not a rule**: the note label "Note (needed to return)" and its messages, "Monthly report v1 is approved" / "…: result not confirmed" (F-16 words), "Time unknown".
## Added during F-34: hypercare (19 Nov)

Screen: SCR-46 part 1 (running, record, setup-needed, qualified; `/work/W-3101..W-3104`, failure paths W-3105..W-3112, link target W-3120), the hypercare line's work item (`line_key: "delivery_hypercare"`), contract mock only (D-LINE-WORKSPACE proposed). Nothing is deployed, evaluated or qualified. Every "Day 10 of 30", "30 days · from Setup", Met and "qualified" is sample fixture text: PSL has not set `delivery.hypercare_window` or `delivery.hypercare_criteria` (D11 open), so the honest state today is the setup-needed hold. The page computes no day, window end, criterion or qualification.

- **Writes (mock only)**: `record_release` (inputs `version`, `released_at` ISO, `environment`; the deployment log uploaded first through E-EVIDENCE-UPLOAD with `evidence_kind: "deployment_log"`, sent in `evidence_ids`) and `log_observation` (`what`, optional proof `hypercare_observation`). Each carries CSRF, `expected_revision` as read and one `idempotency_key` per attempt. No deploy, evaluation trigger or Setup write exists.
- **After Record release the mock re-read is the hold** (`state: setup_needed`, no steps, no criteria rows), because a backend must not start a window it has no rule for.
- **Proposals**: G-F34-1 `workspace.links[]` target kind `setup_rules` `{kind, area}` (drawn only for a known area; the PM may get 403 on Setup, so please send the link only to people who may open it); G-46-1 `log_observation` and `OBS-` table rows (real write held); `environment` as free `text` (is it a list?); `evidence_kind` names `deployment_log`, `hypercare_observation`.
- **Not built, recorded**: G-46-2 evaluation trigger (who or what runs Tola's evaluation); G-46-3 drop "Record go-live acceptance" from this line; where the incidents count comes from; who sets the window and criteria (D11, D-ADMIN-AUTHORITY).
- **Only a returned `verified` status draws the green banner.** An agent step "Mark hypercare qualified" marked done (W-3110) is not qualification; the deterministic factory check sets it.
- **Shared fixes**: the "Done: …" notice now follows the re-read in `useWorkspaceStep` (same shape as F-41); an empty tag cell already read Unknown (F-31); the mock already accepted a workspace step's evidence upload (F-31).
- **Missing `waiting` tone (D-46, UI-1-2)**: the boards draw the running hypercare status, "Release not recorded" and the "Open · owner set" row tag amber (waiting on someone), but the workspace tone list (`neutral, person, agent, stopped, uncertain, verified, restricted`) has no plain waiting value; `person` draws orange and `uncertain` (the only amber) is reserved for effect uncertain. The fixtures return `person`; the page adds no mapping. Please add a `waiting` tone to `status.tone` and tag tones. Until then these three tags are listed as tone exceptions.
- **Setup link for a PM (UX-1-4, Conflicts 1)**: please send "Open Setup › Rules" only to people who may open Setup.
- **Backend asks from QA (QA-2-3, QA-2-4)**: the mock serves a default item for an unknown work id, where the real E-WORK-ITEM must answer 404 (the page treats 403 and 404 alike); and the mock accepts unknown `evidence_ids` on a step write, where the real E-WORK-STEP must refuse an id that was not issued by E-EVIDENCE-UPLOAD on this case (422).

## Added during F-47: Start work proof upload (19 Nov)

Screens: SCR-04 minutes, change, income schedules and ledger sources (desktop and phone), the Proof box in the Start work drawer. Contract mock only (D-START-INTAKE r1 proposed; nothing released). Gap ids G-SCR04P-* and the four backend questions are in [gaps-e-finance-payroll.md](backend-handoff/gaps-e-finance-payroll.md). No generated type changed.

- **Order of writes**: one E-EVIDENCE-UPLOAD per chosen file, on the line's case, the moment the file is chosen; then one E-WORK-START per press carrying the uploaded `evidence_id`s in `intake.<field>` (one id, or a list when the field is `multiple`) and the `case_revision` the last upload returned. The upload 200 must carry a non-empty `evidence_id` (a 200 without one is shown as not uploaded) and should carry `case_revision`; without it the start sends the last revision the page knew.
- **Which case for the two Finance lines** (gaps-e question 3): the mock serves `income_schedules` on fixed case `C-FIN-SCHEDULES` (revision 3) and `ledger_sources` on `C-FIN-LEDGER` (revision 2), one case per line so one line's upload doesn't make the other's revision stale. The backend picks both; the page reads `case_id` and `case_revision` from E-LINES only.
- **Evidence kinds**: `schedule_source` and `ledger_source` (proposed; no source names them), alongside the existing `meeting_notes` and `client_request`.
- **Upload limits**: size, type, page count and duplicate-by-sha256 are the backend's, answered as a 422 `{code, message}`; the page shows `message` word for word and checks nothing itself. The mock's only sample is `"EXE files can't be used as proof."` for a name ending `.exe`, and an empty file.
- **One revision per case**: please confirm a case revision is shared by everything on the case (uploads, starts, responses). The mock keeps start-work cases apart from F-09's response cases (`C-0101` has its own counter in each).
- **Evidence on the start**: an id not uploaded to the same case by the same person should answer 422 `{fields: [{name: <field>, message}]}`; the page shows it under the Proof box. Mock message: "That proof isn't on this record. Add it again."
- **403 and 404 on an upload** are shown the same ("You can’t add proof to this item."), and the file is not kept on the form.
- **`next` for the Finance lines** (G-SCR04P-9): the fixtures send none, as the boards draw none; if the backend sends it, it is drawn.
- **Who may start the Finance lines** (Conflicts 7): in the mock only the Finance persona is served them; the backend's E-LINES and `startable_lines` decide. The CEO persona keeps its 8 lines until D-LEADERS-START.
- **Held**: the Finance runs may wait in `setup_needed` while SCR-13 finance rules are NOT SET (the drawer only starts the line); fixed assets and cash forecast (F-47B); management accounts and `money` (F-47C); payroll and business-unit drawers.
- **Mock only**: cookie `psl_mock_start_work` = `upload_uncertain` (the next upload is stored and answers 500) or `start_uncertain` (the next start is stored and answers 500; a replay with the same key answers its 201), once per reset; ids `EV-SW-<case_id>-<n>`; fixtures `W-4401`, `W-4402`.

## Added during F-41: payments list and reminder (19 Nov)

Screens: SCR-20 (`/finance/payments`, the list; entry by address and from Chidi's note, no top-nav item) and SCR-32 (the payment reminder on the line workspace, `/work/W-3801..W-3813`, `line_key: payment_reminder`). Contract mock only (`frontend/mock/invoices.mjs`, `fixtures/finance/invoices.*.json`, `fixtures/work/W-38xx*`); nothing is sent to a client and no money record is written. Gap ids G-SCR20-* and G-SCR32-* are in [gaps-e-finance-payroll.md](backend-handoff/gaps-e-finance-payroll.md). Spec conflicts were taken as recommended under D-115 (provisional, pending the design engineer).

- **E-INVOICES overlay** (all optional, absent reads as not supplied; the page never adds up rows): `totals_detail.{owed, overdue, received_this_month}: {known?: {amount, currency}, has_unknown}` (G-SCR20-1, -2; "+ Unknown" only when `has_unknown`); `period` "YYYY-MM" (the month "received this month" covers); `bank_data_as_of` "YYYY-MM-DD" and `coverage` (the sentence under the strip, word for word) (G-SCR20-3); row `overdue: {days?, unknown}` in place of a bare `overdue_days`, so "not overdue" (—) and "not known" (Unknown) differ (G-SCR20-4, D-94); row `milestone_label` (G-SCR20-5; without it WORK reads client · project title); top-level `agent_note {agent: "chidi", lines[], work_id?, strong_lines?[]}` (G-SCR20-6). Without `totals_detail` the page reads only the typed `totals.owed`.
- **Never in the browser**: totals, overdue sums, overdue counts, days overdue, a PAID/PART PAID state from amounts, or a count from rows (`total` only). Invoiced, received and still owed are three separate fields; unknown is `unknown: true` with no amount, never 0.
- **Query**: `q` (reference or client), `status` (one `filters[].value`), `cursor`, `limit` 20. The mock's status-to-row rule (issued = all) is a stand-in; the real one is the backend's.
- **Reminder line `payment_reminder`**: steps `send_reminder` (`sends: true`), `edit_draft` (fields `subject` text and `message` long_text, both opened from `fields[].value`, G-SCR32-1; a save is a new draft version seen on the next read, `version.label` "Draft v2"), `set_aside`. States served after each: sent (status "SENT · CHECKING DELIVERY", a `recipients` section "Delivery" with each person's own `receipt`), set aside (`next` sentence), uncertain (`effect_uncertain`, `reconcile` with outcomes delivered / not_delivered / unknown, no `resend`), delivered (receipts `received` with `at`).
- **Attachment** (G-SCR32-3): `sections[].items[].attachment {label, size_bytes, document_id?}`, drawn as text only ("INV-0391.pdf · Uploaded · 84 KB"); opening the file is not built.
- **Facts are values** (G-SCR32-4): "None yet" and "None" must come from the backend; a last payment that is not known must be sent with no value (Unknown), never "None".
- **No billing contact** (G-SCR32-2): send the send step with `disabled_reason`. The mock still accepts a direct POST to a step that carries `disabled_reason`; the backend must refuse it.
- **Priority 1 before a real send**: idempotency by key (same key, same reply, no second email), refusal of any `send_reminder` while the item is `effect_uncertain` or carries `reconcile` (INV-RESEND), and the email provider. The page sends one write per press and never retries; it does not rely on the mock's replay map.
- **Priority 1: a hung send, then a reload** (QA-2-1, TECH-1-2, PMO-2-1): the browser has no request timeout. A `send_reminder` POST that never answers keeps every step off on that page, but a reload re-reads the item and, if the backend still shows the item as not yet sent, offers Send again. The backend must therefore refuse a second `send_reminder` for the same item while a first is in flight or its effect is unknown, not only while the item is `effect_uncertain` or carries `reconcile`, and must answer a repeated idempotency key with the first reply. Please also say whether the item read should show an in-flight send (so the page can lock after a reload) and what timeout the client should use.
- **Later, for the backlog** (PMO-2-2): QA-2-1 wording (a failed or timed-out send reads "We couldn’t confirm this step. Check the page before trying again."; the spec says "We are checking what happened. Nothing was sent again."; the design engineer chooses); TECH-1-2 (a client timeout); FE-PAYMENTS-RECEIPT (record a payment received, held on D-RECEIPT-ALLOCATION); the PSL questions above (who sends reminders, the PM copy, the second-reminder interval).
- **Questions**: who may send reminders and whether the PM is always copied (gaps-e:176-178; the page shows only the returned steps and recipients); the second-reminder interval (G-SCR32-5, the board's "7 days" sentence is not shown until a configured value is sent); draft versioning on `edit_draft` (does the backend keep Draft v1?).
- **Held, not on the page**: recording a payment received, proof, allocation (FE-PAYMENTS-RECEIPT, D-RECEIPT-ALLOCATION, D14 UNCONFIGURED); the short-payment decision and its link from a PART PAID row (D-DECISION-VARIANTS, G-SCR20-12).
- **Wording that is the frontend's, not a rule**: "No invoices to show yet.", "No invoices match", "We couldn’t load the payments. Nothing was changed.", "You can’t open this page", "Open the reminder draft", "Updated <time>", "Uploaded".

## Added during F-42: fixed asset schedule (19 Nov)

Screen: SCR-55 part 1 (investigating, register review, date review, calculating; `/work/W-3901..W-3904`), the fixed asset schedule's work item (PPE-0006) on the line workspace (`line_key: "fixed_assets"`, `screen: "SCR-55"`), contract mock only (D-LINE-WORKSPACE proposed; nothing is calculated, posted, uploaded or exported). Fixtures W-3901..W-3912 and their decide sidecars are sample data (Bisi Ade, Ada Okafor, Chidi, the assets and costs). Gap ids G-C-*, G-55-* are in [gaps-f-finance-workspaces.md](backend-handoff/gaps-f-finance-workspaces.md). The frame is F-33's, reused: decide in place through `steps[].verdict` (G-C-1, G-C-2), buttons only from `tasks[].you_can_act`, no idempotency key on E-TASK-DECIDE (F-33 PMO-3-1), and no card for an `already_decided` task.

- **Priority before a real decision (PMO-2-1)**:
  - **Claim on page load (question)**: as F-33 and F-42's specs say (F-33 spec:96, F-42 spec:145), the review page sends one E-TASK-CLAIM when it opens, only when `tasks[].you_can_act` is true; QA counted one claim per decidable page view and none otherwise. Does opening the page claim the task and so lock other reviewers out until it is released or decided? If yes, please say how a claim is released (timeout, explicit release) or whether the page should claim only when the person presses a decision.
  - **P-4, Calculate sent as `waiting`**: the Calculate station on the calculating board is sent with the `waiting` tone so the page does not read "Agent working" while the F07 calculation rules are unset. Please confirm the station tone the backend will send for a calculation that cannot start because a rule is missing.
  - **No idempotency key on E-TASK-DECIDE** (as F-33): a double press, a retry after a 5xx or a network failure, and a reload after `effect_uncertain` are stopped only by the claim plus `expected_revision`. The backend must refuse a second decide at the same revision (409) and never apply a decision twice; please say whether E-TASK-DECIDE should take an `idempotency_key`.
- **Two decide tasks on one work item** (readiness question 1): the register review (`T-3902`) and the date review (`T-3903`) are separate tasks in `tasks[]`, each claimed and decided on its own `task_id`. On the date review the register task stays in `tasks[]` with `cannot_act_reason: already_decided`. Please confirm two tasks rather than one task with two steps, and say whether the date review is skipped when no date is unclear.
- **The explain-dates step** (G-55-1, needs a board): who writes the explanation for each unclear date and attaches the proof is not built. After "Approve register" the mock serves a `waiting` item ("WAITING FOR DATE EXPLANATIONS", station 3 current, no task the person can act on, `next` as returned). The date review fixture opens with the explanations and the proof already present. Proposed later as an E-WORK-STEP `explain_dates` with an evidence field.
- **The proof** is a titled `text` section whose item carries `cites [{label: "asset-dates-explanation.pdf", evidence_id}]` and `detail: "Uploaded · 64 KB"`. It is shown as text: a cite with only `evidence_id` has no app path, and nothing is downloaded. Please say how evidence is opened from a work item.
- **Costs** are a `table` column of kind `money` with `cells[].money {amount: "<decimal string>", currency, unknown}`; the page formats the string as returned and computes no total, depreciation, opening, closing or count. Unknown reads "Unknown" (W-3910). "64", "4", "1", "3" and "3 assets have unclear dates…" are backend text, never counted by the page.
- **Unset rules are holds** (readiness question 2): `finance.asset_schedule.reviewer` / F07.review_authority (W-3907), `finance.asset_schedule.register` / F07.source_rules (W-3908), both stopping at Register review, and `finance.asset_schedule.calculation` / F07.calculation_rules (W-3909), stopping at Calculate. Each is `state: setup_needed`, status "SETUP NEEDED" (`stopped`), a "Why it's held" facts row with "NOT SET", a `next` sentence naming Setup in words, no step, no task anyone can act on, and no reviewer, role or figure. Please confirm the station each key stops at, and the Setup link (G-C-3).
- **Calculating** (W-3904 and the date approval sidecar): "PROCESSING" with the "Calculation" facts as returned and `item.agent.status: done` (Chidi does not calculate). Builder proposal: station 4 is sent as `waiting`, because the station enum has no status for a factory (non-agent) step and `current_agent` would draw "Agent working" on Calculate. Please say which station status a deterministic factory step carries. The fixture's "F07 CALCULATION RULES" is sample text; today the real state is the W-3909 hold.
- **"Depreciation starts from these dates."** is the date task's `decision.basis` as returned; which date starts depreciation is F07 Calculation rules, NOT SET. The page never picks a date.
- **D-RETURN (open)**: a returned register or dates re-read is "RETURNED" (`person`) with the reviewer's words as an untitled `text` section note and no step or `next`; a rejected one is `cancelled`, "REJECTED" (`stopped`). No correction step is built. What does a return give the preparer?
- **Chidi never reads asset values** (G-55-6, INV-AGENT): the line is the Register section's `note`, from data. The guarantee that values stay out of Chidi's context is the backend's.
- **Ask Chidi** (G-C-4): the `workspace.links[]` `assistant` link to `/assistant`, with no work-item context.
- **State and view names used** (please confirm): investigating `processing`/`investigating`; register review `action_needed`/`register_review`; waiting for explanations `waiting`/`waiting_dates`; date review `action_needed`/`date_review`; calculating `processing`/`calculating`; returned `action_needed`/`returned`; rejected `cancelled`/`rejected`; held `setup_needed`/`setup_needed`; decide not confirmed `effect_uncertain`/`effect_uncertain`.
- **Held to part 2**: the schedule by asset class and its review, Withdraw approval (`revoke`, G-55-4), the furniture opening balance (G-55-2), the accounting note (G-55-3), "Correct and resubmit", the correction proof upload, the "Feeds MANAGEMENT ACCOUNTS" link, and the board's compact amounts ("₦42.1M", "₦0.0M"; no endpoint supplies a short amount).

## Added during F-36: assign the accountable PM (19 Nov)

Screen: SCR-24 (desktop panel and phone sheet), opened from My work → Unassigned at `/my-work?queue=unassigned&assign=<work_id>` for an RFP whose E-WORK-ITEM carries `assign`. Contract mock only (D-RFP-INTAKE r1 proposed; nothing is sent to anyone: no alert, no WhatsApp, no email, and no analysis job exists). The persona `pmo_lead` (Kemi Adebayo) and the W-3301..W-3306 RFPs are sample data. Gap ids G-24-* are in [gaps-b-rfp-planning.md](backend-handoff/gaps-b-rfp-planning.md). The overlay is `frontend/mock/proposals/rfp-assign.json`; the generated types and openapi.json carry none of it.

- **Priority before a real assignment (PMO-3-1, security review SEC-N1/N2)**: the mock checks these today; the backend must enforce each itself. (1) `acting_role` is one the signed-in person actually holds for this item, never taken from the request on trust. (2) The `evidence_id` sent with the assignment belongs to this item's case (it was uploaded to that case by this person); refuse an id from another case with 422 or 403, never attach it. (3) The write carries `case_revision` and is refused with 409 when it is not the current revision; a refusal changes nothing. The mock's upload grant is looser than real authorisation and is not a model for it.
- **Authority only from the item** (no request field is a role): the panel exists only when E-WORK-ITEM carries `assign` with at least one candidate. Candidates are exactly `assign.candidates`; nothing is chosen ahead of the person, nothing is filtered or sorted in the browser, and nothing is read from `/me`. 403 and 404 look the same. Please confirm the backend alone decides who may assign and who is offered (which Setup rule?).
- **G-24-1 (blocking for the real write)**: `assign.roles: [{role, label}]` (minItems 1) with `assign.role` kept as the default key; request field `acting_role` (one of `roles[].role`), sent only when `roles` is present. One role is drawn as text, several as a drop-down with the default chosen. The backend must check the person holds that role and PSL allows it, and record it in the audit. **What does `assign.role` mean?** F-31 reads it as the label of the person being chosen ("PM" for "Confirm PM"); here it is the assigner's role. Please settle one meaning; the typed fixtures here send "PMO Lead", the overlay fixture sends the default key `pmo_lead`.
- **G-24-2 (blocking, with G-23-5)**: `assign.evidence_kind: string` shows a one-file Proof field; the file goes up first (E-EVIDENCE-UPLOAD on the item's case) and the request carries `evidence_id` and `case_revision` (the revision the upload returned). Needed: where an RFP's evidence case lives before it is assigned (the mock gives each fixture its own case `C-33xx`; D-RFP-INTAKE places RFPs on one fixed intake case, which would make assignments contend on its revision).
- **G-24-3 (nice to have)**: `assign.next: {summary, agent?, channels[]}`. The page shows `summary` then `agent` exactly as returned and names no channel itself; `channels` is not drawn on its own. Without it the page says "The PM you choose is alerted and sees it in Needs me. They start the RFP response." The backend should not send a Tola sentence until the analysis job exists (G-24-4, JOB-RFP-ANALYSE).
- **No idempotency key** on E-WORK-ASSIGN (the typed body has none): the page sends once, never resends, and after a 5xx, a network error or a timeout it re-reads the item first. The success words ("<reference> is now with <name>.") appear only after the item and the Unassigned list have been read again; an uncertain write shows "Not confirmed" and then either the read-back "Assigned to <name>" (no `assign`) or the form again (`assign` still present). A repeat after success must fail on `expected_revision` (409). `assigned_to` in the 200 is shown as returned.
- **Questions** (`gaps-b-rfp-planning.md:49-52`): which Setup rule names assigners and candidates; can an RFP be reassigned or unassigned (no board, not built); what the assignment alert says under I-ALERTS ("no client details").
- **Wording that is the frontend's, not a rule**: "Assign accountable PM", "Choose a PM", "n people can prepare RFPs here", "No one can prepare RFPs here yet.", "Not confirmed", the fixed "What happens next" sentence, and the intro sentence "Only people allowed to prepare RFPs for this workspace are listed. Who may assign is set by PSL in Setup." (a statement about the backend's rule, not applied by the page).

## Added during F-39: escalation (19 Nov)

Screen: SCR-51 part 1 (investigating, decide, not escalated, drafted; `/work/W-3601..W-3604`), the escalation's work item on the line workspace (`line_key: "escalation"`), contract mock only (D-LINE-WORKSPACE proposed). **Nothing reaches the client in part 1:** no message is sent, emailed or delivered to Lagoon Health or anyone outside PSL. "Message v1" is Tola's draft, shown as returned; "Send for review" hands it to the PMO Lead inside the app. Fixtures W-3601..W-3609 are sample data (ESC-0012, ISS-0241, Kemi Adebayo, Tola). Gap ids G-SCR51-* are in [gaps-c-client-lines.md](backend-handoff/gaps-c-client-lines.md).

- **Reused overlay, nothing new**: `workspace.steps[].verdict` (F-33 G-C-1: "Escalate to the client" is `approve`, "Don't escalate" is `reject` with a required note) and `workspace.links[]` kinds `assistant` and `work` (X-LINKS; "Ask Tola", "Back to the issue" to W-3609, the issue ISS-0241).
- **Buttons only from `tasks[].you_can_act`**; the panel's role words are `required_role`; nothing reads `/me`. The mock has no PMO Lead persona, so the decide board is served to `pm` and the fixture says `you_can_act: true`.
- **Decide has no idempotency key** (as F-33): a double press and a retry after a 5xx are stopped only by the claim and `expected_revision`; please confirm the backend refuses a second decide at the same revision.
- **Per-verdict words (X-VERDICTS, G-SCR51-2)**: recorded, not built. The labels and the consequence sentence are the steps' `label` and `consequence`. Proposed `tasks[].decision.verdicts[] {verdict, label, consequence, note_required}`, and that "Don't escalate" is `reject` and closes the item as NOT ESCALATED (state `cancelled`, our assumption).
- **Held, for the backend or PSL to answer**: whether "Don't escalate" tells the person who raised it; whether the PMO Lead may edit Message v1 (no edit is built); which internal notes skip review (G-SCR51-1); who reviews client messages. There is no policy slot, so fixture W-3608 is the proposed hold: `send_for_review` with `disabled_reason` "No one is set to review client messages yet. An admin sets this in Setup." and no reviewer named (sample wording).
- **Recorded, not built**: `escalations` in the register enums (G-SCR51-4); `action_id` and `issue` in `cites` (G-SCR51-5; the cites travel in W-3602 but are not drawn); the issue link (G-SCR51-6); `agent.finished_at` and an agent card title ("Drafted 13 Nov 14:00", "Investigating the escalation"); recipients from contact records (G-SCR51-3, part 2).
- **Facts and counts are text**: "15 DAYS LATE", "3 TIMES", "MILESTONE 3 · GO-LIVE 4 DEC", Tola's step sources and Message v1's dates are the backend's text; the page counts and dates nothing. A missing value reads "Unknown", never 0 (W-3606).
- **Decided task and sidecars**: after approve the item is `MESSAGE DRAFTED` (`W-3602.approve.json`), after reject `NOT ESCALATED` (`W-3602.reject.json`), each with the task `already_decided` one revision higher. `send_for_review` re-reads as "WAITING FOR REVIEW" with a review task the PMO Lead cannot act on here (part 2).
- **Two shared-frame limits seen** (not changed here): the in-place decide panel draws the reason from `cannot_act_reason` but not `tasks[].asked` (so W-3605 does not name Kemi Adebayo on the page), and a step with no fields is posted without `inputs` (the generated schema accepts that).

## Added during F-43: cash forecast (19 Nov)

Screen: SCR-56 part 1 (investigating, review, uncertain delivery, verified; `/work/W-4001..W-4004`), the cash forecast FC-0014 on the line workspace (`line_key: "cash_forecast"`, `screen: "SCR-56"`), contract mock only (D-LINE-WORKSPACE proposed). Nothing is published, sent, posted or paid; the forecast moves no cash. Fixtures W-4001..W-4013, the W-4002/W-4013 decide sidecars and the W-4003 reconcile sidecars are sample data (Bisi Ade, Chidi, the months and amounts, "Forecast reviewer"). The frame is F-33's, reused: decide in place through `steps[].verdict` (G-C-1), buttons only from `tasks[].you_can_act`, reconcile only through the existing reconcile panel when `allowed_actions` includes `reconcile`. Gap ids are in [gaps-f-finance-workspaces.md](backend-handoff/gaps-f-finance-workspaces.md).

- **Who reviews the forecast (question)**: Setup has `finance.cash_forecast.preparer`, `.inclusion` and `.group_reviewer`, but no key for the forecast review. The fixtures send `required_role: "Forecast reviewer"` as sample text only. Which role or Setup key decides the review?
- **No idempotency key on E-TASK-DECIDE** (as F-33 PMO-3-1, F-42): a double press, a retry after a 5xx or a network failure, and a reload after `effect_uncertain` are stopped only by the claim plus `expected_revision`. The backend must refuse a second decide at the same revision (409) and never apply a decision twice; please say whether E-TASK-DECIDE should take an `idempotency_key`.
- **The holds** (G-C-3): preparer NOT SET (W-4006) and inclusion rule NOT SET (W-4007) are sent as `state: setup_needed`, status "SETUP NEEDED" (`stopped`), a "Why it's held" facts row with "NOT SET", a `next` sentence, station 2 `stopped`, `tasks: []` and no step. Please confirm this shape, the station each key stops at, and the Setup link.
- **Cancel delivery while uncertain** (gaps :137): not built; the uncertain item sends `allowed_actions: ["reconcile"]` only and no `reconcile.resend`. What does cancelling an uncertain delivery do, and which state follows?
- **What a reconcile answer leads to** (assumptions in the mock): delivered with proof → `verified`; not delivered → `action_needed` "NOT DELIVERED · HELD" with no resend; can't tell → `waiting` "HELD". Please define the reconcile reply and the state after each outcome for an internal delivery.
- **Publishing and receipts** (G-C-7, gaps :136): is publishing automatic or a step, and who are the "RECEIPTS 2 of 2"? The verified figures strip is backend text, never counted.
- **Per-recipient reconcile** (G-C-5): the reconcile is one answer for the whole delivery. Please say whether each recipient is reconciled separately.
- **`steps[].verdict`** (G-C-1): the three verdicts are sent as `approve`, `return`, `reject` on steps with a `task_id`; any other value is not drawn (W-4011). Please confirm the field or name its replacement.
- **The basis audience** (G-56-9): the basis is `tasks[0].decision.basis` as one backend sentence ("…for management. It doesn't move any cash."); the page bolds and composes nothing.
- **Amounts**: the table is `table` columns of kind `money`, each cell `{amount: "<decimal string>", currency, unknown}`; Unknown has no amount. The page computes no closing, opening, total or variance and shortens nothing; "₦22.6M" on the boards is not drawn (no endpoint supplies a short amount; `money.display_short` is a proposal only if the design engineer wants one).
- **D-RETURN (open)**: a returned forecast re-reads to "RETURNED" (`person`) with no step; a rejected one is `cancelled`, "REJECTED" (`stopped`). No correction step is built. Does a return give the preparer a task?
- **Ask Chidi** (G-C-4): the `workspace.links[]` `assistant` link to `/assistant`, with no work-item context.
- **Held to later parts**: group rows and group review (part 2), Record actuals and matching (part 3, D-RECEIPT-ALLOCATION, D-DECISION-VARIANTS), Withdraw (`revoke`), Correct and resubmit, the Start work forecast drawer (F-47B).

## Added during F-45: ledger source recorded as a reference (19 Nov)

Screen: SCR-58 part 1 (investigating, observe, review, verified; `/work/W-4201..W-4204`), the ledger source LED-0052 "QuickBooks journal JE-7741 · October" on the line workspace (`line_key: "ledger_sources"`, `screen: "SCR-58"`), contract mock only (D-LINE-WORKSPACE proposed; nothing is posted, nothing is read from or sent to QuickBooks, no amount is shown). Fixtures W-4201..W-4213 and their sidecars are sample data (Bisi Ade, Chuka Eze, Chidi, JE-7741, the realm and the dates), all on case `C-LED-0052` (revision 4). Gap ids G-C-*, G-58-* are in [gaps-f-finance-workspaces.md](backend-handoff/gaps-f-finance-workspaces.md). The frame is F-33's and F-42's, reused: decide in place through `steps[].verdict` (G-C-1, G-C-2), buttons only from `tasks[].you_can_act`, no card for an `already_decided` task, and the observation through F-17's step form with F-31's step-evidence upload.

- **Three separate people (readiness question 1, G-58-4)**: the page has no rule about who captured, observed or reviews a source, and reads no `/me`. Please enforce for every ledger source that the capturer, the observer and the reviewer are three different people, in E-WORK-STEP `record_observation` (refuse the capturer) and in E-TASK-CLAIM/E-TASK-DECIDE (refuse the capturer and the observer). Today the mock shows it only as the backend's words: the observer's re-read has `cannot_act_reason: prepared_by_you` ("You prepared LED-0052 v1, so someone else must review it."), and the capturer sees the step with `disabled_reason` "You captured this source, so someone else must look it up." (W-4210). Which reason code? v7 has none for "took part" (a new code needs one `cannotActCopy` case in `src/features/decide/**`).
- **What Unknown or More than one does (G-58-3, readiness question 2)**: the mock serves `state: waiting`, status "CHECK HELD" (`stopped`), station 3 `stopped`, facts "What was found · UNKNOWN" and "Verification rules · NOT SET", a `next` sentence, no step and no task (W-4209; the W-4208 re-read). The page decides nothing from the answer chosen. Please say the real state, which station "Verification rules" (`finance.ledger_sources.verification`, NOT SET) holds, and who is told.
- **Reviewer not set** (`finance.ledger_sources.reviewer`, NOT SET): `state: setup_needed`, status "SETUP NEEDED" (`stopped`), station 4 `stopped`, a "Why it's held" facts row "Who reviews ledger sources · NOT SET", a `next` sentence, no task, no step and no reviewer name or role (W-4205). No Setup link is drawn (G-C-3). Please confirm the shape.
- **Verdicts (G-C-1)**: `steps[].verdict` with `approve` and `reject` only, one step each with `task_id`; reject needs a note (the mock refuses a blank one with 422). No Return and no Withdraw on a ledger review. No idempotency key on E-TASK-DECIDE (as F-33, F-42): a double press, a retry and a stale tab are stopped only by the claim plus `expected_revision`; please refuse a second decide at the same revision (409) and never apply one twice.
- **Claim on page load (question, as F-42)**: the review page sends one E-TASK-CLAIM when it opens, only when `you_can_act` is true. Does that lock other reviewers out? How is a claim released?
- **The observation step**: E-WORK-STEP `record_observation` with `inputs: {found: "found" | "not_found" | "unknown" | "more_than_one"}`, `evidence_ids: [<the proof's evidence_id>]` and an `idempotency_key`; field names `found` (a `choice`, required, nothing preselected) and `proof` (`evidence`, required). The key names, the four values and the field help ("Recording what you saw isn't an approval…") are proposals; the step's `consequence` names the independent reviewer in words only.
- **The proof (append-only)**: E-EVIDENCE-UPLOAD on `C-LED-0052` with `kind: "ledger_observation"` and the item's `case_revision`, sent before the step. The mock's grant is F-31's step-evidence rule (a kind named by an `evidence` field of a served item's step on that case), looser than real authorisation; it does not check `disabled_reason`, so a person refused the step could still upload to the case on the mock. The backend must grant the upload only to a person who may take that step, and must check that every `evidence_ids` entry was uploaded to this item's case. Which case does a ledger source's proof live on (F-47's start uses `C-FIN-LEDGER`)? "×" removes the file from this observation only; the uploaded proof stays on the case.
- **Verified is the backend's**: "VERIFIED" with "Posting performed NO", "Authenticity certified NO", "Completeness certified NO" and "Reference recorded YES · 14 NOV" are facts as returned; the page never derives them. A decide that answers `work_state: effect_uncertain` (W-4212) shows "CHECKING" (`uncertain`) and "result not confirmed".
- **Re-check (G-58-5)**: "A reference only. If the source changes later, a re-check reopens it." is sent as `workspace.next` (one line) on the verified state, so the frame draws it in the side column under "Next" (D-125, Option B), not as a `text` section; the trigger is not built.
- **Ask Chidi (G-C-4)**: the `workspace.links[]` `assistant` link to `/assistant`, with no work-item context. Chidi reads the file and its provenance only; please confirm the factory reads nothing from QuickBooks.
- **State and view names used** (please confirm): investigating `processing`/`investigating`; observe `action_needed`/`observe`; review `action_needed`/`review`; verified `verified`/`verified`; rejected `cancelled`/`rejected`; held after Unknown `waiting`/`check_held`; reviewer not set `setup_needed`/`setup_needed`; decide not confirmed `effect_uncertain`/`effect_uncertain`.
- **Held to part 2**: the duplicate refusal and its compare table (G-58-1; two amounts only the backend may supply and flag), "Correct" with `continues` (G-58-2, G-C-6), "Open LED-0049" (G-C-3), the rejected board, and the F-47 landing repoint (`WORK_IDS.ledger_sources` to W-4201, whichever of F-45 and F-47 merges second; F-47 merged first, so this is the coordinator's follow-up).

## Added during F-40: handover to Support (SCR-48, 19 Nov)

Screen: SCR-48 (`/work/W-3701..W-3711`, line workspace item HND-0048), contract mock only (D-LINE-WORKSPACE and D-RESPONSE-VIEW proposed). Nothing is sent to Support and nobody at Support receives or acknowledges anything; every "published", "received" and "acknowledged" is fixture text returned after the write and re-read. Gap ids G-48-* are in [gaps-d-delivery.md](backend-handoff/gaps-d-delivery.md) (lines 135-150).

- **The `support_handover` response variant**: `tasks[].response` with `variant: "support_handover"`. Fields the page reads: `responders[]` (`id`, `name`, `role`; the Support lead, who has no login), `actions[]` (`value`, `label`), `versions[]` (`id`, `label`, `sent_at`), `evidence_kind`, `intro`, `recorded` and `next[]`. The page offers only actions that carry a label.
- **"Support replied"**: drawn as name and role (Femi Ojo, Support lead) from `responders[]`, plus a structured date-time the PM enters, sent as `responded_at` in the E-RESPONSE body. The page does not compose either from text.
- **G-48-1 (mock only)**: the E-RESPONSE body carries a `gaps: string[]` field that is not in the v7 schema (marked PROPOSAL in `contract.ts`). The mock requires it when the action is `changes_requested` (422 `gaps`). A real backend may reject it until settled. Please settle the mapping Received = `approved`, Gaps found = `changes_requested`, and the list of gaps, each becoming an open `checklist` item with an id.
- **G-48-2**: "Publish to Support" is a mock step with `sends: true`. No Support recipient, channel, receipt word or uncertain-send recovery exists in the integration list. After an uncertain result the page offers only reconcile, never a resend.
- **HND-0048 `work_id`**: the Delivery tab's Handover row (`P-0101.json`) now carries `work_id: "W-3704"`, one added line. The row and the sub-nav's Handover link open the work item. Hypercare's W-3101 was already there.
- **`delivery.handover_review` is not set**: the Setup rule has no value. W-3702 is a hold: "Review needed?" reads Unknown (never "No"), there are no controls and no Publish. No review decision, approver or recipient is built.
- **Support never logs in**: the PM records Support's reply with the reply document as proof, and the record keeps the PM's name ("Recorded under your name"). Authority is only `tasks[].you_can_act`. Open question C (confirm the PM records it) and what closes a gap (a later "received, no gaps" reply on v2, or each gap) are still the backend's to answer.

## Added during F-37: RFP response requirements and answers (19 Nov)

Screen: SCR-26 (`/work/W-3401..W-3404`), the RFP response workspace on the line workspace, contract mock only (D-LINE-WORKSPACE proposed). Gap ids G-26-* are in [gaps-b-rfp-planning.md](backend-handoff/gaps-b-rfp-planning.md); the overlay is `frontend/mock/proposals/rfp-response.json`.

- **Step names** (the keys are the backend's to confirm): `accept`, `accept_selected`, `edit_accept`, `write_own`, `add_requirement`.
- **Mock overlay, not in the generated types**: `steps[].submit_label` (the words on the form's submit button) and `steps[].fields[].value` (the start value of a text, long text or choice field; G-26-3 asks the backend to define it for any field kind). Start values sit on the step, not the item.
- **`items[].team_key`** (reused from F-31) ties a row to a team.
- **The mock's 422 on `item_ids`**: for the RFP lines the mock refuses an item id that is not in the served item or does not list the step, with `fields: [{name: "item_ids"}]`. The backend must refuse the same way.
- **Open questions**:
  - G-26-1: which tabs are separate work items (`rfp.tabs[].work_id`) and which are views (`?view=<tab key>`).
  - G-26-2: the section read (filter, search, cursor) and a scope for "all matching".
  - G-26-5: the past-answer source, its grants, and where "that bid was won" comes from (an earlier E-RFP-OUTCOME). Not built on the page.
  - QA-3-1: the T-3401 record-input response (E-RESPONSE `team_input`) is not mocked.

## Added during F-49: log a received RFP (SCR-23, 19 Nov)

Screens: SCR-23 (desktop and phone), the "Log a received RFP" line in the Start work drawer. Contract mock only (D-RFP-INTAKE r1 and D-START-INTAKE r1 proposed; nothing released). Gap ids G-23-1 to G-23-6 are in [gaps-b-rfp-planning.md](backend-handoff/gaps-b-rfp-planning.md). No generated type changed. Spec conflicts were accepted as recommended under D-130 (design engineer, 19 Nov). Overlay schemas: `frontend/mock/proposals/rfp-intake.json`.

- **Order of writes**: one E-EVIDENCE-UPLOAD (`kind: "rfp_document"`) the moment the file is chosen, on the line's fixed case `C-RFP-INTAKE` (revision 5 in the mock); then one E-WORK-START per press with `intake.rfp_document` = the `evidence_id` and the `case_revision` the upload returned (6). The 201 answers `{work_id: "W-3351", state: "owner_needed"}`; the person lands on `/work/W-3351` and the RFP is Unassigned for F-36's assign panel.
- **Intake field names** (proposed, no source names them): `client`, `rfp_reference`, `rfp_document`, `received_at`, `submission_method` (`email`, `portal`, `by_hand`, `not_stated`), `submission_target`, `deadline_status` (`unknown`, `stated`, `not_stated`), `deadline_at`, `note`. Please confirm or rename.
- **G-23-1 new client**: the mock overlay `allow_new: true` on the `client` field (cookie `psl_mock_rfp=new_client` only) lets the picker end with "New client"; the page then sends `intake.client = {new: {name}}`. Does Start work create the client in the same transaction, or is there a separate clients write? No sentence about "the client register" is drawn, because only the backend can say it.
- **G-23-2 `show_when`**: mock overlay `show_when: {field, equals[]}` on an intake field (set on `submission_target` and `deadline_at`). The page draws the field only while the named field holds a listed value, and never sends a hidden field's value. Without it the page draws every field and the backend's 422 decides.
- **G-23-3 deadline state**: `deadline_status` is its own value (`unknown`, `stated`, `not_stated`); `deadline_at` goes only with `stated`. The page never sends a date for the other two and never fills one in. Mock 422 samples: a stated deadline with no date, "Enter the deadline the RFP states."; a date sent for another state.
- **G-23-5 which case**: the mock names one fixed case `C-RFP-INTAKE` for every RFP, so two people logging at once get a 409 stale revision (the page re-reads, keeps what was typed, uses a new key). Please say whether each RFP gets its own case and how the shared-revision conflict is avoided.
- **Duplicates** (readiness question 3): the page never checks. The mock refuses a repeated reference for the same client with a 422 `{name: "rfp_reference", message: "This RFP is already logged for that client."}` as a backend-stated sample. Please say whether the real answer is 409 or 422, and what makes two RFPs the same (client plus reference, or the file's sha256).
- **Received**: the `datetime` field is sent as an ISO instant from the browser's local time (`toISOString`); the page invents no zone rule and shows no "WAT". Please say whether the backend wants a fixed zone. The backend refuses a time in the future (mock 422: "Received can't be in the future.", shown under Received).
- **G-23-4 / G-23-6**: the submission method and target are sent and never shown back (`rfp.submission_plan` is later); upload size and type limits are the backend's 422, shown word for word.
- **Not drawn, because no source returns them**: the board's intro sentence, "Taken from page 2 of the RFP (proof attached)" and "Shown on the submission pack and used to send it". Each field's `help` comes from the line.
- **Mock only**: cookie `psl_mock_rfp=new_client`; ids `EV-SW-C-RFP-INTAKE-<n>`; fixtures `W-3351`, `options/client.json`, `lines.pmo_lead.json` (persona `pmo_lead`; its eight other lines are the `pm` copy and have no project options in the mock); a written start adds one Unassigned row to `pmo_lead`'s My work list until reset.

## Added during F-38: RFP submission, send for review and the reviewer's decision (19 Nov)

Screen: SCR-40 (`/work/W-3501..W-3509`), the RFP submission work item on the line workspace (`line_key: "rfp_submission"`), contract mock only (D-LINE-WORKSPACE proposed). **Nothing is submitted, emailed or delivered to Tamarind Loans or anyone outside PSL.** "Submitted", "Emailed", "Received", "TL-SUB-0091" and the receipt words are fixture text the page shows only after the re-read returns them; the company forms are a test template. Gap ids G-40-* are in [gaps-b-rfp-planning.md](backend-handoff/gaps-b-rfp-planning.md).

- **Step and verdict keys** (the backend confirms): `send_for_review` (no inputs) and `edit_cover_letter` (`inputs.cover_letter`) for the PM; `approve_submission`, `return_submission`, `reject_submission` for the document reviewer, each with `task_id` and `verdict` (F-33 G-C-1). The reviewer decides in place with E-TASK-CLAIM and E-TASK-DECIDE; a note is required for Return and Reject.
- **Priority 1, the real send (G-40-1, G-40-2):** the frontend never sends. On Approve the backend must enqueue the send of the approved version only (`decision.version.document_id` plus a `sha256` on the version), to the target the RFP recorded (`rfp.submission_plan`, G-23-4: email, portal or by hand), exactly once. E-TASK-DECIDE has no idempotency key (PMO-3-1, as F-33); the resend refusal and idempotency are the backend's. Until it exists a double press is stopped only by the claim and `expected_revision`.
- **Uncertain send:** if the approve answers `work_state: effect_uncertain`, the re-read must carry `reconcile` (`outcomes`, `evidence_kind`) and `allowed_actions: ["reconcile"]`, with no `resend`. The page then offers only the reconcile panel and no second send.
- **What `received` means (G-40-3):** a mail server accepting a message is not proof the client has it. The fixtures use "Their mail server accepted it … verified as sent" as sample text; the real words are the backend's, settled with PSL.
- **File size and content type (G-40-4):** E-DOCUMENT has no size or content type; "Open the full pack (PDF, 6.1 MB)" is a returned link label.
- **Submission record (G-40-9):** the record sent here must be the one `rfp_outcome.submission` (E-RFP-OUTCOME) reads, so "Record the outcome" shows its id and delivery.
- **Mock overlay, not in the generated types:** `workspace.steps[].verdict` and `workspace.links[]` (`assistant`, `document`), both reused; `steps[].fields[].value` as the start of a long_text field (G-26-3); `rfp.tabs[].work_id` on the Submission tab (G-26-1). `checklist` items carry `cite_label` ("FROM THE RFP, P.2"), which the typed contract already has. Proposed: the reviewer's read of W-3502 carries no `rfp` block (it is a decision page); `decision.recipient` ("Goes to …") is read on the Decide panel.
- **A step held by the backend** is returned with `disabled_reason` and drawn disabled with that reason (W-3508 "A part still uses a test template."; W-3507 "Not available yet" when the cover letter's text is not sent).
- **Held, for PSL:** may a pack with a test-template part be approved and sent (G-40-6); the "submit by" lead time (G-40-5); what Return and Reject do to the RFP (G-40-7, D-RETURN); whether the person who may submit for PSL (`rfp.submit`) is the document reviewer. D-COSTING-RULE and D-ALERT-PROVIDERS are open, so no real approval or email send can exist yet.
- **Page computes nothing:** the 20 MB check, the "submit by" date, days left and the approvals count are the backend's text ("all 3 approvals" follows D-APPROVAL-ORDER; the board still says 4). No price or amount appears on this screen.
- **Mock-only change outside the spec's lane:** `frontend/mock/documents.mjs` serves D-3501 version 1 (4 lines); without it E-DOCUMENT is 501 for the pack.

## Added during F-51: fixed asset schedule proof and cash forecast start (SCR-04 ppe and forecast, 20 Nov)

Screens: the four SCR-04 boards `SCR-04-{desktop,mobile}-{ppe,forecast}`, the "Fixed asset schedule" and "Cash forecast" lines in the Start work drawer (FE-M2A-PROOF part 2). Contract mock only (D-START-INTAKE r1 proposed; nothing released). No generated type changed. Spec conflicts 1 to 4 were accepted as recommended under D-130. Gap ids: G-SCR04P-9 and gaps-e question 3 in [gaps-e-finance-payroll.md](backend-handoff/gaps-e-finance-payroll.md).

- **Order of writes (fixed assets)**: one E-EVIDENCE-UPLOAD (`kind: "ppe_register"`) the moment the file is chosen, on the line's fixed case `C-FIN-PPE` (revision 4 in the mock); then one E-WORK-START per press with `intake.proof` = the `evidence_id`, optional `prior_schedule` and `accounting_note`, and the `case_revision` the last upload returned. The 201 answers `{work_id: "W-3901", state: "processing"}`.
- **Forecast**: one E-WORK-START, no upload, on the fixed case `C-FIN-FORECAST` (revision 2): `intake` = `scenario`, `as_of`, `months` (integer), `audience`. `sources` is a `display` field and is never sent. The 201 answers `{work_id: "W-4001", state: "processing"}`.
- **Who may start**: the mock serves both lines to the finance persona only (D-130). Please confirm who may start them; the page reads only `startable_lines` and E-LINES.
- **Fixed case and revision source** (gaps-e question 3): the mock names `C-FIN-PPE` and `C-FIN-FORECAST`; the backend may choose otherwise. `evidence_kind` `ppe_register` is a proposed name.
- **Option lists from data**: `prior_schedule` and `scenario` come from E-LINE-OPTIONS. "Accounting note" is an optional `choice` and "Audience" a required `choice` with `internal`, `management`, `group`. The mock's Accounting-note options ("Sample note A" to "D") are placeholders; the real list, and whether Group is offered while its rule is NOT SET, are the backend's.
- **Backend-stated 422 samples** (the page checks none): Months below 1 or above 12 or not a whole number, "Months must be between 1 and 12."; an unreadable As of, "As of must be a date."; an audience not in the list, "Choose one of the listed audiences."; no file, "Proof is required."; a proof id not issued on the case, "That proof isn't on this record. Add it again."
- **Held run**: where a rule such as `finance.cash_forecast.preparer` is NOT SET, start the work and answer 201 with a work item in `setup_needed`; the drawer never holds the form. Mock cookie `psl_mock_start_work=start_hold` makes every forecast start answer `W-4006` (F-43's "preparer not set" item).
- **Sources text**: the drawer shows the line's `display` value as sent ("All 3 accepted" in the fixture); the page never counts or says "accepted" itself. Please say where the real text comes from.
- **`next`** (G-SCR04P-9): neither line sends one; the boards draw no "What happens next".
- **Mock only**: cookie value `start_hold` (new); ids `EV-SW-C-FIN-PPE-<n>`; fixtures `options/prior_schedule.json`, `options/scenario.json`, the two lines in `lines.finance_lead.json`.
