# Questions for the backend: connecting the frontend to API 1.22.0

From the frontend connection map (`delivery/connect/README.md`), 23 Nov 2026. Checked against live OpenAPI 1.22.0 (`contracts/psl-factory.openapi.json` at main `9bac3109`) and, where the schema was not specific enough, against the Django source.

The first section is the short list. Each item groups the screen questions it answers, so one reply settles many. The full list of 222 questions follows, by screen, with stable IDs (`A-1` to `E-32`). Please answer against those IDs. Nothing here asks you to invent a business rule. Where a value waits on a PSL decision, say so and we keep the screen held.

## The short list (answer these first)

1. **Proof files to evidence ids (blocks most writes).** `POST /cases/{case_id}/files` returns an `upload_id`. Decisions, line commands, Setup drafts, client contacts, milestone completion and go-live signatures all need an integer `evidence_id` (or `proof_ids`) that is already recorded case evidence. The only path we found is file-agent work: `POST /cases/{case_id}/files/{upload_id}/drafts`, then `POST .../file-drafts/{job_id}/review`, then `reviewed_evidence_id`. Is that the intended path for a person attaching a signed PDF? Is there a direct "record this file as evidence of kind X" call? Can a plain note serve where the design has no file? Covers A-18, A-27, B-25, B-29, B-37, B-40, B-45, B-52, C-2, C-45, D-1, D-12, D-15, D-26, E-21.
2. **The factory view on work: station track, six facts, agent steps.** v7 gave rows and work items `station{index,count,name}`, `stations[]`, the six facts (drafted, reviewed, approved, sent, receipt, verified) and the agent's steps with cited records. Live `GET /work` and `GET /work/{id}` carry none of these. They are central to the approved design. Will they come back, should we derive them from `history` and the line panels, or should the design drop them? Covers A-6, A-11, A-12, A-31, B-3, B-4, the shared block DC-3 in cluster D, and every "Tola's note" row.
3. **One schema per line panel.** `GET /work/{id}` `panels[]` gives only `{key, url}`, and several panel items are typed as bare `object` (`working[]`, `needs[]`, forecast `result`, BU `result`, project tab `sections[].items`, untyped `action` values). Please publish the panel keys per line with their response schemas, or typed examples, and the allowed `action` values per command. Covers A-16, C-20, E-4, E-12, E-17, E-19, E-25, E-27, E-28, E-31.
4. **Setup without a workspace.** Every Setup read and write except `GET /setup/primary-roles` and the staff reads needs `{case_id}`. Our Setup pages are organisation-wide. Is there an organisation-level read, or should the Setup frame always pick a workspace first? If so, which workspace holds organisation-scope values, and how does a person discover the workspaces they may configure? Covers B-21, B-27, B-38, B-51.
5. **Counts, totals and page size.** Lists return a fixed page (8 rows on `GET /work`), no `limit`, no per-queue or per-tab counts, and filtering can leave a page empty while `next_page` is set. The design shows counts on tabs and offers 10, 20 or 50 rows. Can lists return counts and accept `limit`, and can empty pages be skipped? Covers A-7, A-8, A-38, A-41, A-43, B-5, B-12, B-33, B-34, B-36.
6. **Role words and the menu.** `/me` has no `roles`, and `destinations[]` is the same six entries for every account. Where do we read "Finance Lead · Lagoon Health", and which sections answer 403 per role so the menu can hide them? Covers A-1, A-2, A-36, A-39, A-53.
7. **References and codes, not display text.** Work rows have no `reference` (for example "INV-0412"). Project items give `state` as display words, and register sections are told apart by `title`. Can rows carry the reference and raw status codes, with stable keys for sections and lines? Covers A-6, A-14, B-2, B-12, B-13, D-11.
8. **Start work forms.** `GET /lines` has no field list, `POST /work` has a different body for each of the 25 lines, and `invoice` is not among them. Can each line return its intake fields (name, label, type, required, options source), or do we hand-build 25 forms? Covers A-23, A-25, A-26.
9. **Option lists for form choices.** Several commands take keys whose allowed values are not served: RFP outcome roles, loss reasons and debrief documents, costing amount keys and approval statuses, change stages, release phases, month-end statuses, register filters and invoice statuses. Covers B-14, B-16, C-1, C-26, C-27, D-6, D-14, E-15.
10. **"Confirm what happened" after an uncertain delivery.** `POST /work/{id}/actions` `reconcile` is now a backend lookup (202). The design lets a person with recovery authority record delivered, not delivered or unknown, with proof, when the lookup cannot decide. Is that still possible? Covers A-13, C-19.
11. **Unknown money.** `POST .../payments` accepts a receipt with a null amount (`amount_basis: unknown`), the opposite of our G-SCR20-11. Totals are either a figure or null, so the board's "known part plus Unknown" has no source. Is this intended? Covers E-8, E-10, E-16.
12. **Design parts with no live source.** For each of these, please tell us whether it is coming or should be dropped: Tola's notes and findings on line screens, the document compare view and per-section notes (B-9), alert quiet hours, digest and per-event switches (A-44), image attachments to the Assistant (A-32), the Delivery overview read (D-10), the "Publish to Support" step (D-22), the Finance confirmation at closure (D-25), and "customers affected" and "side effects" on an emergency outcome (D-29).
13. **Hosting and links.** We will serve the frontend from one origin and need it listed exactly in `PSL_FRONTEND_ORIGINS`. Which origin should it be for Railway testing? Will `work_desk_url` and `destinations[].django_url` be removed? Will invitation and recovery links (`join_url`) point at the Next.js origin? Covers A-4, A-54.

## Full list by screen

### A · App frame and core screens


**App frame and session**

- **A-1** `GET /me`: where do we read the person's role words (the v7 `roles[]`) — only from `GET /role-dashboard` `positions[]`, or will `/me` carry a `roles` list?
- **A-2** `GET /me` `destinations[]`: is it intentionally the same six entries for every account, and do `GET /overview`, `/setup/...` and `/clients` answer 403 per role so the frame can hide those sections?
- **A-3** `POST` writes: is a 403 `csrf_failed` always safe to retry once after `GET /session` (nothing executed)?
- **A-4** `GET /me`: will `work_desk_url` and `destinations[].django_url` be removed or left pointing at retired pages? We will not use them.
- **A-5** Status 429 and 503 `read_limited`: do they carry a retry-after or a `code` we can show?
- **A-55** File downloads (`/cases/{case}/files/{upload}/` and the other five routes in `config/urls.py`): a signed-out request gets Django's `302` to `/accounts/login/?next=…`, which the API-only server no longer serves. Can these routes answer `401` JSON like `/api/v1`, so the frontend can show its own signed-out state? (F-56 TECH-1-1, 23 Nov 2026)
- **A-56** `POST /api/v1/session` and `GET /api/v1/role-dashboard` answer 422 "'invite_minutes' is a required property" for a superuser account on a freshly migrated database (local test account `live-admin`, 23 Nov 2026). Is a setup value missing from migrations or seeds, or is this a response-schema bug? (F-57 QA-2-1)

**SCR-01**

- **A-6** `GET /work` item: can rows carry `reference`, `kind` (decide/do/fix/started), `station{index,count,name}` and `agent`, as in v7?
- **A-7** `GET /work`: can the response include per-queue counts, and a `state` filter?
- **A-8** `GET /work`: can the page size be settable (`limit`), and can empty pages be skipped so `next_page` never leads to an empty page?
- **A-9** `GET /work` `line`: do you want us to read titles from `lines[]` only, or can each item carry its `line_title`?
- **A-10** `GET /work` item: is `updated_at` the right stand-in for age, or can you add `started_at`?

**SCR-02**

- **A-11** `GET /work/{id}`: is a stations list (name, status, who holds it) coming, or should the track be dropped / derived from `state` only?
- **A-12** `GET /work/{id}`: can it carry the six facts (drafted, reviewed, approved, sent, receipt, verified) as v7 did, or is each fact read from the line's panel?
- **A-13** `POST /work/{id}/actions` `reconcile`: can a person with recovery authority record "delivered / not delivered / unknown" with proof when the lookup cannot decide, as the design shows?
- **A-14** `GET /work/{id}` `reference`, `started_by`, `started_at`, `amount`: are these available anywhere in live, or are the id and `owner` the only identity?
- **A-15** `GET /work/{id}/history`: can it page (cursor) and filter beyond 30 events, and return an actor kind and a readable event sentence?
- **A-16** `panels[]`: is there a list of every panel `key` per line with its response schema, so we can write one adapter per line?
- **A-17** `current_activity`: which lines return it, and is `watching:true` the only signal to keep polling?

**SCR-03**

- **A-18** `POST /tasks/{id}/decision`: which `review_evidence[]` item should we pre-select for the person, and may the person choose none (the key is required)?
- **A-19** `GET /tasks/{id}`: can it return the approval chain and a `cannot_act_reason` (prepared by you, already decided, not your turn)?
- **A-20** `POST /tasks/{id}/decision`: no `revoke` verdict here, but `payment-controls` and `reviews` have it; is revoke only on those?
- **A-21** `GET /tasks/{id}`: can it return `basis`, a change list against the previous version, and the preparer's name?
- **A-22** Task ids are integers on live; confirm `GET /work/{id}` `tasks[].url` is the page to open for the right packet (task vs role-work vs payment-controls).

**SCR-04**

- **A-23** `GET /lines`: can each item return the intake field list (name, label, type, required, help, options source) as v7 did, or do we hard-code 25 forms?
- **A-24** `POST /work`: is 200 (not 201) with `work_id` the intended success for a first start, and what status does a replay of the same `idempotency_key` return?
- **A-25** `GET /lines` `can_submit_via_api:false`: which lines are false today and what should the screen show for them?
- **A-26** Invoice: which operation starts the Finance invoice line, given `invoice` is not among the 25 `POST /work` lines?
- **A-27** `POST /cases/{case_id}/files`: is the size and type limit published, and does the upload give back a `case_revision` we must send on start?

**SCR-05**

- **A-28** `GET /assistant/conversations`: can items carry `title`, `status` and `status_line` (working / answered / cannot answer / drafted) so the list can show them?
- **A-29** `POST /assistant/conversations`: for the "new conversation" button, which `case_id` do we send when the person has not picked a project (department scope)?
- **A-30** `GET …/conversations/{id}` `messages[].status`: what are all the values, and where is the reason when the agent cannot answer?
- **A-31** Is there a working-progress field (steps or started time) to show while `status` is not final, and how often should we poll?
- **A-32** Is there a way to attach an image to a question (our design allows it), or should we remove that part?

**SCR-06**

- **A-33** `GET /overview`: does `total` mean all recorded work or open work, and is it scoped to the person?
- **A-34** `GET /overview`: can it return totals (in progress, need a person, stopped, verified this month) and per-line station counts with `needs_person`?
- **A-35** `GET /overview`: is a group (floor) for each line key planned, or do we keep our own mapping of 26 keys to 8 floors?
- **A-36** Which roles may read `/overview`: do others get 403 (v7: leads, CEO, CTO only)?

**SCR-10**

- **A-37** `GET /work?queue=exceptions`: can each row carry the exception kind, the time the exception began, and a one-line "what is being done"?
- **A-38** `GET /work?queue=exceptions`: can we get the open total and a `state` filter?
- **A-39** Which role gets this queue (v7 said leads only): is it everyone with access to the record?

**SCR-14**

- **A-40** `GET /work?queue=verified`: can rows carry `verified_at`, the output reference and a one-line proof ("Email delivery receipt · 03 Nov")?
- **A-41** `GET /work?queue=verified`: can we filter by month and get a total count?

**SCR-15**

- **A-42** `GET /notifications`: can items carry `at`, `agent` and a work id (or a typed link) so we can show time, avatar and open the work item?
- **A-43** `GET /notifications`: will it page (`page`/`next_page`) and return an unread count?
- **A-44** `GET /me/alert-preferences`: will per-event switches, digest time and quiet hours come later, or should the design drop them for this release?
- **A-45** `POST /notifications/{id}/read`: is the body `{}` required, and does it need the unread count back?

**SCR-17**

- **A-46** `POST /session` 422 `sign_in_failed`: can it return how many tries are left or when sign-in resumes, or should the design drop those lines?
- **A-47** What are the password rules and the validity of reset links and invitations (30 minutes, 72 hours in the design) — can the preview and recovery status return `expires_at` and the minimum length?
- **A-48** `GET /me/onboarding`: if `admitted` is false what should the person see?
- **A-49** `POST /session` `remember`: what session length does each choice give?

**SCR-21**

- **A-50** `GET /staff`: can people carry `last_sign_in`, `deactivated_at`, `invited_at` and a total count?
- **A-51** `GET /staff/{id}/deactivation` `workspaces[].actions[]`: does each action list the people eligible to take it (for "Move to")?
- **A-52** `GET /staff`: `access` is a single string; can it come as a list of `{role, workspace}` so we can show "Finance Lead · Lagoon Health"?
- **A-53** Which role may open this screen: only delegated Admins ("workspaces you administer"), and what does a non-admin get (empty list or 403)?
- **A-54** `POST /setup/{case}/invitations`: how long is an invitation valid (design says 72 hours) and is the `join_url` host the Next.js origin?

### B · Projects, Setup and clients


**SCR-07**

- **B-1** `GET /projects/{case_id}` `title`: is it always "<Client> · <project>"? The crumb splits on " · ".
- **B-2** `items[].state` is display text from `WORK_STATUS`; can you add the raw status code (ready, waiting, waiting_effect, verified, blocked, ...) so tags are not matched on words?
- **B-3** Can `items[]` carry the station position (index, count, name) and a short detail line, or is this deliberately not in the journey?
- **B-4** Is there a live source for "what is next" and for Tola's project summary, or should those be dropped from the page?
- **B-5** Can `tabs[]` return a count per tab, and which key replaces the Delivery tab (`department-handoffs`, a dossier, none)?
- **B-6** `facts.finance.delivered`: does it mean "invoices verified" as the board labels it, or "invoices with a delivery record"? Where does "Paid" come from on this page?

**SCR-08**

- **B-7** How does a person reach `version_id` from the Documents tab? `GET /projects/{case_id}/documents` items carry only an evidence `record_id` ("Version 2"), not a document version id; which field or link gives `document-reviews/{version_id}`?
- **B-8** Can the preview or controls read return a project title, a document reference, the template name and a test-template flag for the page header?
- **B-9** Is there any live source for per-section agent notes, "changed since previous version", and a compare read? If not, is dropping them the intended design?
- **B-10** `document-reviews/{version_id}` `findings[]` and `review_status`: are these the replacement for the checks panel and the returned banner? Where are the returner's name, time and note?
- **B-11** `POST document-reviews/{version_id}` needs `delegated`: what sets it, and when is it true for an ordinary reviewer?

**SCR-11**

- **B-12** `GET /projects/{case_id}/{tab}` registers: can sections carry a stable `key` (issues, changes, emergencies, rfps) and a total count, so the page does not match on `title` text?
- **B-13** Can register `items` carry `reference` separately from `title`, the owner's role, and `age_seconds` (the issue age is computed but not returned)?
- **B-14** Which values are valid for the `state`, `owner` and `severity` filters, and where does the page read the options?
- **B-15** Should the page open detail from `api_url` (it differs per register), and is there an RFP detail other than the receipt?

**SCR-12**

- **B-16** `money` `invoices[].status`: what are the possible values, and is there a code for "paid / part paid / not paid / not due" or must it be shown as given?
- **B-17** Is `missing_reason` the replacement for v7 `amount_note`, and what text does it hold when the amount is known?
- **B-18** Can `items[]` carry a position number (or state that array order is the stage order)?
- **B-19** `sources[]` has no reference text (such as the signed agreement version); can `label` be relied on to contain it, or can a `reference` field be added?
- **B-20** Can `POST /assistant/conversations` accept the figure `key` so the answer is about that figure?

**SCR-13**

- **B-21** Is there an organisation-level Setup read (rules, delegations, templates, roles) that does not need a `case_id`, or should the frontend always choose a workspace first? Which workspace do organisation scopes belong to?
- **B-22** `GET /setup/{case_id}/rules` has no `component`; how does a row map to a `policy-configurations` component so the page can open a draft?
- **B-23** Can `rules` items carry `can_change` and the editable role options, or must the page infer authority from `policy-scopes` `can_configure` and `can_activate`?
- **B-24** Who may move a draft to `validated` and `active`: the same person who drafted it, or a separate reviewer?
- **B-25** How does a client create the `evidence_id` that every policy write needs (proof file)? No live evidence-upload operation was found.
- **B-26** `GET /setup/{case_id}/delegations` returns user ids only: can it return names, role, reason and status, as the design shows?
- **B-27** Which user can discover which workspaces they may use for Setup (`GET /projects` lists all readable ones, not the ones with `policy.read`)?

**SCR-19**

- **B-28** `POST milestones/completions` `name`: is it any text, or must it equal a contract stage label from `/money`? Is there a milestone id?
- **B-29** How is a `kind=completion` evidence record created through the API? `POST /cases/{case_id}/files` returns an `upload_id`, not an evidence id.
- **B-30** Can the response return the Finance handoff or invoice work id that the completion queues, and when does it appear?
- **B-31** Can the options read return `can_complete` and a reason (not your role, already complete, previous milestone open) so the button can be explained?

**SCR-22**

- **B-32** `GET /projects` `reviews` and `exceptions`: are these "waiting on a person" and "stopped" as the row shows them, and what do `lifecycle` and `phase` hold?
- **B-33** Can the list return per-status counts and a next-milestone name and date, or should those be dropped from the rows?
- **B-34** Is `limit` going to be supported, or is the page size fixed?

**SCR-29**

- **B-35** Can action `items` in the tab carry the status code, `owner` as {name, role}, and the originating meeting {title, date}?
- **B-36** Can the tab return totals for actions (total, overdue, without owner) or must they be counted from every page?
- **B-37** Every action update needs an `evidence` id and a `reason`: how does a person without a file provide evidence (for example a plain note)?

**SCR-34**

- **B-38** Is there an organisation-wide template read, or must the page always pick a project first?
- **B-39** Can `items[]` carry `line`, `test_template`, `updated_at`, `updated_by` and `versions`, or are they gone by design?
- **B-40** What is the `proof` required by a replacement: the previous template's evidence, or a new one, and how is it created?
- **B-41** Can `GET /projects/{case_id}/templates` list the templates available when the person has `document.read` but not upload rights (it needs `document.read`; does it show private templates of others)?

**SCR-35**

- **B-42** Is a "client" a group (key = hash of the name) or a record? Is the group `key` stable and safe to use in a URL?
- **B-43** Can `GET /clients` return the amount owed per group, or is money only per project?
- **B-44** `GET /clients/{case_id}` is per workspace: which workspace's contact is "the client's" billing contact when a group has several projects?
- **B-45** `POST /clients/{case_id}/contacts` needs `evidence_id`: what can the person supply for a billing contact (the options list `proofs`)?
- **B-46** What do `contacts_needed` and `billing` recorded / needed / unknown mean for the "billing contact set" tag?

**SCR-38**

- **B-47** Is `/money` the intended source for the milestone table, with `/milestones` only for proof of completion? Which key joins them (`items[].key` and `record_id`)?
- **B-48** A person with only `milestone.complete` or `delivery.read` can open the milestones tab but `/money` returns 404 without `finance.read`: what should that person see?
- **B-49** Can `/money` `items[]` carry a milestone id and a position so a row can link to its completion?

**SCR-39**

- **B-50** Is there a readable (not raw payload) version of a costing rule and its worked examples, with names for proposer and reviewer?
- **B-51** Which project shows the "organisation" costing rule in Setup, given every costing read needs a `case_id`?
- **B-52** `POST .../costing/proposals/{id}` needs `evidence_id` and `reason`: what evidence does a reviewer supply for a verdict?
- **B-53** What do `POST /work` and `GET /work/{work_id}` do for costing: start a pricing line, or the review task? Which work definition?

### C · RFP, planning, weekly report and minutes


**SCR-16**

- **C-1** `POST /work/{work_id}/rfp-outcome` takes `role`, `loss_reason_key`, `loss_catalog_id` and `debrief_version_id`; which operation lists the allowed roles, loss reasons and debrief documents?
- **C-2** How does a file the person attaches become the integer `evidence_id` that `rfp-outcome`, `team-inputs` and `assignment` expect (there is `POST /cases/{case_id}/files` returning `upload_id`, and `commercial-response/files` returning `id`)?
- **C-3** Is `received_via` (email, WhatsApp, call) stored anywhere on `commercial-response` `action:"witness"`, or should it go in `note`?
- **C-4** `GET /received-bids/{case_id}/team-inputs` does not say which teams are still owed or blocked; is `choices[].team` the full asked list?
- **C-5** Which `/work/{work_id}/reviews` `kind` carries the follow-up `review` (the one between `draft` and `send`)?
- **C-6** For `selection_required`, what does `selection_packet` contain and what must `selection_acknowledged` confirm?

**SCR-23**

- **C-7** `POST /received-bids` returns `case_id` and `receipt_id` but no `work_id`; how does the screen reach the new Unassigned work item (find it in `GET /work?queue=unassigned` by `case_id`)?
- **C-8** What are `authority` (organisation delegation id), `definition` and `context_attested` in `POST /received-bids`, and what does the person see for each?
- **C-9** Is `prospect_name` how a new client is created (closing our G-23-1), and is an existing client matched by name, by `organisations`, or not at all?
- **C-10** Is there a stored Note field for the person logging the RFP, or should the field be removed from the form?
- **C-11** Which duplicate rule applies to the same `reference`, and what status and `code` does it return (our G-23-2/BQ on repeat logging)?

**SCR-24**

- **C-12** Is `evidence` truly required in `POST /received-bids/{case_id}/assignment` (design says optional), and is `reason` the same as our optional Note?
- **C-13** Can `GET …/assignment` return the next-steps sentences and the nominee's role (our G-24-3)?
- **C-14** Does assigning move the item out of `queue=unassigned` immediately, and which work state results?

**SCR-25**

- **C-15** `weekly-report-intake` `evidence[]` and `narratives[]` have only `{id, version, kind}`; where do the labels (for example "Milestone 2 · UAT signed 11 Nov") and this week's meetings, issues, actions and changes come from?
- **C-16** Where is the reviewer's returned note read (only `return_review_id` is given)?
- **C-17** Where is the assembled report text read for the PM before review, and is it `document-reviews/{version_id}` preview?
- **C-18** Does `action:"start"` replace the PM's current `send_to_tola` step, and is a work item (and its progress) visible before it?
- **C-19** Can `POST /work/{id}/actions` `reconcile` carry the checked result and proof?
- **C-20** Which `panels[].key` on `GET /work/{work_id}` points to `weekly-report`?

**SCR-26**

- **C-21** `bid-answers.rows[]` carries only `key` and `response`; where do the requirement wording, RFP page, reference and ordering come from, and is there paging for 64+ rows?
- **C-22** Is there a way to add a requirement (our `add_requirement`), or are requirements fixed by the source analysis?
- **C-23** Which operation gives the Progress figures, the "before review" checks and the tab counts?
- **C-24** How does the PM send the response for review (which op or `reviews` `kind`/`subject`), and how is a return from Engineering shown?
- **C-25** What do `disposition: clarification` rows trigger, and is there a client clarification send/answer record (our G-26-8)?

**SCR-27**

- **C-26** What are the allowed values of `amounts[].key` and `unit` (engineering, security, project management, total) and their display names?
- **C-27** `approvals[].status` is a string; what are the values and is the order PM, PMO Lead, CEO (D-APPROVAL-ORDER) enforced and readable?
- **C-28** Which `reviews` `kind`/`subject` records each approval on the costing sheet, and who may decide the CEO step?
- **C-29** When `max_absolute_value` is unset (PSL decision pending), what is returned for `adjustment_targets`?
- **C-30** Is the delivery plan a costing input anywhere on `bid-pricing.inputs`?

**SCR-28**

- **C-31** `minutes.suggestions[]` has `quote` but no proposed owner, due date or title; does the extraction supply them elsewhere?
- **C-32** Can the audience (internal/client) still change at confirmation, or is it fixed at intake (our G-SCR28-5)?
- **C-33** When are actions created, at `confirmation` or after approval (our G-SCR28-7)?
- **C-34** Where are meeting name, date, time and attendee count read for the meeting card?
- **C-35** Which `reviews` payload do the PMO Lead and Quality reviewer use for outward minutes, and how does Return keep confirmed actions?

**SCR-40**

- **C-36** Does `POST …/bid-submission` need to be pressed after the review approval (our G-40-1), or does approval queue it?
- **C-37** What are the `findings[]` codes in `bid-submission.file` and how should each be worded?
- **C-38** How is a pack made of several parts (forms, response document) listed to the reviewer, and where is the test-template flag (G-40-6)?
- **C-39** Which `reviews` `kind` approves a bid pack, `document` or `bid`?

**SCR-41**

- **C-40** What is `register.value` (project name, code, identity), and who chooses it?
- **C-41** How do `key` and `checked` on `assign` and `details` work, and what does the person confirm?
- **C-42** Can `GET /work/{id}/engagement` return packet rows (scope, price, plan) with labels and the project and planning links as names?
- **C-43** What are Routes B and C, and should the screen name them (our G-41-7)?

**SCR-42**

- **C-44** Where are the labels "asked" for each department (what was requested and when)?
- **C-45** `department-inputs` uses `source_id` (integer); how does a person pick or attach that source, and is it the same id space as `team-inputs.evidence_id`?
- **C-46** Is Infrastructure shown as part of Planning even though team-input on the RFP lists Product instead?
- **C-47** How does the PM know the owner for Product is missing (`owner_status: unassigned`) and where does the person set it (our G-42-4)?
- **C-48** Is the `handoff` decision a separate human approval from `prepare_readiness` (our G-42-6)?

### D · Delivery, issues, change, emergency and escalation


**SCR-30**

- **D-2** `GET .../issues/{id}` and `issue-followup` carry no raised date, age or "blocks" milestone; where do these come from?
- **D-3** Is there a ready-made "what has happened" list for an issue (owner updates, reminders) or must we build it from `history`, `messages` and `acknowledgement`?
- **D-4** In `issue-followup` POST, when is `team_reply` used versus `POST .../team-replies` (same data)?

**SCR-31**

- **D-5** Must all five deciders approve every change (the design's open question)? `decisions[]` lists roles but not whether each is required.
- **D-6** `change.stage` values: please list them so we can draw the five-step track.
- **D-7** `close` needs `pm_signature`/`client_signature` source fields (source_system, decision_id...); what does a PM enter for a client who does not log in?

**SCR-33**

- **D-8** Where do "went well / did not / lessons" go: three headed sections inside `summary`, or `decisions[]`? Is there a draft state?
- **D-9** Can `GET /projects/{case}/meetings` `kind=retrospective` be filtered to the current one the closure checklist selects (`retrospective_id`)?

**SCR-43**

- **D-10** Will there be a delivery overview read (the six lines, their gate state, reference and date, even before started)? Today the design needs `delivery[]`.
- **D-11** Which `GET /projects/{case}` `items[].line` values are the six delivery lines? Please give stable keys (today a display title).

**SCR-44**

- **D-12** What evidence does `planning-exit` expect in `evidence_id` (the list is `proofs[]`)? Can the decision be recorded with only a note, as the design shows?
- **D-13** Who triggers `prepare_readiness`: the PM by click, or the system once approved (the design says Tola)?
- **D-14** Please list the `release-register` `phases[].name` and `checks[].status` values, so we can draw the tags.

**SCR-45**

- **D-15** Is "signed" always two separate signature evidences (PM and client), or can one uploaded signed copy serve both?
- **D-16** What does the PM enter for `signers.*.source_system`, `decision_id`, `decision_version` (the client does not log in)?
- **D-17** `go-live-milestone` `draft_mapping` needs `owner_decision_id`; who is the owner and when is this done before "Mark milestone complete"?

**SCR-46**

- **D-18** Should "log an observation" in the PM's hands record a metric reading (`stability` POST) or a free note? How should an open issue appear in the list?
- **D-19** Is there a per-criterion result (MET / NOT MET) to draw, or only `qualified` plus `findings[]`?

**SCR-47**

- **D-20** Does `files[]` carry a group or source kind (RFP, costing...), or must we group by `sources[].label`?
- **D-21** Is archive started by a person (`reserve` with `source_ids`) or by the system after go-live? Can it default to `required_source_ids`?

**SCR-48**

- **D-22** Where does the PM see and trigger "Publish to Support", or is it automatic after review? Which field says "ready to publish"?
- **D-23** Can `support-replies` carry gaps as a list (`gaps[]`) rather than inside `note`?
- **D-24** Which read gives the handover document title, version and attachments?

**SCR-49**

- **D-25** How does Finance record its confirmation (milestone notification coverage)? No operation is listed.
- **D-26** In `reviews` `kind:"closure"`, what is `evidence_id` (the closure report evidence)? Is `version_id` the closure document version?
- **D-27** Can closure reads carry the open debt list (the design's "still open after closure")?

**SCR-50**

- **D-28** `record_review` has no verdict; how does the reviewer return an outcome?
- **D-29** Where do "customers affected" and "side effects" go in the outcome record?
- **D-30** Which read gives the names and times of the authoriser and outcome recorder (`recorded_authorizations` is ids only)?

**SCR-51**

- **D-31** Which `verdict` means "Don't escalate" (`reject` or `return`)? Is the note returned in `history[]`?
- **D-32** Which read gives the drafted message text and recipients for the review screen?

**SCR-52**

- **D-33** Can the intake offer "all projects I can see" (flag `all_projects_available`) without listing every record id?
- **D-34** Where are the headline figures (counts) the design shows; are they derived from `selections` or do we compute them?
- **D-35** Who requests the leadership review: the system after the draft, or a PM step?

**All delivery screens**

- **D-1** what call turns `POST /cases/{case_id}/files` (`upload_id`) into the evidence id (`evidence_id`, kind such as `signature`, release log, notes file) that line commands require?

### E · Finance and Payroll


**SCR-09**

- **E-1** Does `inputs[].codes[]` have a published list with plain-language text (and expected / found sheet names) so the error board can be written?
- **E-2** Is there an endpoint or file for "Download template" for each `provider_options.formats` entry?
- **E-3** Which `kind` values does `payroll/{kind}/{record_id}/working-rows` accept (input, combined run, match), and who gets 403 vs 404 when not an admitted reader?

**SCR-18**

- **E-4** What are the fields of `payroll-operations` → `working[]` and `hr_receipt`, and do they carry matched / unmatched / conflict / held counts?
- **E-5** In `payroll/reports/{id}` → `by_business_unit`, how is a business unit with unmatched staff shown (null, a flag, or left out), and is a staff count included?
- **E-6** Is "I didn't receive the HR snapshot, confirm receipt" (`hr_receipt`) a POST on `payroll-operations` (which action value)?

**SCR-20**

- **E-7** Is `GET /payments` item `age_days` days overdue or days since issue, and where is the due date?
- **E-8** `POST .../payments` accepts a null amount with `amount_basis: unknown`. We had asked for a receipt to be refused when its amount is unknown (G-SCR20-11); is that intended?
- **E-9** Can `GET /payments` return `received this month` and a bank-data-as-of date, or should we use `/projects/{case_id}/money`?
- **E-10** When `totals[].owed` is null, is that the whole total unknown, or can a known part plus unknown be given?
- **E-11** Does `limited: true` mean the totals exclude rows, and how should the page word it?

**SCR-32**

- **E-12** What `action` values does `reminder/actions` take (release, schedule, reconcile, close, set aside)? The spec shows `action` untyped.
- **E-13** Does the 7-day follow-up sentence come from `settings.minimum_days_between`, and is it exposed to the reader?

**SCR-36**

- **E-14** Does `GET /month-end` hide payroll/restricted rows for non-HR readers, and does `work[]` include restricted lines as a label only?
- **E-15** What are `periods[].values` and `status` values (open, captured, closed)?
- **E-16** Is `cash[].amount` ever null when `cash_unavailable` is true, or is it "0.00"?

**SCR-37**

- **E-17** What are the fields of `hr-disclosures` `needs[]`, `disclosures[]`, `decisions[]` and `corrections[]` items?
- **E-18** Is the correction list per disclosure only, or can a project-level list of waiting corrections be read?

**SCR-53**

- **E-19** What are the `action` values of `POST /work/{id}/accounting`, and what is in `review_stations[]` and `tasks[]`?
- **E-20** Is `findings[]` a code list or prepared sentences?

**SCR-54**

- **E-21** Which `reviews` variant carries a schedule approval, and is `evidence_id` required for approve?
- **E-22** How is "schedule reviewer not set" signalled on `finance-schedule`?

**SCR-55**

- **E-23** What is `purpose: basis` (calculation basis review) and when is it requested versus register and schedule?
- **E-24** Where does the reader get the accounting note text from `accounting_note_id`?

**SCR-56**

- **E-25** What are the shapes of `forecast` → `result`, `jobs[]`, `disclosure`, `matches[]`?
- **E-26** Do payroll rows in a group disclosure respect the restricted-payroll visibility (HR-only) before a group reviewer sees them?

**SCR-57**

- **E-27** What are the fields of `business-units` → `result` and `inputs`, and where is the small-group withholding reason?
- **E-28** Which `action` values does `POST business-units` accept?

**SCR-58**

- **E-29** Do `observation` and `latest_decision` carry the reviewer's name and time, and is "not the capturer, not the observer" an independent-review reason code?

**SCR-59**

- **E-30** Does `eligible_total` ever carry an unknown or excluded part, and how is it marked?
- **E-31** Which `action` values does `payroll-operations` accept, and what does `working[]` carry per station?
- **E-32** Can a BU totals run (SCR-57) read the published payroll aggregate, or the match run, as its payroll input?

## New from lanes

Added during the two-day push (D-180), with a lane prefix (LA-, LB-, LC-).

- **LC-1 (F-85)** `GET /work/{id}` `panels[]` and `tasks[].url`: for each line, which `panels[].key` values exist and what is each response schema? The weekly-report readback is typed, but `recipients[]` and `evidence[]` items are typed loosely. A typed example per line would let one adapter per line be written without guessing.
- **LC-2 (F-85)** `POST /cases/{case_id}/files` is built as the evidence picker on the best reading of question 1: upload, then file-agent draft and review to `reviewed_evidence_id`. If a direct "record this file as evidence" call exists, which one is it?
- **LC-3 (F-88)** `GET /received-bids/{case_id}/assignment` `proofs[]` and `POST …/assignment` `evidence`: `proofs[]` is capped at 26 and has only `{id,label}`. Which evidence kinds does it list, and is a proof for a received RFP something the person can add from the screen (and through which call), or must it already exist?
- **LC-4 (F-88)** `POST /received-bids` on a repeated `reference` or a repeated `start_key` with different values: which status and `code` come back (409 or 200 replay), and does a replay with the same `start_key` return the same `receipt_id`?
- **LC-5 (F-88)** After `POST …/assignment` returns 201, does the item leave `GET /received-bids/assignments` at once, and which work state does it have? A second assignment on the same `intake`: 409 with which `code`?
- **LC-6 (F-86)** `GET /projects/{case_id}/intake-sources?line=pmo-weekly-report/v1`: which names come back in `fields[]` for the weekly report, and does any of them list templates or client content (the ids `template_id` and `content_id` in the `POST /work` weekly body, both nullable)? Until answered the weekly start sends both as null.

- **LB-1** (lane B, F-76, SCR-21) `GET /staff` returns `available: false` with `observed_at`. We read it as "the list is partial or stale as of `observed_at`" and show a notice. Is that right, or does it mean something else (staff directory offline, no rows at all)? Related to A-50.
- **LC-7 (F-87)** `POST /work/{id}/background` `{expected_revision, enabled}` and `GET /work/{id}` `actions[]` `background`: where does the page read whether background work is now running or paused? `progress.status` is free text. Without it the page shows both Pause and Continue and relies on a 409 or 422.
- **LC-8 (F-87)** `POST /work/{id}/actions` `reconcile` (202 `{work_id, state, revision}`): when the lookup cannot decide, does the state stay `awaiting_reconciliation` or `effect_uncertain`, and is there a later route for a person to record the outcome with proof (see question 10, C-19)? The page only shows the returned state.
- **LC-9 (F-89)** `POST /work/{id}/reviews` (kind `document`) and `POST /work/{id}/weekly-report` (`correct`) have no key field. If a page repeats a verdict after a timeout, does the server refuse it (409 on `expected_revision`, `version_id` or an existing review) or does it record and send again? Is there a readable sign (state, `review_id`, `recipients[]`, revision) that an approve whose answer was lost was recorded?
- **LC-10 (F-89)** `GET /work/{id}/weekly-report` `review_verdicts[]`: is it exactly the verdicts this person may give now (including the independence rule when they wrote the report)? Does a reviewer, who is not the author, receive `editable_parts` or `draft` (the report text), or `null`? After `correct`, does `document_version_id` change (v2) and does `return_review_id` clear?
- **LB-2** (lane B, F-78, SCR-19) PSL decided the PMO Lead confirms the exact milestone before completion is recorded. Does `POST /projects/{case_id}/milestones/completions` enforce PMO Lead authority (backend-answers.md says the sibling go-live flow still checks PM authority), and does `GET .../milestones/completions/options` `can_complete` reflect it?
