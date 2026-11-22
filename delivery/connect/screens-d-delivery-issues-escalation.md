<!-- Part of the connection map: see README.md. Cluster D. Written 23 Nov 2026 from live OpenAPI 1.22.0 (main 9bac3109) and the frontend at f8b28059. -->

# Cluster D: issue, change, delivery lines, emergency, escalation, leadership report (SCR-30, 31, 33, 43-52)

Sources checked: v7 `openapi.json`, `frontend/mock/fixtures/work/*.json` (the line fixtures), `frontend/src/features/workspace`, `frontend/src/features/projects/DeliveryTab.tsx`, live `psl-factory.openapi.json` (via `oa.py`), the backend handoff crosswalk, and the backend source in `apps` where a body field was unclear.

## Common to every screen in this cluster (read once; sections below say "see DC-n")
- **DC-1 Ids and tokens.** v7: `work_id` "W-2411", `case_id` "P-0101", one `expected_revision` (plus `idempotency_key` on steps). Live: integer `work_id`, uuid `case_id`, and almost every write wants BOTH `expected_revision` (work) and `case_revision` (project). Live work lines have no `idempotency_key`; a few writes take an `operation_key` uuid. Project-scoped writes (issues, meetings, escalation-register, emergency-intake) take `case_revision` or `revision` instead of a work revision.
- **DC-2 No generic step.** v7 drew every line from `GET /work/{id}` `workspace` (`sections`, `steps`, `status`, `agent_note`, `links`) and wrote through `POST /work/{id}/steps`, `POST /tasks/{id}/response`, `POST /tasks/{id}/decision`, `POST /work/{id}/assignment`. Live has none of these for these lines. Live `GET /work/{id}` gives only `tasks[]`, `panels[]` (url of the line's own read, for example `/work/{id}/release-register`), `progress`, `actions`, `output_url`; each line is read and written through its own endpoint. So the shared frame cannot draw these lines from one object: each line needs its own adapter that turns the line read into sections and the line commands into steps.
- **DC-3 Agent cards.** v7 `agent.steps[]` (text, status, source such as "ISS-0241 · 3 WEEKS OPEN"), `agent.started_at`, `agent_note.lines`, `stations[]`, `facts[]` (drafted, reviewed, approved, sent...) have no live source. Live gives `progress {status, updated_at}` on the work item and `GET /work/{id}/history` rows (`at`, `station`, `status`, `actor`, `reason`). Tola's step-by-step card with cited records cannot be filled; only a one-line status and times.
- **DC-4 Proof files.** v7: upload with `POST /cases/{case_id}/evidence` and pass `evidence_id` (a string). Live: `POST /cases/{case_id}/files` (multipart) returns an `upload_id`, not an evidence id, while the line commands ask for an integer `evidence_id` that must already be a recorded case evidence (the line reads list the allowed ones as `proofs[] {id, version, kind}`, for example kind `signature`). Which call turns an uploaded file into that evidence is not in the contract (question D-1). This hits every "Proof" field below.
- **DC-5 Who can act.** v7 sent `you_can_act` and `cannot_act_reason` per task. Live gives `tasks[].can_claim/can_decide/verdicts` (Finance-style) only for decision tasks; for these lines the allowed actions come from each line read (`actions[]`, `verdicts[]`, `can_record`, `can_correct`, `roles[]`).

---

### SCR-30 · Issue detail
**Built today:** yes (all four states) — F-30, `/work/{id}` for an issue follow-up item (line key `issue_followup`, view `default`), `src/features/workspace/Workspace.tsx` (issue branch), `AssignForm.tsx`, `useWorkspaceStep.ts`, `useWorkspaceAssign.ts`, fixtures `W-2411..2414`, `W-3609`.
**Live operations:** `GET/POST /work/{work_id}/issue-followup`; `GET/POST /projects/{case_id}/issues`, `GET/POST /projects/{case_id}/issues/{issue_id}`, `POST .../issues/{issue_id}/assignment`, `POST .../team-replies`, `GET/POST .../issues/{issue_id}/messages`; `GET /work/{id}/history`; start with `POST /work` `{line:"pmo-issues/v1", intake:{issue_id}}`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Issue reference, title, severity, status tag (HIGH · FIX IN TESTING) | work item → `workspace.sections.facts.items[]` (`severity`, `status`), `workspace.status.label/tone` | `issue-followup` → `issue.reference/title/severity/status` (Open, In Progress, Resolved, Closed) | reshaped (status words differ from "FIX IN TESTING"; tone is yours to derive) |
| Owner name ("Engineering"), raised date, age, "blocks go-live" | `facts` items `value` | `issue-followup` → `team.label` (owner or team name), `issue.owner_id` (id only; names come from `GET .../issues` `owners[]`). No raised date, no age, no "blocks" link | partly missing in live |
| What has happened (logged, owner acknowledged, owner update, Tola investigated) | `sections.happened.items[]` timeline | `issue.acknowledged_at`, `issue.resolved_at`, `team.status`, `acknowledgement {status, at, basis, reply_id}` (`GET .../issues/{id}`); `GET /work/{id}/history` | reshaped (no ready-made timeline with text) |
| Chasing (asked owner 09 Nov, reminder 11 Nov, escalate by 13 Nov) | `sections.chasing` | `GET .../issues/{id}/messages` → `items[] {kind request/reminder, status, receipt}`, `timing {reminder_due_at, escalation_due_at, reminder_overdue, escalation_overdue, escalation_target}` | new in live (richer: drafted, reviewed, delivered separately) |
| "No owner" and "no response" banners | `status` tone, `lead` text | `team.status`, `team.finding`, `finding`, `next_action`, `can_request_update` | reshaped |
| Owner choices for "Set an owner" | `workspace.assign.candidates[]` | `GET .../issues` → `owners[] {id,name}`; team keys not listed here | reshaped |
| Tola's note | `agent_note.lines` | none | missing in live (DC-3) |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Post an owner update (acknowledge / started / progress) | `POST /work/{id}/steps` `{step:"post_owner_update", inputs:{update_type, update}, expected_revision, idempotency_key}` 200 | `POST /work/{id}/issue-followup` `{action, expected_revision, case_revision, task_id, task_revision, operation:"acknowledge"\|"start"\|"progress", evidence_id, note, next_action, team_reply}` 200, or `POST /projects/{case}/issues/{issue}` `{action, case_revision, state_id, evidence_id, note, operation, next_action, owner_id, severity, fix_id, root_cause_id}` 201 | reshaped: needs proof (`evidence_id`) and a next action the design does not ask for |
| Record the owner's reply | step `record_reply` `{reply}` | `POST .../issues/{id}/team-replies` `{case_revision, state_id, assignment_id, operation_key (uuid), party, channel (email, whatsapp, ticket, meeting, phone, document), responded_at, source_ref, operation, evidence_id, note, next_action, fix_id, root_cause_id, resolution_role}` 201 (same data can ride in `issue-followup.team_reply`) | reshaped: a reply needs who, channel, when, a source reference and proof |
| Set an owner (person, team or outside party) | `POST /work/{id}/assignment` `{person_id, note, expected_revision}` | `POST .../issues/{id}/assignment` `{case_revision, state_id, mode:"team"\|"internal", team_key, recorder_id, recorder_role, evidence_id, reason}` 201 | reshaped (closes G-SCR30-3: teams are supported; but it names who records and wants proof) |
| Message the owner (ask / reminder) | none (Tola does it) | `POST .../issues/{id}/messages` actions: prepare, edit draft, review (`verdict`), release (`channel`, `not_before`), check, reconcile, recover; body per action; 201 | new in live |
| Raise an escalation | step `starts_line` opens Start work prefilled | `POST /projects/{case}/escalation-register` `{action:"request", profile_id, direction, target, evidence_id, note}` then `POST /work` for `pmo-escalation/v1` | moved |
| Refresh / restart the investigation | none | `POST /work/{id}/issue-followup` `{action:"refresh"\|"restart", reason}` | new in live |

**Design parts the live API cannot fill:**
- "Raised 09 Nov", "Age 3 days" and "Blocks Go-live" (the issue read has no raised date, no age and no link to the milestone it blocks).
- Tola's story ("Found 14 failed logins, all Android 9 or older") and her note: live keeps no agent narrative.
- The status wording "FIX IN TESTING": live status is only Open, In Progress, Resolved, Closed.

**Live data the design does not show yet (worth knowing):**
- Who can record the owner's reply, and the channel, date and source reference of each reply (all required).
- Message drafts, their independent review and delivery receipts, with reminder and escalation due times.
- Closing needs QA and PM (`role` QA/PM on the close command), as the design text says.

**Effort to connect:** L, because update, reply, owner and message are four separate commands with new required fields (proof, channel, source reference) and the timeline has to be assembled from several reads.
**Questions for the backend:**
1. D-2: `GET .../issues/{id}` and `issue-followup` carry no raised date, age or "blocks" milestone; where do these come from?
2. D-3: Is there a ready-made "what has happened" list for an issue (owner updates, reminders) or must we build it from `history`, `messages` and `acknowledgement`?
3. D-4: In `issue-followup` POST, when is `team_reply` used versus `POST .../team-replies` (same data)?

---

### SCR-31 · Change request detail
**Built today:** no (gated). Designs only: 9 states. Frame would be `/work/{id}` with line key `change_request`; the Start drawer has the line (`project`, `request`, `proof`).
**Live operations:** `GET/POST /work/{work_id}/change`; `GET/POST /projects/{case_id}/ordinary-changes`; `GET /projects/{case_id}/change-versions/{version_id}`; `POST /work/{id}/reviews`, `POST /work/{id}/corrections`, `GET/POST /projects/{case_id}/change-milestone-link`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The five stages (authorisation, notice, execution, go-live note, signatures) and where we are | not built | `change` → `stage`, `finding`, `next_action`, `can_authorize`, `can_close`, `can_restart` | new in live (stage is a string; the five-step track must be derived) |
| Impact assessments for Engineering, QA, Infra, Security | not built | `change` → `impact[] {team, status, assessment_id, summary, effort}`, `assessors[]` | same four teams as the design |
| The five deciders (Product, Engineering, Client, Engineering Lead, Security Manager) and their verdict | not built | `change` → `decisions[] {role, status, verdicts[]}` | same five roles as the design |
| Notice and go-live note documents with their review and receipts | not built | `change` → `documents[] {id, purpose "notice"\|"go_live", verdicts, receipt_ids}`, `jobs[] {id, status, can_retry}` | new in live |
| Authorisation and closure | not built | `change` → `authorization_id`, `authorization_choices[]`, `closure_id`, `deployment_authorized` | new in live |
| Change reference, category, module | not built | `ordinary-changes` → `records[] {reference, category Standard/Normal, module, description}` | new in live |

**Writes** (all `POST /work/{id}/change`, 201, `{action, expected_revision, case_revision, change_version_id, ...}`)
| What the person does | Today | Live body (action) | Fit |
|---|---|---|---|
| Record a team's impact assessment | not built | `assess` `{contributor, cost_impact, timeline_impact, client_facing, production_impact, scope_items, outputs{discipline, timeline, cost_resource, risk, dependency}, effort_person_days (string), evidence, note, proof_upload}` | reshaped: much more than "assessment, effort, proof" |
| Record a decision | not built | `decide` `{role, verdict approve/return/reject, evidence, note}` | same shape plus proof |
| Record the authorisation | not built | `authorize` `{commercial: id or null}` | reshaped: no "authorised by / on" fields, no proof |
| Record execution evidence | not built | `execution` `{kind plan_updated/implemented/testing_validated/documentation_updated, evidence, note, scope_items, dossier_id, candidate_id}` | reshaped (four typed steps, not one note) |
| Review the notice or go-live note | not built | `document_review` `{version_id, verdict, note}` | new |
| Record PM and client signatures (close) | not built | `close` `{receipt_id, pm_signature_id, client_signature_id, note, operation_key, mode signed/owner_applicability, pm_signature{...}, client_signature{...}}` | reshaped: signer details required |
| Retry delivery / restart | not built | `operate_delivery` `{job_id, operation cancel/retry, reason}`; `restart` `{reason}` | new |
| Log a new change | not built | `POST /projects/{case}/ordinary-changes` `capture` `{reference, category, module, description, reason, evidence_id}`; standard changes use `preapprove` and `bind_standard`; 201 | new |

**Design parts the live API cannot fill:**
- "Authorised by Kemi Adebayo · change authoriser · 13 Nov 10:00" as a typed record: `authorize` takes no person or time.
- "Milestone 3's scope now includes SMS reminders" after closing (the milestone link is a separate call, `change-milestone-link`).

**Live data the design does not show yet (worth knowing):**
- Standard changes (pre-approved procedures) next to Normal changes.
- Impact fields: cost, timeline, client-facing, production impact.
- Notice delivery jobs can be retried or cancelled; closing can be "owner applicability" without a client signature.

**Effort to connect:** L, nothing is built and the line has 8 commands with typed signer and proof fields.
**Questions for the backend:**
1. D-5: Must all five deciders approve every change (the design's open question)? `decisions[]` lists roles but not whether each is required.
2. D-6: `change.stage` values: please list them so we can draw the five-step track.
3. D-7: `close` needs `pm_signature`/`client_signature` source fields (source_system, decision_id...); what does a PM enter for a client who does not log in?

---

### SCR-33 · Project retrospective
**Built today:** no (F-40 part 2, not started). Designed as a closure-line step; no route.
**Live operations:** `GET/POST /projects/{case_id}/meetings` (kind `retrospective`), `GET /projects/{case_id}/meetings/options`, `GET .../meetings/{meeting_id}`, `POST .../meetings/{meeting_id}/actions`, `POST /projects/{case_id}/actions/create`, `GET /projects/{case_id}/delivery/{dossier_id}/closure-checklist` (shows whether a retrospective is current).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Project and "needed before closure" | not built | `GET /projects/{case_id}`; `closure-checklist` → `checks[]` key `retrospective` | new in live |
| Saved retrospectives and their versions | not built | `meetings?kind=retrospective` → `items[] {id, version_id, version, reference, occurred_at, purpose}` | new in live |
| One retrospective's text, who took part, decisions | not built | `meetings/{id}` → `summary`, `participants[] {id,label}`, `decisions[] {text, evidence_id}`, `actions[]` | reshaped (one `summary`, not three headed boxes) |
| People who can be named as taking part, proof files | not built | `meetings/options` → `participants[]`, `owners[]`, `proofs[]` | new in live |
| Closure checklist strip (go-live, hypercare, archive, handover, retrospective, finance) | not built | `closure-checklist` → `checks[] {key, title, status current/held/unknown/closed/recorded/unavailable, summary, references, finding}`, `ready_to_prepare` | reshaped (also has `context` and `report` checks) |

**Writes**
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Save the retrospective | not built | `POST /projects/{case}/meetings` `{revision, reference, kind:"retrospective", occurred_at, purpose, summary, participant_ids[], decisions[{text, evidence_id, change_evidence_id?}], evidence_id, meeting_id?}` 201 (append a revision with `meeting_id`) | reshaped |
| Save a draft | not built | none | missing in live |
| Make a follow-up action from a lesson | not built | `POST /projects/{case}/actions/create` `{revision, reference, description, owner_id, due_at, evidence_id, reason, meeting_id, calculated, change_evidence_id}` 201, then `POST .../meetings/{id}/actions` `{revision, action_id, evidence_id}` 201 | new |

**Design parts the live API cannot fill:**
- Three separate headed texts (what went well, what did not, lessons) with their own "Cites": live has one `summary` and `decisions[]` each needing proof.
- "Save draft": every save is a recorded version.

**Live data the design does not show yet (worth knowing):**
- Each save needs an exact evidence (the notes file) and a reference; later saves append versions.
- Decisions in a retrospective can carry a change evidence and become project actions.

**Effort to connect:** M, one form and two reads, but the three-box layout must be packed into `summary` (or structured by convention) and the proof path (DC-4) must work.
**Questions for the backend:**
1. D-8: Where do "went well / did not / lessons" go: three headed sections inside `summary`, or `decisions[]`? Is there a draft state?
2. D-9: Can `GET /projects/{case}/meetings` `kind=retrospective` be filtered to the current one the closure checklist selects (`retrospective_id`)?

---

### SCR-43 · Delivery overview
**Built today:** yes (read only) — F-32, route `/projects/{caseId}/delivery`, `src/features/projects/DeliveryTab.tsx`, `model.ts` (`deliveryRowsOf`, `deliveryAgentOf`, `deliveryNoteOf`).
**Live operations:** `GET /projects/{case_id}` (journey `items[]`, `tabs[]`), `GET /work/{work_id}` per line, `GET /work/{id}/release-register`, `GET /work/{id}/planning-exit`, `GET /projects/{case}/delivery/{dossier}/closure-checklist`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The Delivery tab itself | `GET /projects/{id}` `delivery[]` (a mock proposal, not in v7 openapi) | none: live tabs are journey, milestones, documents, templates, money, month-end, registers, actions, hr; `GET /projects/{case}/{tab}` accepts only milestones/documents/registers/actions | missing in live |
| The six lines in order with number, title, reference, gate tag, date | `delivery[] {line_key, title, short_title, state, reference, gate{label,tone}, at, detail, work_id}` | `GET /projects/{case}` `items[] {id, line, reference, state, started, updated, api_url}` (only lines already started; no gate wording or tone) | reshaped; rows must be derived by filtering `items` to the six delivery lines |
| "3 of 6 done", file reference DLV-0052, line-order sentence | `delivery_summary` (proposal) | none | missing in live |
| Tola's delivery check and "Next" sentence | `delivery_agent`, `next` | none | missing in live (DC-3) |
| Closure not yet startable: why | row `detail` | `closure-checklist` → `ready_to_prepare`, `checks[]` | new in live |
| Release gate state per project | row gate | `release-register` → `phases[] {name, checks[]}` | new in live |

**Writes:** none today (read only). Live has no start-from-overview call; lines start with `POST /work` per line (`delivery-release/v1`, `-go-live/v1`, `-hypercare/v1`, `-archive/v1`, `-handover/v1`, `-closure/v1`) with `intake {dossier_id, ...}`.
| What the person does | Today | Live | Fit |
|---|---|---|---|
| Open a line | link to `/work/{work_id}` | `items[].api_url` `/api/v1/work/{id}` | same idea, integer ids |

**Design parts the live API cannot fill:**
- The whole tab as one read: no `delivery[]`, no gate label ("RELEASE READY · 25 MAR"), no "3 of 6 done", no project delivery file number, no Tola delivery check.
- Rows for lines not yet started ("06 Closure — NOT YET"): live `items` only lists started work.

**Live data the design does not show yet (worth knowing):**
- Per-line detail panels (`panels[]` on each work item) and the closure checklist with what holds closure.
- Journey `facts` (counts of waiting and stopped work).

**Effort to connect:** M, the tab can be composed in the frontend from `items` plus each line's read, but several parts are not available, and counting "done" would be a frontend rule (D-PROJECTS-VIEW says the backend composes it).
**Questions for the backend:**
1. D-10: Will there be a delivery overview read (the six lines, their gate state, reference and date, even before started)? Today the design needs `delivery[]`.
2. D-11: Which `GET /projects/{case}` `items[].line` values are the six delivery lines? Please give stable keys (today a display title).

---

### SCR-44 · Release gates
**Built today:** yes, partly — F-32 (waiting, decision, returned, owner-needed, readiness, ready), line key `delivery_release`, `/work/{id}` (fixtures W-2501..2510), `Workspace.tsx`, `InlineDecide.tsx`.
**Live operations:** `GET/POST /work/{id}/release-register`, `GET/POST /work/{id}/planning-exit`, `POST .../planning-exit/workaround`, `GET/POST /projects/{case}/delivery/{dossier}/client-testing` (+ `/pack`, `/files`), `GET/POST /setup/{case}/decision-appointments`, `GET /setup/{case}/policy-configurations`, `POST .../review`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Release gates list (PMO Lead assigned, client UAT recorded, Planning decision, readiness) | work item → `sections.gates.items[] {text, status, held_by, tag, due}` | `release-register` → `phases[] {name, checks[] {key, title, authority, status, records[{id,type}]}}`; `planning-exit` → `checklist[] {name, status}` | reshaped (phases and checks; status is free text) |
| What you are deciding (delivered vs plan, UAT, open issues, changes since SOW) | `sections.deciding` facts | `planning-exit` → `packet` (a fingerprint string), `checklist`, `blockers[] {id, reference}` | partly missing: figures like "4 of 4 stages built" are not given |
| Client UAT response and pack | gate row text | `client-testing` → `outcome` (approved, changes_requested, rejected, approved_with_workaround), `proof_current`, `gate_id`; `/pack` | new in live |
| Returned decision and "send again" | `status` + steps | `planning-exit` → `workaround {return_id, issue_state_id, response_id, review_id}`, `blockers[]` | reshaped |
| Owner needed (no PMO Lead) | status `owner_needed` | `GET /work/{id}` `state: owner_needed`; `GET /setup/{case}/decision-appointments` → `appointments[]`, `people[]`, `can_draft` | reshaped |
| Readiness note and "release ready" | `sections.readiness`, `ready` | `release-register` → `readiness_ids[]`, `release {reference, released_at, environment, evidence_id}` | reshaped |
| Tola's check | `sections.checks` | none | missing in live (DC-3) |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Approve or return the planning decision | `POST /tasks/{id}/claim`, then `POST /tasks/{id}/decision` `{expected_revision, verdict approve/return, note}` | `POST /work/{id}/planning-exit` `{expected_revision, case_revision, packet, verdict approve/return/reject, evidence_id, note, issue_id?}` 200 | reshaped: no claim step; needs the packet fingerprint and an evidence id the design does not ask for; "return" can link the blocking issue |
| Link the client's workaround after a return | none | `POST /work/{id}/planning-exit/workaround` `{return_id, issue_state_id, response_id, review_id, note, ...}` 201 | new |
| Record release sources and gates | none | `POST /work/{id}/release-register` 200, actions `capture_source` (10 kinds), `verify_source`, `capture_gate` (qa_exit, uat_product_manager, uat_product_owner, uat_client, engineering_go, glpi_security, glpi_cto, glpi_ceo), `verify_gate`, `record_progress`, `record_glpi_request` | new |
| Prepare readiness | agent does it after approval | `release-register` `{action:"prepare_readiness"}` | moved (human-triggered in live) |
| Record the actual release | in hypercare | `release-register` `{action:"observe_release", readiness_id, released_at, reference, evidence_id, note, environment, private_log_id}` | moved |
| Client testing | not in design | `POST .../client-testing` actions target/response/inspect/review/export/retract; `.../pack` record/verify/schedule | new |

**Design parts the live API cannot fill:**
- "Approve for release" with only an optional note: the live decision needs the packet and an evidence id.
- The "Decide" panel figures (stages built, open issues by severity, changes since SOW).

**Live data the design does not show yet (worth knowing):**
- Release is gated by eight named records (QA exit, UAT sign-offs, Engineering go, GLPI security/CTO/CEO).
- Client UAT pack tracking, reply deadline and reminders.
- A blocked decision names the blocking issues.

**Effort to connect:** L, the gates list changes from four rows to phases and typed records, and the decision write is a different operation with new required fields.
**Questions for the backend:**
1. D-12: What evidence does `planning-exit` expect in `evidence_id` (the list is `proofs[]`)? Can the decision be recorded with only a note, as the design shows?
2. D-13: Who triggers `prepare_readiness`: the PM by click, or the system once approved (the design says Tola)?
3. D-14: Please list the `release-register` `phases[].name` and `checks[].status` values, so we can draw the tags.

---

### SCR-45 · Go-live acceptance
**Built today:** no (F-32 part 3, not started). Only a plain target W-2510 and a `go_live_acceptance` response variant in `src/features/response/contract.ts`.
**Live operations:** `GET/POST /work/{id}/go-live-signoff`, `GET/POST /work/{id}/go-live-replies`, `GET/POST .../go-live-replies/decline`, `POST .../go-live-replies/successor`, `POST /work/{id}/go-live-milestone`, `POST /work/{id}/reviews` (document), `POST /work/{id}/corrections`, `POST /setup/{case}/policy-configurations/{id}/review`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Go-live document version, in review, attachments | not built | `go-live-signoff` → `version_id`, `receipts[] {id, recorded_at}`, `prior_acceptance_id`; document review via work `tasks[]` | new in live |
| Sent date and delivery confirmed | not built | `receipts[].recorded_at` | reshaped |
| Client reply on file (changes, declined) | not built | `go-live-replies` → `replies[] {id, receipt_id, version_id, number, outcome changes_requested/declined/withdrawn, party, channel, responded_at, note, evidence_id}` | reshaped |
| What this unlocks (hypercare, archive, handover, milestone) | not built | `go-live-replies` → `milestone {recorded_id, configuration_id, name, acceptance_id, proof_ids, owner_decision_ids}`, `linked_issues[]`, `reviewed_handoffs[]` | new in live |
| Declined: options to fix | not built | `go-live-replies/decline` → `issues[]`, `new_candidates[]`, `review_options[]`, `rules` | new in live |
| Signature proof choices | not built | `go-live-signoff` → `proofs[]` (evidence kind `signature`) | new in live |

**Writes**
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Record "Signed" (client and PM) | not built (design: one form, one proof) | `POST /work/{id}/go-live-signoff` `{expected_revision, case_revision, version_id, receipt_id, pm_signature_id, client_signature_id, signers{PM,Client each {source_system, source_reference, decision_id, decision_version, signer_reference, signed_at}}, mode fresh_signatures/metadata_binding, prior_acceptance_id, note}` 200 | reshaped: two signature evidences, signer details for both |
| Record "Asked for changes" / "Declined" | not built | `POST /work/{id}/go-live-replies` `{action:"record_reply", receipt_id, previous_id, outcome, party, responded_at, channel, evidence_id, note, role, attested}` 201 | reshaped |
| Prepare v2 after changes | not built | `POST .../go-live-replies/successor` `{inputs{template_id, checklist, incident_reporting, rollback}, reason}` 200 | new |
| Declined: log an issue / new candidate / review | not built | `go-live-replies` actions `link_decline_issue`, `prepare_new_candidate`, `review_remediation` 201 | new |
| Mark milestone complete | design says "Mark milestone 3 complete" | `go-live-milestone` `draft_mapping {name, owner_decision_id}` then `record_completion {configuration_id, acceptance_id, evidence_id}` 201 | reshaped (two steps; the first drafts a mapping that needs a decision) |
| Review the go-live document | not built | `POST /work/{id}/reviews` `{kind:"document", version_id, verdict, note}` 200 | new |

**Design parts the live API cannot fill:**
- One "What the client did: Signed / Asked for changes / Declined" form with a single proof: live splits signed (signoff) from reply (replies) and wants a separate signature evidence for PM and client.
- The unlock list "Hypercare can be evaluated: RUNNING" as one read (parts exist in the hypercare and milestone reads).

**Live data the design does not show yet (worth knowing):**
- Reply channels (email, customer_portal, meeting, phone, other) and the recorder's role and attestation.
- Metadata-only binding of an earlier acceptance.
- Response rules (who may record, correct, remediate) are set through `go-live-replies/decline` POST and reviewed in Setup.

**Effort to connect:** L, not built, three write paths plus the milestone mapping.
**Questions for the backend:**
1. D-15: Is "signed" always two separate signature evidences (PM and client), or can one uploaded signed copy serve both?
2. D-16: What does the PM enter for `signers.*.source_system`, `decision_id`, `decision_version` (the client does not log in)?
3. D-17: `go-live-milestone` `draft_mapping` needs `owner_decision_id`; who is the owner and when is this done before "Mark milestone complete"?

---

### SCR-46 · Hypercare
**Built today:** yes, partly — F-34 part 1, line key `delivery_hypercare`, `/work/{id}` (fixtures W-3101..3120), `Workspace.tsx` (steps `log_observation`, `record_release`). Part 3 not built.
**Live operations:** `GET/POST /work/{id}/stability`, `POST .../stability/criteria`, `GET/POST .../stability/events`, `GET/POST /work/{id}/release-register`, `POST /work/{id}/background`, `POST /setup/{case}/policy-configurations/{id}/review`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Day 10 of 30, status | `workspace.status.label` | `stability` → `due_at`, `verified`, `qualified`, `assessment_id`, `checks[] {name release/acceptance/stability, status ready/held, finding}`, `findings[]` | reshaped (no day count; derive from `criteria.minimum_hours`, `due_at`) |
| Observations list (issue, note, incidents: ref, what, state) | `sections.observations` table | `stability` → `observations[] {owner Engineering/Infrastructure, source_id, verification_id}` | reshaped: live observations are owner readings, not issue or note rows |
| Criteria (window, no high issues, no incidents, medium issues owned) with MET / NOT MET | `sections.criteria.items[]` | `stability` → `criteria {clock, minimum_hours, confirmation_owners, metrics[{key, unit, owner, operator, threshold}], financial_controls, issue_clearance{scope, blocking_statuses, blocking_severities}}`; no per-criterion MET / NOT MET | reshaped |
| Setup needed (no criteria) | status `setup_needed` | `stability` → `criteria: null`, `can_draft_criteria`, `checks[].status held` | reshaped |
| Qualified / not met / evaluating | `sections.evaluation`, status | `qualified` (true/false/null), `verified`, `assessment_id` | reshaped |
| Release recorded? and acceptance | in the record step | `stability/events` → `can_record_release`, `readiness_ids[]`, `release_evidence[]`, `private_logs[]`, `signatures[]`, `acceptance_packet`, `receipts[]` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Record the release | `POST /work/{id}/steps` `{step:"record_release", inputs{version, released_at, environment}, evidence_ids[1], idempotency_key}` | `POST /work/{id}/stability/events` `{action:"release", readiness_id, released_at, reference (the version), evidence_id, note, environment, private_log_id}` 201 (or `release-register` `observe_release` 200) | reshaped (`version`→`reference`, proof→`evidence_id`, plus readiness and log) |
| Log an observation | step `log_observation` `{what, proof}` | `POST /work/{id}/stability` `{configuration_id, owner Engineering/Infrastructure, observed_at, confirmed, reference, evidence_id, metrics{...}, verify_sample?}` 201 | reshaped: a metric reading by a named owner, not a free-text note |
| Record go-live acceptance here | none (SCR-45 owns it) | `stability/events` `{action:"acceptance", packet, receipt_id, pm_signature_id, client_signature_id, signers, note}` | new (same as SCR-45 signoff) |
| Set the criteria | admin in Setup | `POST .../stability/criteria` `{case_revision, criteria, evidence_id, effective_from}` 201, then `policy-configurations/{id}/review` | moved |
| Pause or continue Tola's evaluation | none | `POST /work/{id}/background` `{expected_revision, enabled}` 202 | new |

**Design parts the live API cannot fill:**
- Observation rows like "ISS-0301 Login slow · medium · OPEN" and "OBS-0012 noted": live observations are metric readings by Engineering or Infrastructure; issues enter only through `issue_clearance`.
- "Log an issue" from this screen.
- "Day 10 of the window": live has `minimum_hours` and `due_at` only.

**Live data the design does not show yet (worth knowing):**
- Release evidence and a private deployment log choice.
- Two observation owners must confirm; thresholds are metric based (lte, gte, eq).
- Whether the release and acceptance checks are ready or held, with a finding text.

**Effort to connect:** L, the observation form, observation list and criteria list are different in meaning.
**Questions for the backend:**
1. D-18: Should "log an observation" in the PM's hands record a metric reading (`stability` POST) or a free note? How should an open issue appear in the list?
2. D-19: Is there a per-criterion result (MET / NOT MET) to draw, or only `qualified` plus `findings[]`?

---

### SCR-47 · Archive
**Built today:** no (F-34 part 3). Designed states default, working, uncertain.
**Live operations:** `GET/POST /work/{id}/archive-files`, `POST .../archive-files/{job_id}/recovery`, `POST .../archive-files/rules`, `GET /work/{id}/history`, `POST /work/{id}/corrections`, `GET /projects/{case}/intake-sources`, `POST /work` (`delivery-archive/v1`, `intake {dossier_id, inventory}`).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Archive index: file groups (RFP, costing, planning, release, minutes) with counts and state | not built | `archive-files` → `files[] {id, name, status, job{id, revision, state pending/leased/unknown/missing/confirmed/held}, actions[lookup,retry], receipt{id,at}}` (one row per file, no group) | reshaped (groups must be derived from names or `sources[]`) |
| "42 files, each matched" and verified | not built | `verified`, `finding`, `plan_id`, `store` | reshaped |
| What can be archived | not built | `sources[] {id, label}`, `required_source_ids[]`, `can_reserve`, `limited` | new in live |
| Copying: 28 of 42 | not built | count `files[].job.state` | reshaped |
| Not confirmed 6 of 42 | not built | files with `job.state unknown` and `actions` lookup/retry | reshaped |
| Storage rule "keep, never purge" | not built | `store` (adapter name) only | partly missing |

**Writes**
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Start the archive | none (Tola archives, "no approval step") | `POST /work/{id}/archive-files` `{expected_revision, case_revision, source_ids[]}` 202 queued | new: a person picks the sources and reserves |
| Check files the store did not confirm | design: an admin marks each file found or not found | `POST .../archive-files/{job_id}/recovery` `{revision, action:"lookup"\|"retry"}` 200 | reshaped: the system looks up; the person does not mark found or not found; retry only after a lookup says missing |
| Reconcile the work | v7 `POST /work/{id}/actions` `{action:"reconcile", outcome, evidence_id}` | `POST /work/{id}/actions` `{expected_revision, action:"reconcile"}` 202 | reshaped (no outcome or evidence) |
| Draft the store rules | Setup | `POST .../archive-files/rules` `{case_revision, adapter, operator_id, max_files, max_bytes, lease_seconds, evidence_id}` 201 | moved |

**Design parts the live API cannot fill:**
- File groups by stage with counts.
- "Archiving has no approval step": live needs a person to reserve (select sources).
- "Mark each file found or not found" by hand.

**Live data the design does not show yet (worth knowing):**
- Per-file receipts, store name, limits (`limited`), and a held state when the rule is missing.

**Effort to connect:** M, one read and three small writes, but groups and the manual check change.
**Questions for the backend:**
1. D-20: Does `files[]` carry a group or source kind (RFP, costing...), or must we group by `sources[].label`?
2. D-21: Is archive started by a person (`reserve` with `source_ids`) or by the system after go-live? Can it default to `required_source_ids`?

---

### SCR-48 · Handover to Support
**Built today:** yes — F-40 part 1, line key `delivery_handover`, `/work/{id}` (fixtures W-3701..3720), `Workspace.tsx` + `ResponseDrawer.tsx` (`SupportHandoverForm`), `src/features/response/useResponse.ts`.
**Live operations:** `GET/POST /work/{id}/support-receipt`, `GET/POST /work/{id}/support-replies`, `POST /work/{id}/corrections`, `POST /work/{id}/actions`, `POST /work/{id}/reviews` (document review), `GET /projects/{case}/intake-sources`, `POST /work` (`delivery-handover/v1`, `intake {dossier_id, inputs{template_id, support_document, escalation_document}}`).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Handover version, draft, attachments | `sections.handover.items[]` with cites | work item `tasks[]` (document review), `GET /work/{id}` | missing in live (no document summary on the handover reads) |
| "Review needed? NO · below the rule's threshold" | facts item | none | missing in live |
| Support's reply: received or gaps, who, when | task + `receipt` | `support-replies` → `receipts[] {id, recipient, recorded_at, previous_id, status received/gaps, reply}` | reshaped |
| Gaps list (two gaps) | `sections.gaps` (`gaps[]` proposal) | `reply` object (free), `note` | missing in live as a list |
| Who can record, channels, proofs | `response` block | `support-replies` → `roles[]`, `channels[]` (email, whatsapp, client_portal, signed_document, meeting), `can_record`, `proofs[]` | reshaped |
| Recipient's own acknowledge | not in design (Support has no login) | `support-receipt` → `receipts[] {id, can_acknowledge, status}`, `proofs[]` | new in live |
| Tola's work | `sections.tola` | none | missing in live (DC-3) |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Publish to Support | `POST /work/{id}/steps` `{step:"publish", idempotency_key}` | none: publication is reserved by the system under a configured publisher after the document review; the person only reviews (`POST /work/{id}/reviews` `{kind:"document", version_id, verdict, note}`) | missing in live |
| Record Support's reply (received or gaps) | `POST /tasks/{id}/claim`, then `POST /tasks/{id}/response` `{expected_revision, who, action:"approved"\|"changes_requested", responded_at, evidence_id, attested:true, gaps[]?, received_via, note}` 200 | `POST /work/{id}/support-replies` `{expected_revision, case_revision, receipt_id, previous_id, status:"received"\|"gaps", evidence_id, note, party, channel, responded_at, role}` 201 | reshaped (`action`→`status`, `who`→`party`, `received_via`→`channel`, `attested` gone, role added, gaps only inside `note`) |
| Support acknowledges itself | none | `POST /work/{id}/support-receipt` `{receipt_id, evidence_id, status, note}` 200 | new |
| Ask Tola to draft v2 | step `draft_v2` | `POST /work/{id}/corrections` `{expected_revision, case_revision, line, reason, source{inputs{template_id, support_document, escalation_document}}}` 200 | reshaped |
| Reconcile an uncertain delivery | `POST /work/{id}/actions` `{action:"reconcile", outcome, evidence_id}` | `POST /work/{id}/actions` `{action:"reconcile"}` 202 | reshaped |

**Design parts the live API cannot fill:**
- The "Publish to Support" button (the system publishes after review).
- Gaps as numbered separate rows (G-48-1 stays open: only `note`).
- Handover document summary ("Support handover v1 DRAFT", attachments).

**Live data the design does not show yet (worth knowing):**
- Support recipients can acknowledge for themselves; the PM's record is the fallback and keeps the recorder's name.
- The recorder's role is checked; a record can replace an earlier one (`previous_id`).

**Effort to connect:** M, the response form is the same shape with renamed fields; the publish step and the document summary are missing.
**Questions for the backend:**
1. D-22: Where does the PM see and trigger "Publish to Support", or is it automatic after review? Which field says "ready to publish"?
2. D-23: Can `support-replies` carry gaps as a list (`gaps[]`) rather than inside `note`?
3. D-24: Which read gives the handover document title, version and attachments?

---

### SCR-49 · Closure
**Built today:** partly — only the blocked state as a generic fixture (W-2003, screen SCR-49, line key `delivery_closure`); no dedicated build (F-40 part 3 not started).
**Live operations:** `GET /projects/{case}/delivery/{dossier}/closure-checklist`, `POST /work/{id}/reviews` (`kind:"closure"`), `POST /work/{id}/closure-report`, `POST /work/{id}/corrections`, `GET /work/{id}`, `GET /projects/{case}/intake-sources`, `POST /work` (`delivery-closure/v1`, `intake {dossier_id, inputs}`).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The six prerequisites (go-live, hypercare, archive, handover, retrospective, finance) with DONE / NOT YET / UNKNOWN | `sections.closure.items[] {text, status, held_by, due}` | `closure-checklist` → `checks[] {key, title, status current/held/unknown/closed/recorded/unavailable, summary, references[], finding}`; keys: context, go_live, hypercare, archive, handover, retrospective, finance, report | reshaped (adds "Current project scope" and "PM closure report" checks) |
| Finance confirmation UNKNOWN / CONFIRMED | `criteria` facts | `checks[key=finance]` ("Finance notification coverage": confirms the milestone notification inventory; `unknown` until Finance confirms) | reshaped: answers part of G-49-2; this is not "debts confirmed" |
| Closure report and the decision | `sections.findings` | the closure report is evidence (`report_evidence_id`); `closure-checklist?report_evidence_id=&retrospective_id=` | reshaped |
| Closed: what stays open (INV-0533 owed) | `sections` | `closure-checklist` → `recorded_closure_id`, check `context` status `closed` | missing in live (no unpaid-invoice list here) |
| Awaiting Head of PMO | `status.label` | work `tasks[]` (`can_decide`, `verdicts`), `state` | reshaped |
| Tola's checks | `agent` | none | missing in live (DC-3) |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Close or return | `POST /tasks/{id}/claim` + `POST /tasks/{id}/decision` `{verdict approve/return, note}` | `POST /work/{id}/reviews` `{kind:"closure", expected_revision, case_revision, version_id, evidence_id, verdict approve/return/reject, note}` 200 | reshaped: needs the report version and an evidence id; no separate claim |
| Replace the report after a return | step "Ask Tola to update the report" | `POST /work/{id}/closure-report` `{expected_revision, case_revision, previous_evidence_id, report_text (16 000 chars), source_reference, reason}` 201 | reshaped (a person supplies the report text) |
| Correct sources | none | `POST /work/{id}/corrections` | new |
| Finance confirmation | none in design | the entry that records it (`delivery.finance_confirm`) is not in the OpenAPI | missing in live |
| Write the retrospective | link to SCR-33 | `POST /projects/{case}/meetings` kind retrospective | see SCR-33 |

**Design parts the live API cannot fill:**
- "Closing makes the project read-only / moves to Closed in Projects" as a read: live says the closure record exists (`recorded_closure_id`, check `closed`); nothing about project lifecycle.
- "INV-0533 stays owed": no debt list on closure reads (use the finance reads).
- A closure item before the line starts (`blocked` state): live does not describe one; `ready_to_prepare` is the nearest.

**Live data the design does not show yet (worth knowing):**
- Two extra checks (current scope, PM closure report) that hold closure.
- Selecting a specific retrospective or report evidence changes the checklist result.

**Effort to connect:** M, one checklist read and one decision write, plus report text replacement.
**Questions for the backend:**
1. D-25: How does Finance record its confirmation (milestone notification coverage)? No operation is listed.
2. D-26: In `reviews` `kind:"closure"`, what is `evidence_id` (the closure report evidence)? Is `version_id` the closure document version?
3. D-27: Can closure reads carry the open debt list (the design's "still open after closure")?

---

### SCR-50 · Emergency change
**Built today:** no (F-39 parts 3 and 4 not started). Boards: record, refused, review, retro, report.
**Live operations:** `GET/POST /work/{id}/emergency`, `GET/POST /projects/{case}/emergency-intake` (+ `/{version_id}`), `GET/POST /projects/{case}/emergency-outcomes/{outcome_id}/followups` (+ `/{followup_id}`), `GET/POST /projects/{case}/authority-recoveries` (+ `/{request_id}`), `POST /work/{id}/reviews`, `POST /work/{id}/actions`, `POST /work/{id}/corrections`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The incident, 4 steps (preauthorise, implement, retrospective, report) | not built | `emergency` → `incident_id`, `critical_production`, `p1`, `stage`, `finding`, `actions[]` (preauthorization_decision, authorize, capture_outcome, record_review, retrospective_decision, reconcile_retrospective) | new in live |
| Who must decide (CTO, Engineering Lead, ...) and who did | not built | `emergency` → `options[] {role, authority_role, verdicts}`, `decisions[] {id, role, authority_role, verdict}` | new in live |
| Authorised by Segun Okoro · CTO · 13 Nov 08:05 | not built | `authorization_id`, `recorded_authorizations[]` (ids only; names and times not shown) | partly missing |
| Outcome: logins restored 08:16, customers affected, side effects | not built | `outcome_id`, `recorded_outcomes[]` (ids); the text is the evidence note | partly missing: no `customers_affected`, no `side_effects` fields (G-SCR50-2 not closed) |
| Report delivered and receipts | not built | `document_version_id`, `review_verdicts[]`, `receipt_ids[]` | reshaped |
| Retrospective follow-up change | not built | `.../emergency-outcomes/{id}/followups` list of ordinary changes | new in live |

**Writes** (`POST /work/{id}/emergency`, 201, `{action, expected_revision, case_revision, profile_id, ...}`)
| What the person does | Today | Live body (action) | Fit |
|---|---|---|---|
| CTO pre-authorisation (approve / refuse) | not built | `preauthorization_decision` `{role, authority_role, verdict approve/return/reject, evidence_id, note}` | new; the refused board = verdict `reject` |
| Authorise the effect | not built | `authorize` `{}` | new |
| Record what was done | not built (design: what was done, recorded by, proof) | `capture_outcome` `{evidence_id, note, implemented_at}` | reshaped (`implemented_at` required) |
| Confirm the outcome ("Confirm outcome / Return with a note") | not built | `record_review` `{evidence_id, note}` (no verdict) | reshaped: no "return" option on this action |
| Retrospective decision (accept or needs follow-up) | not built | `retrospective_decision` `{role Product/Engineering Lead, verdict, evidence_id, note}`; follow-up via `followups` `create` `{reference, category, module, description, note, evidence_id}` | reshaped |
| Review the report | not built | `POST /work/{id}/reviews` `{kind:"document", version_id, verdict, note}` | new |
| Reconcile the result | not built | `reconcile_retrospective` `{}` or `POST /work/{id}/actions` `{action:"reconcile"}` | new |
| Start an emergency | not built | `POST /projects/{case}/emergency-intake` `{revision, request_id (uuid), incident_id, module, plan}` 201; classify with `POST .../{version_id}` | new |
| Ask for authority recovery | not built | `POST /projects/{case}/authority-recoveries` | new |

**Design parts the live API cannot fill:**
- "Customers affected UNKNOWN · BANK TO CONFIRM" and "Side effects NONE FOUND" as structured fields (only note and evidence).
- "Confirm outcome / Return with a note": the review command has no verdict.

**Live data the design does not show yet (worth knowing):**
- `critical_production` and `p1` classification, which decide who must pre-authorise.
- Historical-authority recovery requests and linked follow-up ordinary changes.

**Effort to connect:** L, nothing built; six commands and several roles.
**Questions for the backend:**
1. D-28: `record_review` has no verdict; how does the reviewer return an outcome?
2. D-29: Where do "customers affected" and "side effects" go in the outcome record?
3. D-30: Which read gives the names and times of the authoriser and outcome recorder (`recorded_authorizations` is ids only)?

---

### SCR-51 · Escalation
**Built today:** partly — F-39 part 1 (investigating, decide, not-escalated, draft); review and received not built. Line key `escalation`, `/work/{id}` (fixtures W-3601..3609), `Workspace.tsx`, `InlineDecide.tsx`.
**Live operations:** `GET/POST /projects/{case}/escalation-register` (+ `GET .../{request_id}`), `GET/POST /work/{id}/escalation`, `POST /work/{id}/reviews`, `POST /work/{id}/actions`, `POST /work/{id}/corrections`, `POST /work` (`pmo-escalation/v1`, `intake {request_id, template_id}`).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Raised by, from issue, "asked for: escalate to the client" | `sections.raised` facts | `escalation` → `id`, `direction escalate/de_escalate`, `target Client/PMO/CTO`; register → `issues[] {id, reference}`, `profiles[] {classification}`, `requests[]` | reshaped (no issue title or age on the work read) |
| What Tola found (15 days late, delays milestone 3, asked 3 times) | `sections.found` facts | none | missing in live |
| Stage (investigating, decide, drafted, review, received) | `stations`, `status` | `escalation` → `stage`, `next_action`, `document_version_id`, `can_request_communication_review` | reshaped |
| Decision available to you | task `decision` | `client_decisions[] {role PMO Lead/Head of PMO, verdicts}`, `history[] {id, request_id, role, verdict, created_at}` | reshaped |
| Message draft (v1) and review | `sections.message` | `document_version_id`, `review_verdicts[]` (text not on this read) | partly missing |
| Delivery receipts and uncertain jobs | `recipients` | `receipts[] {id, publication_id, recorded_at}`, `jobs[] {id, state, operations cancel/retry}` | reshaped |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Escalate / Don't escalate | `POST /tasks/{id}/claim` + `POST /tasks/{id}/decision` `{verdict approve\|reject, note}` | `POST /work/{id}/escalation` `{action:"decide_client_action", expected_revision, case_revision, request_id, role PMO Lead/Head of PMO, verdict approve/return/reject, note, delegated}` 200 | reshaped (likely approve = escalate, reject = don't; confirm; `return` also exists) |
| Send the message for review | step `send_for_review` | `escalation` `{action:"request_communication_review", version_id}` 200 | reshaped |
| Approve and send / return | `POST /tasks/{id}/decision` | `POST /work/{id}/reviews` `{kind:"document", version_id, verdict, note}` 200 | moved |
| Recover or check a send | `POST /work/{id}/actions` `{reconcile, outcome}` | `escalation` `{action:"check_original_delivery"}` or `{action:"recover_delivery", job_id, operation cancel/retry, reason}` | reshaped |
| Raise an escalation | Start work `escalation` (`project`, `from_issue`, `escalate_to`) | `POST /projects/{case}/escalation-register` `classify` `{issue_id, state_id, classification, timeline_impact, trigger_at, evidence_id, note}` then `request` `{profile_id, direction, target, evidence_id, note}` 201; then `POST /work` | reshaped (two commands, both need proof) |

**Design parts the live API cannot fill:**
- Tola's findings facts and investigation steps.
- Message text on the work read (only `document_version_id`; the text sits in the document reads).
- The reason on a "not escalated" decision: `history[]` has `role`, `verdict`, `created_at`, not the note.

**Live data the design does not show yet (worth knowing):**
- Escalation can be a de-escalation, or target PMO or CTO.
- Classification (unclassified, internal, client_dependent) and a delegated-decision flag.

**Effort to connect:** M, same flow with different shapes; the review and received states are not built yet.
**Questions for the backend:**
1. D-31: Which `verdict` means "Don't escalate" (`reject` or `return`)? Is the note returned in `history[]`?
2. D-32: Which read gives the drafted message text and recipients for the review screen?

---

### SCR-52 · Leadership report
**Built today:** yes — F-35, line key `leadership_report`, `/work/{id}` (fixtures W-3201..3212), `Workspace.tsx`, `InlineDecide.tsx`; the Start work drawer line `leadership_report` (`report`, `report_date`, `audience`).
**Live operations:** `GET/POST /projects/{case}/leadership-report-intake`, `GET/POST /work/{id}/leadership-report`, `POST /work/{id}/reviews`, `POST /work/{id}/actions`, `POST /work/{id}/corrections`, `GET /work/{id}/history`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Setup: report type, period, include, template, audience | Start work line fields (`report`, `report_date`, `audience` display) | `leadership-report-intake?kind=` → `sources[] {id, evidence_id}` (per domain, paged), `templates[]`, `all_projects_available`, `setup_actions[]`, `owner_evidence[]` | reshaped (project-scoped; record-level choices) |
| Drafting progress | `agent` steps | `GET /work/{id}` `progress`, `state` | missing in live (DC-3) |
| Report figures (projects covered, milestones, escalations, invoices) | `sections.report` figures | `leadership-report` → `editable_sections` (monthly: delivery_health, risks, performance, escalations, critical_incidents; Tuesday: progress, risks, blockers, dependencies; each `{text, evidence_ids, coverage}`) | reshaped (text sections, not figures) |
| Review panel and "Projects covered 5 of 5" | `held` facts | `selection`, `scope {mode, actor, configuration, domains}`, `review_verdicts[]` | partly missing (no coverage count) |
| Recipients and receipts | `sections.recipients` | `recipients[] {name, status, receipt_id, recorded_at}`, `next_action` | reshaped |
| No-access note | `access` text | none; `all_projects_available` is false when scope is limited | partly |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Start the report | `POST /work` `{line:"leadership_report", intake{report, report_date}}` | `POST /projects/{case}/leadership-report-intake` `{action, case_revision, key, reference, background, selection{template_id, content_id, start_at, end_at, kind, audience internal/management, selections{meetings[], actions[], milestones[], issues[], changes[], escalations[]}, scope{domains}}, sections}` 201 | reshaped: exact record ids chosen, not include flags |
| Set report scope / reviewer / audience | Setup rules | same op `{action, case_revision, evidence_id, effective_from, enabled \| role PMO Lead/Head of PMO \| purpose + participants[]}` 201 (drafts for separate review) | moved |
| Send for leadership review | step `send_for_review` | not an action: review is requested by the system once drafted | missing in live |
| Approve and send / return | `POST /tasks/{id}/decision` | `POST /work/{id}/reviews` `{kind:"document", version_id (= document_version_id), verdict, note}` 200 | moved |
| Edit the draft | none | `POST /work/{id}/leadership-report` `{expected_revision, case_revision, reason, selection, sections}` 200 | new |
| Check an uncertain delivery | `POST /work/{id}/actions` `{reconcile, outcome}` | `POST /work/{id}/actions` `{expected_revision, action:"reconcile"}` 202 | reshaped |

**Design parts the live API cannot fill:**
- One report across "every project you can see": the intake is project-scoped (`/projects/{case_id}/...`), with `all_projects_available` as a flag.
- Headline figures (Milestones completed 3, Open escalations 2, Invoices verified 2): live holds narrative sections with cited evidence.
- The period as a free "01–31 Oct": live wants `start_at`/`end_at` and exact source rows.

**Live data the design does not show yet (worth knowing):**
- Each section's coverage marker (supported, partial, unknown, not_applicable).
- A drafted setup (scope, reviewer, audience) is reviewed separately before it takes effect.

**Effort to connect:** L, intake changes from three choices to picking exact source records per domain, and the review page needs the narrative sections.
**Questions for the backend:**
1. D-33: Can the intake offer "all projects I can see" (flag `all_projects_available`) without listing every record id?
2. D-34: Where are the headline figures (counts) the design shows; are they derived from `selections` or do we compute them?
3. D-35: Who requests the leadership review: the system after the draft, or a PM step?

---

## Cluster summary
- **Every line here moves from one generic workspace read to its own endpoint and its own command.** The shared frame (`sections`, `steps`, `status`, `agent_note`) will not carry them; each line needs an adapter (DC-2). Built screens affected: SCR-30, 43, 44, 46, 48, 51, 52.
- **Human decisions and records all need a recorded proof or evidence id, a role, and both revisions.** None of the designs' forms ask for `case_revision`, `role`, `channel` or a source reference. The upload-to-evidence path (D-1) blocks every one.
- **Biggest shape changes:** hypercare observations (metric readings, SCR-46), go-live signatures (two evidences plus signer details, SCR-45), release gates (eight typed records, SCR-44), leadership report intake (exact records per domain, SCR-52), and closure's Finance check (it means "milestone notifications confirmed", SCR-49).
- **Missing in live:** the Delivery overview read (SCR-43), the "Publish to Support" button (SCR-48), Tola's step cards and findings on every screen, hand-marking archive files found (SCR-47), a record for Finance confirmation (SCR-49), outcome "customers affected" fields (SCR-50).
- **Connect first:** SCR-30 (issues) and SCR-48/52 (response and review shapes are closest), then SCR-44/46 (they gate the rest of delivery), then the unbuilt SCR-31, 45, 47, 49, 50 directly against live, with no mock first.
- **Closes earlier gaps:** teams as issue owners (G-SCR30-3), the meaning of closure Finance confirmation (part of G-49-2), recorder kept on support replies. **Leaves open:** G-48-1 (gaps list), G-SCR50-2, G-43-1 to G-43-5 (overview).

## Question list (for the backend developer)
D-1 (all screens): what call turns `POST /cases/{case_id}/files` (`upload_id`) into the evidence id (`evidence_id`, kind such as `signature`, release log, notes file) that line commands require?
D-2 to D-4: SCR-30. D-5 to D-7: SCR-31. D-8, D-9: SCR-33. D-10, D-11: SCR-43. D-12 to D-14: SCR-44. D-15 to D-17: SCR-45. D-18, D-19: SCR-46. D-20, D-21: SCR-47. D-22 to D-24: SCR-48. D-25 to D-27: SCR-49. D-28 to D-30: SCR-50. D-31, D-32: SCR-51. D-33 to D-35: SCR-52. (Full sentences in each screen section.)
