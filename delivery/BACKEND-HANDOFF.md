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
