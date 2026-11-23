# Backend Answers

**224 answered screen questions**

Each entry keeps the frontend developer's original question and ID. The questions reflect API 1.22.0, which was live when the frontend team wrote them. The answers describe API 1.26.0. Paths in the answers are relative to `/api/v1`.

[Original frontend questions](backend-questions.md) · [13 priority answers and five follow-ups](backend-answers-2026-11-23.md) · [OpenAPI contract](../../contracts/psl-factory.openapi.json) · [Production API](https://psl-web-production.up.railway.app/api/v1/openapi.json)

## A · App frame and core screens

### App frame and session

#### A-1

**Question**  `GET /me`: where do we read the person's role words (the v7 `roles[]`) — only from `GET /role-dashboard` `positions[]`, or will `/me` carry a `roles` list?

**Answer**  Read positions from GET /me or GET /role-dashboard. Use each position’s name, mode and workspace for the role words. There is no separate roles array.

#### A-2

**Question**  `GET /me` `destinations[]`: is it intentionally the same six entries for every account, and do `GET /overview`, `/setup/...` and `/clients` answer 403 per role so the frame can hide those sections?

**Answer**  Use destinations[].key, url and available for navigation. The list keeps its six entries. Authenticated Overview is scoped and may be empty; the Clients list is scoped to visible links; specific Setup reads and writes enforce their own permissions.

#### A-3

**Question**  `POST` writes: is a 403 `csrf_failed` always safe to retry once after `GET /session` (nothing executed)?

**Answer**  Retry once after refreshing GET /session when the response specifically says csrf_failed. The CSRF middleware rejected that request before the handler. Use the same request and idempotency key.

#### A-4

**Question**  `GET /me`: will `work_desk_url` and `destinations[].django_url` be removed or left pointing at retired pages? We will not use them.

**Answer**  Use destinations[].url for Next.js. Compatibility fields remain. API-only /me returns Next.js destinations and /my-work; archived Django pages return the retired-page response on the API-only service.

#### A-5

**Question**  Status 429 and 503 `read_limited`: do they carry a retry-after or a `code` we can show?

**Answer**  Read the JSON code and message. The work access limit uses rate_limited; a bounded source read uses read_limited with 503. The common error response does not guarantee Retry-After.

#### A-55

**Question**  File downloads (`/cases/{case}/files/{upload}/` and the other five routes in `config/urls.py`): a signed-out request gets Django's `302` to `/accounts/login/?next=…`, which the API-only server no longer serves. Can these routes answer `401` JSON like `/api/v1`, so the frontend can show its own signed-out state? (F-56 TECH-1-1, 23 Nov 2026)

**Answer**  All six public backend download links return JSON 401 to a signed-out request. The old Django login route returns retired-page on the API-only service. The original signed-in file access checks still run.

#### A-56

**Question**  `POST /api/v1/session` and `GET /api/v1/role-dashboard` answer 422 "'invite_minutes' is a required property" for a superuser account on a freshly migrated database (local test account `live-admin`, 23 Nov 2026). Is a setup value missing from migrations or seeds, or is this a response-schema bug? (F-57 QA-2-1)

**Answer**  The Admin role can load without invite_minutes. Existing administration-only authority remains usable, and an incomplete invitation delegation cannot invite. Enabling invitations in a new delegation requires a real duration. PostgreSQL session and role tests passed.

### SCR-01

#### A-6

**Question**  `GET /work` item: can rows carry `reference`, `kind` (decide/do/fix/started), `station{index,count,name}` and `agent`, as in v7?

**Answer**  Work rows expose the action kind, current station index and name, owner, reference, intake and verification times. The initiating staff member sees the Assistant persona when their own chat started the work. Follow tracking_url for the latest recorded worker activity.

#### A-7

**Question**  `GET /work`: can the response include per-queue counts, and a `state` filter?

**Answer**  GET /work accepts state and supplies the filtered total when it can evaluate all matching work. GET /work/counts reports totals for all queue types together when complete and includes the number actually observed.

#### A-8

**Question**  `GET /work`: can the page size be settable (`limit`), and can empty pages be skipped so `next_page` never leads to an empty page?

**Answer**  limit accepts 8, 10, 15, 20 or 50. The backend looks ahead through at most two empty candidate pages within its read budget. Continue with next_page when there is one. An empty page is still possible.

#### A-9

**Question**  `GET /work` `line`: do you want us to read titles from `lines[]` only, or can each item carry its `line_title`?

**Answer**  Resolve item.line against lines[].key and title. A work row has no line_title field.

#### A-10

**Question**  `GET /work` item: is `updated_at` the right stand-in for age, or can you add `started_at`?

**Answer**  Read started_at for age from intake and updated_at for the last update. The project journey also supplies each item’s start time.

### SCR-02

#### A-11

**Question**  `GET /work/{id}`: is a stations list (name, status, who holds it) coming, or should the track be dropped / derived from `state` only?

**Answer**  Tracking gives the current station, station order, recorded status, current owner and next step. Intake and human decision stations name their recorded actor when available. A future station can have no recorded owner.

#### A-12

**Question**  `GET /work/{id}`: can it carry the six facts (drafted, reviewed, approved, sent, receipt, verified) as v7 did, or is each fact read from the line's panel?

**Answer**  Read tracking.facts for drafted, reviewed, approved, sent, receipt and verified. Null is unknown or unavailable. Invoice and controlled-publication facts use their native records. For checklist facts on specialist lines use their own panels.

#### A-13

**Question**  `POST /work/{id}/actions` `reconcile`: can a person with recovery authority record "delivered / not delivered / unknown" with proof when the lookup cannot decide, as the design shows?

**Answer**  POST to work detail’s delivery_observation_url using the original uncertain effect, outcome, reason and work proof. The original reconcile action still performs the provider lookup. The observation does not dispatch or verify a send.

#### A-14

**Question**  `GET /work/{id}` `reference`, `started_by`, `started_at`, `amount`: are these available anywhere in live, or are the id and `owner` the only identity?

**Answer**  Work detail gives reference, ID and current owner. Tracking gives the intake date and person who started it. Read the relevant invoice or Finance panel for amounts and currency.

#### A-15

**Question**  `GET /work/{id}/history`: can it page (cursor) and filter beyond 30 events, and return an actor kind and a readable event sentence?

**Answer**  GET /work/{id}/history accepts kind=worker, decision or evidence and returns actor_kind, actor, station, status, time and the next cursor for older events. Compose the sentence from those fields.

#### A-16

**Question**  `panels[]`: is there a list of every panel `key` per line with its response schema, so we can write one adapter per line?

**Answer**  Use each returned panel’s key, url and contract_path. The latter points to the exact OpenAPI path where available. Choose schemas by operation and line. The server owns the panel list for each item.

#### A-17

**Question**  `current_activity`: which lines return it, and is `watching:true` the only signal to keep polling?

**Answer**  current_activity is optional and comes from accounting, BU, escalation, forecast, ledger, PPE, reporting or schedules projections. watching indicates that activity view can keep watching. Also use work state, progress and explicit next action to stop or resume polling.

### SCR-03

#### A-18

**Question**  `POST /tasks/{id}/decision`: which `review_evidence[]` item should we pre-select for the person, and may the person choose none (the key is required)?

**Answer**  For an invoice task, choose an exact item from review_evidence; decision.evidence_id is required. If no options are present, show why the decision is unavailable or route to proof collection. A PMO Lead approval rule does not change Finance task proof.

#### A-19

**Question**  `GET /tasks/{id}`: can it return the approval chain and a `cannot_act_reason` (prepared by you, already decided, not your turn)?

**Answer**  Task detail exposes its roles, checks, permitted verdicts and hold code where it applies. The tracking read gives the recorded stations and the invoice-specific review steps are available through its review-stations link.

#### A-20

**Question**  `POST /tasks/{id}/decision`: no `revoke` verdict here, but `payment-controls` and `reviews` have it; is revoke only on those?

**Answer**  This task accepts approve, return or reject. Revoke is specific to review variants that expose it, such as schedule or asset, or to the relevant payment control operation.

#### A-21

**Question**  `GET /tasks/{id}`: can it return `basis`, a change list against the previous version, and the preparer's name?

**Answer**  invoice_packet provides the amount, currency, basis, preparer and current proof. Compare earlier_version for changes where a previous accessible version of the exact obligation exists. Recipient changes keep their own evidence.

#### A-22

**Question**  Task ids are integers on live; confirm `GET /work/{id}` `tasks[].url` is the page to open for the right packet (task vs role-work vs payment-controls).

**Answer**  Work and task IDs are integers. Use the given tasks[].url for that task, the role-work link for a role assignment, and the payment-controls operation for payment controls. They refer to different record types.

### SCR-04

#### A-23

**Question**  `GET /lines`: can each item return the intake field list (name, label, type, required, help, options source) as v7 did, or do we hard-code 25 forms?

**Answer**  GET /lines returns request_schema, content_type, project_options_url and submit_url. Each authorised line supplies the exact validation schema. Labels, help and source links come from the screen and the line’s options endpoints.

#### A-24

**Question**  `POST /work`: is 200 (not 201) with `work_id` the intended success for a first start, and what status does a replay of the same `idempotency_key` return?

**Answer**  POST /work returns 200 with work_id, state, revision and background status. Replaying the same operation on the same inputs returns the same work. Changed data under a reused key is a conflict wherever the native operation reports that replay mismatch.

#### A-25

**Question**  `GET /lines` `can_submit_via_api:false`: which lines are false today and what should the screen show for them?

**Answer**  The listed native start types have a typed submit operation. received-bid uses its separate multipart endpoint. The catalogue is filtered by current authority. If can_submit_via_api is false in any deployed version, use its indicated supported flow or show it as unavailable.

#### A-26

**Question**  Invoice: which operation starts the Finance invoice line, given `invoice` is not among the 25 `POST /work` lines?

**Answer**  POST /work uses line=pmo-finance/v1. The two intake variants use mode=completion for coverage and handoff, or mode=preparation for an existing billing preparation.

#### A-27

**Question**  `POST /cases/{case_id}/files`: is the size and type limit published, and does the upload give back a `case_revision` we must send on start?

**Answer**  Private file upload permits one multipart file up to 5 MiB and returns upload_id, name, size, SHA-256 and download URL. It does not return a case revision. Use the case or project chooser for the current revision. Model review and individual domain uploads impose their own file rules.

### SCR-05

#### A-28

**Question**  `GET /assistant/conversations`: can items carry `title`, `status` and `status_line` (working / answered / cannot answer / drafted) so the list can show them?

**Answer**  The conversation list supplies a title, latest status, scope and update time. Conversation detail gives message history.

#### A-29

**Question**  `POST /assistant/conversations`: for the "new conversation" button, which `case_id` do we send when the person has not picked a project (department scope)?

**Answer**  Department conversations still need an authorised case_id as the starting workspace. Send scope=department for a persona/role that allows it. A department lead can choose an accessible project to anchor the thread; the department rules determine what the assistant reads.

#### A-30

**Question**  `GET …/conversations/{id}` `messages[].status`: what are all the values, and where is the reason when the agent cannot answer?

**Answer**  Message status is queued, running, answered or held, or the projected source_changed. A held turn has no public failure explanation; show a generic retry/access message. An answered turn can contain the insufficient-evidence reply.

#### A-31

**Question**  Is there a working-progress field (steps or started time) to show while `status` is not final, and how often should we poll?

**Answer**  Read the turn’s state, started_at and finished_at. Poll while it is queued or running. Native work tracking provides station activity for linked work.

#### A-32

**Question**  Is there a way to attach an image to a question (our design allows it), or should we remove that part?

**Answer**  Upload up to three private images to the conversation’s case and pass their IDs with the message. The backend checks ownership, format and permission, includes them with authorised case context in the OpenRouter request, and returns the image IDs with the turn.

### SCR-06

#### A-33

**Question**  `GET /overview`: does `total` mean all recorded work or open work, and is it scoped to the person?

**Answer**  Overview gives as_of and counts by line for discoverable work excluding verified and cancelled. It is scoped to the signed-in person. There is no top-level total; summing the returned line counts gives the visible open total under that definition.

#### A-34

**Question**  `GET /overview`: can it return totals (in progress, need a person, stopped, verified this month) and per-line station counts with `needs_person`?

**Answer**  GET /work/counts supplies open, stopped, held, needs-person and monthly verified counts with a per-line station breakdown. Label observed counts with the returned coverage.

#### A-35

**Question**  `GET /overview`: is a group (floor) for each line key planned, or do we keep our own mapping of 26 keys to 8 floors?

**Answer**  The API exposes line key, title and total. Floor grouping is a display mapping owned by the frontend. The backend does not supply a floor per line.

#### A-36

**Question**  Which roles may read `/overview`: do others get 403 (v7: leads, CEO, CTO only)?

**Answer**  The current endpoint is authenticated and uses record scope; it does not enforce a leads/CEO/CTO-only rule. A user may get an empty scoped view.

### SCR-10

#### A-37

**Question**  `GET /work?queue=exceptions`: can each row carry the exception kind, the time the exception began, and a one-line "what is being done"?

**Answer**  Exception rows return exception_code, the current next step, and the recorded start time when the exception is the persisted work status. A derived hold or an earlier record can have no captured start time.

#### A-38

**Question**  `GET /work?queue=exceptions`: can we get the open total and a `state` filter?

**Answer**  Use queue=exceptions with state and read total. It is null when full coverage is unavailable. Do not count the displayed page as the open total.

#### A-39

**Question**  Which role gets this queue (v7 said leads only): is it everyone with access to the record?

**Answer**  The work queue uses current discoverable work and exception eligibility for the actor. Its access does not come from a leads-only menu rule.

### SCR-14

#### A-40

**Question**  `GET /work?queue=verified`: can rows carry `verified_at`, the output reference and a one-line proof ("Email delivery receipt · 03 Nov")?

**Answer**  Verified rows carry the actual recorded verified_at and, where accessible, queue_output_url. Use that exact output or receipt for the proof sentence. Recipient-only data stays on its published report.

#### A-41

**Question**  `GET /work?queue=verified`: can we filter by month and get a total count?

**Answer**  Filter the verified queue by verified_month=YYYY-MM. The filter uses a recorded verification event; undated legacy work stays out of a dated filter.

### SCR-15

#### A-42

**Question**  `GET /notifications`: can items carry `at`, `agent` and a work id (or a typed link) so we can show time, avatar and open the work item?

**Answer**  Personal alerts supply typed destinations and the original event time where recorded. A legacy alert can have no recorded time.

#### A-43

**Question**  `GET /notifications`: will it page (`page`/`next_page`) and return an unread count?

**Answer**  GET /alerts gives a cursor and unread count for the matching authorised alert set. Acknowledge the exact alert to change its read state.

#### A-44

**Question**  `GET /me/alert-preferences`: will per-event switches, digest time and quiet hours come later, or should the design drop them for this release?

**Answer**  Use the in-app alert inbox and its daily summary. The response supplies the date and open actions, updates and unread items without a recorded time. Email and WhatsApp remain deferred.

#### A-45

**Question**  `POST /notifications/{id}/read`: is the body `{}` required, and does it need the unread count back?

**Answer**  Send the required JSON object {}. Success returns id and read. The receiver can update local state or reread the inbox. There is no count in that response.

### SCR-17

#### A-46

**Question**  `POST /session` 422 `sign_in_failed`: can it return how many tries are left or when sign-in resumes, or should the design drop those lines?

**Answer**  Sign-in returns generic sign_in_failed with no remaining-attempt or lockout time fields. The current Next.js sign-in uses that generic result. Avoid showing a countdown without a supported rate-limit response.

#### A-47

**Question**  What are the password rules and the validity of reset links and invitations (30 minutes, 72 hours in the design) — can the preview and recovery status return `expires_at` and the minimum length?

**Answer**  Invitation setup and recovery password paths use a 12-character minimum and their password validators. Recovery has a 30-minute lifetime and exposes ready as a boolean. Invitation preview gives expires_at, which comes from the real invitation. The response does not include a password-rule object.

#### A-48

**Question**  `GET /me/onboarding`: if `admitted` is false what should the person see?

**Answer**  For admitted=false show the signed-in person that no work is available to them and give the ordinary sign-out or contact-Admin path. Current Next.js handles this state. It does not require redirecting to an archived Django form.

#### A-49

**Question**  `POST /session` `remember`: what session length does each choice give?

**Answer**  remember=false uses a browser-session cookie. true uses the configured normal Django age, 14 days if the standard default has no deployment override. The endpoint does not return an expiry time.

### SCR-21

#### A-50

**Question**  `GET /staff`: can people carry `last_sign_in`, `deactivated_at`, `invited_at` and a total count?

**Answer**  GET /staff returns separate authorised totals for accounts and invitations, last sign-in, invitation creation and expiry, and the audited deactivation date where available.

#### A-51

**Question**  `GET /staff/{id}/deactivation` `workspaces[].actions[]`: does each action list the people eligible to take it (for "Move to")?

**Answer**  The deactivation packet’s workspaces[].actions[] gives eligible successors per action and whether it may become unassigned. Send the selected person or permitted null with the exact fingerprint.

#### A-52

**Question**  `GET /staff`: `access` is a single string; can it come as a list of `{role, workspace}` so we can show "Finance Lead · Lagoon Health"?

**Answer**  Roster access is a display summary. GET /staff/{id} gives authorised workspaces and each primary_role. /me positions describe the signed-in person, not arbitrary staff.

#### A-53

**Question**  Which role may open this screen: only delegated Admins ("workspaces you administer"), and what does a non-admin get (empty list or 403)?

**Answer**  Staff roster uses scoped staff-administration authority and returns an availability flag with scoped/empty results. Targeted staff reads and writes enforce exact authority. A global Admin label is no substitute for current scope.

#### A-54

**Question**  `POST /setup/{case}/invitations`: how long is an invitation valid (design says 72 hours) and is the `join_url` host the Next.js origin?

**Answer**  The active tenant authority’s invite_minutes and expiry determine the invitation expiry. Use invitation.expires_at; there is no universal 72-hour duration. join_url is built from the request host and carries the token as a fragment. Verify the actual Next.js invite origin and route at deployment.

## B · Projects, Setup and clients

### SCR-07

#### B-1

**Question**  `GET /projects/{case_id}` `title`: is it always "<Client> · <project>"? The crumb splits on " · ".

**Answer**  title is the project display name. Treat it as one string. The project/client relationship is separate, so splitting on a dot does not reliably identify a client.

#### B-2

**Question**  `items[].state` is display text from `WORK_STATUS`; can you add the raw status code (ready, waiting, waiting_effect, verified, blocked, ...) so tags are not matched on words?

**Answer**  Project tab register/action rows have state_code and display state. The top-level project journey items still have display state; follow api_url to exact work for its machine state and line.

#### B-3

**Question**  Can `items[]` carry the station position (index, count, name) and a short detail line, or is this deliberately not in the journey?

**Answer**  Each journey item identifies its work kind, start, current state and exact API link. Open the linked tracking read for station order, current owner and next step.

#### B-4

**Question**  Is there a live source for "what is next" and for Tola's project summary, or should those be dropped from the page?

**Answer**  Use each work item’s next_step and blocker, and facts.finance.next for the Finance milestone prompt when available. Tola can be opened through the project’s assistant links. The project read does not contain a prewritten Tola summary.

#### B-5

**Question**  Can `tabs[]` return a count per tab, and which key replaces the Delivery tab (`department-handoffs`, a dossier, none)?

**Answer**  Tabs provide allowed keys and links, not counts. Use the Delivery overview for its six lines and Department handoffs for native receipts; those views serve different tasks.

#### B-6

**Question**  `facts.finance.delivered`: does it mean "invoices verified" as the board labels it, or "invoices with a delivery record"? Where does "Paid" come from on this page?

**Answer**  facts.finance.delivered counts visible invoices with a delivery record. It does not measure payments. Use paid/owed from /money, /billing-invoices/{id} or /payments under Finance access.

### SCR-08

#### B-7

**Question**  How does a person reach `version_id` from the Documents tab? `GET /projects/{case_id}/documents` items carry only an evidence `record_id` ("Version 2"), not a document version id; which field or link gives `document-reviews/{version_id}`?

**Answer**  GET /projects/{case}/document-versions lists readable standalone controlled report versions and links to their exact preview and controls. The project Evidence tab continues to identify original sources.

#### B-8

**Question**  Can the preview or controls read return a project title, a document reference, the template name and a test-template flag for the page header?

**Answer**  Use the report title, version, audience, template name/version and sample flag from the preview, plus the project title from Project detail.

#### B-9

**Question**  Is there any live source for per-section agent notes, "changed since previous version", and a compare read? If not, is dropping them the intended design?

**Answer**  Compare two authorised versions of the same standalone report for changed, added, removed and unchanged sections and evidence IDs. Weekly report review separately returns draft-only notes by section.

#### B-10

**Question**  `document-reviews/{version_id}` `findings[]` and `review_status`: are these the replacement for the checks panel and the returned banner? Where are the returner's name, time and note?

**Answer**  The /publication read gives findings for the checks and review_status for the current review workflow. The generic API does not return the returner’s name, timestamp and reason in that read. Those need a scope-checked review-history projection where the board requires them.

#### B-11

**Question**  `POST document-reviews/{version_id}` needs `delegated`: what sets it, and when is it true for an ordinary reviewer?

**Answer**  Use the allowed decision token from preview. The suffix distinguishes ordinary and delegated routes. delegated=true is used only for the current delegated option. The server verifies that authority. An ordinary reviewer uses false.

### SCR-11

#### B-12

**Question**  `GET /projects/{case_id}/{tab}` registers: can sections carry a stable `key` (issues, changes, emergencies, rfps) and a total count, so the page does not match on `title` text?

**Answer**  Use sections[].key, including issues, escalations, changes, emergencies and rfp. Each section gives page and has_more. It does not publish a section-wide total.

#### B-13

**Question**  Can register `items` carry `reference` separately from `title`, the owner's role, and `age_seconds` (the issue age is computed but not returned)?

**Answer**  The register exposes a recorded reference and issue age where available. Owner comes from the recorded assignment. A role label is only appropriate where the native source records one.

#### B-14

**Question**  Which values are valid for the `state`, `owner` and `severity` filters, and where does the page read the options?

**Answer**  Project journey uses its native filters for issue/action state, current owner and issue severity. For an exact action, the detail lists permitted owners; for issue owners use the corresponding issue options. The generic project tab declares string filters and lacks an option catalogue for all three.

#### B-15

**Question**  Should the page open detail from `api_url` (it differs per register), and is there an RFP detail other than the receipt?

**Answer**  Follow each actual item.api_url when present. RFP intake receipt, bid assignment and team inputs are separate reads. The later RFP response is a work line with its own panels. Avoid treating all register IDs as the same kind.

### SCR-12

#### B-16

**Question**  `money` `invoices[].status`: what are the possible values, and is there a code for "paid / part paid / not paid / not due" or must it be shown as given?

**Answer**  /money invoice status is Draft, Issued or Delivered. Read paid and owed for amounts, and GET /payments status for issued, part-paid, overdue, paid, voided and unknown. Delivery does not mean payment.

#### B-17

**Question**  Is `missing_reason` the replacement for v7 `amount_note`, and what text does it hold when the amount is known?

**Answer**  missing_reason explains missing stage or amount context. It may be null for a recorded figure. Display an unknown amount when amount is null. Do not substitute zero.

#### B-18

**Question**  Can `items[]` carry a position number (or state that array order is the stage order)?

**Answer**  Contract stages use the native stage order in the returned money array. Each row has a stable key and contract_stage flag. There is no numeric position field.

#### B-19

**Question**  `sources[]` has no reference text (such as the signed agreement version); can `label` be relied on to contain it, or can a `reference` field be added?

**Answer**  The Money read supplies source type, record ID, date, original reference where recorded and the exact authorised destination. Use the label for display.

#### B-20

**Question**  Can `POST /assistant/conversations` accept the figure `key` so the answer is about that figure?

**Answer**  Start a project conversation with agent and case_id. Assistant thread detail supplies available_sources and the message POST accepts those returned source_keys. A finance figure key is not a conversation creation parameter.

### SCR-13

#### B-21

**Question**  Is there an organisation-level Setup read (rules, delegations, templates, roles) that does not need a `case_id`, or should the frontend always choose a workspace first? Which workspace do organisation scopes belong to?

**Answer**  Setup scopes lists the company policy sources a company Admin can read and their exact authority-workspace link. Use the linked versioned policy endpoint for changes and activation under the applicable grants.

#### B-22

**Question**  `GET /setup/{case_id}/rules` has no `component`; how does a row map to a `policy-configurations` component so the page can open a draft?

**Answer**  GET /setup/{case}/rules supplies a stable component key for each rule. Use the scoped configuration endpoints and their version for changes.

#### B-23

**Question**  Can `rules` items carry `can_change` and the editable role options, or must the page infer authority from `policy-scopes` `can_configure` and `can_activate`?

**Answer**  Use can_configure/can_activate where a scope operation supplies them, plus its native choices. Those flags do not automatically authorise each rule type. General rule rows lack per-row can_change and an editable role list.

#### B-24

**Question**  Who may move a draft to `validated` and `active`: the same person who drafted it, or a separate reviewer?

**Answer**  Use the configuration’s actual review actions and current policy authority. Several policy paths require independent proof or validation. Admin’s company Setup ownership does not grant a domain decision or bypass a separate reviewer.

#### B-25

**Question**  How does a client create the `evidence_id` that every policy write needs (proof file)? No live evidence-upload operation was found.

**Answer**  POST /setup/{case}/decision-proofs records a checked, owned PDF as native policy-decision evidence. Use the resulting evidence ID with the appropriate Setup action. Configuration and rule activation still check their own authority.

#### B-26

**Question**  `GET /setup/{case_id}/delegations` returns user ids only: can it return names, role, reason and status, as the design shows?

**Answer**  GET /setup/{case}/delegations returns role, names, current validity status and the reason recorded with that active configuration where available. Delegation draft intake accepts the reason. Earlier versions may have no captured reason.

#### B-27

**Question**  Which user can discover which workspaces they may use for Setup (`GET /projects` lists all readable ones, not the ones with `policy.read`)?

**Answer**  Use GET /setup/scopes for workspaces permitted to read policy and the returned can_configure. A readable project in /projects is not necessarily one the account may configure.

### SCR-19

#### B-28

**Question**  `POST milestones/completions` `name`: is it any text, or must it equal a contract stage label from `/money`? Is there a milestone id?

**Answer**  POST milestones/completions accepts the real milestone name with current revision and typed completion evidence. It returns a new milestone ID. Billing-stage binding requires the exact configured milestone identity, so use the expected name/record from the native project flow.

#### B-29

**Question**  How is a `kind=completion` evidence record created through the API? `POST /cases/{case_id}/files` returns an `upload_id`, not an evidence id.

**Answer**  For milestone completion, submit an existing eligible native proof or a checked private PDF upload. The backend retains the source and evaluates the exact milestone, signed baseline and independent gates.

#### B-30

**Question**  Can the response return the Finance handoff or invoice work id that the completion queues, and when does it appear?

**Answer**  The response confirms the milestone, revision and proof. It does not guarantee a Finance work ID immediately. The service queues the handoff; read the project’s department handoffs after its worker records it.

#### B-31

**Question**  Can the options read return `can_complete` and a reason (not your role, already complete, previous milestone open) so the button can be explained?

**Answer**  Milestone completion options expose can_complete, can_attach_pdf and the exact recorded hold, including baseline_required, proof_required and name_in_use. The write rechecks the current record.

### SCR-22

#### B-32

**Question**  `GET /projects` `reviews` and `exceptions`: are these "waiting on a person" and "stopped" as the row shows them, and what do `lifecycle` and `phase` hold?

**Answer**  Use reviews/exceptions as the project list’s scoped projections, and lifecycle/phase as the returned project badges. They are not universal queue counts. Null means unavailable in that projection.

#### B-33

**Question**  Can the list return per-status counts and a next-milestone name and date, or should those be dropped from the rows?

**Answer**  GET /projects returns matching authorised lifecycle counts and a name/date for the next stage where Finance has a current signed stage with that information.

#### B-34

**Question**  Is `limit` going to be supported, or is the page size fixed?

**Answer**  Projects uses cursor paging at the server’s fixed size of 25. This is separate from the work queue limit.

### SCR-29

#### B-35

**Question**  Can action `items` in the tab carry the status code, `owner` as {name, role}, and the originating meeting {title, date}?

**Answer**  Project action rows show status, owner and the visible source meeting’s label and date where linked. The exact action detail supplies its current revision and assignment.

#### B-36

**Question**  Can the tab return totals for actions (total, overdue, without owner) or must they be counted from every page?

**Answer**  Project tabs expose total, overdue and unassigned action counts from the authorised records. The backend uses the native due-date and pause rules.

#### B-37

**Question**  Every action update needs an `evidence` id and a `reason`: how does a person without a file provide evidence (for example a plain note)?

**Answer**  Project action updates accept an eligible evidence ID or a checked private PDF. A current PMO Lead can approve an eligible PMO-owned Planning step directly. Independent approvals keep their own checks.

### SCR-34

#### B-38

**Question**  Is there an organisation-wide template read, or must the page always pick a project first?

**Answer**  The template catalogue takes a case_id and applies its scope/visibility. Setup scopes identifies eligible workspaces. The current endpoint has no unrestricted company-wide template list.

#### B-39

**Question**  Can `items[]` carry `line`, `test_template`, `updated_at`, `updated_by` and `versions`, or are they gone by design?

**Answer**  The catalogue identifies exact template name, version, document type, sample, creator and recorded time, with a download link.

#### B-40

**Question**  What is the `proof` required by a replacement: the previous template's evidence, or a new one, and how is it created?

**Answer**  Use a current policy_decision proof from the same project justifying the replacement, plus previous for the exact former template and the new file. The server checks the proposed proof on the replacement. The previous template ID alone is not proof of the new decision.

#### B-41

**Question**  Can `GET /projects/{case_id}/templates` list the templates available when the person has `document.read` but not upload rights (it needs `document.read`; does it show private templates of others)?

**Answer**  document.read permits the scoped catalogue. can_upload indicates editing rights separately. The API uses visible_templates and the download route performs its own scope checks.

### SCR-35

#### B-42

**Question**  Is a "client" a group (key = hash of the name) or a record? Is the group `key` stable and safe to use in a URL?

**Answer**  A group is a stable opaque grouping key for the reviewed client links visible to the actor. Feed key to /clients/groups/{group}. An individual project still has its own case_id and record access.

#### B-43

**Question**  Can `GET /clients` return the amount owed per group, or is money only per project?

**Answer**  Client-group detail includes debt for readable member projects only, with currency, known amount, unknown records, observation date and scope coverage.

#### B-44

**Question**  `GET /clients/{case_id}` is per workspace: which workspace's contact is "the client's" billing contact when a group has several projects?

**Answer**  Billing contacts are project- and purpose-specific. Open the invoice/project’s current contact. A group does not select or create one master contact.

#### B-45

**Question**  `POST /clients/{case_id}/contacts` needs `evidence_id`: what can the person supply for a billing contact (the options list `proofs`)?

**Answer**  GET contact options supplies eligible customers and exact contact proof IDs for the selected purpose. Use a recorded same-project proof of the contact instruction. A generic upload ID does not become that proof automatically.

#### B-46

**Question**  What do `contacts_needed` and `billing` recorded / needed / unknown mean for the "billing contact set" tag?

**Answer**  recorded means a current billing contact is recorded for that project; needed means the required contact is missing; unknown means the relevant billing scope could not be established. contacts_needed counts group projects in the needed state.

### SCR-38

#### B-47

**Question**  Is `/money` the intended source for the milestone table, with `/milestones` only for proof of completion? Which key joins them (`items[].key` and `record_id`)?

**Answer**  /money is the Finance billing-stage view. Milestones is recorded completion proof. The money key is a stage key, not the milestone record ID. Use a typed milestone source when returned, or the native stage-to-milestone link.

#### B-48

**Question**  A person with only `milestone.complete` or `delivery.read` can open the milestones tab but `/money` returns 404 without `finance.read`: what should that person see?

**Answer**  Show the permitted milestone/completion record view and its proof/actions. Amounts, invoices and balances come from the Finance-scoped read.

#### B-49

**Question**  Can `/money` `items[]` carry a milestone id and a position so a row can link to its completion?

**Answer**  Money includes the signed stage position and the exact milestone ID where a native link exists.

### SCR-39

#### B-50

**Question**  Is there a readable (not raw payload) version of a costing rule and its worked examples, with names for proposer and reviewer?

**Answer**  Costing source returns the structured rule and oracle payload, with exact review IDs, verdicts and dates. Proposal detail compares parameter and worked example results. Public read models do not include a prose summary or all proposer/reviewer names.

#### B-51

**Question**  Which project shows the "organisation" costing rule in Setup, given every costing read needs a `case_id`?

**Answer**  Start from Setup scopes, then use the authorised source workspace and its current organisation policy/version for the rule. Do not pick an arbitrary project as the company pricing authority.

#### B-52

**Question**  `POST .../costing/proposals/{id}` needs `evidence_id` and `reason`: what evidence does a reviewer supply for a verdict?

**Answer**  Review the exact proposal, comparison and independent examples using /costing/proposals/{id}. Submit a current case evidence ID for the independent reviewer’s decision, the verdict and the reason. The options and native policy check source identity and reviewer authority.

#### B-53

**Question**  What do `POST /work` and `GET /work/{work_id}` do for costing: start a pricing line, or the review task? Which work definition?

**Answer**  /work starts or reads the process line; costing rules, calculations and proposals have separate project costing operations. Bid pricing is exposed on rfp-response/v1 via its bid-pricing panel. A costing rule proposal is not a separate work definition.

## C · Bid, report and planning screens

### SCR-16

#### C-1

**Question**  `POST /work/{work_id}/rfp-outcome` takes `role`, `loss_reason_key`, `loss_catalog_id` and `debrief_version_id`; which operation lists the allowed roles, loss reasons and debrief documents?

**Answer**  When a bid is lost, the PMO staff member recording the outcome types the actual reason in a free-text note. Use a text field for the reason.

**API 1.25.0**  Use `GET /work/{work_id}/bid-outcomes` for eligible roles and available debriefs. Send `verdict: lost`, the reason in `note`, and the customer outcome evidence to `POST /work/{work_id}/rfp-outcome`. Omit `loss_reason_key` and `loss_catalog_id`. Read the saved reason from `outcome.note` for the exact submission.

#### C-2

**Question**  How does a file the person attaches become the integer `evidence_id` that `rfp-outcome`, `team-inputs` and `assignment` expect (there is `POST /cases/{case_id}/files` returning `upload_id`, and `commercial-response/files` returning `id`)?

**Answer**  The bid assignment, team input and outcome actions accept eligible evidence or a checked private PDF bound to that action. Release and signature actions use their own typed evidence and authority.

#### C-3

**Question**  Is `received_via` (email, WhatsApp, call) stored anywhere on `commercial-response` `action:"witness"`, or should it go in `note`?

**Answer**  The original bid outcome witness includes an optional recorded reception channel alongside its date, note and proof. Earlier records can have no channel.

#### C-4

**Question**  `GET /received-bids/{case_id}/team-inputs` does not say which teams are still owed or blocked; is `choices[].team` the full asked list?

**Answer**  The assigned project manager records an actual request or block for a named bid team through team-requests. The team-inputs read separates not requested, awaiting reply, blocked and received for the current intake and links the actual receipt.

#### C-5

**Question**  Which `/work/{work_id}/reviews` `kind` carries the follow-up `review` (the one between `draft` and `send`)?

**Answer**  Call POST /work/{work_id}/bid-outcomes/{outcome_id}/followup with action review. It sits between draft and send on the follow-up itself.

#### C-6

**Question**  For `selection_required`, what does `selection_packet` contain and what must `selection_acknowledged` confirm?

**Answer**  selection_packet is an opaque snapshot token for the current selected submission and the visible selection inventory. The person checks that exact submission and coverage before setting selection_acknowledged. A new snapshot needs a fresh check.

### SCR-23

#### C-7

**Question**  `POST /received-bids` returns `case_id` and `receipt_id` but no `work_id`; how does the screen reach the new Unassigned work item (find it in `GET /work?queue=unassigned` by `case_id`)?

**Answer**  Open /received-bids/{case_id}/receipts/{receipt_id} using the returned IDs. The dedicated /received-bids/assignments queue and /received-bids/{case_id}/assignment cover unassigned bids. A generic work ID is unnecessary for that path.

#### C-8

**Question**  What are `authority` (organisation delegation id), `definition` and `context_attested` in `POST /received-bids`, and what does the person see for each?

**Answer**  Select the organisation using GET /received-bids/organisations. Send its delegation ID as authority. The optional legacy definition identifies received-bid. context_attested is the person's confirmation of the captured prospect and submission instructions.

#### C-9

**Question**  Is `prospect_name` how a new client is created (closing our G-23-1), and is an existing client matched by name, by `organisations`, or not at all?

**Answer**  prospect_name is the name captured on the bid. It does not create or match a client. The organisation list supplies intake authority. Use explicit client and engagement linkage when the workflow has that record.

#### C-10

**Question**  Is there a stored Note field for the person logging the RFP, or should the field be removed from the form?

**Answer**  The fresh bid intake can save a bounded note on the original intake version and returns it with the receipt.

#### C-11

**Question**  Which duplicate rule applies to the same `reference`, and what status and `code` does it return (our G-23-2/BQ on repeat logging)?

**Answer**  The same actor, authority, start key and exact input replay the original receipt. A second intake using the same organisation and reference is blocked with HTTP 422 action_unavailable. The response message explains the duplicate. There is no duplicate-specific code.

### SCR-24

#### C-12

**Question**  Is `evidence` truly required in `POST /received-bids/{case_id}/assignment` (design says optional), and is `reason` the same as our optional Note?

**Answer**  evidence is required, with an eligible integer ID from the assignment read's proofs. reason is also required. Label it as the reason for the assignment.

#### C-13

**Question**  Can `GET …/assignment` return the next-steps sentences and the nominee's role (our G-24-3)?

**Answer**  Assignment reads return the nominee’s recorded role and the applicable next actions for the current assignment.

#### C-14

**Question**  Does assigning move the item out of `queue=unassigned` immediately, and which work state results?

**Answer**  A completed assignment leaves the dedicated bid assignment queue. The read shows the recorded assignment. A separate factory work item need not exist yet.

### SCR-25

#### C-15

**Question**  `weekly-report-intake` `evidence[]` and `narratives[]` have only `{id, version, kind}`; where do the labels (for example "Milestone 2 · UAT signed 11 Nov") and this week's meetings, issues, actions and changes come from?

**Answer**  The weekly report read includes a bounded authorised list of the week’s evidence and narrative with their source labels and coverage.

#### C-16

**Question**  Where is the reviewer's returned note read (only `return_review_id` is given)?

**Answer**  The weekly report read supplies the permitted reviewer return note for the exact draft and its review.

#### C-17

**Question**  Where is the assembled report text read for the PM before review, and is it `document-reviews/{version_id}` preview?

**Answer**  The weekly panel links to the authorised exact draft preview. Review-only notes are attached to each applicable section for authorised reviewers. The published document leaves them out.

#### C-18

**Question**  Does `action:"start"` replace the PM's current `send_to_tola` step, and is a work item (and its progress) visible before it?

**Answer**  Use weekly-report-intake action start to begin the recorded work. The background setting controls queueing. A saved intake draft has no factory work ID. After start, use work detail and tracking for observable progress.

#### C-19

**Question**  Can `POST /work/{id}/actions` `reconcile` carry the checked result and proof?

**Answer**  Work action reconcile uses the native receipt or effect check. The separate delivery reconciliation command accepts an authorised manual observation with proof and reason when needed. Use the exact action shown by the panel.

#### C-20

**Question**  Which `panels[].key` on `GET /work/{work_id}` points to `weekly-report`?

**Answer**  The detail panel key is weekly-report.

### SCR-26

#### C-21

**Question**  `bid-answers.rows[]` carries only `key` and `response`; where do the requirement wording, RFP page, reference and ordering come from, and is there paging for 64+ rows?

**Answer**  Bid answers use a paginated list with requirement ordering, original source reference and any exact reviewed wording/page citation. The citation write checks the quoted wording against the authorised source.

#### C-22

**Question**  Is there a way to add a requirement (our `add_requirement`), or are requirements fixed by the source analysis?

**Answer**  The reviewed source analysis fixes the requirement set for that bid version. bid-answers supports suggest, review and undo; it has no add_requirement action. Correct the source and use the new reviewed version if the requirement set was wrong.

#### C-23

**Question**  Which operation gives the Progress figures, the "before review" checks and the tab counts?

**Answer**  The answer panel supplies counts and review readiness for the current requirement inventory. Keep submission gate checks separate.

#### C-24

**Question**  How does the PM send the response for review (which op or `reviews` `kind`/`subject`), and how is a return from Engineering shown?

**Answer**  The bid answers summary identifies the exact work and recorded Engineering review return reason where there is a current decision. Request the pack review through the separate pack action.

#### C-25

**Question**  What do `disposition: clarification` rows trigger, and is there a client clarification send/answer record (our G-26-8)?

**Answer**  The bid clarification read and write retain the question and actual response against the selected requirement with date and evidence. Staff send it through their chosen channel outside this API.

### SCR-27

#### C-26

**Question**  What are the allowed values of `amounts[].key` and `unit` (engineering, security, project management, total) and their display names?

**Answer**  Use the actual reviewed costing rule and its calculation. Keys and units come from that version. Do not assume a fixed Engineering/Security/PM/total list. Resolve a configured display name from the rule where it exists.

#### C-27

**Question**  `approvals[].status` is a string; what are the values and is the order PM, PMO Lead, CEO (D-APPROVAL-ORDER) enforced and readable?

**Answer**  The costing read has stable codes for the current Project Manager, Head of PMO and CEO review status. The backend still checks the sequence and source revision.

#### C-28

**Question**  Which `reviews` `kind`/`subject` records each approval on the costing sheet, and who may decide the CEO step?

**Answer**  Use /work/{work_id}/reviews with kind bid, subject commercial and the current commercial revision. The CEO decision requires the currently authorised person in that configured step.

#### C-29

**Question**  When `max_absolute_value` is unset (PSL decision pending), what is returned for `adjustment_targets`?

**Answer**  Finance staff can adjust any bid pricing line in naira (NGN). Finance decides the lines and amounts for each bid. The Finance Lead reviews and approves the exact changes before the revised bid moves forward.

**API 1.25.0**  `GET /work/{work_id}/bid-pricing` returns `finance_targets` with current naira input and output lines, `finance_pending` with the exact proposed change, and `finance_last_decision` with the decision. Use `can_propose` and `can_decide` for the buttons. POST `action: propose`, the target, new naira amount and reason with the current revisions. The current price stays in effect while the proposal is pending. A different Finance Lead submits `action: approve` or `action: return` with the proposal ID, reason and current revisions. Approval saves the new calculation and starts a fresh round of the existing bid reviews.

#### C-30

**Question**  Is the delivery plan a costing input anywhere on `bid-pricing.inputs`?

**Answer**  Yes. Delivery plan is a named input bound to the selected planning evidence version alongside the other reviewed sources.

### SCR-28

#### C-31

**Question**  `minutes.suggestions[]` has `quote` but no proposed owner, due date or title; does the extraction supply them elsewhere?

**Answer**  Minutes suggestions expose the cited wording as the proposed title. The extractor supplies no confirmed person or deadline. Those fields stay empty until the meeting reviewer confirms them from the source.

#### C-32

**Question**  Can the audience (internal/client) still change at confirmation, or is it fixed at intake (our G-SCR28-5)?

**Answer**  Audience is fixed for the selected intake and its source. Confirmation records the meeting content and choices for that intake. A different audience takes its own eligible intake.

#### C-33

**Question**  When are actions created, at `confirmation` or after approval (our G-SCR28-7)?

**Answer**  Confirming the minutes records confirmed actions. Approval of outward minutes is separate and controls what can be released.

#### C-34

**Question**  Where are meeting name, date, time and attendee count read for the meeting card?

**Answer**  GET /projects/{case_id}/meetings/{meeting_id} gives reference, purpose, occurred_at and visible participants. Count the visible participants for the card. The minutes panel's confirmed_meeting_version_id is a version ID, so use the native meeting link or list to find its meeting ID.

#### C-35

**Question**  Which `reviews` payload do the PMO Lead and Quality reviewer use for outward minutes, and how does Return keep confirmed actions?

**Answer**  Request outward review through the minutes review-request action. Record the configured reviewer decision with kind document for the exact version. Return acts on that document version and preserves the native confirmed actions.

### SCR-40

#### C-36

**Question**  Does `POST …/bid-submission` need to be pressed after the review approval (our G-40-1), or does approval queue it?

**Answer**  Approving the pack and queueing bid submission are separate. A permitted person starts POST /bid-submission after the current pack passes its checks. Verify the separate submission receipt afterward.

#### C-37

**Question**  What are the `findings[]` codes in `bid-submission.file` and how should each be worded?

**Answer**  PDF package checks include stable codes and readable explanations for format, count and size findings.

#### C-38

**Question**  How is a pack made of several parts (forms, response document) listed to the reviewer, and where is the test-template flag (G-40-6)?

**Answer**  The panel identifies the recorded package sections and sample status, and links the exact verified PDF. Native submission verifies a single PDF package.

#### C-39

**Question**  Which `reviews` `kind` approves a bid pack, `document` or `bid`?

**Answer**  Use kind bid and subject document for the bid pack's exact controlled version. The review keeps that document's authority and inspection checks.

### SCR-41

#### C-40

**Question**  What is `register.value` (project name, code, identity), and who chooses it?

**Answer**  register.value is the official project identifier in the configured namespace and format. The person authorised for registration enters or confirms the value and its planning evidence.

#### C-41

**Question**  How do `key` and `checked` on `assign` and `details` work, and what does the person confirm?

**Answer**  key is the operation's idempotency key. Use it unchanged on an exact retry. checked belongs to details and records that the person checked the actual captured details and selected source. assign records the assignment without that checkbox.

#### C-42

**Question**  Can `GET /work/{id}/engagement` return packet rows (scope, price, plan) with labels and the project and planning links as names?

**Answer**  Engagement supplies readable sources on its exact agreed packet and named Project, Planning and Money links for scope, plan and Finance price.

#### C-43

**Question**  What are Routes B and C, and should the screen name them (our G-41-7)?

**Answer**  Route A converts a won bid. Route B is the direct, non-bid engagement route supported by same-case source evidence. Route C requires Product intake evidence. Show those plain names with the route code where it helps.

### SCR-42

#### C-44

**Question**  Where are the labels "asked" for each department (what was requested and when)?

**Answer**  The department request panel gives its reference, request type, creation date and original received date where recorded. Read the linked source for the original wording.

#### C-45

**Question**  `department-inputs` uses `source_id` (integer); how does a person pick or attach that source, and is it the same id space as `team-inputs.evidence_id`?

**Answer**  Pick the current evidence record admitted by the project's planning source choices and send its source_id. Planning and bid inputs both reference evidence records, but each line validates its own case, source kind and permission. A file upload ID is insufficient.

#### C-46

**Question**  Is Infrastructure shown as part of Planning even though team-input on the RFP lists Product instead?

**Answer**  Planning includes Infrastructure and Product alongside Engineering, QA and Security. Its choices come from the planning line. Earlier bid team inputs use different choices.

#### C-47

**Question**  How does the PM know the owner for Product is missing (`owner_status: unassigned`) and where does the person set it (our G-42-4)?

**Answer**  The planning source-clarifications read provides owner_status and can_assign. Use its eligible assignment command and owner choices when Product is unassigned.

#### C-48

**Question**  Is the `handoff` decision a separate human approval from `prepare_readiness` (our G-42-6)?

**Answer**  prepare_readiness prepares and records the checks. Handoff is a separate human command bound to the current readiness record and the right authority. Neither step substitutes for a separate decision required by the next line.

## D · Delivery, change and leadership screens

### SCR-30

#### D-2

**Question**  `GET .../issues/{id}` and `issue-followup` carry no raised date, age or "blocks" milestone; where do these come from?

**Answer**  Issue detail and follow-up give the original opening time and age. Use blocked-milestone to link a recorded project milestone or its currently approved planned stage, with original evidence. Completion remains a separate decision.

#### D-3

**Question**  Is there a ready-made "what has happened" list for an issue (owner updates, reminders) or must we build it from `history`, `messages` and `acknowledgement`?

**Answer**  Issue detail includes a bounded timeline of visible state changes, acknowledgement, and actual owner message and delivery events. The exact Messages panel retains its own permissions and shows reminder timing.

#### D-4

**Question**  In `issue-followup` POST, when is `team_reply` used versus `POST .../team-replies` (same data)?

**Answer**  Use issue-followup respond with team_reply when responding to the exact work task and recording its linked team witness. Use /issues/{id}/team-replies for an independently captured team reply. Submit one path for the same reply.

### SCR-31

#### D-5

**Question**  Must all five deciders approve every change (the design's open question)? `decisions[]` lists roles but not whether each is required.

**Answer**  For a normal change, Product and Engineering are always required. Client is added when client-facing. Engineering Lead and Security Manager are added when the timeline is affected. Standard and emergency changes use their own rules.

#### D-6

**Question**  `change.stage` values: please list them so we can draw the five-step track.

**Answer**  The stage codes are source, impact, authorization, notice, execution, go_live, signatures and complete. The frontend can group these into the five visual steps.

#### D-7

**Question**  `close` needs `pm_signature`/`client_signature` source fields (source_system, decision_id...); what does a PM enter for a client who does not log in?

**Answer**  Record proof of the actual client's decision with real source system, reference, decision ID and version, signer and signed time as required. An authorised PM can record an external signature without a client login. The source identifiers must come from the retained proof or its source record.

### SCR-33

#### D-8

**Question**  Where do "went well / did not / lessons" go: three headed sections inside `summary`, or `decisions[]`? Is there a draft state?

**Answer**  Put “went well,” “didn't go well” and “lessons” in the retrospective summary. Decisions and actions are separate records. The native retrospective command saves a meeting record; the minutes preparation flow is the separate draft path.

#### D-9

**Question**  Can `GET /projects/{case}/meetings` `kind=retrospective` be filtered to the current one the closure checklist selects (`retrospective_id`)?

**Answer**  Closure returns the retrospective link with its exact selected version_id. Use that version for the historical record the checklist used.

### SCR-43

#### D-10

**Question**  Will there be a delivery overview read (the six lines, their gate state, reference and date, even before started)? Today the design needs `delivery[]`.

**Answer**  The overview returns the same six stable Delivery lines for every project, including not_started when no work exists, with recorded state, date, reference and links to each line’s gate checks.

#### D-11

**Question**  Which `GET /projects/{case}` `items[].line` values are the six delivery lines? Please give stable keys (today a display title).

**Answer**  Use delivery-release/v1, delivery-go-live/v1, delivery-hypercare/v1, delivery-handover/v1, delivery-archive/v1 and delivery-closure/v1 from delivery-overview.lines[].key.

### SCR-44

#### D-12

**Question**  What evidence does `planning-exit` expect in `evidence_id` (the list is `proofs[]`)? Can the decision be recorded with only a note, as the design shows?

**Answer**  The current PMO Lead who is the named approver can approve an eligible PMO-owned Planning exit directly. The backend saves their approval, role and time and enforces the current packet and independent gates.

#### D-13

**Question**  Who triggers `prepare_readiness`: the PM by click, or the system once approved (the design says Tola)?

**Answer**  Both paths can prepare readiness. An authorised PM can trigger prepare_readiness. The delivery worker can prepare it when execution is configured and current gates pass. Subsequent acceptance and release observations must still be recorded.

#### D-14

**Question**  Please list the `release-register` `phases[].name` and `checks[].status` values, so we can draw the tags.

**Answer**  Phase names are Initiation, Planning, Execution and Closure. Check statuses are unknown, stale_scope, current, restricted_or_authority_changed and unknown_or_stale. Read allowed commands from the separate actions list and let the server verify the exact transition.

### SCR-45

#### D-15

**Question**  Is "signed" always two separate signature evidences (PM and client), or can one uploaded signed copy serve both?

**Answer**  Go-live needs two distinct evidence IDs, one for each exact signature. A single uploaded signed copy may be source material only where two distinct, verified signer records can be linked to it. The API does not accept the same evidence ID twice.

#### D-16

**Question**  What does the PM enter for `signers.*.source_system`, `decision_id`, `decision_version` (the client does not log in)?

**Answer**  Use the actual external decision's source system, identifier and version, bound to the signer and exact acceptance. Choose those from the retained external signature or register. Missing source information needs reconciliation before acceptance can be verified.

#### D-17

**Question**  `go-live-milestone` `draft_mapping` needs `owner_decision_id`; who is the owner and when is this done before "Mark milestone complete"?

**Answer**  The PMO Lead reviews the project and the go-live evidence, confirms which milestone is complete, and records that decision before the milestone is marked complete.

**API 1.25.0**  `GET /work/{work_id}/go-live-replies` gives the PMO Lead `milestone.can_confirm`, the verified acceptance ID and eligible completion evidence IDs. POST `action: confirm_and_complete` to `/work/{work_id}/go-live-milestone` with the exact milestone name, acceptance, completion evidence and current revisions. A note is optional. Read the PMO Lead's saved decision under `milestone.confirmation` and the completed milestone under `milestone.recorded_id`. The internal Finance handoff follows from the completion.

### SCR-46

#### D-18

**Question**  Should "log an observation" in the PM's hands record a metric reading (`stability` POST) or a free note? How should an open issue appear in the list?

**Answer**  Submit a structured stability observation with its actual approved metrics, time and proof. Use the separate issue record for an open issue and display it separately. A free-form note can add context.

#### D-19

**Question**  Is there a per-criterion result (MET / NOT MET) to draw, or only `qualified` plus `findings[]`?

**Answer**  The Hypercare read gives a result for each configured time, confirmation, metric and issue criterion using the same checks as its decision.

### SCR-47

#### D-20

**Question**  Does `files[]` carry a group or source kind (RFP, costing...), or must we group by `sources[].label`?

**Answer**  Archive files expose a stable group and the exact source kind and ID where authorised. Use the source link to open the original.

#### D-21

**Question**  Is archive started by a person (`reserve` with `source_ids`) or by the system after go-live? Can it default to `required_source_ids`?

**Answer**  An authorised person reserves the archive from the exact current source IDs. The worker can process the reserved archive. required_source_ids can preselect the list for review. A go-live alone is insufficient to record a completed archive.

### SCR-48

#### D-22

**Question**  Where does the PM see and trigger "Publish to Support", or is it automatic after review? Which field says "ready to publish"?

**Answer**  GET /support-publication says can_publish and supplies the approved version when ready. An authorised PM uses POST on that route to queue publication. Read the eventual Support receipt separately.

#### D-23

**Question**  Can `support-replies` carry gaps as a list (`gaps[]`) rather than inside `note`?

**Answer**  Support replies preserve an optional structured gaps list alongside the reply status and note on the protected exact acknowledgement.

#### D-24

**Question**  Which read gives the handover document title, version and attachments?

**Answer**  The actual Support recipient reads the exact handover title, version and sections at support-receipt. The read includes the two bound supporting records when the recipient also has source access.

### SCR-49

#### D-25

**Question**  How does Finance record its confirmation (milestone notification coverage)? No operation is listed.

**Answer**  Use GET and POST /projects/{case_id}/delivery/{dossier_id}/finance-confirmation. Finance checks the milestone receipts and records the exact reviewed set, completeness, evidence and note.

#### D-26

**Question**  In `reviews` `kind:"closure"`, what is `evidence_id` (the closure report evidence)? Is `version_id` the closure document version?

**Answer**  kind closure targets the controlled closure document with version_id. evidence_id is the eligible evidence for the review decision. The source report, decision proof and document version each retain their own reference.

#### D-27

**Question**  Can closure reads carry the open debt list (the design's "still open after closure")?

**Answer**  Closure returns protected debt figures for that project with the Finance observation date and unknown coverage, where the viewer can read Finance data.

### SCR-50

#### D-28

**Question**  `record_review` has no verdict; how does the reviewer return an outcome?

**Answer**  record_review logs the actual post-implementation assessment. For an applicable retrospective decision use its separate return action. For an outward document use that version's independent review verdict.

#### D-29

**Question**  Where do "customers affected" and "side effects" go in the outcome record?

**Answer**  Send customers_affected as a non-negative number or null and side_effects as text or null on the outcome. Read them in outcome_impact. Null means there is no confirmed value.

#### D-30

**Question**  Which read gives the names and times of the authoriser and outcome recorder (`recorded_authorizations` is ids only)?

**Answer**  Emergency decisions and the recorded outcome give their named authorised actor and time where stored in the native history.

### SCR-51

#### D-31

**Question**  Which `verdict` means "Don't escalate" (`reject` or `return`)? Is the note returned in `history[]`?

**Answer**  Use reject for a declined escalation and return for rework. The eligible reviewer can see the reason and exact decision time.

#### D-32

**Question**  Which read gives the drafted message text and recipients for the review screen?

**Answer**  The escalation draft read includes an authorised exact preview and permitted recipients. Sending and delivery receipts remain separate operations.

### SCR-52

#### D-33

**Question**  Can the intake offer "all projects I can see" (flag `all_projects_available`) without listing every record id?

**Answer**  The PMO Lead and Finance Lead can generate either format whenever they need it. The Factory’s AI workers use the current records each lead can access across all PSL projects. Show when the report gathered its information. Staff can generate the report without choosing dates or waiting for a day of the week.

**API 1.26.0**  `GET /projects/{case_id}/leadership-report-intake` returns `automatic_project_scope: true` for either current lead. Start either format with the report type, audience and template. Omit `start_at` and `end_at` for the information available at the time of the request. Use `background: true` to queue the agent work. Read the capture time under `coverage.captured_at` and the project list under `coverage.project_register`. Existing report reviews and recipient checks still apply.

#### D-34

**Question**  Where are the headline figures (counts) the design shows; are they derived from `selections` or do we compute them?

**Answer**  Leadership reporting supplies per-source counts from its exact authorised selection manifest, with when it was captured and what it covers.

#### D-35

**Question**  Who requests the leadership review: the system after the draft, or a PM step?

**Answer**  For the monthly executive report, the configured worker can request exact human review while preparing the retained draft. If the review was not requested, the work offers the authorised request-review action once eligible. The internal Tuesday report uses its own review rule.

### All delivery screens

#### D-1

**Question**  what call turns `POST /cases/{case_id}/files` (`upload_id`) into the evidence id (`evidence_id`, kind such as `signature`, release log, notes file) that line commands require?

**Answer**  Use the operation that owns the evidence. Go-live sign-off proofs accepts a checked signed PDF for the exact receipt and signer role. The release register accepts a checked PDF on the actual release observation. Minutes file intake retains the extracted notes with their source. Each action retains the exact native evidence ID, and sign-off remains a separate decision.

## E · Finance, payroll and HR screens

### SCR-09

#### E-1

**Question**  Does `inputs[].codes[]` have a published list with plain-language text (and expected / found sheet names) so the error board can be written?

**Answer**  Payroll input options give supported codes and safe readable explanations, including the configured expected sheet where applicable. Protected working rows carry actual import findings.

#### E-2

**Question**  Is there an endpoint or file for "Download template" for each `provider_options.formats` entry?

**Answer**  Download a blank JSON, CSV or XLSX template for the selected provider’s approved schema and file layout.

#### E-3

**Question**  Which `kind` values does `payroll/{kind}/{record_id}/working-rows` accept (input, combined run, match), and who gets 403 vs 404 when not an admitted reader?

**Answer**  kind is input or run. Combine, match and aggregate use run with that run's ID. An invisible workspace or absent record is 404. An admitted workspace reader without the required payroll grant receives 403. Exact native access is also checked before exposing any working rows.

### SCR-18

#### E-4

**Question**  What are the fields of `payroll-operations` → `working[]` and `hr_receipt`, and do they carry matched / unmatched / conflict / held counts?

**Answer**  Payroll inputs return private matched, unmatched, conflict and held counts from the working runs the viewer can read.

#### E-5

**Question**  In `payroll/reports/{id}` → `by_business_unit`, how is a business unit with unmatched staff shown (null, a flag, or left out), and is a staff count included?

**Answer**  The recipient report returns approved BU totals and the eligible total, without staff counts or unmatched employee rows. An unmatched row is not given a zero BU entry. Check unresolved matching privately before treating the disclosed totals as complete.

#### E-6

**Question**  Is "I didn't receive the HR snapshot, confirm receipt" (`hr_receipt`) a POST on `payroll-operations` (which action value)?

**Answer**  POST /payroll-operations with action receive_hr and the exact received snapshot and evidence IDs. Use can_acknowledge to offer this action. If the snapshot was never received, there is no receipt to confirm.

### SCR-20

#### E-7

**Question**  Is `GET /payments` item `age_days` days overdue or days since issue, and where is the due date?

**Answer**  age_days measures days past the invoice due date. The reminder balance or applicable project money item gives the due date. The company Payments row does not carry a separate due_date.

#### E-8

**Question**  `POST .../payments` accepts a null amount with `amount_basis: unknown`. We had asked for a receipt to be refused when its amount is unknown (G-SCR20-11); is that intended?

**Answer**  A new receipt requires a positive known amount and payment source. Existing incomplete entries can still use the native correction path. Verification and allocation remain separate.

#### E-9

**Question**  Can `GET /payments` return `received this month` and a bank-data-as-of date, or should we use `/projects/{case_id}/money`?

**Answer**  Payments returns verified month-to-date receipts for readable workspaces with currency and coverage, the last source receipt time where known and its verification information. Bank-feed freshness needs a live feed.

#### E-10

**Question**  When `totals[].owed` is null, is that the whole total unknown, or can a known part plus unknown be given?

**Answer**  For the returned rows in a currency and basis group, null owed means a complete total is unavailable. Use known_owed for the sum of confirmed balances and unknown_owed_count for the number with missing balances.

#### E-11

**Question**  Does `limited: true` mean the totals exclude rows, and how should the page word it?

**Answer**  limited warns that the read was bounded. Label the totals as covering the rows returned and follow cursor for more. The response cannot support a company-wide total when its coverage is incomplete.

### SCR-32

#### E-12

**Question**  What `action` values does `reminder/actions` take (release, schedule, reconcile, close, set aside)? The spec shows `action` untyped.

**Answer**  Accepted actions are send, set_aside, cancel_schedule, check_mailbox and confirm. send accepts an optional scheduled_for. check_mailbox reads an enabled synthetic transport and confirm records actual evidence for a dispatch.

#### E-13

**Question**  Does the 7-day follow-up sentence come from `settings.minimum_days_between`, and is it exposed to the reader?

**Answer**  The reminders read gives the configured interval, the earliest allowed follow-up date where calculable and whether it is waiting for the original receipt.

### SCR-36

#### E-14

**Question**  Does `GET /month-end` hide payroll/restricted rows for non-HR readers, and does `work[]` include restricted lines as a label only?

**Answer**  Month-end checks readers against each finance line and the exact restricted source or acknowledged aggregate receipt. It omits work the person cannot access, including its labels. A permitted aggregate reader can still see the relevant work summary.

#### E-15

**Question**  What are `periods[].values` and `status` values (open, captured, closed)?

**Answer**  The reviewed period rows use Reviewed figures or Needs a fresh review. values contains label, value and unit for the authorised reviewed metrics. An unavailable review gives an empty list. Receivables snapshot status is a separate field.

#### E-16

**Question**  Is `cash[].amount` ever null when `cash_unavailable` is true, or is it "0.00"?

**Answer**  Each returned cash row has a string amount. Unavailable coverage is flagged by cash_unavailable and may leave rows missing. Show 0.00 only for a confirmed zero row.

### SCR-37

#### E-17

**Question**  What are the fields of `hr-disclosures` `needs[]`, `disclosures[]`, `decisions[]` and `corrections[]` items?

**Answer**  needs has id, reference, version, entity, period, purpose and fields. disclosures has id, need_id, latest_decision and created_at. The exact disclosure detail adds decisions with id, verdict and created_at, and corrections with id, snapshot_id, decision and successor_id.

#### E-18

**Question**  Is the correction list per disclosure only, or can a project-level list of waiting corrections be read?

**Answer**  The authorised HR handoff read surfaces pending corrections across eligible disclosures. Open the original disclosure to decide each request.

### SCR-53

#### E-19

**Question**  What are the `action` values of `POST /work/{id}/accounting`, and what is in `review_stations[]` and `tasks[]`?

**Answer**  POST /accounting accepts recheck_reviewers and reassess. review_stations lists each station label and subjects with id, status, review_id, evidence_id and reviewed_at. tasks gives id, revision, label, can_claim, can_decide and allowed verdicts.

#### E-20

**Question**  Is `findings[]` a code list or prepared sentences?

**Answer**  Accounting intake and mapping return findings and finding_details with a stable code, original message, and line or field where known. Unclassified legacy messages remain readable.

### SCR-54

#### E-21

**Question**  Which `reviews` variant carries a schedule approval, and is `evidence_id` required for approve?

**Answer**  Use kind schedule on /work/{work_id}/reviews, with the exact target_id, current revisions, verdict and note. The schema requires evidence_id, including for approve.

#### E-22

**Question**  How is "schedule reviewer not set" signalled on `finance-schedule`?

**Answer**  The Finance schedule read exposes an approval hold code when an eligible reviewer or prior step is missing. Setup owners use the existing reviewer configuration.

### SCR-55

#### E-23

**Question**  What is `purpose: basis` (calculation basis review) and when is it requested versus register and schedule?

**Answer**  register reviews the source asset register, basis reviews a required justification for the chosen date or calculation basis, and schedule reviews the resulting depreciation schedule. The current review_options sets the purpose and target to offer. A separate basis review is used where required.

#### E-24

**Question**  Where does the reader get the accounting note text from `accounting_note_id`?

**Answer**  The asset panel links directly to the selected accounting note when the person can read the exact Finance mapping. Opening and date proofs retain their own links.

### SCR-56

#### E-25

**Question**  What are the shapes of `forecast` → `result`, `jobs[]`, `disclosure`, `matches[]`?

**Answer**  result contains status, entity, currency, basis, as_of, findings, expected items, periods and actuals. jobs gives ID, status, receipt IDs and retry/operate permissions. disclosure gives configuration, permitted rows and recipients, evidence choices and selected fields/metadata. matches gives ID, item_key, actual_id and amount.

#### E-26

**Question**  Do payroll rows in a group disclosure respect the restricted-payroll visibility (HR-only) before a group reviewer sees them?

**Answer**  Group recipients get a separate approved projection with only the selected row fields and metadata. The field list excludes staff names, individual pay records and raw payroll input. A payroll-related cash assumption still needs explicit inclusion and review on that exact projection.

### SCR-57

#### E-27

**Question**  What are the fields of `business-units` → `result` and `inputs`, and where is the small-group withholding reason?

**Answer**  inputs has mode, payroll_id, source_id, rule_ids and optional comparison with run and metric. result has ID, kind, status, codes, scope and totals. A too-small group holds the publication; use the authorised staff-facing finding. A recipient does not get the private staff counts.

#### E-28

**Question**  Which `action` values does `POST business-units` accept?

**Answer**  POST /business-units accepts prepare_rule, publish and restart. Record the independent approval through /reviews with kind business_unit.

### SCR-58

#### E-29

**Question**  Do `observation` and `latest_decision` carry the reviewer's name and time, and is "not the capturer, not the observer" an independent-review reason code?

**Answer**  The protected Ledger response gives the latest decision’s reviewer and date, plus a stable hold code when the independent reviewer rule prevents the person from deciding.

### SCR-59

#### E-30

**Question**  Does `eligible_total` ever carry an unknown or excluded part, and how is it marked?

**Answer**  eligible_total is a confirmed decimal string on an approved publication. The private computation records exclusions and holds an incomplete eligible total when required. No unknown or excluded amount is folded into the recipient’s total. Zainab can disclose the total and BU breakdown only after the recipient acknowledges the exact current report.

#### E-31

**Question**  Which `action` values does `payroll-operations` accept, and what does `working[]` carry per station?

**Answer**  Operations are working, receive_hr, publish, withdraw, successor and restart. working takes stage combine, match or aggregate. Each station read gives the run ID, kind, complete/held status and codes. Use Working Rows to inspect the private calculation where admitted.

#### E-32

**Question**  Can a BU totals run (SCR-57) read the published payroll aggregate, or the match run, as its payroll input?

**Answer**  Staff BU totals use the exact eligible payroll match run. The published payroll aggregate already lacks the working rows needed to allocate the totals. Intake options return only match runs the current operator can use.
