<!-- Part of the connection map: see README.md. Cluster C. Written 23 Nov 2026 from live OpenAPI 1.22.0 (main 9bac3109) and the frontend at f8b28059. -->

# Cluster C: connection map (RFP and bid, client lines, engagement and planning)

Conventions used below. "v7" is the practice contract served by the mock; "live" is OpenAPI 1.22.0. Common to every screen in this cluster:
- v7 `GET /api/v1/work/{work_id}` carried `workspace` (sections, steps, status, version, agent_note, next), `rfp`, `rfp_outcome`, `assign`, `stations`, `facts`, `agent`, `allowed_actions`, `reconcile`, and `tasks[].response`. Live has none of these. Live work detail returns `panels[]` ({key,url}), `tasks[]` (id, kind, role, status, revision, can_decide, verdicts), `screens[]`, `actions[]` (`background`, `reconcile`, `release_invoice`), `information[]`, `progress`, `current_activity`, `output_url`. Each line is read from its own endpoint and written with its own command; the generic `POST /work/{work_id}/steps`, `/assignment` and `/tasks/{id}/response` do not exist live (live `/tasks/{id}/claim|decision` are Finance only).
- Ids change type: v7 `work_id` "W-3402" and `case_id` "C-0211" are strings; live `work_id` is an integer and `case_id` a UUID. Revisions are integers in both, but the field name varies by endpoint: `expected_revision` + `case_revision` (work endpoints), `revision` (planning, team inputs, assignment), `case_revision` only (commercial response, bid pack receipts).
- The shared workspace renderer (`src/features/workspace/*`, `src/features/rfp/RfpFrame.tsx`) is driven entirely by v7 `workspace`/`rfp`. Against live it cannot be reused as is: each line needs its own read model feeding the same section/step components.
- Money in live is a decimal string, durations of effort are strings (`person_days`), unknown is `null`.

---

### SCR-16 · Record a response
**Built today:** yes (F-09 client/SOW/team responses, F-18 RFP outcome) — routes `/work/[id]` (response drawer/panel and RFP Outcome tab); main files `src/features/response/*` (`api.ts`, `contract.ts`, `useResponse.ts`, `ResponseForm.tsx`, `TeamInputForm.tsx`), `src/features/rfp/*` (`useOutcome.ts`, `OutcomeForm.tsx`, `FollowupCard.tsx`), `src/features/workspace/ResponseDrawer.tsx`.
**Live operations:** `GET|POST /projects/{case_id}/commercial-response` (+ `/files`, file download), `GET|POST /received-bids/{case_id}/team-inputs`, `GET /work/{work_id}/bid-outcomes`, `POST /work/{work_id}/rfp-outcome`, `GET|POST /work/{work_id}/bid-outcomes/{outcome_id}/followup`, `GET|POST /projects/{case_id}/delivery/{dossier_id}/client-testing` (+ `/files`, `/pack`), `POST /work/{work_id}/reviews`, `GET|POST /work/{work_id}/planning-owner-requests`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Who can have responded, the sent versions to pick from | `GET /work/{id}` → `tasks[].response.responders[]`, `.versions[]` | `GET /projects/{case_id}/commercial-response` → `parties[{reference,label}]`, `receipts[{id,label}]`, `current_revision_id` | moved, reshaped |
| Allowed responses (approved, changes, signed, rejected) | `tasks[].response.actions[]` | outcome enum `signed / changes_requested / declined` on commercial response; `approved / changes_requested / rejected / approved_with_workaround` on client testing | reshaped (new word "declined"; "approved" only for testing) |
| Whether I may record, claim needed | `tasks[].response.claim_required`, `can_*` | `commercial-response` → `can_record`; no claim step | reshaped |
| Proof files already attached | uploaded then `evidence_id` | `owned_files[{id,name,size,sha256}]`, `witness_files`, download `…/{evidence_id}/files/{upload_id}` | new in live |
| Already-recorded response (who, when, summary) | `tasks[].response.recorded` | `witness {client_name, outcome, responded_at}`, `responses[]`, `packet`, `adoption` | reshaped |
| Team input: which teams have given, estimate needed | `response.teams[{key,name,given,estimate_needed}]`, `blocking` | `GET /received-bids/{case_id}/team-inputs` → `items[{team,received_at,source_party,summary,person_days}]`, `choices[{team,proofs[]}]` (teams: Engineering, QA, Security, Product) | moved, reshaped |
| Outcome form choices (results, record-as roles, loss reasons, lesson categories) | `rfp_outcome.results/record_as/reasons/lesson_categories/evidence_kind` | not served; `GET /work/{id}/bid-outcomes` gives `submissions[]`, `selection_required`, `selection_packet`, `outcome`, `handoff` only | missing in live |
| The submission the outcome is about, recorded outcome | `rfp_outcome.submission`, `.recorded.{result,at,by,rows,reminder,debrief,engagement}` | `bid-outcomes` → `submissions[{id,submitted_at,late,receipt_ids}]`, `outcome {result, award_amount, award_currency, customer_expected_on, followup_on, remind_at, comparison}`, `handoff {kind route_a/loss_archive}` | reshaped |
| Follow-up draft to the client | `rfp_outcome.followup {to, body, version, status, can_send}` | `GET …/bid-outcomes/{outcome_id}/followup` → `message, draft_id, review_id, routes[], history[], receipt_proofs[]` | reshaped |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Record a client response / SOW signature | `POST /tasks/{id}/response` {expected_revision, who, action, responded_at, evidence_id, attested, version_id, received_via, note} → 200 | `POST /projects/{case_id}/commercial-response` `action:"witness"` {case_revision, revision_id, receipt_id, client_name, responded_at, outcome, genuine, proof_ids[], note, operation_key (uuid), predecessor_id, party_ref} → 201 {record_ids}. Signing is a second call `action:"signatures"` {response_id, prd_id, signatures{sow,prd}}, then `adopt` | reshaped (2–3 steps) |
| Upload proof | `POST /cases/{id}/evidence` base64 JSON | `POST /projects/{case_id}/commercial-response/files` multipart {case_revision, file} → 201 {id,…}; client testing has its own `/files` | reshaped |
| Record team input | response with `team`, `estimate_person_days`, `what` | `POST /received-bids/{case_id}/team-inputs` {revision, team, evidence_id, received_at, source_party, summary, person_days (string or null), attested} → 201 | reshaped (zero vs unknown is explicit) |
| Record RFP outcome | `POST /work/{id}/rfp-outcome` {result, learned_at, record_as, evidence_id, reason, lessons, awarded_amount{unknown}, expected_decision_on, remind_at} | same path: {expected_revision, case_revision, submission_id, verdict, observed_at, role, evidence_id, note, selection_packet, selection_acknowledged, award_amount, award_currency, customer_expected_on, followup_on, remind_at, loss_reason_key, loss_catalog_id, debrief_version_id} → 200 {work_id,state,revision} | renamed/reshaped (`result`→`verdict`, `learned_at`→`observed_at`, `record_as`→`role`) |
| Send follow-up | `POST …/rfp-outcome/followup` {version, body} | `POST …/bid-outcomes/{outcome_id}/followup` four actions: `draft`, `review` {draft_id, message}, `send` {review_id, route}, `confirm` {dispatch_id, evidence_id, reference, delivered} | reshaped (review step before send) |
| Review a response | n/a | `POST /work/{id}/reviews` | new in live |

**Design parts the live API cannot fill:**
- The "received via" channel (email, WhatsApp, call) on a client response; live has no field (only `note`).
- The word lists for the outcome form (who the outcome is recorded as, loss reasons, lesson categories) and the lessons text box; live takes keys and a debrief document instead.
- Agent note lines and the "what happens next" sentences on the recorded view.
- The Product team in "estimate needed"/"cannot be recorded yet" marking; live has four fixed teams and no reason text.

**Live data the design does not show yet (worth knowing):** `late` flag on a submission; `selection_required` and `selection_packet` when two submissions exist (a person must acknowledge which one the customer chose); `comparison` of award versus submitted price; `handoff.kind` (route A to a new project, or loss archive); follow-up `history[]` with delivered/not; client testing pack and proof review.
**Effort to connect:** L — three different live families (commercial, team input, outcome) replace one generic task response, and several have extra independent-review steps.
**Questions for the backend:**
1. C-1: `POST /work/{work_id}/rfp-outcome` takes `role`, `loss_reason_key`, `loss_catalog_id` and `debrief_version_id`; which operation lists the allowed roles, loss reasons and debrief documents?
2. C-2: How does a file the person attaches become the integer `evidence_id` that `rfp-outcome`, `team-inputs` and `assignment` expect (there is `POST /cases/{case_id}/files` returning `upload_id`, and `commercial-response/files` returning `id`)?
3. C-3: Is `received_via` (email, WhatsApp, call) stored anywhere on `commercial-response` `action:"witness"`, or should it go in `note`?
4. C-4: `GET /received-bids/{case_id}/team-inputs` does not say which teams are still owed or blocked; is `choices[].team` the full asked list?
5. C-5: Which `/work/{work_id}/reviews` `kind` carries the follow-up `review` (the one between `draft` and `send`)?
6. C-6: For `selection_required`, what does `selection_packet` contain and what must `selection_acknowledged` confirm?

---

### SCR-23 · Log a received RFP
**Built today:** yes (F-36, F-49) — Start work drawer on `/work` (line `rfp_intake`, "Log RFP"); files `src/features/start-work/*` (`LineForm.tsx`, `useStartWork.ts`), mock `frontend/mock/start-work.mjs`.
**Live operations:** `GET /received-bids/organisations`, `POST /received-bids` (multipart), `GET /received-bids/{case_id}/receipts/{receipt_id}`; not `GET /lines` (backend says keep received bids as their own intake).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Form fields (client, reference, document, received, method, target, deadline, note) | `GET /lines` → `lines[rfp_intake].intake[]` | none: fields are fixed in the POST body | missing in live (hard-code) |
| Client picker | `GET /lines/{line}/fields/client/options` | `GET /received-bids/organisations` → `items[{id,organisation}]` (organisations "where you can record a received bid", sent back as `authority`) | reshaped (a delegation, not a client list) |
| Confirmation after logging | `POST /work` → `{work_id,state}` | `POST /received-bids` → `{receipt_id, case_id, django_url}`; read back with `GET …/receipts/{id}` → `reference, received_at, deadline_status, deadline_at, customer_instructions{prospect_name, submission_method, submission_target}, original{filename,bytes,download_url}`, `current`, `number` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Upload RFP file | `POST /cases/{id}/evidence` base64 → `evidence_id` | file travels in the same call (`document`, multipart) | moved |
| Log the RFP | `POST /work` JSON {line, case_id, case_revision, intake{client, rfp_reference, rfp_document, received_at, submission_method, submit_to, deadline_status, deadline_at, note}, idempotency_key} → 201 {work_id} | `POST /received-bids` multipart {authority (int), start_key (uuid), reference, received_at, deadline_status (unknown/stated/not_stated), deadline_at, prospect_name, submission_method (email/portal/by_hand/not_stated), submission_target, context_attested, document, definition} → 200 {receipt_id, case_id}. No case_id/case_revision needed | renamed/reshaped; the response has no `work_id` |

**Design parts the live API cannot fill:** the free-text Note; picking an existing client by name (live has `prospect_name` text and an organisation authority); returning the new work item id so the page can open it.
**Live data the design does not show yet (worth knowing):** a numbered, versioned receipt (`number`, `current`), so logging again leaves earlier receipts intact; an authenticated download link for the original file.
**Effort to connect:** M — one form, one multipart call, but the client picker, the missing `work_id` and the removal of base64 upload need new wiring.
**Questions for the backend:**
1. C-7: `POST /received-bids` returns `case_id` and `receipt_id` but no `work_id`; how does the screen reach the new Unassigned work item (find it in `GET /work?queue=unassigned` by `case_id`)?
2. C-8: What are `authority` (organisation delegation id), `definition` and `context_attested` in `POST /received-bids`, and what does the person see for each?
3. C-9: Is `prospect_name` how a new client is created (closing our G-23-1), and is an existing client matched by name, by `organisations`, or not at all?
4. C-10: Is there a stored Note field for the person logging the RFP, or should the field be removed from the form?
5. C-11: Which duplicate rule applies to the same `reference`, and what status and `code` does it return (our G-23-2/BQ on repeat logging)?

Closes from our earlier gaps: G-23-1 (new client), G-23-2/G-23-3 (deadline states stored separately), G-23-4 (method and target readable on the receipt), G-23-5 (the RFP gets its own case, no shared revision), G-23-6 (multipart upload; size limit still unstated, answered only by 413).

---

### SCR-24 · Assign the accountable PM
**Built today:** yes (F-36, F-49) — drawer over My work's Unassigned list; files `src/features/rfp/AssignPmDrawer.tsx`, `src/features/rfp/proposals.ts`, `src/features/workspace/AssignForm.tsx`, `useWorkspaceAssign.ts`.
**Live operations:** `GET /work?queue=unassigned`, `GET /received-bids/assignments`, `GET /received-bids/{case_id}/assignment`, `POST /received-bids/{case_id}/assignment`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The unassigned list | `GET /work?queue=unassigned` | `GET /received-bids/assignments` → `items[{case_id,intake_id,revision,reference,received_at,deadline_status,deadline,owner_access_required}]`, `cursor`, `checked` (also `GET /work?queue=unassigned`, page-based) | moved |
| People who can be chosen | `GET /work/{id}` → `assign.candidates[{person_id,name,role,hint}]` | `…/assignment` → `nominees[{id,label}]` | renamed (no role/hint) |
| "You are assigning as" roles | proposal `assign.roles[]` (G-24-1) | `roles[]` (strings) | new in live — closes G-24-1 |
| Proof choices | proposal `assign.evidence_kind` (G-24-2) | `proofs[{id,label}]` | new in live — closes G-24-2 |
| Already assigned / setup missing | n/a | `assignment {id, person_id, role, intake_id}`, `setup_required` | new in live |
| "What happens next" sentence | proposal `assign.next` (G-24-3) | not served | missing in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Assign the PM | `POST /work/{id}/assignment` {expected_revision, person_id, note, acting_role, evidence_id, case_revision} → 200 {state, assigned_to} | `POST /received-bids/{case_id}/assignment` {intake (int), revision, candidate (int), role, evidence (int, required), reason (required)} → 201 {id, person_id, role, intake_id} | reshaped; keyed by `case_id` from the list row, not `work_id`; proof and reason become required |

**Design parts the live API cannot fill:** proof is drawn as optional but is required by the live body; the "what happens next" lines and the PM's name in the success words (only `nominees[].label` and `person_id`); no work state returned after assigning, so "assigned" must wait for a re-read.
**Live data the design does not show yet (worth knowing):** `owner_access_required` on a row; `setup_required` when no one is configured to assign; the list `checked` count.
**Effort to connect:** M — one read and one write, but the drawer must key on `case_id`, use integer ids and make proof and reason mandatory.
**Questions for the backend:**
1. C-12: Is `evidence` truly required in `POST /received-bids/{case_id}/assignment` (design says optional), and is `reason` the same as our optional Note?
2. C-13: Can `GET …/assignment` return the next-steps sentences and the nominee's role (our G-24-3)?
3. C-14: Does assigning move the item out of `queue=unassigned` immediately, and which work state results?

---

### SCR-25 · Weekly client update
**Built today:** yes (F-21, F-22) — `/work/[id]`, line keys `weekly_report` and `weekly_client_report`; files `src/features/workspace/Workspace.tsx`, `StepForm.tsx`, `Sections.tsx`, `Steps.tsx`, `useWorkspaceStep.ts`.
**Live operations:** `GET|POST /projects/{case_id}/weekly-report-intake`, `GET|POST /work/{work_id}/weekly-report`, `POST /work/{work_id}/reviews`, `POST /work/{work_id}/actions`, `POST /work/{work_id}/corrections`, `GET /work/{work_id}`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Title, status tag, version, byline | `workspace.title/status/version/byline` | `GET /work/{id}` → `title, status_label, state, progress`; version only as `weekly-report` → `document_version_id` | missing in live (partly) |
| My four parts (status, risks, timeline, next steps) and what they cite | `workspace.sections[update].items[]` with `cites` | before start: `GET …/weekly-report-intake` → `draft.values.parts.{status,risks,timeline,next_steps}.{text,evidence_ids[]}`; after start: `GET /work/{id}/weekly-report` → `editable_parts` (same shape), `draft` | reshaped |
| Pick a cite (this week's records) | `workspace.steps[].fields[type=records]` options from `GET /lines/{line}/fields/…/options` | `weekly-report-intake` → `evidence[{id,version,kind}]`, `templates[{id,name,version}]`, `narratives[]`, `next_before` | reshaped (no labels) |
| This week's meetings, milestones, actions, issues, changes | `sections` of kind facts | not served as such (only `evidence[]` by kind) | missing in live |
| Reviewer's returned note | `sections[returned]` text | `weekly-report` → `return_review_id` (note text not included) | missing in live |
| Assembled report text | `sections[report]` | `document_version_id` only; preview lives on `GET /projects/{case_id}/document-reviews/{version_id}` | moved |
| Who received it and delivery receipts | `sections[recipients]`, `receipt` enum | `weekly-report` → `recipients[{name,status,receipt_id,recorded_at}]`, `next_action` | renamed |
| Assembly progress | `sections[assembly]`, `agent`, `stations` | `GET /work/{id}` → `current_activity {label, watching}`, `progress` | reshaped |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Save draft | `POST /work/{id}/steps` step `save_draft` | `POST /projects/{case_id}/weekly-report-intake` `action:"save_draft"` {case_revision, draft_id, selection{template_id, content_id, start_at, end_at}, parts{…}, key, reference, background} → 201 {draft_id, case_revision}; after start `POST /work/{id}/weekly-report` `action:"save_draft"` | reshaped |
| Send to Tola to assemble | step `send_to_tola` {inputs{status, status_cites…}} | `weekly-report-intake` `action:"start"` → 201 {work_id, state, revision, background (queued/existing/held/not_requested)} | reshaped (work is created here; today the work item already exists) |
| Edit after return | step `edit_update` | `POST /work/{id}/weekly-report` `action:"correct"` {expected_revision, case_revision, parts, reason} → 201 | reshaped |
| Approve / return / reject the report | `approve_send`, `return` {note}, `refuse` steps or decide | `POST /work/{id}/reviews` kind `document` {version_id, verdict approve/return/reject, note} | moved |
| Check an uncertain send | `POST /work/{id}/actions` reconcile {outcome, evidence_id} | same path, `action:"reconcile"` only (no outcome, no evidence), → 202 | reshaped (202) |

**Design parts the live API cannot fill:** the "this week's records" lists (meetings, milestones, actions, issues, changes) and readable cite labels; the reviewer's returned note and "what happened" timeline; header tag wording ("Returned to you", "Received by client"); agent note lines; the reconcile choice of delivered / not delivered / unknown.
**Live data the design does not show yet (worth knowing):** reporting period (`start_at`/`end_at`) and a template choice; a background switch (queued / held); `can_correct`; recipient receipt ids.
**Effort to connect:** L — the whole workspace read model has to be rebuilt from two endpoints plus the document preview, and work starts in a different place.
**Questions for the backend:**
1. C-15: `weekly-report-intake` `evidence[]` and `narratives[]` have only `{id, version, kind}`; where do the labels (for example "Milestone 2 · UAT signed 11 Nov") and this week's meetings, issues, actions and changes come from?
2. C-16: Where is the reviewer's returned note read (only `return_review_id` is given)?
3. C-17: Where is the assembled report text read for the PM before review, and is it `document-reviews/{version_id}` preview?
4. C-18: Does `action:"start"` replace the PM's current `send_to_tola` step, and is a work item (and its progress) visible before it?
5. C-19: Can `POST /work/{id}/actions` `reconcile` carry the checked result and proof?
6. C-20: Which `panels[].key` on `GET /work/{work_id}` points to `weekly-report`?

---

### SCR-26 · RFP response workspace
**Built today:** yes (F-37) — `/work/[id]`, line `rfp_response` inside the RFP frame; files `src/features/rfp/RfpFrame.tsx`, `src/features/workspace/Workspace.tsx`, `Sections.tsx`, `InlineDecide.tsx`, `proposals.ts`.
**Live operations:** `GET|POST /work/{work_id}/bid-answers`, `GET /work/{work_id}/bid-outcomes`, `…/followup`, `POST /work/{work_id}/reviews`, `POST /work/{work_id}/rfp-outcome`, `POST /work/{work_id}/corrections`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| RFP header (reference, client, deadline, PM, tabs with counts) | `GET /work/{id}` → `rfp.{reference,title,client,status,pm,tabs}` | not served: `GET /work/{id}` → title, `panels[]`; deadline from the received-bid receipt, PM from assignment | missing in live |
| Requirement rows (ref, wording, answer, status) | `sections[requirements]` table with `total`, `filters`, `next_cursor` | `GET /work/{id}/bid-answers` → `rows[{key, response, disposition, status}]` (no requirement wording, page or paging) | reshaped / missing |
| Tola's suggestions with source | `sections[suggestions]` items with `cites`, `tag` | `rows[].suggestion_id`, `suggested_answer`; `prior_options[{token,label}]` (reusable winning answers) | renamed; closes G-26-5 in part |
| Progress figures, before-review checklist | `sections[progress]`, `[before_review]` | not served | missing in live |
| Who can accept or undo | steps per item | `can_write`, `rows[].can_review`, `can_undo`, `review_verdict`, `review_id` | new in live |
| Reviewer panel (PMO Lead, Engineering Lead) | `sections[checklist]`, tasks | `GET /work/{id}` → `tasks[]` with `verdicts` | reshaped |
| Outcome and follow-up | `rfp_outcome` | see SCR-16 | reshaped |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Ask Tola for an answer | (agent runs on assign) | `POST /work/{id}/bid-answers` `action:"suggest"` {expected_revision, case_revision, key, operation_key, prior_answer} → 201 | new in live |
| Accept / edit / write own | `POST /work/{id}/steps` `accept`, `accept_selected` (item_ids), `edit_accept`, `write_own` | `action:"review"` {decisions[{suggestion, predecessor, verdict accept/edit/replace, answer, disposition addressed/clarification/out_of_scope, note}]} → 201 {record_ids}, atomic for many | reshaped |
| Undo | not in v7 | `action:"undo"` {review_id} | new in live |
| Add a requirement | step `add_requirement` {requirement, rfp_page} | none | missing in live |
| Record team input | step `record_input` | see SCR-16 | moved |
| Send for review / approve / return | step `send_for_review`; decide task | `POST /work/{id}/reviews` kind `bid` {subject response/commercial/document, target_id, role, verdict, evidence_id, note} | reshaped |

**Design parts the live API cannot fill:** requirement text, RFP page numbers and requirement numbers (R-07); filters, row counts and "41 of 64"; the Progress figures and "Before review" checklist; the tab bar and its counts; "Add a requirement"; the "needs clarification from the client" sent-date lines; the Engineering Lead "recorded by PM" row; counts of answers accepted unchanged vs edited.
**Live data the design does not show yet (worth knowing):** each row's `disposition` (addressed, needs clarification, out of scope) and `status` (queued, running, held, stale); previous winning answers to reuse; undo of a single answer.
**Effort to connect:** L — the central table loses its data source and the accept/edit/reject steps change shape and become atomic review decisions.
**Questions for the backend:**
1. C-21: `bid-answers.rows[]` carries only `key` and `response`; where do the requirement wording, RFP page, reference and ordering come from, and is there paging for 64+ rows?
2. C-22: Is there a way to add a requirement (our `add_requirement`), or are requirements fixed by the source analysis?
3. C-23: Which operation gives the Progress figures, the "before review" checks and the tab counts?
4. C-24: How does the PM send the response for review (which op or `reviews` `kind`/`subject`), and how is a return from Engineering shown?
5. C-25: What do `disposition: clarification` rows trigger, and is there a client clarification send/answer record (our G-26-8)?

---

### SCR-27 · Costing sheet
**Built today:** no (FE-COSTING has no feature, no route and no mock fixture).
**Live operations:** `GET|POST /work/{work_id}/bid-pricing`, `GET|POST /work/{work_id}/security-estimate`, `POST /work/{work_id}/reviews`, `GET /work/{work_id}`; also `GET|POST /projects/{case_id}/costing` and `…/costing/calculations/{run_id}` (source-owner controls).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Calculation lines (engineering, security, PM share, total) | not built (G-27-1 asked for them) | `bid-pricing` → `amounts[{key,unit,value}]` (value `null` = unknown) | new in live |
| Inputs and their versions | not built | `inputs[{label,version}]`, `commercial_revision`, `current` | new in live |
| Approvals in order | not built | `approvals[{label,status,recorded_at}]` | new in live |
| Missing estimate flags | not built | `estimate_missing`, `security_estimate_missing`, `costing_note` | new in live |
| What the PM may adjust, and limits | not built | `adjustment_targets[{key,label,max_absolute_value}]`, `adjustment_currency`, `can_configure`, `can_open_calculator` | new in live |
| Ask Security: contact, channels, draft, receipt | not built | `GET /work/{id}/security-estimate` → `channels[{channel,contact,allow_attachment}]`, `draft_body`, `model_status`, `model_answer`, `receipt`, `attachments[]`, `evidence[]` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Add an adjustment | not built | `POST /work/{id}/bid-pricing` {expected_revision, case_revision, target, amount (string, may be negative), reason} → 200 (creates a new costing and fresh review) | new in live |
| Ask Security for the estimate | not built | `POST /work/{id}/security-estimate` actions `prepare`, `prepare_with_assistant`, `review` {draft_id, channel, due_on, body, evidence_id, attachment_id, model_turn_id}, `release` {request_id}, `receipt` {dispatch_id, reference, delivered, evidence_id} → 201 | new in live |
| Approve / return / reject the sheet | `POST /tasks/{id}/decision` | `POST /work/{id}/reviews` kind `bid` {subject `commercial`, target_id, role, verdict, evidence_id, note} | moved |

**Design parts the live API cannot fill:** the line "Rule: share of delivery" explanation text and rule version labels (only `amounts[].key`, `unit`, `value`); the Tola note about past bids; "why you can adjust" and the adjustment limit sentence (limit is a number only, `max_absolute_value`; PSL has not set values, so it may be empty); the delivery-plan input row (no source); costing version history (v1 replaced by v2).
**Live data the design does not show yet (worth knowing):** the bounded adjustment limit per target; model-drafted Security wording with a review step before sending; original delivery receipt of the Security request; a held run state (`held`) when a rule is not configured.
**Effort to connect:** M — new screen against rich live reads; the unknowns are the labels and the approval order.
**Questions for the backend:**
1. C-26: What are the allowed values of `amounts[].key` and `unit` (engineering, security, project management, total) and their display names?
2. C-27: `approvals[].status` is a string; what are the values and is the order PM, PMO Lead, CEO (D-APPROVAL-ORDER) enforced and readable?
3. C-28: Which `reviews` `kind`/`subject` records each approval on the costing sheet, and who may decide the CEO step?
4. C-29: When `max_absolute_value` is unset (PSL decision pending), what is returned for `adjustment_targets`?
5. C-30: Is the delivery plan a costing input anywhere on `bid-pricing.inputs`?

---

### SCR-28 · Confirm the minutes
**Built today:** yes (F-23, F-28) — `/work/[id]`, line `minutes`; files `src/features/workspace/Workspace.tsx`, `Sections.tsx`, `StepForm.tsx`, `InlineDecide.tsx`; Start work drawer collects audience and notes.
**Live operations:** `GET /projects/{case_id}/intake-sources`, `POST /projects/{case_id}/minutes/intake`, `GET /work/{id}/minutes`, `GET /work/{id}/minutes/action-options`, `POST /work/{id}/minutes/confirmation`, `…/review-request`, `…/delivery`, `POST /work/{id}/reviews`, `POST /work/{id}/corrections`, `GET /projects/{case_id}/meetings/options`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Meeting facts (name, date, attendees, file) | `sections[meeting]` | not served; `meetings/options` → `participants[{id,label}]`, `owners[]`, `proofs[]`; notes file `notes_evidence_id` | reshaped |
| Tola's suggested decisions and actions with source quote | `sections[decisions]` suggestions with `cites` | `GET /work/{id}/minutes` → `suggestions[{key, kind decision/action, quote, evidence_id}]` | renamed (no owner, due, tag) |
| Existing actions to link | not drawn | `…/minutes/action-options` → `items[{reference,current{description,owner,deadline,timing}}]`, `linked_action_ids` | new in live |
| Tola's reading progress | `sections[reading]`, `agent` | `GET /work/{id}` → `current_activity`, `progress` | reshaped |
| Drafted minutes preview | `sections[summary]` | `minutes` → `document {version_id, audience, can_request_review, preview[{heading,text}]}` | renamed |
| Recipients and receipts | `sections[recipients]` | `minutes` → `delivery {job_id, state, recipients[{name,status,receipt_id,recorded_at}]}` | renamed |
| Whether I can confirm | step list | `can_confirm`, `confirmed_meeting_version_id` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Start minutes from notes | `POST /work` {line minutes, intake{audience, notes, meeting}} | `POST /projects/{case_id}/minutes/intake` multipart {case_revision, idempotency_key, reference, template_id, meeting_version_id, audience, background, notes_file} → 200 {work_id, state, background}; template from `GET /projects/{case_id}/intake-sources?line=pmo-minutes/v1&field=…` | moved/reshaped |
| Keep / edit / remove / add a decision or action, set owners and due dates | steps `edit_item`, `remove_item`, `add_action`, `edit_decision`, `assign_owner` (one at a time) | one `POST /work/{id}/minutes/confirmation` {expected_revision, case_revision, extraction_id, minutes{kind, occurred_at, purpose, summary, participant_ids[], decisions[{text, evidence_id}], actions[{reference, description, owner_id, due_at, evidence_id, reason}], existing_action_ids[], note}} → 200 | reshaped (one confirm with everything) |
| Choose internal or client | step input `audience` on confirm | `audience` only at intake (multipart) | moved |
| Send for review | step `send_for_review` | `POST …/minutes/review-request` {version_id} → 200 | reshaped |
| Approve and send / return | `approve_send`, `return` | `POST /work/{id}/reviews` kind `document` {version_id, verdict, note} | moved |
| Retry or cancel a stuck send | reconcile | `POST …/minutes/delivery` {job_id, action cancel/retry, reason} | new in live |

**Design parts the live API cannot fill:** the meeting card (title, time, attendee count) and notes file name/size; suggested owner and due date per suggestion; per-item "From Notes · 14:12" tag; in-place "save for later"; the "Ask Tola" link.
**Live data the design does not show yet (worth knowing):** meeting kind (alignment, kickoff, status, retrospective, other), purpose and summary fields; participant list; linking to existing open actions; each action's `reason`; publication retry/cancel with a reason.
**Effort to connect:** L — the item-by-item editing becomes one composed confirmation payload, and the read model is rebuilt from `minutes` plus option lists.
**Questions for the backend:**
1. C-31: `minutes.suggestions[]` has `quote` but no proposed owner, due date or title; does the extraction supply them elsewhere?
2. C-32: Can the audience (internal/client) still change at confirmation, or is it fixed at intake (our G-SCR28-5)?
3. C-33: When are actions created, at `confirmation` or after approval (our G-SCR28-7)?
4. C-34: Where are meeting name, date, time and attendee count read for the meeting card?
5. C-35: Which `reviews` payload do the PMO Lead and Quality reviewer use for outward minutes, and how does Return keep confirmed actions?

---

### SCR-40 · RFP submission
**Built today:** yes (F-38) — `/work/[id]`, line `rfp_submission` in the RFP frame; files `src/features/workspace/Workspace.tsx`, `InlineDecide.tsx`, `src/features/rfp/RfpFrame.tsx`, `RecordedView.tsx`.
**Live operations:** `GET|POST /work/{id}/bid-pack`, `POST …/bid-pack/review-request`, `POST /work/{id}/reviews`, `GET|POST …/bid-pack/portal-receipt`, `GET|POST /work/{id}/bid-submission`, `GET …/bid-submission/pdf/{version_id}`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Pack version, cover letter | `workspace.version`, step `edit_cover_letter` | `GET /work/{id}/bid-pack` → `pack_id, number, cover_note, document_version_id, decision{label,created_at,note}` | renamed |
| Pack contents checklist and checks (format, send to, deadline margin) | `sections[pack]`, `[checks]` | `GET …/bid-submission` → `file{id,sha256,size,findings[]}`, `route`; deadline from the receipt | reshaped |
| Review state, return note | `workspace.status`, decide task | `bid-pack.decision`; `GET /work/{id}` → `tasks[].verdicts` | reshaped |
| Sent to (method and address) | `rfp.submission_plan` (G-23-4) | received-bid receipt `customer_instructions.submission_method/target` | moved |
| Sending status | `rfp_outcome.submission.delivery` | `bid-submission` → `job_id, job_status, submission{submitted_at, receipt_ids, late}`, `approval_recorded` | renamed |
| Portal receipt | not built | `bid-pack/portal-receipt` → `ready, hold, receipt{reference, submitted_at, late}, proofs[]` | new in live |
| PDF to open | document version | `GET …/bid-submission/pdf/{version_id}` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Edit cover letter / save pack | step `edit_cover_letter` | `POST /work/{id}/bid-pack` {expected_revision, case_revision, response_id, base_pack_id, cover_note, file_extension, file_count, file_size_rule (less_than/at_most), file_size_bytes} → 200 {pack_id, number} | reshaped (client file rules are typed here) |
| Send for review | step `send_for_review` | `POST …/bid-pack/review-request` {pack_id, version_id} | reshaped |
| Approve / return / reject | `approve_submission`, `return_submission`, `reject_submission` | `POST /work/{id}/reviews` kind `document` {version_id, verdict, note} | moved |
| Submit | on approve (automatic) | `POST …/bid-submission` {version_id} → 202 queued | new step, 202 |
| Record a portal submission | not built | `POST …/bid-pack/portal-receipt` {version_id, evidence_id, attestation} → 201 | new in live |

**Design parts the live API cannot fill:** per-part pack checklist ("Company forms · template"), "Open the full pack (6.1 MB)" size text (only `file.size`), the history timeline ("What happened"), the agent note; delivery confirmation words for email (receipt ids only).
**Live data the design does not show yet (worth knowing):** PDF findings from the format check; `late` flags; `hold` text when portal receipt is not ready; the "cover note" and typed file rules.
**Effort to connect:** M — mostly renamed reads plus a new explicit "submit" step and the portal receipt.
**Questions for the backend:**
1. C-36: Does `POST …/bid-submission` need to be pressed after the review approval (our G-40-1), or does approval queue it?
2. C-37: What are the `findings[]` codes in `bid-submission.file` and how should each be worded?
3. C-38: How is a pack made of several parts (forms, response document) listed to the reviewer, and where is the test-template flag (G-40-6)?
4. C-39: Which `reviews` `kind` approves a bid pack, `document` or `bid`?

---

### SCR-41 · Engagement
**Built today:** yes (F-31) — `/work/[id]`, line `engagement`; files `src/features/workspace/Workspace.tsx`, `StepForm.tsx`, `AssignForm.tsx`, `Sections.tsx`.
**Live operations:** `POST /work`, `GET /work/{id}`, `GET /projects/{case_id}/engagement-intake`, `GET|POST /work/{id}/engagement`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Won RFP the engagement came from, route | `sections[packet]`, `[created]` | `engagement-intake` / `GET /work/{id}/engagement` → `capture {route A/B/C, reference, rfp_disposition_id}` | reshaped |
| Packet parts (scope, price, plan) | `sections[packet]` table | not served as a table | missing in live |
| PM and roles to confirm | `sections[pm]`, `assign.candidates` | `managers[{id,name}]`, `assignment_roles[]`, `registration_roles[]` | renamed |
| Plan evidence choices | step field `plan_evidence` | `source_proofs[{id,version,kind}]` | renamed |
| What is possible now | step list | `actions[]` (assign, details, register, reassess), `finding` | new in live |
| Details already saved, registration, Planning handoff | `sections[registered]` | `details {reference, plan_id, planned_start, contact_id}`, `registration_id`, `planning_work_id`, `planning_receipt_id`, `planning_packet_id`, `project_contact_id` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Confirm the PM | prefilled step `assign` | `POST /work/{id}/engagement` `action:"assign"` {expected_revision, case_revision, key, evidence_id, role, pm_id} → 201 {record_id} | reshaped |
| Record plan and contact details | part of `register_engagement` | `action:"details"` {capture_id, reference, plan_id, checked, planned_start, contact_id, evidence_id, key} | new step |
| Register the engagement | `register_engagement` {plan_evidence, start_date, client_contact} | `action:"register"` {role, value, plan_id, details_id, evidence_id, key} → 201 | reshaped |
| Re-check after a change | none | `action:"reassess"` {capture_id, reason} | new in live |
| Start the engagement line | auto after a won outcome | `POST /work` (Start work) with the capture | moved |

**Design parts the live API cannot fill:** the packet table (scope, price, plan with IN/OUT tags) and costing price vs awarded price; the "what registering does" sentences and links to the created project and planning item (only ids); client project contact name and role (`contact_id` only).
**Live data the design does not show yet (worth knowing):** the route (A, B or C) and its original capture; `finding` explaining why a step is held; reassess.
**Effort to connect:** M — three explicit steps replace one registration form; labels for ids are missing.
**Questions for the backend:**
1. C-40: What is `register.value` (project name, code, identity), and who chooses it?
2. C-41: How do `key` and `checked` on `assign` and `details` work, and what does the person confirm?
3. C-42: Can `GET /work/{id}/engagement` return packet rows (scope, price, plan) with labels and the project and planning links as names?
4. C-43: What are Routes B and C, and should the screen name them (our G-41-7)?

---

### SCR-42 · Planning
**Built today:** yes (F-31) — `/work/[id]`, line `planning`; files `src/features/workspace/Workspace.tsx`, `Sections.tsx`, `StepForm.tsx`, `src/features/response/TeamInputForm.tsx` (record input).
**Live operations:** `POST /work`, `GET /work/{id}`, `POST /work/{id}/background`, `GET|POST /projects/{case_id}/planning`, `POST …/planning/department-inputs`, `POST …/planning/effort-review`, `GET|POST /work/{id}/planning-owner-requests`, `GET|POST …/planning/source-clarifications`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Departments with status, effort and proof | `sections[departments]` table (department, asked, status, estimate, proof) | `GET /projects/{case_id}/planning` → `departments[{department, input{summary, source_party, received_at, effort_state known/unknown/not_applicable, person_days, changed_effort}}]` (Engineering, QA, Security, Product, Infrastructure) | reshaped |
| Held reasons (nobody to receive a request) | `status`, `blocker` | `finding`, `packet.questions[]`, `source_correlations[]`, `GET …/source-clarifications` → `findings[]`, `clarifications[{owner_status, status}]` | reshaped |
| Estimate changed vs costing | `sections[estimate_changed]` | `departments[].input.changed_effort`, `effort_reviewed`, `review_roles[]`, `reviewed_costing` | reshaped |
| Readiness and handoff | `sections[tola_work]`, facts | `readiness {evidence_id, delivery_dossiers[{id,label}], source_ids[]}` | reshaped |
| Department owner's pending request | not drawn | `GET /work/{id}/planning-owner-requests` → `requests[{request_id, receipt_id, role, proofs[]}]` | new in live |
| May I record | step availability | `can_record_input`, `can_assign` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Record a department's input | `POST /tasks/{id}/response` {team, estimate_person_days, what} | `POST …/planning/department-inputs` {revision, packet_id, department, previous_id, source_id, source_party, received_at, summary, effort_state, person_days} → 201 | moved, reshaped (versioned successors) |
| Set who receives a department request | step `who_receives` | `POST …/source-clarifications` `action:"assign"` {packet_id, key, owner_id}; owner replies with `respond` {disposition, evidence_id…} | reshaped |
| Department owner confirms a source | none | `POST /work/{id}/planning-owner-requests` {request_id, receipt_id, evidence_id} → 201 | new in live |
| Prepare readiness | step `prepare_readiness` | `POST …/planning` `action:"prepare_readiness"` {revision, packet_id} → 200 | moved |
| Hand off to delivery | not drawn | `action:"handoff"` {readiness_id, dossier_id} | new in live |
| Review changed effort | not drawn (G-42-5) | `POST …/planning/effort-review` {packet_id, role, disposition retain_costing/new_costing, evidence_id, reason} | new in live — answers G-42-5 |
| Capture sources / align meeting | none | `action:"capture"`, `action:"align"` | new in live |
| Pause or continue Tola | none | `POST /work/{id}/background` {enabled} → 202 | new in live |

**Design parts the live API cannot fill:** the "asked" column wording ("Scope breakdown and effort") and the sent-request date lines; agent checklist steps ("Read the packet"); the risks and "plan 4 stages" lines in readiness facts; the "who receives this?" link to Setup.
**Live data the design does not show yet (worth knowing):** unknown effort kept separate from "not applicable" and from zero; a human readiness decision before handoff; source correlations (current, conflicting, excluded); a new costing may be required (`new_costing`).
**Effort to connect:** L — the table reads from a dedicated planning resource; five new commands, with a human decision (effort review, handoff) the design draws only partly.
**Questions for the backend:**
1. C-44: Where are the labels "asked" for each department (what was requested and when)?
2. C-45: `department-inputs` uses `source_id` (integer); how does a person pick or attach that source, and is it the same id space as `team-inputs.evidence_id`?
3. C-46: Is Infrastructure shown as part of Planning even though team-input on the RFP lists Product instead?
4. C-47: How does the PM know the owner for Product is missing (`owner_status: unassigned`) and where does the person set it (our G-42-4)?
5. C-48: Is the `handoff` decision a separate human approval from `prepare_readiness` (our G-42-6)?

---

## Cluster summary
- The biggest change is structural: v7 gave one workspace block plus one step endpoint for all of these lines; live gives a separate read and command set per line. Every workspace screen here (SCR-25, 26, 28, 40, 41, 42) needs its own read model feeding the shared section and step components, and its own write mapping. Start with a per-line adapter layer.
- Live work ids are integers and cases are UUIDs; both appear in routes and mocks today as "W-…" and "C-…". The `/work/[id]` and project routes, the mock and the generated types all need to change once.
- File evidence is a cross-cutting gap: v7 uploaded base64 and got an `evidence_id`; live uses multipart files and requires integer `evidence_id`/`proof_ids` chosen from lists, with no single upload operation we can point to (questions C-2, C-45). Settle this before wiring SCR-16, 23, 24, 42.
- SCR-16 splits into commercial response, team input, client testing and outcome, each with its own body; outcome and follow-up add a review step the design does not draw. SCR-26 loses its requirement table data (no wording or page in `bid-answers`).
- Closed or answered by live: G-23-1..G-23-6 (RFP intake), G-24-1 and G-24-2 (roles and proof on assignment), G-26-5 (reusable past answers), G-42-5 (effort review). Still open: G-24-3, G-26-8 (client clarifications), G-27-5 (cost version history), G-40-5 and G-40-6, G-41-5 (named links after register).
- Connect first: SCR-23 and SCR-24 (small, self-contained, and the RFP chain starts there), then SCR-16 team input and the outcome, then SCR-40 and SCR-42. SCR-27 is new and can be built straight against live.
