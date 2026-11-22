<!-- Part of the connection map: see README.md. Cluster B. Written 23 Nov 2026 from live OpenAPI 1.22.0 (main 9bac3109) and the frontend at f8b28059. -->

# Cluster B: project pages, project tabs, Setup, Clients, document review

Screens: SCR-07, 08, 11, 12, 13, 19, 22, 29, 34, 35, 38, 39. Read-only research; no repository file was changed.
Sources: v7 `architecture/packages/v7/openapi.json`, live OpenAPI 1.22.0, the backend's Django source under
`apps/core/factory_api/` (used to confirm what the untyped `items` objects really hold),
the handoff README and crosswalk, and the frontend under `frontend/src`.

## Cross-cutting facts for this cluster (read these first)

**1. The project page is one live read plus separate per-tab reads, and the "tab" shape is different.**
- v7 `GET /projects/{case_id}` returns the whole journey (`lines[]`, `next`, `pm`, `route`, `facts[]`, `agent_summary`,
  `delivery[]`, `tab_counts`). Live `GET /projects/{case_id}` returns `tabs[]` ({key, title, django_url, api_url}),
  `items[]` (work rows, 20 per page, `page` / `next_page`), `facts` (an object with counts, not a list), `assistant[]`.
- v7 `GET /projects/{case_id}/{tab}` returned typed arrays (`milestones[]`, `documents[]`, `registers[]`, `actions[]`,
  `money[]`, plus `summary`). Live returns the same envelope for every tab: `{case_id, tab, sections[], as_of}`. Each
  section is `{title, items[], page, has_more, django_url, api_url}` and every item has the same eight fields:
  `title, state, detail, at, due, severity, owner, record_id` (+ `django_url`, `api_url`). One `page` number applies to all
  sections, 25 rows a section. There is no `limit`, no `cursor`, no `register` switch and no counts.
- Live tab keys (permission-filtered): `journey, milestones, documents, templates, money, month-end, registers, actions, hr`.
  The frontend's seven tabs are `journey, delivery, milestones, documents, money, registers, actions`. Only four keys go through
  `/projects/{case_id}/{tab}` (`milestones, documents, registers, actions`). `money`, `templates`, `month-end`, `hr` are their own
  operations. There is no `delivery` tab in live.
- Live row ids are integers (work `id`, `record_id`, `version_id`); v7 used strings (`work_id`, `document_id`). The live item
  `state` is display text ("Waiting", "Version 2", "Awaiting decision"), not the v7 state enum, so the existing tag mapping
  (`STATE_TAGS`) cannot be fed from it without a code.

**2. Setup is workspace-scoped in live; the frontend Setup is organisation-wide.** Detailed in SCR-13 below and summarised in the
Cluster summary.

**3. Clients in live are groups of workspaces, not client records.** Detailed in SCR-35.

**4. Writes in this cluster are mostly not built in the frontend.** Only three screens write today: Setup rules (SCR-13),
Setup delegation (SCR-13), Setup templates (SCR-34), the billing contact (SCR-35), and the document decision (SCR-08, through the
work item). Every project tab (SCR-11, 12, 29, 38) is read-only today.

---

### SCR-07 · Project journey
**Built today:** yes. F-07 (DONE), routes `/projects/[caseId]` (and `/projects/[caseId]/delivery` for the Delivery tab), main files
`src/features/projects/ProjectJourney.tsx`, `model.ts`, `useProject.ts`, `ProjectTabs.tsx`, `DeliveryTab.tsx`.
**Live operations:** `GET /projects/{case_id}`, `GET /projects/{case_id}/department-handoffs`, `POST /assistant/conversations`,
`GET /work/{work_id}`, and the tab reads (`GET /projects/{case_id}/{tab}`, `/money`, `/templates`, `/month-end`, `/hr`).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Project title, client crumb (client is the part before " · ") | E-PROJECT → `title` | `GET /projects/{case_id}` → `title` (format of the string not documented) | same (crumb split is a guess, see Q1) |
| Case revision | E-PROJECT → `revision` | → `revision` | same |
| Project manager, route line ("PM Tunde Bello · Route A") | `pm{name,role,is_you}`, `route` | `facts.engagement{route, reference, manager}` (only with `engagement.read`; `manager` is a plain name, can be null) | reshaped; `role` / `is_you` missing in live |
| Count of pieces of work and lines | `work_count`, `line_count` | `facts.total` (pieces); no line count | reshaped / missing in live (line count) |
| Facts strip: contract stages, invoices verified, waiting on people, stopped, next milestone, paid | `facts[]` list of {label, value, money, unknown} | `facts{total, waiting, stopped, finance{stages, delivered, next, limited}, engagement}` | reshaped. "Paid" is not here (it lives in `/money`); "invoices verified" has no match: `finance.delivered` counts invoices that have a delivery record |
| Each piece of work in order: name, reference, status tag, "Station 4 of 7" | `lines[]` {line, work_id, reference, title, state enum, station{index,count,name}, status_label, tone} | `items[]` {id (int), line (title), reference, state (display text), started, updated, api_url}; 20 a page by `page`, `next_page` | reshaped. No station, no tone, no state enum |
| Link to the work page | `/work/{work_id}` | `items[].api_url` = `/api/v1/work/{id}`; `django_url` is a retired page | reshaped (integer id) |
| "What is next" sentence | `next` | none (`facts.finance.next` is only the next finance milestone) | missing in live |
| Tola's summary of the project | `agent_summary{agent,text}` | none. `assistant[]` only lists which agents can be opened here | missing in live |
| Tab bar with counts | `tab_counts{milestones,documents,registers,actions}` | `tabs[]` {key, title, api_url}; no counts | reshaped; counts missing in live |
| Delivery tab (rows, gates, Tola's delivery check) | `delivery[]`, `delivery_agent`, `delivery_summary` (mock proposals) | no `delivery` tab. Nearest: `GET /projects/{case_id}/department-handoffs` ({work_id, process, title, status}, `before` paging) and the `delivery/{dossier_id}/...` desks | missing in live (as drawn) |
| Is this a sample project | `sample` | `sample` | same |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| "Ask me about this project" opens the assistant | link to `/assistant` only | `POST /assistant/conversations` {agent, case_id, idempotency_key (uuid), scope:"project"}; 200 with `conversation_id` | new in live (the frontend does not start a conversation from here today) |

**Design parts the live API cannot fill:**
- The "What is next" line under the journey.
- Tola's written summary of the project (paragraphs and the agent name).
- "Station 4 of 7 · Finance review" under each piece of work, and the colour of its status tag (live gives words, not a code).
- The tab counts (Milestones 3, Registers 2...).
- The Delivery tab as drawn (ordered delivery lines with gates and Tola's check).
- "Invoices verified" and "Paid" in the facts strip, and the count of lines.
**Live data the design does not show yet (worth knowing):** started and last-updated time on each piece of work; waiting / stopped totals computed for the whole project (not just the page); `finance.limited` (the finance numbers are partial); the Templates, Month-end and HR tabs for roles that have them; `department-handoffs` filtered by process.
**Effort to connect:** L. The page leans on v7 fields live does not have (summary, next, stations, delivery, counts), so the Journey tab is rebuilt around `items`/`facts` and the Delivery tab needs a decision.
**Questions for the backend:**
1. B-1 `GET /projects/{case_id}` `title`: is it always "<Client> · <project>"? The crumb splits on " · ".
2. B-2 `items[].state` is display text from `WORK_STATUS`; can you add the raw status code (ready, waiting, waiting_effect, verified, blocked, ...) so tags are not matched on words?
3. B-3 Can `items[]` carry the station position (index, count, name) and a short detail line, or is this deliberately not in the journey?
4. B-4 Is there a live source for "what is next" and for Tola's project summary, or should those be dropped from the page?
5. B-5 Can `tabs[]` return a count per tab, and which key replaces the Delivery tab (`department-handoffs`, a dossier, none)?
6. B-6 `facts.finance.delivered`: does it mean "invoices verified" as the board labels it, or "invoices with a delivery record"? Where does "Paid" come from on this page?

---

### SCR-08 · Document review
**Built today:** yes. F-29 (DONE), route `/projects/[caseId]/documents/[documentId]?v=<n>`, main files
`src/features/documents/DocumentReview.tsx`, `documentModel.ts`, `useDocument.ts`, `ReviewControls.tsx`, with the decision hook
`src/features/decide/useDecision.ts`.
**Live operations:** `GET` and `POST /projects/{case_id}/document-reviews/{version_id}`, `GET` and `POST .../{version_id}/publication`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Which document: title, version, status, template, test-template flag | E-DOCUMENT `GET /documents/{document_id}/versions/{version}` → `title, version (string), status, template, test_template` | `GET /projects/{case_id}/document-reviews/{version_id}` → `title`, `version` (integer), `current` (is this the latest) | moved; `status`, `template`, `test_template` missing in live (`publication` → `review_status` is a status text) |
| The numbered sections with their text | proposal `sections[]` {key, heading, text} | `preview[]` {field, text} (field is the section heading, in template order) | renamed / reshaped |
| Notes from Tola in a section, "changed since v1" marks, compare with v1 | proposal `sections[].notes`, `changed_since` | none | missing in live |
| What the agent checked (template, amounts, every section filled) | proposal `checks[]` {label, status, detail} | `publication` read → `findings[]` (strings: reasons the document cannot be decided yet) | reshaped; no pass/held/blocked list, only blockers |
| Audience ("Client · Lagoon Health") | proposal `audience.label` | `audience` (string) | renamed |
| Crumb: project and reference | proposal `case_id, project_title, reference` | `case_id` is in the path; no project title, no reference | missing in live |
| Who reviews, drafted by | proposal `review{role_label, work_id, task_id}`, `drafted_by` | none; `decisions[]` lists the verdicts this person may record now | reshaped |
| Returned state: who returned, when, the note | proposal `returned{by, role, at, note}` | `review_status` (text); no note, no person, no time | missing in live |
| Case revision to send back | task `revision` | `revision` (case revision) | reshaped |
| Editable fields, publish packet, delivery job | not drawn | `publication` read → `editable[]`, `can_request_review`, `publication{packet, recipients}`, `delivery{job_id, state, recovery_actions, receipts}` | new in live |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Take the review (claim) | `POST /tasks/{task_id}/claim` {expected_revision} → 200 | none: the decision is recorded directly, no claim | missing in live (claim not needed) |
| Approve or return with a note | `POST /tasks/{task_id}/decision` {expected_revision, verdict approve/return, note} → 200 {task_id, verdict, decided_by, work_state} | `POST /projects/{case_id}/document-reviews/{version_id}` {expected_revision (case revision), verdict approve/return/reject, delegated (bool, required), note (≤4000)} → 200 {review_id, verdict}. 422 `action_unavailable` while findings remain | reshaped; `reject` and `delegated` are new |
| Ask for a next version / edit as v3 | none (no write existed) | `POST .../publication` {action:"revise", revision, sections{key:text}} → 200 {id, version_id, revision}. Agent redraft is not offered | new in live (human edit only) |
| Send for review / publish / retry or cancel delivery | none | `POST .../publication` {action: request_review / publish (+packet fingerprint) / retry or cancel (+job_id, reason)} → 200 | new in live |

**Design parts the live API cannot fill:**
- Tola's margin notes in sections and the "changed since previous version" marks, and Compare versions.
- The checks panel with per-check Done / Held / Blocked and the matched reference ("Matches COST-0140 v2"); live gives only a list of blocking sentences.
- The returned banner ("Returned by Kemi · 14:20 today" and the quoted note).
- "Ask Tola to draft v3" (live only lets a person edit the sections).
- The crumb with project name and the document reference; the TEST TEMPLATE tag.
**Live data the design does not show yet (worth knowing):** a third verdict, reject; "delegated" decisions; whether this is the current version (`current`); the publication step (packet fingerprint, recipients, delivery job, receipts, retry / cancel); section editing for the audience's fields.
**Effort to connect:** M. The page is rewired to `version_id` and a case-scoped read, the claim step goes, and several drawn parts disappear or need new design; the work-item read used for the task is no longer needed.
**Questions for the backend:**
1. B-7 How does a person reach `version_id` from the Documents tab? `GET /projects/{case_id}/documents` items carry only an evidence `record_id` ("Version 2"), not a document version id; which field or link gives `document-reviews/{version_id}`?
2. B-8 Can the preview or controls read return a project title, a document reference, the template name and a test-template flag for the page header?
3. B-9 Is there any live source for per-section agent notes, "changed since previous version", and a compare read? If not, is dropping them the intended design?
4. B-10 `document-reviews/{version_id}` `findings[]` and `review_status`: are these the replacement for the checks panel and the returned banner? Where are the returner's name, time and note?
5. B-11 `POST document-reviews/{version_id}` needs `delegated`: what sets it, and when is it true for an ordinary reviewer?

---

### SCR-11 · Registers (issues, changes, RFPs)
**Built today:** yes. F-25 (DONE), route `/projects/[caseId]/registers?register=issues|changes|emergencies|rfps&q=`, main files
`src/features/projects/RegistersTab.tsx`, `tabsModel.ts`, `useProjectTab.ts`, `ProjectTabContent.tsx`.
**Live operations:** `GET /projects/{case_id}/registers`, `GET` and `POST /projects/{case_id}/issues/{issue_id}`, `GET /projects/{case_id}/escalation-register/{request_id}`, `POST .../escalation-register`, `GET .../change-versions/{version_id}`, `POST .../ordinary-changes`, `POST .../emergency-intake/{version_id}`, `GET /received-bids/{case_id}/receipts/{receipt_id}`, `POST /received-bids/{case_id}/assignment`. (Also `GET /projects/{case_id}/issues`, the issue list with owner and proof choices.)

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Choose Issues / Changes / Emergencies / RFPs | E-PROJECT-TAB `?register=` | `GET /projects/{case_id}/registers` returns all permitted sections at once: "Issues", "Escalations", "Changes", "Emergency changes", "Bid requests" (each only if the person has `issue.read`, `change.read`, `emergency.read`, `rfp.read`) | reshaped (no switch; the page filters sections by `title`) |
| Row: reference, title | `registers[].reference, title` | `items[].title` (the reference for issues, changes, escalations; the issue's own title goes in `detail`) | reshaped |
| Severity | `severity` high/medium/low | `severity` text ("Critical/High/Medium/Low", issues only) | renamed (different words, adds Critical) |
| Owner and role | `owner{name, role, recorded_by_pm, outside_party}` | `owner` (plain name, or team label, or "Owner needed") | reshaped (role and flags missing) |
| State word, age | `state`, `age_seconds` | `state` (text), no age (the backend computes age days but does not send it) | reshaped / missing in live (age) |
| Row opens its work page | `work_id` | `api_url` to the record (`/projects/{c}/issues/{id}`, `.../escalation-register/{id}`, `.../change-versions/{version_id}`, `.../emergency-intake/{version_id}`, `/received-bids/{c}/receipts/{receipt}`) | moved |
| Counts per register ("3 ISSUES") | `summary.registers{}` | none; only `has_more` per section | missing in live |
| Search | `q` | `q` (max 120) | same |
| Filter | not drawn (G-SCR11-1) | `state`, `owner` (user id or `unassigned`), `severity` (raw values; the valid options are not returned) | new in live |
| Paging | `cursor`, `limit` 10/20/50 | `page` (shared across sections), 25 a section | reshaped |
| Issue detail | none | `GET /projects/{case_id}/issues/{issue_id}` → issue{reference, title, kind, status, severity, next_action, acknowledged_at, resolved_at}, team, acknowledgement | new in live |

**Writes** (none are drawn on the register today)
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Record an issue | not built | `POST /projects/{case_id}/issues` {case_revision, reference, title, kind, owner_id, next_action, evidence_id, note, severity, external_links[]} → 201 | new in live |
| Update or close an issue | not built | `POST /projects/{case_id}/issues/{issue_id}` {action, case_revision, state_id, evidence_id, note, operation acknowledge/start/progress/resolve/manage, ...} → 201 | new in live |
| Record a change / emergency / escalation / assign a bid | not built | `POST ordinary-changes`, `emergency-intake/{version_id}`, `escalation-register`, `received-bids/{case_id}/assignment` | new in live (not drawn) |

**Design parts the live API cannot fill:**
- One list per register with the same columns and a count badge on each switch.
- Owner "role" and the "recorded by PM" / outside-party marks; the age column ("2d").
- A single combined register table (live returns separate sections with their own pages).
**Live data the design does not show yet (worth knowing):** issue next action, acknowledgement state, resolved time; who may update an issue (`team.can_record`, `can_resolve`); escalations and bid requests as their own sections; state / owner / severity filters.
**Effort to connect:** M. The row mapping is small but the tab model, paging and the register switch are rebuilt around sections and `page`.
**Questions for the backend:**
1. B-12 `GET /projects/{case_id}/{tab}` registers: can sections carry a stable `key` (issues, changes, emergencies, rfps) and a total count, so the page does not match on `title` text?
2. B-13 Can register `items` carry `reference` separately from `title`, the owner's role, and `age_seconds` (the issue age is computed but not returned)?
3. B-14 Which values are valid for the `state`, `owner` and `severity` filters, and where does the page read the options?
4. B-15 Should the page open detail from `api_url` (it differs per register), and is there an RFP detail other than the receipt?

---

### SCR-12 · Report with drill-down (Money tab)
**Built today:** yes. F-26 (DONE), route `/projects/[caseId]/money?figure=<id>`, main files `src/features/projects/MoneyTab.tsx`, `moneyModel.ts`, `useMoney.ts`.
**Live operations:** `GET /projects/{case_id}/money` (`?figure=<key>`), `GET /projects/{case_id}/billing-invoices/{invoice_id}`, `.../milestones/{milestone_id}`, `.../financial-corrections/{kind}/{record_id}`, `.../cash-lots/{lot_id}`, `.../commercial-response`, `.../invoices/{issue_id}/payments/{receipt_id}`, `GET /payments` (the all-projects payments queue; not part of this tab).

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| One row per contract stage, in order | E-PROJECT-TAB money → `money[]` sorted by `position` | `GET /projects/{case_id}/money` → `items[]` (`key`, `label`; order as returned; `contract_stage` flag) | moved; renamed (`stage` → `label`; `position` missing) |
| Stage amount, with Unknown | `amount{amount, currency, unknown}` | `amount` (decimal string or null), `currency`, `missing_reason` (text when unknown) | reshaped; null replaces `unknown:true` |
| Note under the amount | `amount_note` | `missing_reason` | renamed (likely) |
| Invoice cell (reference + state words) and link | `invoice{reference, work_id, state}`, `invoice_status` | `invoices[]` {id, reference, version, currency, status (text), at, paid, owed, api_url}; a stage may hold several | reshaped. Link goes to `.../billing-invoices/{id}` not a work page |
| Paid status (paid / part paid / not paid / not due / Finance tracks) and owed | `paid{status enum, owed{}}` | per invoice `paid`, `owed` (decimal strings or null) and `status` (free text) | reshaped. No status enum; the page must not work it out from the numbers |
| "Where this figure comes from" panel | E-REPORT `GET /reports/{report_id}` → `figures[]` {label, value, sources[], source_details[]} | same money read → `items[].sources[]` {label, django_url, at, kind (invoice, agreement, correction, cash-lot, reviewed-terms, milestone, preparation), record_id, api_url} | moved / reshaped. One read instead of two; `?figure=` can narrow to one stage |
| Report timestamp | `as_of` | `as_of` | same |
| Partial coverage warning | none | `limited` | new in live |
| Stage changes | none on this tab | `items[].changes[]` {link_id, version_id, reference, number, note, plan_id, additional_amount (always null), api_url} | new in live |
| Link to Finance workspace | none | `finance_url` (retired Django page) | new in live |
| Drill into an invoice or payment | none | `billing-invoices/{invoice_id}` (amount, paid, owed, issued/delivered times, `payments_url`, `corrections_url`) | new in live |

**Writes**
| What the person does | Today | Live | Fit |
|---|---|---|---|
| "Ask Chidi" about a figure | link only | `POST /assistant/conversations` {agent, case_id, idempotency_key, scope}; no figure context | new in live (no way to name a figure) |

**Design parts the live API cannot fill:**
- The "document / rule / record" source labels with references like "SOW-0198 v2" (live gives a label and a record id only).
- The explicit paid status word per row and the "owed" amount per stage when a stage has more than one invoice.
- The drill-down's separate "figure value differs from row" check (the figure and the row now come from one read).
- Sorting by `position`.
**Live data the design does not show yet (worth knowing):** due date and completion time per stage; several invoices per stage; the change links on a stage; the `limited` warning; links into corrections, cash lots and the commercial response (signed agreement).
**Effort to connect:** M. Same screen, different shape: two reads become one, and the paid state needs a decision.
**Questions for the backend:**
1. B-16 `money` `invoices[].status`: what are the possible values, and is there a code for "paid / part paid / not paid / not due" or must it be shown as given?
2. B-17 Is `missing_reason` the replacement for v7 `amount_note`, and what text does it hold when the amount is known?
3. B-18 Can `items[]` carry a position number (or state that array order is the stage order)?
4. B-19 `sources[]` has no reference text (such as the signed agreement version); can `label` be relied on to contain it, or can a `reference` field be added?
5. B-20 Can `POST /assistant/conversations` accept the figure `key` so the answer is about that figure?

---

### SCR-13 · Setup: roles, rules, delegation (plus payroll fields, delivery and finance rules)
**Built today:** partly. F-11, F-27 (DONE). Routes: `/setup/rules`, `/setup/rules/finance`, `/setup/rules/delivery`, `/setup/delegation` are built. `/setup/roles`, `/setup/payroll-visibility`, `/setup/staff`, `/setup/costing-rule` show only a "comes next" page. Files `src/features/setup/` (`RulesView`, `SetRulePanel`, `FinanceRulesView`, `DeliveryRulesView`, `DelegationView`, `DelegationForm`, `SetupFrame`, `api.ts`).
**Live operations:** `GET /setup/primary-roles`, and under `/setup/{case_id}/`: `primary-roles` (GET, POST), `team-decisions` (POST), `delegations` (GET), `delegations/options`, `delegations/drafts` (POST), `rules`, `decision-appointments` (GET, POST), `policy-configurations` (GET, POST), `policy-configurations/{id}/review`, `policy-configurations/references`, `policy-configurations/typed-drafts`, `policy-scopes`, `policy-impact...`, `hr-field-visibility` (GET, POST, and `/{configuration_id}`).

**How a Setup page chooses a workspace.** Every live Setup read and write except one carries `{case_id}` in the path, and a "workspace" is a project case (`rules` and the policy reads accept any case the person has `policy.read` on). Live has no "current workspace" and no organisation-wide setup list. A Setup page therefore needs: (a) a workspace picker in the Setup frame, filled from `GET /projects?status=active|all` (`case_id`, `title`) filtered to the workspaces where the person has setup authority (only discoverable by trying: `GET /setup/{case_id}/rules` returns 404 without `policy.read`; `GET /setup/{case_id}/primary-roles` returns `can_create`; `GET /setup/{case_id}/policy-scopes` returns `can_configure`); (b) the chosen `case_id` in the route or a query value, so reload and links work; (c) the workspace `revision` from each read to send with writes. Organisation-wide values do exist, but only as an organisation scope version applied to workspaces (`GET/POST /setup/{case_id}/policy-scopes`, kind `organization`); reading or editing one still goes through a workspace.
**What is organisation-wide in live:** `GET /setup/primary-roles` (the six built-in roles, no case id), `GET /staff`, `GET /staff/{person_id}` and its `deactivation` / `restoration` pairs, `GET /staff/delegations/{authority_id}` (technical delegation), `GET /role-dashboard` (the person's own roles and work across workspaces) and `GET /me`. The rule board, delegations, role catalogue extras, templates, costing and payroll-field settings are all per workspace.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| List of rules with set / not set, version, area, group | E-SETUP-RULES `GET /setup/rules` → `items[]` {component, name, set, revision, area, group, used_by, display_value, link, holds_work, effective_from, can_change, restricted, editor}, `not_set_count`, `roles_missing_count`, `next_cursor` | `GET /setup/{case_id}/rules` → `items[]` {label, area ("Pre-sale", "All lines", "Finance", "Delivery"), status (ACTIVE / MISSING / UNAVAILABLE / UNKNOWN / INVALID), version, value, details[], roles[], url}; a fixed ten-row summary, no paging, plus `revision`, `as_of` | moved and reshaped. No `component`, no `can_change`, no `editor`, no `holds_work`, no `effective_from`, no counts |
| Which roles hold a rule, role pickers | `editor{kind:role_set, options, selected}` | `items[].roles[]` (names only); role list from `GET /setup/primary-roles` or `/setup/{case_id}/primary-roles` {key, name, description, functions[], definition_id} | reshaped |
| Versions of a rule and its state | `revision` only | `GET /setup/{case_id}/policy-configurations?component=` → `items[]` {id, component, version, state_id, state draft/validated/active/revoked/superseded, actions[]}, `case_revision`, `next_page` | new in live |
| Delegations list | E-DELEGATIONS `GET /setup/delegations` → `items[]` {delegation_id, from{name,role}, delegate, authority, starts, ends, reason, status, can_change}, `authorities[]`, `delegate_options[]` | `GET /setup/{case_id}/delegations` → `items[]` {role, principal_id, delegate_id, valid_from, valid_until}; names only through `GET .../delegations/options?role=` → `people[]` {id, label}, `roles[]`, `proofs[]`, `source_configuration`, `limited` | moved and reshaped. People are ids, not names; no reason, no status, no `can_change`, no paging |
| Payroll field visibility (SCR-13 fields) | not built | `GET /setup/{case_id}/hr-field-visibility` → `fields[]`, `draft`, `status`, `can_propose`, `proofs[]` | new in live |
| Roles table, people, role changes | not built | `GET /setup/{case_id}/primary-roles`, `GET .../people/{person_id}/primary-role?role=` (preview), `GET /staff` | new in live |
| Is the person allowed to change | per row `can_change` | none per row; whole-area flags `can_create` (roles), `can_configure` / `can_activate` (policy-scopes), `can_draft` (appointments), `can_propose` (HR fields) | reshaped |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Save a rule's roles (with proof, start date, reason) | `PUT /setup/rules/{component}` {expected_revision, value{roles}, starts, reason, evidence_id (string)} → 200 {component, revision} | `POST /setup/{case_id}/policy-configurations/typed-drafts` {component, case_revision, evidence_id (int), effective_from, value (a different object per component, 34 shapes)} → 201 draft {id, state:"draft", actions[]}; then `POST .../policy-configurations/{id}/review` {case_revision, state_id, transition validated/active/revoked} → 200 | reshaped: one save becomes draft then review steps; the draft is not in force until activated. The roles-only `value` does not exist |
| Upload proof for a rule | `POST /cases/{case_id}/evidence` (JSON base64) | no matching operation. `POST /cases/{case_id}/files` (multipart) returns an `upload_id`, not an evidence id; `POST /setup/{case_id}/policy-configurations/references` {ref, schema_ref, content, evidence_id} registers a policy document against an existing `evidence_id` | missing in live (how to create the evidence) |
| Add a delegation | `PUT /setup/delegation` {expected_revision, delegate, starts, ends, authority, reason} → 200 | `POST /setup/{case_id}/delegations/drafts` {revision, source_configuration, submission_key (uuid), role, principal (int), delegate (int), starts, ends, effective, evidence (int)} → 201 {configuration_id, version, revision}; then activate through `policy-configurations/{id}/review` | reshaped. Draft only; needs proof and a role instead of "authority" text; `submission_key` makes it idempotent |
| Assign someone to a role | not built | `POST /setup/{case_id}/people/{person_id}/primary-role` (after the preview), `POST .../team-decisions`, `POST .../primary-roles` | new in live |
| Propose payroll field visibility | not built | `POST /setup/{case_id}/hr-field-visibility` {case_revision, base_id, latest_version, fields[], evidence_id, effective_from, reason} → 201 draft; review at `.../hr-field-visibility/{configuration_id}` | new in live |

**Design parts the live API cannot fill:**
- One organisation-wide rules page; every rule is read in one workspace at a time.
- The Edit control on each rule row, and "set / not set" counts on the tab badges (they must be counted from `status`).
- "Holds N pieces of work" and "effective from" on a rule; the used-by list.
- Delegation rows with names, a reason and a status (scheduled / active / ended); "From" and "To" pickers filtered by who holds the role; ending a delegation early.
- The "Costing rule" tab as a version list inside Setup (see SCR-39).
**Live data the design does not show yet (worth knowing):** draft / validated / active / revoked life cycle of every rule; scoped (organisation / project / contract / service) policy versions and their health; the impact assessment of changing a rule (`policy-impact`); business decision appointments; the six built-in roles and their functions; per-person role preview before a change.
**Effort to connect:** L. A workspace picker, a different data shape on every tab, and a two-step save (draft then review) replace the single save.
**Questions for the backend:**
1. B-21 Is there an organisation-level Setup read (rules, delegations, templates, roles) that does not need a `case_id`, or should the frontend always choose a workspace first? Which workspace do organisation scopes belong to?
2. B-22 `GET /setup/{case_id}/rules` has no `component`; how does a row map to a `policy-configurations` component so the page can open a draft?
3. B-23 Can `rules` items carry `can_change` and the editable role options, or must the page infer authority from `policy-scopes` `can_configure` and `can_activate`?
4. B-24 Who may move a draft to `validated` and `active`: the same person who drafted it, or a separate reviewer?
5. B-25 How does a client create the `evidence_id` that every policy write needs (proof file)? No live evidence-upload operation was found.
6. B-26 `GET /setup/{case_id}/delegations` returns user ids only: can it return names, role, reason and status, as the design shows?
7. B-27 Which user can discover which workspaces they may use for Setup (`GET /projects` lists all readable ones, not the ones with `policy.read`)?

---

### SCR-19 · Mark a milestone complete
**Built today:** no. F-50 is BLOCKED; no route, no files (the Milestones tab only shows a completion state).
**Live operations:** `GET /projects/{case_id}/milestones/completions` (options), `POST` the same path, `GET /projects/{case_id}/milestones/{milestone_id}`, `GET /projects/{case_id}/{tab}` (milestones), `GET /projects/{case_id}/money`, `GET/POST /projects/{case_id}/change-milestone-link`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| The milestone being completed (name, number, contract amount) | not built (tab `milestones[]` has position, name, contract_amount) | `GET /projects/{case_id}/money` → `items[]` {key, label, amount, currency, due_date, completed_at, contract_stage} | new in live (names are the stage labels; no milestone id) |
| Proof the person can attach | not built | `GET .../milestones/completions` → `proofs[]` {id, label ("Completion evidence · version N")}, `revision`, `next_page` | new in live |
| Already completed milestones | tab `milestones[].completion` | tab `milestones` → section "Recorded completions" items {title (name), state "Completion recorded", at, detail (who), record_id, api_url} | reshaped |
| One recorded completion | none | `GET .../milestones/{milestone_id}` → {id, name, completed_at, evidence_id, proof_version} | new in live |
| Whether the person may complete | none | the options read answers 403/404 without `milestone.complete`; no flag | missing in live (no `can_complete`) |
| The invoice that starts after completion | text on board | `POST` says it "queues its Finance handoff"; no handoff id returned | missing in live |

**Writes**
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Upload proof | `POST /cases/{case_id}/evidence` (not built) | none that creates completion evidence (see question) | missing in live |
| Mark complete | none | `POST /projects/{case_id}/milestones/completions` {revision (case), evidence_id, name (free text, ≤200)} → 201 {id, revision, name, evidence_id} | new in live |
| Link a change to a signed milestone | none | `POST /projects/{case_id}/change-milestone-link` {revision, stage "uat" or "completion", plan_event_id, scope_note ≤240} → 200 {id, stage, plan_event_id, revision} | new in live |

**Design parts the live API cannot fill:**
- Choosing a milestone from the contract list with its id (live takes the milestone name as typed text).
- "Completed on <date>" set by the person (live sets the time itself); filename and size of the proof; "Recorded by <name>".
- The line "Chidi drafts the stage 2 invoice" with a link to the new invoice work.
- A disabled button with the reason ("previous milestone not complete").
**Live data the design does not show yet (worth knowing):** the change-to-milestone link (UAT or completion stage) and its scope note; the `proof_version` of a recorded completion.
**Effort to connect:** M. Small writes, but the milestone choice, proof upload and the invoice follow-up are all open.
**Questions for the backend:**
1. B-28 `POST milestones/completions` `name`: is it any text, or must it equal a contract stage label from `/money`? Is there a milestone id?
2. B-29 How is a `kind=completion` evidence record created through the API? `POST /cases/{case_id}/files` returns an `upload_id`, not an evidence id.
3. B-30 Can the response return the Finance handoff or invoice work id that the completion queues, and when does it appear?
4. B-31 Can the options read return `can_complete` and a reason (not your role, already complete, previous milestone open) so the button can be explained?

---

### SCR-22 · Project list
**Built today:** yes. F-07 (DONE), route `/projects`, main files `src/features/projects/ProjectsList.tsx`, `ProjectsPage.tsx`, `model.ts`.
**Live operations:** `GET /projects`, `GET /projects/{case_id}`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Rows of projects | E-PROJECTS `GET /projects` → `items[]` | `GET /projects` → `items[]` | same path, reshaped |
| Project id, title, sample tag | `case_id, title, sample` | `case_id, title, sample`, plus `revision` | same |
| Project manager | `pm` (string) | `manager` (string or null) | renamed; null possible |
| Stage / phase | `stage` | `phase` and `lifecycle` (strings or null) | renamed, split in two |
| Reference, next milestone and due date | `reference`, `next_milestone{name, due}` | none | missing in live |
| "Needs a person" and "stopped" counts | `needs_person`, `stopped` | `reviews`, `exceptions` (integers or null) | renamed (meaning likely, see Q) |
| Tab counts (Active / Closed / All) and total | `counts{active,closed,all}`, `total` | none | missing in live |
| Search, status tab | `q`, `status` active / closed / all (default active) | `q` (max 120), `status` all / closed / active (default **all**) | same params; default differs, send `status=active` explicitly |
| Paging | `limit` 10/20/50, `cursor` → `next_cursor` | `cursor` → `next_cursor`; no `limit` | reshaped |
| Link to a project | `/projects/{case_id}` | same, plus `django_url` (retired page) | same |

**Writes:** none.

**Design parts the live API cannot fill:**
- The next milestone ("UAT sign-off · due 14 Nov") on each row, and the project reference.
- The count badges on Active / Closed / All and the "N projects" total.
- Choosing how many rows a page (live pages are fixed by the backend).
**Live data the design does not show yet (worth knowing):** `lifecycle` (active or closed) and `phase` as separate values; case `revision`; `as_of`.
**Effort to connect:** S. A direct mapping of the same operation; the missing next-milestone, counts and page-size are display changes.
**Questions for the backend:**
1. B-32 `GET /projects` `reviews` and `exceptions`: are these "waiting on a person" and "stopped" as the row shows them, and what do `lifecycle` and `phase` hold?
2. B-33 Can the list return per-status counts and a next-milestone name and date, or should those be dropped from the rows?
3. B-34 Is `limit` going to be supported, or is the page size fixed?

---

### SCR-29 · Project actions
**Built today:** yes. F-25 (DONE), route `/projects/[caseId]/actions`, main files `src/features/projects/ActionsTab.tsx`, `tabsModel.ts` (read only).
**Live operations:** `GET /projects/{case_id}/actions` (tab), `GET` and `POST /projects/{case_id}/actions/{item_id}`, `GET /projects/{case_id}/meetings/options`, `POST /projects/{case_id}/actions/create`, `GET /projects/{case_id}/meetings/{meeting_id}`, `POST /projects/{case_id}/meetings/{meeting_id}/actions`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Action rows | E-PROJECT-TAB actions → `actions[]` {action_id, title, state open/overdue/done, owner, due, from} | tab `actions` → section "Project actions" `items[]` {title (the action text), state ("Open", "In progress" ...), detail (owner name or "Owner needed"), due (date-time), record_id, api_url} | reshaped |
| Owner (name, role, recorded by PM) | `owner{name, role, recorded_by_pm, outside_party}` | `detail` (name only) | reshaped; role and flags missing |
| Due date, with Unknown | `due{date, unknown}` | `due` (date-time or null) | reshaped (null means unknown) |
| "From Weekly sync · 10 Nov" | `from{meeting, at}` | none on the list; `GET .../meetings/{meeting_id}` is separate | missing in live |
| Summary counts (total, overdue, without owner) | `summary.actions{}` | none | missing in live |
| Search and filter | `q` | `q`, `state`, `owner` (user id or `unassigned`), `severity` | new in live |
| One action in full | none | `GET .../actions/{item_id}` → `current{status open/in_progress/paused/completed/cancelled, description, owner, deadline, timing CLOSED/UNKNOWN/PAUSED/OVERDUE/NOT_DUE}`, `operations[]` (what this person may do), `owners[]`, `evidence[]`, `history[]` | new in live |
| Overdue | `state: overdue` | `current.timing = OVERDUE` (only on the detail read; the list `state` is the status word) | reshaped |

**Writes** (none built; the board's line "Changing an owner or due date is recorded with your name" implies one)
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Change owner, due date, start, complete, cancel, reopen | none | `POST /projects/{case_id}/actions/{item_id}` {revision (case), action_revision, operation assign/reassign/cancel/reopen/start/complete, owner, due_at, evidence (int, required), reason} → 200 | new in live |
| Add an action | none | `POST /projects/{case_id}/actions/create` {revision, reference, description, evidence_id, reason, owner_id, due_at, meeting_id, ...} → 201; options at `GET .../meetings/options` | new in live |

**Design parts the live API cannot fill:**
- The header counts ("12 ACTIONS · 3 OVERDUE · 2 WITHOUT OWNER").
- The "From <meeting> · <date>" line on each action.
- The owner's role and the "recorded by PM" note on the row.
**Live data the design does not show yet (worth knowing):** a full history of every action; the list of allowed operations for this person; paused status and timing; action creation from a meeting.
**Effort to connect:** S to M. The read is a straight remap of the section; changes (assign, complete) are a new write flow if the design keeps the sentence about changing owners.
**Questions for the backend:**
1. B-35 Can action `items` in the tab carry the status code, `owner` as {name, role}, and the originating meeting {title, date}?
2. B-36 Can the tab return totals for actions (total, overdue, without owner) or must they be counted from every page?
3. B-37 Every action update needs an `evidence` id and a `reason`: how does a person without a file provide evidence (for example a plain note)?

---

### SCR-34 · Setup: templates
**Built today:** yes. F-20 (DONE), route `/setup/templates`, main files `src/features/setup/TemplatesView.tsx`, `TemplateUploadPanel.tsx`, `useTemplates.ts`, `useTemplateUpload.ts`, `api.ts`.
**Live operations:** `GET /projects/{case_id}/templates` (`?templates=<cursor>`), `POST /projects/{case_id}/templates`, `POST /projects/{case_id}/templates/replacements`. The template page is project-scoped (the template catalogue is read for one project workspace, kind `project`); see the Setup note under SCR-13.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| Templates in the organisation | E-TEMPLATES `GET /setup/templates` → `items[]` | `GET /projects/{case_id}/templates` → `items[]` for that project only | moved (per project, needs a `case_id`) |
| Name, version | `name`, `version` (string) | `name`, `version` (integer) | same / type change |
| Which line it belongs to | `line` | none | missing in live |
| Test template tag | `test_template` | none | missing in live |
| Last changed by and when, number of versions | `updated_at`, `updated_by`, `versions` | none | missing in live |
| Template id and revision for upload | `template_id` (string), `revision` | `id` (integer); `revision` is the case revision for the whole page | reshaped |
| Can the person upload | per row `can_upload` | page-level `can_upload` | reshaped |
| Download | none | `items[].download_url` (null if no file attached) | new in live |
| Proofs to attach to a first version | none | `proofs[]` {id, kind, version} | new in live |
| Paging | `cursor` | `templates` query value = `cursor` from the previous page | renamed |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Upload a new version of a template | `POST /setup/templates/{template_id}/versions` JSON {expected_revision, filename, content_base64, note} → 200 {template_id, version, test_template, revision} | `POST /projects/{case_id}/templates/replacements` multipart {previous (template id), proof (evidence id), revision (case revision), request_key (uuid), file} → **200** {template_id, version, django_url} | moved; JSON base64 becomes multipart; `note` dropped; a proof and a request key are required |
| Register a first template | none | `POST /projects/{case_id}/templates` multipart {name, document_type (minutes, project_artifact, rfp_response, sow, status_report), required[] sections, internal[], client[], management[], proof, revision, request_key, file} → **201** | new in live |

**Design parts the live API cannot fill:**
- The Line column and the TEST TEMPLATE tag.
- "Updated by <name> · date" and "N versions" on each row.
- A note with each upload.
- One organisation list of templates across projects.
**Live data the design does not show yet (worth knowing):** a download link for each file; first-template registration with the required sections per audience (internal / client / management); the proof choices; the request key that makes a repeat upload safe.
**Effort to connect:** M. A workspace choice is needed, upload becomes multipart with a proof, and the first-template form is new.
**Questions for the backend:**
1. B-38 Is there an organisation-wide template read, or must the page always pick a project first?
2. B-39 Can `items[]` carry `line`, `test_template`, `updated_at`, `updated_by` and `versions`, or are they gone by design?
3. B-40 What is the `proof` required by a replacement: the previous template's evidence, or a new one, and how is it created?
4. B-41 Can `GET /projects/{case_id}/templates` list the templates available when the person has `document.read` but not upload rights (it needs `document.read`; does it show private templates of others)?

---

### SCR-35 · Clients and client details
**Built today:** yes. F-19 (DONE), routes `/clients` and `/clients/[clientId]`, main files `src/features/clients/` (`ClientsList`, `ClientDetail`, `BillingContactForm`, `api.ts`, `useClients.ts`, `useClient.ts`).
**Live operations:** `GET /clients`, `GET /clients/groups/{group}`, `GET /clients/{case_id}`, `POST /clients/{case_id}/contacts`, `GET .../contacts/history`, `GET .../contacts/options`, `GET` and `POST .../project-people`, `GET` and `POST .../billing-identities`, `GET` and `POST .../workspace-link`, `POST .../workspace-link/{evidence_id}/confirmation`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| List of clients | E-CLIENTS → `items[]` {client_id, name, projects, owed, billing_contact_set, sample} | `GET /clients` → `groups[]` {key (64-char hash), label, project_count, contacts_needed} and `projects[]` (workspaces not in a group) {case_id, title, client, billing recorded / needed / unknown} | reshaped. A "client" is a group of workspaces |
| Client id in the route | `/clients/{client_id}` | group `key`, or a workspace `case_id` | reshaped (`/clients/[clientId]` becomes a group key or a case id) |
| Number of projects | `projects` | `project_count` | renamed |
| Owed | `owed{amount, currency, unknown}` | none (only per project at `/projects/{case_id}/money`) | missing in live |
| Billing contact set? | `billing_contact_set` | group `contacts_needed` (count) and project `billing` status | reshaped (meaning to confirm) |
| Client page: name, projects, money, "blocked" lines | E-CLIENT → `name, projects[], money{invoiced,received,owed}, blocked[], can_change, sample` | `GET /clients/groups/{group}` → `label`, `projects[]` {case_id, title, client, billing}, `next_page` | reshaped; money and blocked missing in live |
| Billing contact name and email, set | `billing_contact{name, email, set}`, `revision` | `GET /clients/{case_id}` → `contacts[]` {contact_id, version, purpose project/billing, customer, client_name, name, email, role}; `revision` | reshaped; per workspace, with history at `.../contacts/history` |
| Legal billing details | none | `GET .../billing-identities` → `items[]` {customer, identity}, `history[]` (legal_name, billing_address, tax_reference), `coverage[]`, `proofs[]`, `can_save` | new in live |
| Named project people, workspace-to-organisation link | none | `.../project-people`, `.../workspace-link` | new in live |
| Search / paging | `limit`, `cursor` | `q`, `billing` (recorded / needed / unknown), `page` (projects), `clients_page` (groups), 25 each | reshaped |

**Writes**
| What the person does | Today (v7 op + body) | Live (op + body) | Fit |
|---|---|---|---|
| Set the billing contact | `PUT /clients/{client_id}/billing-contact` {expected_revision, name, email, reason?} → 200 {client_id, revision} | `POST /clients/{case_id}/contacts` {purpose:"billing", customer, client_name, name, email, role, evidence_id (int, required), expected_revision} → **200** {contact_id, version, ...}; options at `GET .../contacts/options?purpose=billing` (`customers[]`, `proofs[]`) | moved; PUT becomes POST; needs customer, role and a proof |
| Record legal billing identity | none | `POST /clients/{case_id}/billing-identities` {revision, coverage_id, evidence_id, legal_name, billing_address, tax_reference} → **201** | new in live |
| Record a named project contact | none | `POST /clients/{case_id}/project-people` | new in live |
| Propose / confirm a workspace-to-organisation link | none | `POST .../workspace-link`; `POST .../workspace-link/{evidence_id}/confirmation` (needs a separate confirmer) | new in live |

**Design parts the live API cannot fill:**
- Client rows with a money-owed column and a single "billing contact set" tag.
- The client page's money panel (invoiced / received / owed) and the "blocked" lines.
- Billing contact as one person with just a name and an email (live needs customer, role and a proof).
- A stable client id: a group key changes if the grouping changes; a workspace id is per project.
**Live data the design does not show yet (worth knowing):** contact history with versions; legal billing identity (legal name, address, tax reference) kept apart from the billing contact; named project people; the organisation link, with a second person to confirm it; billing status per project.
**Effort to connect:** L. The meaning of "client" changes from a record to a group of workspaces, and the edit moves from one PUT to proof-backed POSTs.
**Questions for the backend:**
1. B-42 Is a "client" a group (key = hash of the name) or a record? Is the group `key` stable and safe to use in a URL?
2. B-43 Can `GET /clients` return the amount owed per group, or is money only per project?
3. B-44 `GET /clients/{case_id}` is per workspace: which workspace's contact is "the client's" billing contact when a group has several projects?
4. B-45 `POST /clients/{case_id}/contacts` needs `evidence_id`: what can the person supply for a billing contact (the options list `proofs`)?
5. B-46 What do `contacts_needed` and `billing` recorded / needed / unknown mean for the "billing contact set" tag?

---

### SCR-38 · Project milestones
**Built today:** yes. F-25 (DONE), route `/projects/[caseId]/milestones`, main files `src/features/projects/MilestonesTab.tsx`, `tabsModel.ts` (read only).
**Live operations:** `GET /projects/{case_id}/money`, `GET /projects/{case_id}/milestones` (tab), `GET/POST /projects/{case_id}/change-milestone-link`, `GET /projects/{case_id}/change-versions/{version_id}`, `GET/POST /projects/{case_id}/commercial-response`, `POST /setup/{case_id}/policy-configurations/{configuration_id}/review`.

**Reads**
| What the screen shows | Today (v7 op → field) | Live (op → field) | Fit |
|---|---|---|---|
| One row per contract milestone: position, name, contract amount | E-PROJECT-TAB milestones → `milestones[]` {position, name, contract_amount, amount_note} | `GET /projects/{case_id}/money` → `items[]` (`label`, `amount`, `currency`, `missing_reason`, `due_date`, `contract_stage`). The `milestones` tab holds only recorded completions | moved. Contract stages are in `/money`, completions in the tab; the page must join them |
| Done on <date> · proof | `completion{status, at, proof, evidence_id}` | `items[].completed_at` in `/money`; tab section "Recorded completions" `at`, `detail` (who), `api_url` to `milestones/{id}` | reshaped (two sources) |
| Invoice reference and state | `invoice{reference, state}` | `/money` → `invoices[]` {reference, status text, at} | reshaped |
| Paid status | `paid{status, owed}` | `/money` → `invoices[].paid`, `owed` (numbers as strings) | reshaped |
| Changes on a milestone ("changed" board: CHANGES column, change amount Unknown) | `changes[]` | `/money` → `items[].changes[]` {link_id, version_id, reference, number, note, plan_id, `additional_amount` always null (shown as Unknown), api_url}; detail from `GET .../change-versions/{version_id}` | reshaped; Unknown is by design |
| Signed agreement and amounts | none | `GET /projects/{case_id}/commercial-response` | new in live |
| Which tab permissions | milestones tab | the tab shows to people with `commercial.read`, `delivery.read` or `milestone.complete`; `/money` needs `finance.read` | reshaped (see Q) |

**Writes** (none built)
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Link an approved change to a milestone | none | `POST /projects/{case_id}/change-milestone-link` {revision, stage uat/completion, plan_event_id, scope_note} → 200 | new in live |
| Mark a milestone complete | none | `POST .../milestones/completions` (see SCR-19) → 201 | new in live |
| Review stage payment terms | none | `POST /setup/{case_id}/policy-configurations/{id}/review` (validated / active / revoked) | new in live |

**Design parts the live API cannot fill:**
- "INV-0412 · awaiting Finance decision" as one composed status (live has the invoice `status` text only).
- Milestone position numbers and the `amount_note` ("to be amended") on the contract amount.
- A milestone-level "Mark milestone N complete" button with a reason when disabled.
**Live data the design does not show yet (worth knowing):** due date per stage; the `limited` flag (figures may be partial); change versions with their reference and number; the signed commercial response.
**Effort to connect:** M. The Milestones tab becomes a join of `/money` and the tab completions.
**Questions for the backend:**
1. B-47 Is `/money` the intended source for the milestone table, with `/milestones` only for proof of completion? Which key joins them (`items[].key` and `record_id`)?
2. B-48 A person with only `milestone.complete` or `delivery.read` can open the milestones tab but `/money` returns 404 without `finance.read`: what should that person see?
3. B-49 Can `/money` `items[]` carry a milestone id and a position so a row can link to its completion?

---

### SCR-39 · Setup: costing rule
**Built today:** no. `/setup/costing-rule` is the "comes next" placeholder (FE-SETUP-COSTING has no feature id). Design: boards for default, review, example, review-own.
**Live operations:** `GET` and `POST /projects/{case_id}/costing`, `GET .../costing/sources/{kind}/{record_id}`, `GET .../costing/calculations/{run_id}`, `GET` and `POST .../costing/proposals/{proposal_id}`, `POST /work`, `GET /work/{work_id}`. Per project: the costing rule belongs to a workspace.

**Reads** (Today is "not built"; v7 has `GET /setup/costing-rule` → `versions[]`, `sections[]`, `not_set`)
| What the screen shows | Today | Live (op → field) | Fit |
|---|---|---|---|
| Rule versions, which is current / proposed / withdrawn | v7 only: `versions[]` {version, label, status, proposed_by, reviewed_by, effective_from} | `GET /projects/{case_id}/costing` → `rules[]` {id, reference, version, sha256}, `policy_status`, `actions[]`, `oracles[]` (the independent examples), `runs[]` {id, status known / held}, `proposal_ids[]`, `evidence[]` | reshaped. No proposer, reviewer names, label or effective dates here |
| The rule's content (rates, rounding) | v7 `sections[]` | `GET .../costing/sources/{kind}/{record_id}` (kind rule or oracle) → `payload` (calculator, inputs, parameters, nodes, outputs), `reviews[]` {verdict, created_at}; restricted | reshaped; payload is not display-ready |
| Proposed version vs the independent examples | v7 sections | `GET .../costing/proposals/{proposal_id}` → `parameters[]` {key, current, proposed}, `comparison[]` {key, before, after, before_matches, after_matches}, `independent_examples[]`, `proposed_examples[]`, `verdicts[]`, `recorded_verdict`, `successor_rule_id`, `hold` | new / reshaped |
| A calculation result | none | `GET .../costing/calculations/{run_id}` → `status`, `holds[]`, `outputs[]` {key, unit, value}, `current_usable`, `cost_approved`, `invoice_created` | new in live |
| Review task for the proposal | `review_work_id` (v7) | `GET /work/{work_id}`; `POST /work` is mapped for starting the pricing line | new in live |

**Writes**
| What the person does | Today | Live (op + body) | Fit |
|---|---|---|---|
| Propose a new version, withdraw | none (D-COSTING-RULE open) | `POST /projects/{case_id}/costing` {action (rule, oracle, rule_review, oracle_review, calculate, bind, propose, draft_*, ...), revision, ...} a different body per action | new in live |
| Decide the proposal (confirm, return, withdraw) | none | `POST .../costing/proposals/{proposal_id}` {revision, verdict confirm / return / withdraw, reason, evidence_id} → **201** {id, revision}; the author gets 403 on deciding their own proposal, but may withdraw | new in live |

**Design parts the live API cannot fill:**
- The version list with "v4 current since 01 Oct", "v3 · 01 Jan–30 Sep" labels and the proposer / reviewer names (live gives ids and hashes).
- Worked example boards in plain business words: the live example is a payload of calculator nodes, and the comparison gives keys and numbers.
- A single organisation costing rule: live reads one project at a time.
**Live data the design does not show yet (worth knowing):** a held calculation and its holds; whether a result is still usable; the rule's hash for audit; scoped policy versions that make a costing rule apply to a project; the "bind" step that attaches a rule and its examples to a project.
**Effort to connect:** L. Not built, no organisation-wide read, and the content is calculator data that needs a readable form.
**Questions for the backend:**
1. B-50 Is there a readable (not raw payload) version of a costing rule and its worked examples, with names for proposer and reviewer?
2. B-51 Which project shows the "organisation" costing rule in Setup, given every costing read needs a `case_id`?
3. B-52 `POST .../costing/proposals/{id}` needs `evidence_id` and `reason`: what evidence does a reviewer supply for a verdict?
4. B-53 What do `POST /work` and `GET /work/{work_id}` do for costing: start a pricing line, or the review task? Which work definition?

---

## Cluster summary
- **Setup needs a workspace first.** Only `GET /setup/primary-roles` and the staff reads are organisation-wide. Rules, delegations, role catalogue, templates, costing and payroll fields are all `/{case_id}`. The Setup frame needs a workspace picker (from `GET /projects`), a `case_id` in the route and the case `revision` on every write; ask the backend how organisation-level values are meant to be reached (B-21, B-27, B-38, B-51).
- **Setup edits are two-step and proof-backed.** The v7 single save (`PUT rules/{component}`, `PUT delegation`) becomes a typed draft plus a review (`validated`, `active`), or a delegation draft. Every one needs an integer `evidence_id`, and no live operation creates that evidence (B-22, B-24, B-25).
- **The project tabs lose their typed rows.** `/projects/{case_id}/{tab}` returns sections of eight-field items; counts, owner role, age, "from meeting" and register switching all go. `delivery` has no live tab. Money, templates, month-end and HR are separate reads (B-5, B-12, B-13, B-35).
- **The journey and list lose the summary fields:** project summary, "what is next", stations, next milestone, tab counts and totals are not in live; item state is text, not a code (B-2, B-4, B-33).
- **Clients are groups of workspaces.** No `client_id`, no owed amount, billing contact is a proof-backed POST per workspace (B-42 to B-46).
- **Connect first:** SCR-22 (S), SCR-29 and SCR-12 reads (S/M), then SCR-07 Journey with the new `items` and `facts`, then SCR-11 and SCR-38 on the section model. Hold Setup (SCR-13, 34, 39), SCR-19 and SCR-35 writes until the backend answers B-21, B-25 and B-29.
