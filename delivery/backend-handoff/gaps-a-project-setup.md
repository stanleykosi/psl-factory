# Board-vs-contract gaps A: project screens, assistant, setup, sign-in (15 Nov 2026)

Scope: SCR-05, 08, 11, 12, 13 (delegation, roles, payroll fields), 17, 19, 21, 29, 30, 38, 39. All boards are on the main canvas (`design/canvas/project/`); none of these screens is on the Finance canvas. Contract read: `architecture/packages/v7` (openapi.json, endpoints.csv, model.json, delivery.md). All v7 decisions touching these screens are `proposed` or `open` (D-ASSISTANT-VIEW, D-PROJECT-TAB-ROWS, D-PEOPLE-VIEW, D-DELEGATION-VIEW, D-SETUP-RULES-VIEW proposed; D-SIGNIN, D-ADMIN-AUTHORITY, D-PAYROLL-VISIBILITY, D-COSTING-RULE, D-SPEECH-INPUT open). Read-only work, no permission refusals met.

Conventions: "tab bar" means the shared project tab bar (Journey, Milestones, Documents, Money, Registers, Actions) built in `frontend/src/features/projects/ProjectTabs.tsx`, fed by `E-PROJECT.tab_counts`. Tab pages themselves are not built. The project journey (SCR-07/SCR-22) is built; every project screen below links back to `/projects/{case_id}`.

Cross-cutting findings (apply to several screens, written once here, referenced below):
- X1. No operation records a milestone as complete (see SCR-19/38). The invoice line's `milestone` field lists only milestones "marked complete, with proof" (fixture `lines.pm.json`, `invoice.intake.milestone.help`), so completion has to exist before the invoice line can start.
- X2. `E-DOCUMENT` returns only `body_url`, so there is nothing structured to render, annotate or compare (SCR-08).
- X3. Create-style writes in the assistant (`E-CONVERSATION-NEW`, `E-MESSAGE`) have no `idempotency_key` while every other create has one.
- X4. Person records (`E-PEOPLE`) carry role and scope as two parallel string arrays, so "role X for project Y" cannot be paired (SCR-13 roles, SCR-21).
- X5. Several boards show a policy number or period as fixed copy (lock-out "3 tries / 15 minutes", reset link "30 minutes", invite link "72 hours", password "at least 12 characters"). These are not in the contract and are D-SIGNIN's to decide; the frontend must take them from the backend or not show them.

---

## SCR-05 · Assistant (default, thread, draft-started, cant, working; plus "Speak your request")
Task: FE-ASSISTANT (all states) and FE-ASSISTANT-SPEECH (speech) · Boards: 10 · Canvas: main · Gated by: D-SPEECH-INPUT (speech control only); D-AGENT-PROVIDER is open for real answers (synthetic provider meanwhile)
What the screen does: A signed-in person picks one of the agents they may talk to (Tola for PMO, Chidi for Finance, Zainab for HR), asks a question or asks for a draft, and watches the agent work. The agent answers from records the person can see; if it drafts something (for example an invoice), the person checks the draft and starts the normal work item from it. If the agent may not share something, it says why.
Proposed route: `/assistant` (list and home), `/assistant/[conversationId]` (thread); `?agent=` on home
Reads: E-ME GET /api/v1/me — fields used: name, assistant_agents; E-CONVERSATIONS GET /api/v1/assistant/conversations — items[].conversation_id, title, agent, status, status_line, updated_at, next_cursor, as_of; E-CONVERSATION GET /api/v1/assistant/conversations/{conversation_id} — agent, title, status, context.project, context.access, messages[].role, text, at, steps, step_details[].text/state/reference, handoff, sources, source_details[].kind/label/reference/restricted/link, cannot_reason, draft_work_id, draft.title/status_label/rows[].label/value/money/start/next/started; E-MENTION-OPTIONS GET /api/v1/assistant/mentions — items[].kind/id/label/hint, q, kind, cursor
Writes: E-CONVERSATION-NEW POST /api/v1/assistant/conversations — body: agent; guards: CSRF (no idempotency_key, see G-SCR05-3). E-MESSAGE POST .../messages — body: text, mentions[{kind,id}]; guards: CSRF (no idempotency_key, no expected_revision). Start from a draft: E-WORK-START POST /api/v1/work — body: line, case_id, case_revision, intake, idempotency_key taken from `draft.start`; guards: CSRF, idempotency_key, case_revision (409 if the case moved)
Agent work shown: Tola/Chidi/Zainab read records the person may see, show the steps they took ("3 STEPS · DONE", "WORKING · STEP 3 OF 5") with the record each step used, hand over to another agent when the request belongs there ("Tola passed this to Chidi"), and may produce a draft (invoice, SOW, planning packet). Human decision that follows: the person reads the draft and presses "Start this invoice"; real review and approval happen at the line's own stations (Finance Lead for the invoice). The agent never approves, sends or pays.
Covered by v7 as is: conversation list with status and status line; thread messages, typed steps with done/now/next and record reference; hand-off note; sources with restricted marker; "can't share" reason; side panel project and "Your access"; mention search; draft title, label/value rows with money (unknown allowed), "Next" line, start descriptor (line, case, revision, prefilled intake) and the started work; starting through the normal line (D-CONVERSATION-MODEL); polling every 5 s while working (D-UPDATES)
Gaps:
- G-SCR05-1 | draft-started: "Started INV-0415." and "Open the work item", and the thread list entry after start | v7 today: `draft.started{work_id, reference}` exists on the read, but `E-WORK-START` has no field that ties the new work item to the conversation, message or draft | change: add optional `source:{conversation_id, message_index|message_id}` to the E-WORK-START request; the backend writes `draft.started` and rejects a second start from the same draft with 409 (so a reload or second tab cannot start it twice). Messages also need a stable `message_id` on the E-CONVERSATION read | additive | blocking
- G-SCR05-2 | "Edit draft" (desktop thread) | v7 today: nothing; drafts are read-only rows | change: either drop the button by fidelity exception (draft is edited on the line's Start work drawer, prefilled from `draft.start`), or add an edit operation. Needs a product answer, so no proposal beyond that | additive | nice-to-have
- G-SCR05-3 | sending a message and starting a conversation | v7 today: E-CONVERSATION-NEW and E-MESSAGE have no idempotency_key; E-MESSAGE returns agent_run_id which nothing else can read | change: add `idempotency_key` (string) to both requests; a repeat key returns the first result. Drop `agent_run_id` from the frontend's needs unless a run read is added | additive | blocking (double submit creates a second agent run and cost)
- G-SCR05-4 | mention chips "@Harmattan Bank", "#Milestone 2", "#Minutes 06 Nov" under the thread and in the composer | v7 today: `mentions[].kind` is only project, work, document, person; the E-CONVERSATION message has no `mentions` echo | change: add kinds `milestone` and `meeting` (or `evidence`) to E-MENTION-OPTIONS and E-MESSAGE; add `messages[].mentions[{kind,id,label}]` on the read so chips survive a reload. Each mention is a pointer the backend re-checks against the person's access; it never widens access (INV-ACCESS) | additive | nice-to-have
- G-SCR05-5 | mobile "cant": buttons "Show staff-cost totals" and "Ask HR Lead for access" | v7 today: nothing; `cannot_reason` is text only | change: add `messages[].suggestions:[{label, kind: 'ask'|'request_access', text?}]`. "ask" prefills the composer. "request_access" needs an operation that notifies the HR Lead and grants nothing; it is a business decision (who receives an access request) and is not proposed here. Desktop board has no buttons, so the minimum is to drop both by fidelity exception | additive | nice-to-have
- G-SCR05-6 (added during F-48, 19 Nov) | a restricted record leaked through a checklist step | v7 today: `messages[].step_details[].reference` has no `restricted` flag, so CV-2404 drew "Read: ACCESS · payroll (restricted)" | change: mark a step reference `restricted: true` (the frontend then shows no reference), or never put a restricted record's label in a step reference. Until then the frontend hides a step reference whose words equal a restricted `source_details` label or reference (model.ts `stepsOf`); that word match is a stopgap (TECH-2-1), not a guarantee | additive | needed (privacy)
- G-SCR05-6 | agent home text: "Hi Tunde, I'm Tola. What should we get moving?", "I draft plans, SOWs…", placeholders per agent | v7 today: nothing; `/me.assistant_agents` is only a list of keys | change: either keep agent copy frontend-owned (three agents, fixed) or add `assistant_agents` as objects `{agent, role_label, hello?, can?}`. What an agent says it can do must match what the backend will do, so backend-owned is safer | additive (the key list stays) | nice-to-have
- G-SCR05-7 | working state: "You can leave; you'll be alerted." | v7 today: E-NOTIFICATIONS has no stated kind for "agent finished a conversation request" | change: confirm in `D-NOTIFY-MODEL` that a notification (with `work_id`/conversation reference) is created when a `working` conversation ends | additive | nice-to-have
- G-SCR05-8 | Speak your request (microphone button on every composer) | v7 today: nothing, D-SPEECH-INPUT is open (browser speech recognition may send audio to a third party) | change: none proposed. If PSL approves a path, the transcript is typed into the composer and sent through E-MESSAGE like typed text; speech adds no authority and nothing is sent without the person pressing send. If the answer is "omit", record a fidelity exception | n/a | blocking for FE-ASSISTANT-SPEECH only
Questions for the backend developer:
- Is the thread read polled or can the working state carry a `step_details` update per step? (D-UPDATES says 5 s polling; confirm the read is cheap while `status=working`.)
- Do conversation texts that mention restricted records (the "Musa Ibrahim salary" question) stay in the person's own list? The refusal reason is visible to the asker; confirm the question text itself is not exposed to anyone else and what retention applies (INV-RESTRICTED).
- When two people share a project, is a conversation strictly private to its creator? The read has no `owner`.
- `status` after a draft is started: stay `drafted` or move to a new `started`? The list board needs a words for it ("Started INV-0415").

---

## SCR-08 · Document review (default, returned)
Task: FE-DOCUMENT-REVIEW · Boards: 4 · Canvas: main · Gated by: none (D-DECISION-VARIANTS only if the document is a CEO/CTO decision; not drawn here)
What the screen does: The reviewer (PMO Lead) reads a drafted client document (a statement of work) on one page, sees what changed from the previous version and what the agent checked, then approves it or returns it with a note. After a return, the project manager sees who returned it, the note, and can ask the agent to draft the next version or edit it. Approving does not send it to the client.
Proposed route: `/projects/[caseId]/documents/[documentId]` with `?v=<version>` (crumb "LAGOON HEALTH / DOCUMENTS / SOW-0198"). Decision controls act on the human task of the document's work item.
Reads: E-DOCUMENT GET /api/v1/documents/{document_id}/versions/{version} — fields used today: document_id, version, title, status, template, test_template, body_url; E-PROJECT GET /api/v1/projects/{case_id} — title, pm, tab_counts (tab bar); E-WORK-ITEM GET /api/v1/work/{work_id} — tasks[].id/revision/you_can_act/cannot_act_reason, tasks[].decision.version/changes/prepared_by/chain, workspace.agent_note
Writes: E-TASK-CLAIM POST /api/v1/tasks/{task_id}/claim — body: expected_revision; E-TASK-DECIDE POST /api/v1/tasks/{task_id}/decision — body: expected_revision, verdict approve|return, note (needed for return); guards: CSRF, expected_revision, claim when the task needs it. Same writes as the built decide page (`/work/[id]/decide`).
Agent work shown: Tola drafts the version from the planning record and approved costing, flags points it could not settle ("the minutes say 'week 3'. Check which is right"), checks the template, the amounts against the approved costing and that every section is filled. In the returned state Tola offers to draft the next version from the reviewer's note. Human decision: PMO Lead approves or returns (approval records name and time); after a return, the PM decides whether to use Tola's v3 or edit it.
Covered by v7 as is: title, version number, status text, test-template tag, template name; the approve/return decision itself, the chain, the "changes since previous version" list and who prepared it (tasks[].decision) via the existing decide operations; documents tab row (`documents[]`: document_id, title, version, status, test_template, work_id)
Gaps:
- G-SCR08-1 | the numbered sections "1. Scope … 5. Out of scope" with their text | v7 today: only `body_url` (opaque URL, format unstated) | change: E-DOCUMENT gains `sections:[{key, heading, text, changed_since?:boolean}]` (plain text paragraphs, no HTML), and keeps `body_url` for download. State in the contract whether `body_url` needs the session | additive | blocking
- G-SCR08-2 | "Tola: the minutes say 'week 3'. Check which is right." inline in section 4; mobile "Tola flagged section 4" | v7 today: nothing | change: `sections[].notes:[{agent, text, cites?:[{label,reference,...}]}]`. Notes are agent text only; they never decide anything | additive | blocking (the review's point is this flag)
- G-SCR08-3 | Checks panel: "Uses the current template — TEST TEMPLATE v1", "Amounts match approved costing — Matches COST-0140 v2", "Every section filled — 5 of 5" | v7 today: nothing (only `template`, `test_template`) | change: `checks:[{key, label, status: done|held|blocked|unknown, detail?, cite?}]`, computed by the backend deterministically, not by the model. The amount check must say Unknown when costing is unknown, never "matches" by default (INV-UNKNOWN) | additive | blocking
- G-SCR08-4 | "Compare with v1", "Compare v1 and v2", "Changes since v1 are 2 sections; the version history keeps v1" | v7 today: nothing to list versions or compare; `tasks[].decision.changes` holds changed item strings only | change: E-DOCUMENT gains `versions:[{version, status, at, by?}]` and `compare_to?` is requested as `GET .../versions/{version}?compare=<v>` returning per-section `before`/`after` text. The simple form is `sections[].changed_since` plus reading two versions and diffing in the browser | additive | nice-to-have (the frontend can show changed sections without a diff)
- G-SCR08-5 | "Audience: Client · Lagoon Health", "Your review · PMO Lead", "Drafted by Tola…" | v7 today: nothing in E-DOCUMENT | change: `audience:{label}`, `review:{role_label, task_id?, work_id}`, `drafted_by:{agent, from:[string]}` | additive | blocking for work_id/task_id (the page cannot reach its decision without them); others nice-to-have
- G-SCR08-6 | crumb and tab bar (LAGOON HEALTH / DOCUMENTS / SOW-0198; Journey … Actions) | v7 today: E-DOCUMENT returns no case, no reference ("SOW-0198") | change: add `case_id`, `project_title`, `reference` | additive | blocking
- G-SCR08-7 | returned state: "Returned by Kemi Adebayo (PMO Lead) · 14:20 today", the quoted note, "Approval on v2 is not carried over" | v7 today: `chain.steps[]` gives status returned and decided_at; the note text is not on E-WORK-ITEM | change: `tasks[].decision.chain.steps[].note` (or `returned:{by, role, at, note}` on E-DOCUMENT). A return note is visible to the PM and PMO Lead, not to everyone with read access | additive | blocking
- G-SCR08-8 | "Ask Tola to draft v3" and "Edit as v3" | v7 today: no operation drafts or saves a new document version; no document write exists at all | change: (a) a workspace step `draft_next_version` on E-WORK-STEP (agent drafts v3, lands as a review again; the PM then goes through the normal approve), (b) either an edit write `POST /api/v1/documents/{id}/versions` body `{from_version, sections[], expected_revision, idempotency_key}` returning the new version, or "Edit as v3" is dropped by exception. Approval on v2 is not carried over: the backend must start a fresh review of v3 | additive | blocking for the returned state's two buttons; the default state is unaffected
Questions for the backend developer:
- Is the document review one human task on the SOW work item (as the decide page assumes) or a separate review record? That decides where `task_id` comes from.
- "Who reviews client documents" is a Setup rule (PMO Lead, v2) per SCR-13; confirm the decision reads that rule and a document prepared by the same person cannot be approved by them (`cannot_act_reason: prepared_by_you`).
- Where is the body stored and can it be large? Sections as JSON limits size; say if you want pagination for long documents.
- Sending the approved document to the client is a separate step on this line; which operation and screen carry it?

---

## SCR-11 · Registers: issues, changes, RFPs (default; empty named in screens.md but not drawn)
Task: FE-M3-PROJECT-TABS (registers) · Boards: 2 · Canvas: main · Gated by: D-PROJECT-TAB-ROWS (proposed)
What the screen does: Anyone on the project sees the issues, change requests, emergencies and RFPs of one project with who owns each, how severe, what state and how old. They open one to follow it up.
Proposed route: `/projects/[caseId]/registers?register=issues|changes|emergencies|rfps`; row opens the line workspace (SCR-30 for an issue, SCR-31 for a change)
Reads: E-PROJECT GET /api/v1/projects/{case_id} — tab_counts.registers, title, pm; E-PROJECT-TAB GET /api/v1/projects/{case_id}/registers?register=&q=&cursor=&limit= — registers[].register/reference/title/severity/owner{name,role,recorded_by_pm,outside_party}/state/age_seconds/work_id/sample, summary.registers.{issues,changes,emergencies,rfps}, next_cursor, as_of
Writes: none
Agent work shown: none on this screen (agent follow-up is on the issue detail).
Covered by v7 as is: sub-tabs and their counts (summary.registers); columns ISSUE, WHAT, SEVERITY, OWNER ("Engineering (recorded by PM)" = owner.recorded_by_pm), STATE, AGE (absent for a closed issue, shown as "—"); search (`q`); register selector; paging; row to work item through `work_id`; sample marking
Gaps:
- G-SCR11-1 | "Filter" control next to Search | v7 today: only `register` and `q` | change: add optional `severity`, `state`, `owner` query parameters (backend-defined option lists returned as `filters:[{key, options:[{value,label}]}]`). Search alone satisfies the screen if the filter is dropped | additive | nice-to-have
- G-SCR11-2 | columns for Changes, Emergencies and RFPs sub-tabs | v7 today: one row shape for all four registers; only the Issues columns are drawn | change: none needed if Changes use `title`, `state`, `owner`, `severity` the same way; the frontend must not invent columns the boards do not show. Ask design for the three other column sets, or confirm the same set | n/a | nice-to-have
- G-SCR11-3 | footer "Severity is set by the PM. Closing an issue needs QA and the PM; there is no separate approval." | v7 today: nothing (it states a rule) | change: none; copy is static and restates a source rule. Confirm with the backend that it is true before it ships, since the screen would otherwise assert authority it does not enforce | n/a | nice-to-have
- G-SCR11-4 | empty state (screens.md lists it, no board) | v7 today: `registers: []` | change: none; frontend builds the shared empty pattern (STATES board) | n/a | nice-to-have
Questions for the backend developer:
- Is `age_seconds` computed to the response time or stored at creation? Closed rows omit it.
- Does `state` come as display text (the boards show "Fix in testing", "Closed by QA and PM") with no enum? If the frontend needs to colour states, add `state_key`.

---

## SCR-12 · Report with drill-down (default, loading)
Task: FE-M3-REPORT · Boards: 2 · Canvas: main · Gated by: D-PROJECT-TAB-ROWS (proposed); no money rule is decided here
What the screen does: Finance and project people see a project's billing by contract stage: amount, invoice state and whether paid. Tapping an amount shows exactly which signed document, rule and record it comes from. Chidi can explain any figure.
Proposed route: `/projects/[caseId]/money` with `?figure=<id>`
Reads: E-PROJECT GET /api/v1/projects/{case_id} — title, tab_counts; E-PROJECT-TAB GET .../money — money[].position/stage/amount{amount,currency,unknown}/amount_note/invoice{reference,state,at}/invoice_status/paid{status,owed}/figure_id, summary.report_id; E-REPORT GET /api/v1/reports/{report_id} — title, agent, figures[].id/label/value/sources/source_details[]{label,reference,kind,document_id,work_id}
Writes: none (E-CONVERSATION-NEW for "Ask me", see G-SCR12-2)
Agent work shown: Chidi (Finance agent) explains any figure on request. Nothing is decided on this screen.
Covered by v7 as is: stage table with STAGE, AMOUNT (Unknown when unknown=true and amount_note "Not yet due · amount set at go-live"), INVOICE (reference, state, `invoice_status` text like "Awaiting Finance decision", `at` for "Verified 03 Nov"), PAID (paid.status "Finance tracks", owed); figures with sources and typed source details; loading state (frontend); "Every figure links to the record it came from. Unknown amounts are shown as Unknown, never as 0." (matches INV-UNKNOWN)
Gaps:
- G-SCR12-1 | "Where ₦4,250,000 comes from" with "Signed SOW v2, stage table, row 2 / SOW-0198 v2", "RULE · stage terms", "Milestone 2 completion … HB-M2" | v7 today: `figures[].source_details[]` has label, reference, kind (document|rule|record|evidence) and a link id, but a document link has no `version`, a rule link has no id, and a record link has no `case_id` | change: add `version` (document), `component`/`rule_version` (rule), `case_id` (record). Pure display fields | additive | nice-to-have
- G-SCR12-2 | "Chidi · Finance agent — I can explain any figure here. Ask me" | v7 today: E-CONVERSATION-NEW takes only `agent`; no way to open the conversation about a figure | change: add optional `context:{kind:'report_figure', report_id, figure_id}` to E-CONVERSATION-NEW (backend still checks the person's access to the report); or link to `/assistant?agent=chidi` and drop the context. The agent's explanation must come from the figure's own sources | additive | nice-to-have
- G-SCR12-3 | "Tap an amount to see where it comes from" (mobile) | v7 today: money rows carry `figure_id`, the report is a separate read | change: none; reads join money[].figure_id with figures[].id. State in the contract that a row with no `figure_id` has no drill-down and shows "No source recorded", not an empty panel | additive (docs) | nice-to-have
- G-SCR12-4 | row "Stage 4 · hypercare — Unknown" and invoice "—" | v7 today: covered (`amount.unknown`) | change: none. Flag only: the report must never show a computed total of stages while one is Unknown | n/a | nice-to-have
Questions for the backend developer:
- Is the E-REPORT figure for a stage the same number as the money row, or can they drift (cached report)? If they can, include `as_of` on E-REPORT figures.
- Who may read the money tab: the roles on the board are Finance Lead and others; confirm the 403/404 hides the figures from PMO if INV-ACCESS says so (a 404 should show no stage names).
- `paid.status: finance_tracks` reads "Finance tracks" on the board; confirm it means "paid state is tracked by Finance and not shown to this person" and not "unknown".

---

## SCR-19 · Mark a milestone complete (default)
Task: FE-MILESTONE-COMPLETE · Boards: 2 · Canvas: main · Gated by: none (FE-M2A-PROOF is a frontend dependency)
What the screen does: The project manager (PMO) confirms that a milestone from the signed statement of work is complete, with the proof already on record. This records the fact "complete" with their name; it is not invoicing. Chidi then drafts the invoice, which Finance reviews.
Proposed route: `/projects/[caseId]/milestones/[position]/complete` (opened from "Mark milestone 3 complete" on SCR-38)
Reads: E-PROJECT-TAB GET .../milestones — milestones[].position/name/contract_amount/completion{status,at,proof,evidence_id}; E-PROJECT GET — title; evidence file name and size (see G-SCR19-3)
Writes: none in v7. Needed: record the milestone completion (see G-SCR19-1); guards would be CSRF, idempotency_key, expected_revision (case revision). Uploading proof if it is not already on file: E-EVIDENCE-UPLOAD POST /api/v1/cases/{case_id}/evidence — kind, filename, content_base64, case_revision
Agent work shown: none before the press. After it, Chidi (invoice line) drafts the stage invoice from the signed SOW; the amount comes from the contract terms, not from this form. Human decisions that follow: Finance review and Finance Lead approval before anything goes to the client.
Covered by v7 as is: milestone name and number, source SOW stage ("From the signed SOW v2, stage 2") through `name`; completion date and proof text (completion.at, completion.proof); evidence upload to the case; the invoice line (E-LINES `invoice`) which then starts from a completed milestone
Gaps:
- G-SCR19-1 | "Mark complete" and "The milestone is recorded as complete, with your name and the proof" | v7 today: nothing records a milestone completion (X1). The invoice line cannot be the write because its `milestone` option lists only milestones already marked complete | change: new `POST /api/v1/projects/{case_id}/milestones/{milestone_id}/completion`, body `{case_revision, completed_on, evidence_id, confirmed:true, idempotency_key}` returning `{milestone_id, completion{status,at,by}, case_revision}`; then the invoice line start is offered on the same page (E-WORK-START `invoice`, intake project+milestone) or started automatically if PSL decides so (question). Alternative: a `milestone_completion` line in E-LINES with the same intake through E-WORK-START | additive | blocking
- G-SCR19-2 | milestone identity ("Milestone 2", mobile "HB-M2") | v7 today: milestones[] has `position` only | change: add `milestone_id` and `reference` (e.g. HB-M2) to the milestone row, plus `can_complete:boolean` and `cannot_complete_reason` (not_your_role, already_complete, previous_not_complete) so the button is backend-decided and not derived from /me roles | additive | blocking
- G-SCR19-3 | "Client UAT sign-off · recorded on REL-0077 / lagoon-uat-signoff.pdf · Uploaded · 240 KB / Recorded by Tunde Bello on 11 Nov with proof" | v7 today: completion carries `proof` text and `evidence_id` only | change: `completion.evidence:{evidence_id, kind, label, filename, size_bytes, uploaded_at, recorded_by{name}, record_reference}`; a release record "REL-0077" is a delivery-line record, so say which. Evidence is read through the case; a missing or restricted file is shown as Restricted | additive | blocking
- G-SCR19-4 | "Completed on 11 Nov 2026" (a date, not editable on the board) | v7 today: nothing says who sets it | change: decide in the write above: `completed_on` is supplied by the person with a default of the proof's recorded date, and must not be in the future (backend validation, 422 field `completed_on`). Never default to today silently | additive | nice-to-have
- G-SCR19-5 | "Chidi drafts the stage 2 invoice from the SOW terms. The amount comes from the contract, not from this form." | v7 today: E-WORK-START `invoice` line starts the draft; nothing says it starts on completion | change: the write returns `invoice_work_id` if it started the line, else the page offers "Start the invoice" (E-WORK-START). Needs PSL's yes/no | additive | nice-to-have
Questions for the backend developer:
- Is completion editable or revocable? Wrong completions need a correction path that preserves history; "PMO completes milestones; Finance handles invoices" means Finance must not be able to undo it.
- Who may mark complete: the PM of that project only or any PMO? The page should show `can_complete`, not guess.
- Should marking complete start the invoice line automatically (Chidi) or only offer it? Board copy implies automatic.
- Business rule check: does a part-complete or amended milestone (SCR-38 "changed") need a different path?

---

## SCR-29 · Project actions (default)
Task: FE-M3-PROJECT-TABS (actions) · Boards: 2 · Canvas: main · Gated by: D-PROJECT-TAB-ROWS (proposed)
What the screen does: The project team sees every action item from confirmed minutes: what, which meeting it came from, who owns it (or that nobody does), when it is due (or that the date is Unknown), and whether it is open, overdue or done.
Proposed route: `/projects/[caseId]/actions`
Reads: E-PROJECT GET — title, pm, route, tab_counts.actions; E-PROJECT-TAB GET .../actions — actions[].action_id/title/from{meeting,at}/owner{name,role,recorded_by_pm,outside_party}/due{date,unknown}/state/work_id, summary.actions.{total,overdue,without_owner}, next_cursor, as_of
Writes: none
Agent work shown: none on this screen (actions are created from confirmed minutes on the minutes line).
Covered by v7 as is: header counts "9 ACTIONS · 3 OVERDUE · 1 WITHOUT OWNER" (summary.actions); columns ACTION, FROM (meeting and date), OWNER ("No owner" when owner absent; "Client · Lagoon Health" via outside_party; "(recorded by PM)"), DUE ("Unknown" via due.unknown), STATE (open, overdue, done); `work_id` link to the minutes/work item
Gaps:
- G-SCR29-1 | "Filter" control | v7 today: only `q`, `register`, `cursor`, `limit` on the tab read | change: add `state` and `owner` filters (or `owner=none`), or drop the control. Summary counts are already enough to show the three buckets | additive | nice-to-have
- G-SCR29-2 | "Changing an owner or due date is recorded with your name." | v7 today: nothing edits an action; no edit control is drawn | change: none proposed; the sentence implies an edit that is not on the board. Ask design whether it stays; if it does, an action-update operation with expected_revision and reason is needed | additive | nice-to-have
- G-SCR29-3 | "Project actions" header line "PM Tunde Bello · Route A from RFP-0031" | v7 today: `pm` is on E-PROJECT; `route` exists; "from RFP-0031" is not | change: `route` string includes the RFP reference or add `source:{kind:'rfp', reference}` | additive | nice-to-have
Questions for the backend developer:
- `done` actions: does "done" need evidence or just the owner's word? The state is shown as fact; confirm who sets it (the minutes line).
- Action owners that are outside parties (client) have no login: confirm `recorded_by_pm` on those rows is how the PM records their replies.

---

## SCR-30 · Issue detail (default, overdue, no-owner, verified)
Task: FE-ISSUE · Boards: 8 · Canvas: main · Gated by: none
What the screen does: Anyone following an issue sees what it is (severity, state, owner, age, what it blocks), what has happened so far, and the agent's chasing of the owner. The person recording for the owner posts an acknowledge/started/progress update. If the owner has not answered, the PM records a reply or escalates; if there is no owner the PM sets one; when the follow-up is verified the issue still has to be closed in the issue register by QA and the PM.
Proposed route: work item line workspace: line key `issue_followup` (Start work line already in E-LINES); reached from the registers row `work_id`
Reads: E-WORK-ITEM GET /api/v1/work/{work_id} — fields used: title, reference, state, revision, workspace.{line_key, screen, view, title, status{label,tone}, byline, context.crumbs, agent_note, sections[], steps[], revision}, assign.{candidates, note_required}; E-PROJECT GET (tab bar, tab_counts)
Writes: E-WORK-STEP POST /api/v1/work/{work_id}/steps — body: expected_revision (workspace.revision), step key, inputs, note, idempotency_key; guards: CSRF, expected_revision, idempotency_key. E-WORK-ASSIGN POST .../assignment — body: expected_revision, person_id, note (no-owner state)
Agent work shown: Tola investigated (found 14 failed logins, all Android 9 or older), asked the owner, sent a reminder, and says when it will remind again ("I'll remind the owner if there's no update by 13 Nov"). Human decisions: the PM records the owner's update or reply, raises an escalation, sets the owner; closing the issue is outside this screen (QA and the PM, in the register).
Covered by v7 as is (through the shared workspace block, F-17): header status and tone (FIX IN TESTING, NO RESPONSE · 3 DAYS, OWNER NEEDED, FOLLOW-UP VERIFIED); facts OWNER, RAISED, AGE, BLOCKS; "What has happened" as a `timeline`; "Chasing" (asked, reminder sent, escalate by) as a `timeline` or `checklist` with `at`; the owner-update step "Owner follow-up" as a step with fields `update_type` (choice) and `update` (long_text); agent note; "Next" lines; severity as `severity`; sample marking; tab bar
Gaps:
- G-SCR30-1 | "Raise an escalation" (overdue state) | v7 today: a step can only post to E-WORK-STEP or decide a task; no step opens another line's Start work with prefill. The escalation line exists (`escalation`, intake project + from_issue + escalate_to) | change: add `steps[].starts_line:{line_key, prefill:{<field>: <option value>}}`; the frontend opens the Start work drawer for that line prefilled and the backend still validates it (E-WORK-START). Without it the page can only link to Start work | additive | blocking
- G-SCR30-2 | "Open the issue register" (verified), "Set an owner in the issue register" (no-owner) | v7 today: nothing links out of a workspace except through section cites; `context.crumbs` values are not links by contract | change: add `workspace.links:[{label, kind:'register'|'work'|'project', case_id?, register?, work_id?}]` built only from ids | additive | nice-to-have
- G-SCR30-3 | "Set an owner" and the owner "Engineering (recorded by PM)" | v7 today: E-WORK-ASSIGN takes a `person_id` of someone with a login (assign.candidates[].person_id); the owners on the board are teams and outside parties with no login | change: allow `owner` to be a team or outside party: add to E-WORK-ASSIGN either `owner:{kind:'team'|'outside_party', name}` or a step `set_owner` with a `choice` field whose options the backend supplies. The write is recorded as "recorded by PM". Without it only logged-in staff can be owners, which contradicts the 13 Nov decision that Engineering, QA, Security and clients have no login | additive | blocking for the no-owner state
- G-SCR30-4 | "Record a reply" (overdue) | v7 today: could be a workspace step (long_text `reply`, optional `evidence`); E-RESPONSE is for tasks with responders | change: confirm it is a step on E-WORK-STEP; no new operation | additive (confirm) | nice-to-have
- G-SCR30-5 | "Reminder sent 11 Nov 09:00" and "Asked the owner 09 Nov 18:05" | v7 today: recipients `receipt` enum exists; a reminder to Engineering (no login) goes by an unnamed channel | change: none for display. Flag: a reminder is an outside effect; if the send result is unknown the section must show `receipt: uncertain` and `allowed_actions: reconcile` before resend. Name the channel in `channel` | n/a | nice-to-have
- G-SCR30-6 | header differences between boards (default has no tab bar and crumb "ISSUES"; the other three have the tab bar and crumb "REGISTERS / ISSUES") | v7 today: `context.crumbs` carries either | change: none in the contract; ask design to settle one header | n/a | nice-to-have
Questions for the backend developer:
- The default board's "Owner follow-up" is posted by whom? The note under it says the owner can acknowledge, start and report progress (backend `issue.work`), but the owner has no login, so the PM records it. Confirm the update shows "recorded by PM".
- Does severity or state ever change through a step on this screen? The board says no (register only); confirm the steps list contains only acknowledge/started/progress, record reply and set owner.
- Is the work item (E-WORK-ITEM) one per issue, with `reference` = ISS-xxxx?

---

## SCR-38 · Project milestones (default, changed)
Task: FE-M3-PROJECT-TABS (milestones) · Boards: 4 · Canvas: main · Gated by: D-PROJECT-TAB-ROWS (proposed); the change amount is an open fact, not a decision
What the screen does: The project team sees the milestones of the signed statement of work: contract amount, whether completed and with what proof, the invoice and whether it was paid. Each is a separate fact. After a change request adds work to a milestone, the board shows the change next to the milestone and says its amount is Unknown until a signed amendment exists.
Proposed route: `/projects/[caseId]/milestones`
Reads: E-PROJECT GET — title, pm, route, tab_counts.milestones; E-PROJECT-TAB GET .../milestones — milestones[].position/name/contract_amount{amount,currency,unknown}/amount_note/completion{status,at,proof,evidence_id}/invoice{reference,title,state,work_id,at}/paid{status,owed}/changes[]{reference,title,amount,work_id}, as_of
Writes: link to SCR-19 for "Mark milestone 3 complete" (write: see SCR-19)
Agent work shown: none on this screen.
Covered by v7 as is: columns MILESTONE, CONTRACT AMOUNT (Unknown with amount_note "amount set at go-live"), COMPLETION ("Done 27 Oct · proof", "Not yet"), INVOICE (reference and state), PAID ("Part paid · ₦500,000.00 owed", "—"), CHANGES ("CR-0031 · SMS reminders" with its own amount, unknown allowed); the sentence that completion, invoice and payment are separate facts; amounts never summed when one is Unknown
Gaps:
- G-SCR38-1 | "INV-0412 · awaiting Finance decision" (invoice cell text) | v7 today: `milestones[].invoice` has `state` (enum) but no human text; the money tab row has `invoice_status` | change: add `invoice.status_label` to the milestone row (same as `invoice_status` on money rows) | additive | blocking (enum alone cannot say "awaiting Finance decision" vs "awaiting review")
- G-SCR38-2 | "Mark milestone 3 complete" button | v7 today: no per-milestone permission or id (see G-SCR19-2) | change: `milestones[].can_complete`, `cannot_complete_reason`, `milestone_id` | additive | blocking
- G-SCR38-3 | changed board: "₦4,250,000.00 + the change · change amount Unknown until a SOW amendment is signed" | v7 today: `contract_amount` is the original, `changes[].amount` the change (unknown allowed). No signal that the amount is "to be amended" | change: `contract_amount_note` or `changes[].amount_note` ("Unknown until a SOW amendment with it is signed"); backend text so the frontend does not decide when an amendment exists. The sum of original and change must not be computed when the change is Unknown | additive | nice-to-have
- G-SCR38-4 | changed board has CHANGES column instead of INVOICE and PAID | v7 today: both are in the same row | change: none; frontend decides columns per state (show CHANGES when any row has `changes`). Confirm with design that the default board's INVOICE/PAID columns stay when a change exists | n/a | nice-to-have
Questions for the backend developer:
- Is the contract amount read from the signed SOW only and never edited? Changes never rewrite it. Confirm the "amendment signed" event is what adds a new amount.
- `paid.status` values: `finance_tracks` vs `unknown` vs `not_due`: confirm which one the board's "—" maps to.

---

## SCR-13 (delegation) · Setup: delegation (default; mobile delegation list)
Task: FE-SETUP-DELEGATION · Boards: 2 · Canvas: main · Gated by: none (D-DELEGATION-VIEW proposed)
What the screen does: A person with authority to set delegation sees current and scheduled delegations (from, to, dates, reason, state) and adds one so that a colleague with the same role can act while they are away. A delegate decides under their own name and gains no authority they did not already have.
Proposed route: `/setup/delegation`
Reads: E-DELEGATIONS GET /api/v1/setup/delegations — items[].delegation_id/from/delegate/authority/starts/ends/reason/status/can_change/revision, authorities[], delegate_options[], revision, next_cursor, as_of; E-PEOPLE (tab counts "Roles 2") ; E-SETUP-RULES not_set_count ("Rules 8")
Writes: E-DELEGATION PUT /api/v1/setup/delegation — body: expected_revision, delegate, starts, ends, authority, reason; guards: CSRF, expected_revision
Agent work shown: none.
Covered by v7 as is: table FROM (name and role), TO, DATES, REASON, STATE (scheduled/active/ended, board UPCOMING/ENDED); form fields Dates and Reason; "Add delegation"; delegate options (backend-limited); 422 messages
Gaps:
- G-SCR13A-1 | form field "From: Kemi Adebayo · PMO Lead ▾" (an admin chooses who is delegating) | v7 today: E-DELEGATION has `delegate` only; the delegating person is implicitly the caller | change: add `from_person_id` (optional; defaults to the caller; allowed only if the caller can act for them) and return `from` options in E-DELEGATIONS (`from_options:[{person_id,name,role}]`) | additive | blocking (the sample persona is Admin and the board lists Kemi's and Ada's delegations)
- G-SCR13A-2 | "To: Femi Ade · PMO Lead ▾ — Only people who already hold the same role are listed" | v7 today: `delegate_options` is one list, not tied to the chosen From | change: `delegate_options[].for_person_id` (or `GET /setup/delegations/options?from=`), so the list narrows when From changes | additive | blocking
- G-SCR13A-3 | no end / cancel | v7 today: no way to end a scheduled delegation early or edit one (rows carry `can_change`, `revision`) | change: `DELETE`/`POST /setup/delegations/{delegation_id}/end` with expected_revision, or confirm "ended" delegations are append-only and no change control is drawn | additive | nice-to-have
- G-SCR13A-4 | E-DELEGATION returns only `{revision}` | v7 today: no `delegation_id` back | change: return `{delegation_id, revision}` | additive | nice-to-have
- G-SCR13A-5 | "Delegating can't give anyone authority they don't already have." | v7 today: rule text; `authorities[]` limits the type | change: none; backend must enforce that `authority` is within the delegator's own authority, and that a delegate cannot approve their own prepared item. Confirm | n/a | nice-to-have
- G-SCR13A-6 | tab strip counts "Roles 2 | Rules 8" and which tabs a person sees (Costing rule, Delegation, Payroll visibility, Staff accounts, Templates) | v7 today: counts come from separate reads; no list of tabs the person may open | change: `/me` `destinations` is only `setup`; add `setup_tabs:[{key,count?}]` to E-ME or one E-SETUP-SUMMARY | additive | nice-to-have
Questions for the backend developer:
- Can a person delegate roles scoped to a project, or only whole roles? The board shows role only.
- When a delegation ends, do tasks the delegate claimed return to the owner?

---

## SCR-13 (roles) · Setup: roles (default, permission, validation)
Task: FE-SETUP-ROLES (with SCR-21) · Boards: 6 (default, permission, validation, desktop and mobile) · Canvas: main · Gated by: D-ADMIN-AUTHORITY (open: who holds Admin and who may assign roles)
What the screen does: Shows which roles have a holder and which are missing (and how much work is held waiting for them). A person who may change roles assigns someone and releases the held work. Everyone else sees the same table as view-only. If the assignment is invalid, the screen says exactly why.
Proposed route: `/setup/roles`
Reads: E-PEOPLE GET /api/v1/setup/people — items[].person_id/person/roles/scopes/state/can_change/revision, roles_missing[]{role,label,held_work}, role_options[]; E-SETUP-RULES roles_missing_count
Writes: E-PERSON-ROLES PUT /api/v1/setup/people/{person_id}/roles — body: expected_revision, roles[{role,scope}], reason, resume_held; guards: CSRF, expected_revision (the person's `revision`). Delegation part of the validation board: E-DELEGATION (see above)
Agent work shown: none.
Covered by v7 as is: missing roles with `held_work` ("HOLDING 1 ITEM"); role options; per-person can_change (view-only board = every item can_change false); optional `reason`; `resume_held` ("Assign and resume held work"); 422 `fields[]` for "Bisi holds Finance, not Finance Lead"
Gaps:
- G-SCR13B-1 | roles table "Finance Lead / Lagoon Health · approves invoices / Nobody yet / HOLDING 1 ITEM" (role, scope, holder, status) | v7 today: E-PEOPLE returns people with `roles` and `scopes` as parallel string arrays (X4); `roles_missing` has role, label, held_work but no scope or description | change: per person `role_grants:[{role, scope?, label, scope_label}]` and `roles_missing[].scope`, `roles_missing[].description` ("approves invoices"); a `holders:[{role, scope, person_id, name}]` view or let the frontend derive it from role_grants | additive | blocking
- G-SCR13B-2 | "Design Lead — Role not set up — HOLDING 1 ITEM" | v7 today: a role missing from `role_options` has nothing to assign; "Design Lead" is not in the invite role list ("PMO, PMO Lead, Finance, Finance Lead, HR, HR Lead, CEO, CTO") | change: none by the frontend. Ask PSL whether Design Lead is a role (if yes it needs adding to role_options; if no, the board row is wrong). State is `roles_missing[].configured:false` if it is a known role with no setup | n/a | nice-to-have
- G-SCR13B-3 | Person dropdown "Ada Okafor · Finance Lead / Bisi Adeyemi · Finance" and "Only someone who already holds the Finance Lead role can be assigned" | v7 today: nothing lists eligible people per missing role; the 422 happens after the choice | change: `roles_missing[].candidates:[{person_id,name,role,eligible:boolean,reason?}]` composed by the backend (eligibility is the backend's rule, not the frontend's) | additive | blocking
- G-SCR13B-4 | "Starts" date (default board) | v7 today: E-PERSON-ROLES has no `starts` | change: add optional `starts` (date). Without it the assignment is immediate; say which | additive | nice-to-have
- G-SCR13B-5 | validation board: a single "Save" covering Role/Person and "Delegate while away … Ends" | v7 today: two operations (E-PERSON-ROLES and E-DELEGATION), not atomic | change: either send them as two calls and surface each result separately, or add `delegation:{delegate,starts,ends}` to E-PERSON-ROLES in one transaction. Failure of the second must not leave the first half-applied silently | additive | nice-to-have
- G-SCR13B-6 | "Recorded with your name and the time. Previous assignments stay in the history." | v7 today: no read of the history | change: `GET /setup/people/{person_id}/role-history` (or `history` array on the people item) | additive | nice-to-have
- G-SCR13B-7 | permission board: PMO sees the whole roles table including who holds each role | v7 today: E-PEOPLE items also carry email, last_signed_in_at, open_items (D-PEOPLE-VIEW) | change: return those fields only when `can_change` is true (INV-ACCESS, the view-only user sees role, scope and holder only). State it in the schema description | additive | blocking (privacy)
- G-SCR13B-8 | PUT semantics | v7 today: `PUT .../roles` replaces the roles array | change: say whether the array is the full set (removing roles the client forgot) or additions only; the frontend must send the person's existing roles back. Prefer `add`/`remove` arrays | breaking if changed after release; settle now | blocking
Questions for the backend developer:
- Who may assign (D-ADMIN-AUTHORITY is open)? Until it is decided the page must show `can_change:false` for everyone; confirm the contract returns that, not an Admin guess.
- Admin confers no approval authority: confirm assigning a role does not let the admin act in it (board copy "Admins can't approve invoices just by being admins").
- What does "resume held work" do for the items held? Which state do they return to, and is each resumption logged against the assigner?

---

## SCR-13 (fields) · Setup: payroll field visibility (default; mobile)
Task: FE-SETUP-PAYROLL-FIELDS · Boards: 2 · Canvas: main · Gated by: D-PAYROLL-VISIBILITY (open)
What the screen does: The HR Lead sees which payroll staff fields Finance may see (staff ID, business unit, gross pay, deductions, bank account, home address, date of birth) with a reason for each, changes them, and saves a new dated version. Finance always sees business-unit totals only.
Proposed route: `/setup/payroll-visibility`
Reads: E-SETUP-RULES GET /api/v1/setup/rules?area=payroll_visibility — items[].component/name/set/revision/display_value/effective_from/can_change/restricted/editor/used_by
Writes: E-SETUP-RULE-SAVE PUT /api/v1/setup/rules/{component} — body: expected_revision, value, starts, reason, evidence_id; guards: CSRF, expected_revision (0 for first version)
Agent work shown: none.
Covered by v7 as is: a list of rules with a current display value; `can_change` per rule; `starts`, `reason` on the save; versioned history ("Version 2 has been active since 01 Oct")
Gaps:
- G-SCR13C-1 | rows "Staff ID — Visible", "Gross pay — Hidden", with toggles | v7 today: the editor kinds are `role_set` and `read_only` only (D-SETUP-RULES-VIEW); no yes/no per field. D-PAYROLL-VISIBILITY proposes one rule with a role_set | change: a third editor kind `toggle` (options true/false) or a `field_visibility` editor `{fields:[{field, label, visible, why}]}` with its own value shape. Which fields are configurable is for PSL (open decision) | additive | blocking
- G-SCR13C-2 | column "WHY" ("Needed to match payroll lines", "Finance sees BU totals only") | v7 today: no note on a rule item | change: `items[].note` or `fields[].why` | additive | blocking if the toggle editor is chosen
- G-SCR13C-3 | one "Save version 3" for all fields | v7 today: E-SETUP-RULE-SAVE saves one `component` | change: one component `payroll_visibility` with a `value` map of all fields, saved once as a single version (preferred); or per-field rules with no joint version | additive | blocking
- G-SCR13C-4 | "October's payroll keeps using version 2" | v7 today: item carries `effective_from` only | change: the backend pins the version a payroll run used; expose `used_by_runs` or a plain note. Version history list of earlier versions (`versions:[{n, effective_from, reason?}]`) is not in the rules read | additive | nice-to-have
- G-SCR13C-5 | board shows restricted payroll fields as names only (Gross pay, Bank account…) | v7 today: `restricted:true` on a rule hides its value | change: none. Flag INV-RESTRICTED: this screen carries the names of restricted fields but never values; no payroll data is on this page. The backend still enforces field-level payroll access whatever is configured | n/a | nice-to-have
- G-SCR13C-6 | "Only the HR Lead can change this" | v7 today: `can_change` per item | change: none; the page shows only what `can_change` returns, and never infers HR Lead from `/me` | n/a | nice-to-have
Questions for the backend developer:
- Who may change visibility is D-PAYROLL-VISIBILITY (open). Until then every item should return `can_change:false`; confirm.
- Does turning a field on for Finance affect past runs? The board says no; confirm that is enforced by version pinning.

---

## SCR-17 · Sign in (default, error, reset, setup)
Task: FE-SIGNIN · Boards: 8 · Canvas: main · Gated by: D-SIGNIN (open; no sign-in endpoint is proposed in v7)
What the screen does: A staff member signs in with work email and password, can ask for a reset link, and an invited person sets up their account (password and optional WhatsApp number for alerts) from the link in their invitation. An error says the details don't match without saying whether the account exists.
Proposed route: `/sign-in`, `/sign-in/reset`, `/sign-in/setup?token=` (names only; the shape belongs to D-SIGNIN)
Reads: none in v7 (E-ME 401 = signed out). For the setup state: the invitation (name, roles, projects) needs a read (G-SCR17-3)
Writes: none in v7. Needed: sign in, sign out, request reset, set new password, finish setup (G-SCR17-1). Guards: CSRF before a session exists (D-AUTH keeps the Django session cookie with a CSRF header; E-ME returns `csrf_token` only after sign-in)
Agent work shown: none.
Covered by v7 as is: 401 on every operation as the signed-out signal; session cookie + CSRF (D-AUTH); alert-channel settings after sign-in (E-ALERT-PREFS-READ/PUT carry `whatsapp.masked_number`, `verified`)
Gaps:
- G-SCR17-1 | the whole screen: "Sign in", "Send reset link", "Finish setup" | v7 today: nothing (D-SIGNIN open: either session endpoints under `/api/v1/session` or styled Django pages) | change: none proposed by the frontend. The backend developer chooses. Minimum surface to decide: how a CSRF token is obtained before sign-in, the sign-in response and error shape, sign-out (SCR-15 account menu), reset request and reset completion, invite acceptance | additive | blocking
- G-SCR17-2 | "You'll go straight to INV-0412, waiting for your review." (shown to a not-yet-signed-in visitor; on desktop and phone) | v7 today: nothing; it reveals a record reference and its state before authentication | change: board change request, not a contract change. Without a session no record name or state may appear (INV-ACCESS). Replace with generic "You'll go straight to the item you opened" or show it only after sign-in | breaking for the board | blocking
- G-SCR17-3 | setup state: "Welcome, Sola. You've been given PMO for Ojo Foods and Kora Logistics." and prefilled email | v7 today: nothing reads an invitation | change: `GET /api/v1/invitations/{token}` returning `{name, email, roles[{role,scope_label}], expires_at}` for an unexpired token only; an expired or used token answers one generic message | additive | blocking (once D-SIGNIN decides)
- G-SCR17-4 | "3 tries left before sign-in pauses for 15 minutes", "link that works for 30 minutes", "At least 12 characters", "It works for 72 hours" (invite, SCR-21) | v7 today: no policy values anywhere (X5) | change: these are policy values and are not invented. The backend returns the numbers (error body `attempts_left`, `pause_minutes`; reset `valid_minutes`; password `min_length`) or the frontend shows no number | additive | blocking for the error board's number
- G-SCR17-5 | "WhatsApp number for alerts (optional) … We'll send a code to check it" | v7 today: alert preferences read `whatsapp{masked_number, verified}` but nothing to add a number or confirm a code | change: `POST /api/v1/me/whatsapp` (number) and `POST /api/v1/me/whatsapp/verify` (code), each guarded by CSRF; sending a code is an outside effect to be reconciled, not retried blindly. Optional, so setup can finish without it | additive | nice-to-have
- G-SCR17-6 | "Keep me signed in" / "Keep me signed in on this phone" | v7 today: nothing (D-AUTH: Django session) | change: backend states session lifetime for each choice; no value invented here | additive | nice-to-have
- G-SCR17-7 | reset reply "It won't say whether the account exists" | v7 today: nothing | change: the request always answers the same message and timing; no body difference. Backend rule, must be tested | n/a | blocking (security)
- G-SCR17-8 | "Only PMO, Finance, HR and leadership roles have accounts. Ask your admin if you need one." (phone) | v7 today: copy | change: none; note the desktop invite board says PMO, PMO Lead, Finance, Finance Lead, HR, HR Lead, CEO, CTO. Keep one wording | n/a | nice-to-have
Questions for the backend developer:
- Are sign-in and reset served by Django pages or by new JSON endpoints? This changes whether Next.js renders SCR-17 at all (route, redirects, CSRF).
- What does the frontend send as `next` after sign-in, and how is it validated (no open redirects)?
- What is the lock-out rule (attempts, pause) and is it per account or per address? Neither number is decided here.
- Does invite acceptance consume the token on first view or on submit?

---

## SCR-21 · Staff accounts (default, invite, deactivate)
Task: FE-SETUP-ROLES (with SCR-13 roles) · Boards: 6 · Canvas: main · Gated by: D-ADMIN-AUTHORITY (open); invite also needs D-SIGNIN
What the screen does: The person allowed to manage accounts sees everyone who has an account with their roles, whether the account is active, invited or deactivated, and when they last signed in. They invite a new person with named roles, edit roles, resend an invitation, or deactivate someone and move that person's open work to colleagues who hold the same role.
Proposed route: `/setup/staff`, `/setup/staff/invite`, `/setup/staff/[personId]/deactivate`
Reads: E-PEOPLE GET /api/v1/setup/people — items[].person/person_id/email/roles/scopes/state/active/last_signed_in_at/open_items/can_change/revision, roles_missing, role_options[]{role,label,scope_needed}, next_cursor, as_of
Writes: E-INVITE POST /api/v1/setup/people/invitations — body: name, email, roles[{role,scope}], idempotency_key; E-PERSON-ROLES PUT .../roles (Edit roles); E-DEACTIVATE POST .../deactivation — body: expected_revision, reassign[{work_id,person_id}], reason; guards: CSRF, expected_revision, idempotency_key (invite)
Agent work shown: none.
Covered by v7 as is: list with name, email, roles, scopes, account state, last sign-in; invite name/email/roles; role options; reason on deactivation; reassign by work item; "If no one is chosen, it shows Owner needed" (reassign is optional); `open_items` count; 422 fields
Gaps:
- G-SCR21-1 | "3 open items move to someone else": rows "Harmattan Bank · go-live report — Started by Kunle — Move to: Tunde Bello · PMO ▾", "Kunle is to record it" | v7 today: only the count `open_items`; E-DEACTIVATE takes work_ids but nothing lists them or the people who may take each | change: `GET /api/v1/setup/people/{person_id}/open-items` returning `[{work_id, title, project, part, candidates:[{person_id,name,role}]}]` where candidates are the people holding the same role on that project (the board states the rule: "Work moves only to people who hold the same role on that project"; the backend decides eligibility). Also include `cannot_reassign_reason` | additive | blocking
- G-SCR21-2 | "Resend invite" (INVITED · NOT SET UP row) | v7 today: nothing | change: `POST /api/v1/setup/people/{person_id}/invitation` (resend) with idempotency_key; revokes the previous link | additive | blocking for that button
- G-SCR21-3 | "Search", "Filter", "8 PEOPLE" | v7 today: E-PEOPLE has only cursor and limit; no total | change: `q`, `state`, `role` query params and `total` in the response | additive | nice-to-have
- G-SCR21-4 | "Invite … Roles: PMO ▾ for Ojo Foods ▾ × … + Add another role" | v7 today: `role_options[].scope_needed` says a scope is required, but nothing lists project choices | change: `role_options[].scope_options:[{value,label}]` or reuse the pattern of E-LINE-OPTIONS (`GET /setup/people/scope-options?q=`) | additive | blocking
- G-SCR21-5 | "DEACTIVATED 30 OCT · History kept"; "An account can be reactivated; its roles would need to be given again." | v7 today: state `deactivated` but no reactivate and no deactivated_at | change: `deactivated_at` on the item; `POST /setup/people/{person_id}/reactivation` or remove the sentence | additive | nice-to-have
- G-SCR21-6 | invite expiry "works for 72 hours", "Invite sent 2 days ago", "INVITED · NOT SET UP" | v7 today: state `invited` only; no `invited_at`, no expired state | change: `invited_at`, `invite_expires_at`, state `invite_expired` | additive | nice-to-have
- G-SCR21-7 | "Only PMO, Finance, HR, their Leads, the CEO and the CTO have accounts. Engineering, QA, Security and clients don't log in; PMs record their responses." | v7 today: copy; the role list is `role_options` | change: none; copy must match `role_options`, so use backend labels | n/a | nice-to-have
- G-SCR21-8 | "Edit roles" on the row | v7 today: E-PERSON-ROLES replaces roles; see G-SCR13B-8 | change: as in SCR-13 roles | additive | blocking
Questions for the backend developer:
- Who may invite and deactivate (D-ADMIN-AUTHORITY is open)? The page shows controls only where `can_change` is true.
- When someone is deactivated, are tasks they have claimed released? Are signed-in sessions ended immediately?
- Is the invite email an outside effect with a delivery result? If delivery is unknown, the list should say so before another invite is sent.
- Past approvals and records stay under the person's name: confirm no foreign key is removed.

---

## SCR-39 · Setup: costing rule (default, review, example, review-own)
Task: FE-SETUP-COSTING · Boards: 8 · Canvas: main · Gated by: D-COSTING-RULE (open)
What the screen does: Everyone allowed sees the single studio-wide costing rule in use (inputs, priced parameters with where each comes from, how the total is calculated, worked examples and whether the rule still gives the expected totals, who owns the rule and the examples, past versions). A reviewer sees a proposed new version against the current one, can open each worked example, and confirms it or returns it with a note. The proposer sees their own version waiting and cannot confirm it.
Proposed route: `/setup/costing-rule`, review at `/setup/costing-rule?version=5` (and example `?example=2`); the decision acts on the review work item
Reads: E-COSTING-RULE GET /api/v1/setup/costing-rule — versions[].version/label/status/proposed_by/proposed_at/reviewed_by/effective_from, sections[] (typed section kinds), examples[].label/expected/computed/result, review_work_id, cannot_review_reason, not_set; E-WORK-ITEM GET (review_work_id) — tasks[] (id, revision, you_can_act, cannot_act_reason, asked[]); E-SETUP-RULES (tab counts)
Writes: Decide: E-TASK-CLAIM POST .../claim and E-TASK-DECIDE POST .../decision on the review task — body: expected_revision, verdict approve|return, note; guards: CSRF, expected_revision, claim. "New version" and "Withdraw v5": no operation (D-COSTING-RULE)
Agent work shown: Tola ("I can check whether this rule is still confirmed and whether the examples match. I can't change a rate or a step.") checks the rule against its examples. Human decisions: the costing reviewer confirms or returns a new version; the rule owner and the examples owner are different people.
Covered by v7 as is: versions list (status current/proposed/withdrawn/superseded, proposed by/at, effective_from); typed sections for inputs, parameters-with-source, steps (as checklist/text), owners (facts), "what changes" (table with columns v4/v5); examples list with expected, computed and result; `cannot_review_reason` for the own-version board; the review decision through the standard task; unknown amounts
Gaps:
- G-SCR39-1 | "New version" button (default) | v7 today: no write (only a read; D-SETUP-RULES-VIEW says "no costing write is proposed") | change: none proposed, it is a financial rule. Needed when D-COSTING-RULE is decided: how a version is proposed (values, reason, effective date), who proposes, what evidence | additive | blocking for this button only
- G-SCR39-2 | "Withdraw v5" (review-own board) | v7 today: nothing | change: none proposed, same decision | additive | blocking for this button only
- G-SCR39-3 | "Worked example 2 of 3 … Expected total for v5 ₦26,910,000.00 — Set by the examples owner … v5 calculates … v4 (IN USE) / v5 (PROPOSED) breakdown rows … Where it comes from: Kora Logistics quote Q-2025-118.pdf, Signed SOW, 4 pages · open in a new tab … Added by Ada Okafor (examples owner), 03 Oct" | v7 today: `examples[]` has label, expected, computed, result only | change: `examples[].detail`: `{summary, type: normal|exception, expected_by{name,role,at}, lines:[{label, qty?, v_current:money, v_proposed:money}], total_current, total_proposed, source{label, document_id|evidence_id, pages?}}`. All figures are backend-calculated and display-only | additive | blocking for the example boards
- G-SCR39-4 | example "Security estimate missing — Exception — Unknown — Unknown — MATCHES" | v7 today: `result` enum match|differs|unknown | change: the board shows "MATCHES" when expected and computed are both Unknown. Whether "Unknown equals Unknown" counts as a match is a costing rule decision (D-COSTING-RULE). INV-UNKNOWN: Unknown is never zero and never silently equal. Backend returns `result` and the page shows it verbatim | n/a | blocking for that example row
- G-SCR39-5 | "Project adjustment … Added on the costing sheet, with a reason; 0 if none" | v7 today: a text cell | change: board copy says 0 when there is no adjustment. That is a declared "none", not an unknown, but confirm with the costing rule owner and keep Unknown distinct from none in the data | n/a | nice-to-have
- G-SCR39-6 | "Rule owner Ada Okafor · Finance Lead / Examples owner Kemi Adebayo · PMO Lead … The examples owner must be a different person from the rule owner." | v7 today: facts items can show names; nothing enforces or returns the rule | change: sections `owners` (facts) are enough for display; enforcement is the backend's. Naming the owners is PSL's decision (D-COSTING-RULE) and the boards' names are sample | n/a | blocking for the real owners
- G-SCR39-7 | "Bisi Ade · Costing reviewer" as the role; "Asked: Bisi Ade · costing reviewer · 12 NOV 16:20" | v7 today: `tasks[].required_role` string; E-ME roles | change: "Costing reviewer" is not in the role list shown on SCR-21 (PMO, PMO Lead, Finance, Finance Lead, HR, HR Lead, CEO, CTO). Who reviews costing versions is not decided (D-COSTING-RULE); do not invent it | n/a | blocking
- G-SCR39-8 | versions list "v3 · 01 Jan–30 Sep 2026", "v4 · current since 01 Oct 2026 · rates for 2026" | v7 today: `effective_from` only | change: `effective_to`, `note` (reason) per version | additive | nice-to-have
- G-SCR39-9 | review board is reached "← My work" (phone) and from SETUP / COSTING RULE (desktop) | v7 today: `review_work_id` links to the work item whose normal decide page is SCR-02-type | change: confirm the review decision happens on this setup page (embedding the task) and not on `/work/{id}/decide`; either is fine for the contract, one must be chosen | n/a | nice-to-have
- G-SCR39-10 | costing "already made keep the version they used" | v7 today: backend rule | change: each costing record stores the rule version it used; display only | n/a | nice-to-have
- G-SCR39-11 | all money values, rates, percentages and rounding on the boards ("₦150,000.00 per person-day", "15% of delivery", "Nearest ₦1,000, half up") | v7 today: from the backend | change: none. These are sample values on the board; the page must show only what E-COSTING-RULE returns and "Not set" when `not_set:true`; no default rate or rounding in the frontend | n/a | blocking (rule)
Questions for the backend developer:
- Is "one studio-wide rule" already the data model (design engineer 12 Nov: backend change needed), or is it still per project today?
- Who is the reviewer role and who asks them? Without that decision `cannot_review_reason` can only be `prepared_by_you` or `not_your_role`.
- Where do worked examples come from and how are they stored (they must not be editable by the proposer)?
- Does a withdrawn version stay visible with its note? The versions list status has `withdrawn`.

---

## Summary

| Screen | Boards | Gaps (blocking / nice-to-have) | Gated by |
|---|---|---|---|
| SCR-05 Assistant (incl. speech) | 10 | 3 / 5 | D-SPEECH-INPUT (speech); D-AGENT-PROVIDER open |
| SCR-08 Document review | 4 | 7 / 1 | none |
| SCR-11 Registers | 2 | 0 / 4 | D-PROJECT-TAB-ROWS (proposed) |
| SCR-12 Report with drill-down | 2 | 0 / 4 | D-PROJECT-TAB-ROWS (proposed) |
| SCR-13 Delegation | 2 | 2 / 4 | none (D-DELEGATION-VIEW proposed) |
| SCR-13 Roles (default, permission, validation) | 6 | 4 / 4 | D-ADMIN-AUTHORITY |
| SCR-13 Payroll fields | 2 | 3 / 3 | D-PAYROLL-VISIBILITY |
| SCR-17 Sign in | 8 | 5 / 3 | D-SIGNIN |
| SCR-19 Mark milestone complete | 2 | 3 / 2 | none |
| SCR-21 Staff accounts | 6 | 4 / 4 | D-ADMIN-AUTHORITY (invite also D-SIGNIN) |
| SCR-29 Project actions | 2 | 0 / 3 | D-PROJECT-TAB-ROWS (proposed) |
| SCR-30 Issue detail | 8 | 2 / 4 | none |
| SCR-38 Project milestones | 4 | 2 / 2 | D-PROJECT-TAB-ROWS (proposed) |
| SCR-39 Costing rule | 8 | 7 / 4 | D-COSTING-RULE |

Counts above are from the Gaps lists in this file (a gap marked "blocking for X only" counts as blocking).

Top five for the backend developer before the frontend can finish:
1. Record a milestone as complete (G-SCR19-1/2/3, G-SCR38-2). Without it the invoice line has nothing to start from.
2. Make E-DOCUMENT a structured, reviewable read (sections, agent notes, checks, case and work/task ids) and decide how a returned version becomes v3 (G-SCR08-1..8).
3. Close the staff-account reads the writes need: open items with eligible takers, scope options, eligible candidates per missing role, role-scope pairing, and restrict personal fields to people who may change them (G-SCR21-1/4, G-SCR13B-1/3/7/8).
4. Link a started draft to its conversation message and add idempotency keys to the assistant writes (G-SCR05-1/3).
5. Decide sign-in (D-SIGNIN) and drop any record reference shown before authentication (G-SCR17-1/2).
