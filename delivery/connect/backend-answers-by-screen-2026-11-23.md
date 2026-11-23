# Screen-by-screen answers to the frontend backend questions

Audited 23 November 2026. The source on GitHub main has **224 unique IDs** in its numbered sections, A 56, B 53, C 48, D 35 and E 32. The introduction still says 222. A-55 and A-56 were added after that introduction. Every numbered item below has an answer or a specific outstanding action.

The [13 priority answers and five PSL follow-ups](backend-answers-2026-11-23.md) remain the decision record. This section answers the detailed questions under their original IDs, including the ones grouped by the short list. [Original frontend questions](backend-questions.md)

The updated register has 113 answers from existing behavior, 107 answers available on the handoff branch and four items that depend on an approved PSL rule. Related IDs can share one implementation.

GitHub main was at 8f562602 during the original review. The backend changes are now on main. Railway production and design acceptance serve the matching OpenAPI 1.24.0 contract. API paths below are relative to `/api/v1`. [Repository contract](../../contracts/psl-factory.openapi.json) · [Production contract](https://psl-web-production.up.railway.app/api/v1/openapi.json) · [Acceptance contract](https://psl-design-web-design-acceptance.up.railway.app/api/v1/openapi.json)

- **Current** means the answer comes from the existing contract or domain behavior. Some answers explain the supported alternative when a proposed field is absent.
- **Branch** identifies an implementation added in the 1.24.0 handoff release. Each answer states any limits that affect the screen.
- **PSL** means a business decision or business-owned value is still needed. See the [PSL decision list](#questions-for-psl).

## A · App frame and core screens

Sources include [accounts](../../apps/core/factory_api/accounts.py), [work](../../apps/core/factory_api/work.py), [intake](../../apps/core/factory_api/intake.py), [assistant and uploads](../../apps/core/factory_api/agents.py), [alerts](../../apps/core/factory_api/notifications.py), and [staff access](../../apps/core/factory_api/staff_access.py).

- **A-1 — Branch.** Read positions from GET /me or GET /role-dashboard. Use each position’s name, mode and workspace for the role words. There is no separate roles array.
- **A-2 — Branch.** Use destinations[].key, url and available for navigation. The list keeps its six entries. Authenticated Overview is scoped and may be empty; the Clients list is scoped to visible links; specific Setup reads and writes enforce their own permissions.
- **A-3 — Current.** Retry once after refreshing GET /session when the response specifically says csrf_failed. The CSRF middleware rejected that request before the handler. Use the same request and idempotency key.
- **A-4 — Branch.** Use destinations[].url for Next.js. Compatibility fields remain. API-only /me returns Next.js destinations and /my-work; archived Django pages return the retired-page response on the API-only service.
- **A-5 — Current.** Read the JSON code and message. The work access limit uses rate_limited; a bounded source read uses read_limited with 503. The common error response does not guarantee Retry-After.
- **A-6 — Branch.** Work rows expose the action kind, current station index and name, owner, reference, intake and verification times. The initiating staff member sees the Assistant persona when their own chat started the work. Follow tracking_url for the latest recorded worker activity.
- **A-7 — Branch.** GET /work accepts state and supplies the filtered total when it can evaluate all matching work. GET /work/counts reports totals for all queue types together when complete and includes the number actually observed.
- **A-8 — Branch.** limit accepts 8, 10, 15, 20 or 50. The backend looks ahead through at most two empty candidate pages within its read budget. Continue with next_page when there is one. An empty page is still possible.
- **A-9 — Current.** Resolve item.line against lines[].key and title. A work row has no line_title field.
- **A-10 — Branch.** Read started_at for age from intake and updated_at for the last update. The project journey also supplies each item’s start time.
- **A-11 — Branch.** Tracking gives the current station, station order, recorded status, current owner and next step. Intake and human decision stations name their recorded actor when available. A future station can have no recorded owner.
- **A-12 — Branch.** Read tracking.facts for drafted, reviewed, approved, sent, receipt and verified. Null is unknown or unavailable. Invoice and controlled-publication facts use their native records. For checklist facts on specialist lines use their own panels.
- **A-13 — Branch.** POST to work detail’s delivery_observation_url using the original uncertain effect, outcome, reason and work proof. The original reconcile action still performs the provider lookup. The observation does not dispatch or verify a send.
- **A-14 — Branch.** Work detail gives reference, ID and current owner. Tracking gives the intake date and person who started it. Read the relevant invoice or Finance panel for amounts and currency.
- **A-15 — Branch.** GET /work/{id}/history accepts kind=worker, decision or evidence and returns actor_kind, actor, station, status, time and the next cursor for older events. Compose the sentence from those fields.
- **A-16 — Branch.** Use each returned panel’s key, url and contract_path. The latter points to the exact OpenAPI path where available. Choose schemas by operation and line. The server owns the panel list for each item.
- **A-17 — Current.** current_activity is optional and comes from accounting, BU, escalation, forecast, ledger, PPE, reporting or schedules projections. watching indicates that activity view can keep watching. Also use work state, progress and explicit next action to stop or resume polling.
- **A-18 — Current.** For an invoice task, choose an exact item from review_evidence; decision.evidence_id is required. If no options are present, show why the decision is unavailable or route to proof collection. A PMO Lead approval rule does not change Finance task proof.
- **A-19 — Branch.** Task detail exposes its roles, checks, permitted verdicts and hold code where it applies. The tracking read gives the recorded stations and the invoice-specific review steps are available through its review-stations link.
- **A-20 — Current.** This task accepts approve, return or reject. Revoke is specific to review variants that expose it, such as schedule or asset, or to the relevant payment control operation.
- **A-21 — Branch.** invoice_packet provides the amount, currency, basis, preparer and current proof. Compare earlier_version for changes where a previous accessible version of the exact obligation exists. Recipient changes keep their own evidence.
- **A-22 — Current.** Work and task IDs are integers. Use the given tasks[].url for that task, the role-work link for a role assignment, and the payment-controls operation for payment controls. They refer to different record types.
- **A-23 — Branch.** GET /lines returns request_schema, content_type, project_options_url and submit_url. Each authorised line supplies the exact validation schema. Labels, help and source links come from the screen and the line’s options endpoints.
- **A-24 — Current.** POST /work returns 200 with work_id, state, revision and background status. Replaying the same operation on the same inputs returns the same work. Changed data under a reused key is a conflict wherever the native operation reports that replay mismatch.
- **A-25 — Branch.** The listed native start types have a typed submit operation. received-bid uses its separate multipart endpoint. The catalogue is filtered by current authority. If can_submit_via_api is false in any deployed version, use its indicated supported flow or show it as unavailable.
- **A-26 — Current.** POST /work uses line=pmo-finance/v1. The two intake variants use mode=completion for coverage and handoff, or mode=preparation for an existing billing preparation.
- **A-27 — Current.** Private file upload permits one multipart file up to 5 MiB and returns upload_id, name, size, SHA-256 and download URL. It does not return a case revision. Use the case or project chooser for the current revision. Model review and individual domain uploads impose their own file rules.
- **A-28 — Branch.** The conversation list supplies a title, latest status, scope and update time. Conversation detail gives message history.
- **A-29 — Current.** Department conversations still need an authorised case_id as the starting workspace. Send scope=department for a persona/role that allows it. A department lead can choose an accessible project to anchor the thread; the department rules determine what the assistant reads.
- **A-30 — Current.** Message status is queued, running, answered or held, or the projected source_changed. A held turn has no public failure explanation; show a generic retry/access message. An answered turn can contain the insufficient-evidence reply.
- **A-31 — Branch.** Read the turn’s state, started_at and finished_at. Poll while it is queued or running. Native work tracking provides station activity for linked work.
- **A-32 — Branch.** Upload up to three private images to the conversation’s case and pass their IDs with the message. The backend checks ownership, format and permission, includes them with authorised case context in the OpenRouter request, and returns the image IDs with the turn.
- **A-33 — Current.** Overview gives as_of and counts by line for discoverable work excluding verified and cancelled. It is scoped to the signed-in person. There is no top-level total; summing the returned line counts gives the visible open total under that definition.
- **A-34 — Branch.** GET /work/counts supplies open, stopped, held, needs-person and monthly verified counts with a per-line station breakdown. Label observed counts with the returned coverage.
- **A-35 — Current.** The API exposes line key, title and total. Floor grouping is a display mapping owned by the frontend. The backend does not supply a floor per line.
- **A-36 — Current.** The current endpoint is authenticated and uses record scope; it does not enforce a leads/CEO/CTO-only rule. A user may get an empty scoped view.
- **A-37 — Branch.** Exception rows return exception_code, the current next step, and the recorded start time when the exception is the persisted work status. A derived hold or an earlier record can have no captured start time.
- **A-38 — Branch.** Use queue=exceptions with state and read total. It is null when full coverage is unavailable. Do not count the displayed page as the open total.
- **A-39 — Current.** The work queue uses current discoverable work and exception eligibility for the actor. Its access does not come from a leads-only menu rule.
- **A-40 — Branch.** Verified rows carry the actual recorded verified_at and, where accessible, queue_output_url. Use that exact output or receipt for the proof sentence. Recipient-only data stays on its published report.
- **A-41 — Branch.** Filter the verified queue by verified_month=YYYY-MM. The filter uses a recorded verification event; undated legacy work stays out of a dated filter.
- **A-42 — Branch.** Personal alerts supply typed destinations and the original event time where recorded. A legacy alert can have no recorded time.
- **A-43 — Branch.** GET /alerts gives a cursor and unread count for the matching authorised alert set. Acknowledge the exact alert to change its read state.
- **A-44 — Branch.** Use the in-app alert inbox and its daily summary. The response supplies the date and open actions, updates and unread items without a recorded time. Email and WhatsApp remain deferred.
- **A-45 — Current.** Send the required JSON object {}. Success returns id and read. The receiver can update local state or reread the inbox. There is no count in that response.
- **A-46 — Current.** Sign-in returns generic sign_in_failed with no remaining-attempt or lockout time fields. The current Next.js sign-in uses that generic result. Avoid showing a countdown without a supported rate-limit response.
- **A-47 — Current.** Invitation setup and recovery password paths use a 12-character minimum and their password validators. Recovery has a 30-minute lifetime and exposes ready as a boolean. Invitation preview gives expires_at, which comes from the real invitation. The response does not include a password-rule object.
- **A-48 — Current.** For admitted=false show the signed-in person that no work is available to them and give the ordinary sign-out or contact-Admin path. Current Next.js handles this state. It does not require redirecting to an archived Django form.
- **A-49 — Current.** remember=false uses a browser-session cookie. true uses the configured normal Django age, 14 days if the standard default has no deployment override. The endpoint does not return an expiry time.
- **A-50 — Branch.** GET /staff returns separate authorised totals for accounts and invitations, last sign-in, invitation creation and expiry, and the audited deactivation date where available.
- **A-51 — Current.** The deactivation packet’s workspaces[].actions[] gives eligible successors per action and whether it may become unassigned. Send the selected person or permitted null with the exact fingerprint.
- **A-52 — Current.** Roster access is a display summary. GET /staff/{id} gives authorised workspaces and each primary_role. /me positions describe the signed-in person, not arbitrary staff.
- **A-53 — Current.** Staff roster uses scoped staff-administration authority and returns an availability flag with scoped/empty results. Targeted staff reads and writes enforce exact authority. A global Admin label is no substitute for current scope.
- **A-54 — Current.** The active tenant authority’s invite_minutes and expiry determine the invitation expiry. Use invitation.expires_at; there is no universal 72-hour duration. join_url is built from the request host and carries the token as a fragment. Verify the actual Next.js invite origin and route at deployment.
- **A-55 — Branch.** All six public backend download links return JSON 401 to a signed-out request. The old Django login route returns retired-page on the API-only service. The original signed-in file access checks still run.
- **A-56 — Branch.** The Admin role can load without invite_minutes. Existing administration-only authority remains usable, and an incomplete invitation delegation cannot invite. Enabling invitations in a new delegation requires a real duration. PostgreSQL session and role tests passed.

## B · Projects, Setup and clients

Sources include [workspace API](../../apps/core/factory_api/workspaces.py), [project journey](../../apps/core/project_journey.py), [documents](../../apps/core/factory_api/documents.py), [Setup](../../apps/core/factory_api/setup.py), [scoped policies](../../apps/core/factory_api/scoped_policy.py), [project records](../../apps/core/factory_api/project_operations.py), [clients](../../apps/core/factory_api/clients.py), and [costing](../../apps/core/factory_api/costing.py).

- **B-1 — Current.** title is the project display name. Treat it as one string. The project/client relationship is separate, so splitting on a dot does not reliably identify a client.
- **B-2 — Branch.** Project tab register/action rows have state_code and display state. The top-level project journey items still have display state; follow api_url to exact work for its machine state and line.
- **B-3 — Branch.** Each journey item identifies its work kind, start, current state and exact API link. Open the linked tracking read for station order, current owner and next step.
- **B-4 — Current.** Use each work item’s next_step and blocker, and facts.finance.next for the Finance milestone prompt when available. Tola can be opened through the project’s assistant links. The project read does not contain a prewritten Tola summary.
- **B-5 — Branch.** Tabs provide allowed keys and links, not counts. Use the Delivery overview for its six lines and Department handoffs for native receipts; those views serve different tasks.
- **B-6 — Current.** facts.finance.delivered counts visible invoices with a delivery record. It does not measure payments. Use paid/owed from /money, /billing-invoices/{id} or /payments under Finance access.
- **B-7 — Branch.** GET /projects/{case}/document-versions lists readable standalone controlled report versions and links to their exact preview and controls. The project Evidence tab continues to identify original sources.
- **B-8 — Branch.** Use the report title, version, audience, template name/version and sample flag from the preview, plus the project title from Project detail.
- **B-9 — Branch.** Compare two authorised versions of the same standalone report for changed, added, removed and unchanged sections and evidence IDs. Weekly report review separately returns draft-only notes by section.
- **B-10 — Current.** The /publication read gives findings for the checks and review_status for the current review workflow. The generic API does not return the returner’s name, timestamp and reason in that read. Those need a scope-checked review-history projection where the board requires them.
- **B-11 — Current.** Use the allowed decision token from preview. The suffix distinguishes ordinary and delegated routes. delegated=true is used only for the current delegated option. The server verifies that authority. An ordinary reviewer uses false.
- **B-12 — Branch.** Use sections[].key, including issues, escalations, changes, emergencies and rfp. Each section gives page and has_more. It does not publish a section-wide total.
- **B-13 — Branch.** The register exposes a recorded reference and issue age where available. Owner comes from the recorded assignment. A role label is only appropriate where the native source records one.
- **B-14 — Current.** Project journey uses its native filters for issue/action state, current owner and issue severity. For an exact action, the detail lists permitted owners; for issue owners use the corresponding issue options. The generic project tab declares string filters and lacks an option catalogue for all three.
- **B-15 — Current.** Follow each actual item.api_url when present. RFP intake receipt, bid assignment and team inputs are separate reads. The later RFP response is a work line with its own panels. Avoid treating all register IDs as the same kind.
- **B-16 — Current.** /money invoice status is Draft, Issued or Delivered. Read paid and owed for amounts, and GET /payments status for issued, part-paid, overdue, paid, voided and unknown. Delivery does not mean payment.
- **B-17 — Current.** missing_reason explains missing stage or amount context. It may be null for a recorded figure. Display an unknown amount when amount is null. Do not substitute zero.
- **B-18 — Current.** Contract stages use the native stage order in the returned money array. Each row has a stable key and contract_stage flag. There is no numeric position field.
- **B-19 — Branch.** The Money read supplies source type, record ID, date, original reference where recorded and the exact authorised destination. Use the label for display.
- **B-20 — Current.** Start a project conversation with agent and case_id. Assistant thread detail supplies available_sources and the message POST accepts those returned source_keys. A finance figure key is not a conversation creation parameter.
- **B-21 — Branch.** Setup scopes lists the company policy sources a company Admin can read and their exact authority-workspace link. Use the linked versioned policy endpoint for changes and activation under the applicable grants.
- **B-22 — Branch.** GET /setup/{case}/rules supplies a stable component key for each rule. Use the scoped configuration endpoints and their version for changes.
- **B-23 — Current.** Use can_configure/can_activate where a scope operation supplies them, plus its native choices. Those flags do not automatically authorise each rule type. General rule rows lack per-row can_change and an editable role list.
- **B-24 — Current.** Use the configuration’s actual review actions and current policy authority. Several policy paths require independent proof or validation. Admin’s company Setup ownership does not grant a domain decision or bypass a separate reviewer.
- **B-25 — Branch.** POST /setup/{case}/decision-proofs records a checked, owned PDF as native policy-decision evidence. Use the resulting evidence ID with the appropriate Setup action. Configuration and rule activation still check their own authority.
- **B-26 — Branch.** GET /setup/{case}/delegations returns role, names, current validity status and the reason recorded with that active configuration where available. Delegation draft intake accepts the reason. Earlier versions may have no captured reason.
- **B-27 — Branch.** Use GET /setup/scopes for workspaces permitted to read policy and the returned can_configure. A readable project in /projects is not necessarily one the account may configure.
- **B-28 — Current.** POST milestones/completions accepts the real milestone name with current revision and typed completion evidence. It returns a new milestone ID. Billing-stage binding requires the exact configured milestone identity, so use the expected name/record from the native project flow.
- **B-29 — Branch.** For milestone completion, submit an existing eligible native proof or a checked private PDF upload. The backend retains the source and evaluates the exact milestone, signed baseline and independent gates.
- **B-30 — Current.** The response confirms the milestone, revision and proof. It does not guarantee a Finance work ID immediately. The service queues the handoff; read the project’s department handoffs after its worker records it.
- **B-31 — Branch.** Milestone completion options expose can_complete, can_attach_pdf and the exact recorded hold, including baseline_required, proof_required and name_in_use. The write rechecks the current record.
- **B-32 — Current.** Use reviews/exceptions as the project list’s scoped projections, and lifecycle/phase as the returned project badges. They are not universal queue counts. Null means unavailable in that projection.
- **B-33 — Branch.** GET /projects returns matching authorised lifecycle counts and a name/date for the next stage where Finance has a current signed stage with that information.
- **B-34 — Current.** Projects uses cursor paging at the server’s fixed size of 25. This is separate from the work queue limit.
- **B-35 — Branch.** Project action rows show status, owner and the visible source meeting’s label and date where linked. The exact action detail supplies its current revision and assignment.
- **B-36 — Branch.** Project tabs expose total, overdue and unassigned action counts from the authorised records. The backend uses the native due-date and pause rules.
- **B-37 — Branch.** Project action updates accept an eligible evidence ID or a checked private PDF. A current PMO Lead can approve an eligible PMO-owned Planning step directly. Independent approvals keep their own checks.
- **B-38 — Current.** The template catalogue takes a case_id and applies its scope/visibility. Setup scopes identifies eligible workspaces. The current endpoint has no unrestricted company-wide template list.
- **B-39 — Branch.** The catalogue identifies exact template name, version, document type, sample, creator and recorded time, with a download link.
- **B-40 — Current.** Use a current policy_decision proof from the same project justifying the replacement, plus previous for the exact former template and the new file. The server checks the proposed proof on the replacement. The previous template ID alone is not proof of the new decision.
- **B-41 — Current.** document.read permits the scoped catalogue. can_upload indicates editing rights separately. The API uses visible_templates and the download route performs its own scope checks.
- **B-42 — Current.** A group is a stable opaque grouping key for the reviewed client links visible to the actor. Feed key to /clients/groups/{group}. An individual project still has its own case_id and record access.
- **B-43 — Branch.** Client-group detail includes debt for readable member projects only, with currency, known amount, unknown records, observation date and scope coverage.
- **B-44 — Current.** Billing contacts are project- and purpose-specific. Open the invoice/project’s current contact. A group does not select or create one master contact.
- **B-45 — Current.** GET contact options supplies eligible customers and exact contact proof IDs for the selected purpose. Use a recorded same-project proof of the contact instruction. A generic upload ID does not become that proof automatically.
- **B-46 — Current.** recorded means a current billing contact is recorded for that project; needed means the required contact is missing; unknown means the relevant billing scope could not be established. contacts_needed counts group projects in the needed state.
- **B-47 — Current.** /money is the Finance billing-stage view. Milestones is recorded completion proof. The money key is a stage key, not the milestone record ID. Use a typed milestone source when returned, or the native stage-to-milestone link.
- **B-48 — Current.** Show the permitted milestone/completion record view and its proof/actions. Amounts, invoices and balances come from the Finance-scoped read.
- **B-49 — Branch.** Money includes the signed stage position and the exact milestone ID where a native link exists.
- **B-50 — Current.** Costing source returns the structured rule and oracle payload, with exact review IDs, verdicts and dates. Proposal detail compares parameter and worked example results. Public read models do not include a prose summary or all proposer/reviewer names.
- **B-51 — Branch.** Start from Setup scopes, then use the authorised source workspace and its current organisation policy/version for the rule. Do not pick an arbitrary project as the company pricing authority.
- **B-52 — Current.** Review the exact proposal, comparison and independent examples using /costing/proposals/{id}. Submit a current case evidence ID for the independent reviewer’s decision, the verdict and the reason. The options and native policy check source identity and reviewer authority.
- **B-53 — Current.** /work starts or reads the process line; costing rules, calculations and proposals have separate project costing operations. Bid pricing is exposed on rfp-response/v1 via its bid-pricing panel. A costing rule proposal is not a separate work definition.

## C · Bid, report and planning screens

Sources include [received bids](../../apps/core/factory_api/received_bids.py), [bid pricing](../../apps/workflows/factory_rfp_pricing.py), [submission checks](../../apps/pmo/rfp_submission_artifacts.py), [engagement registration](../../apps/pmo/engagement.py), and the [API contract](../../contracts/psl-factory.openapi.json).

- **C-1 — PSL.** The bid outcome read supplies eligible roles, the current debrief and reasons from the active loss catalog. PMO still needs to approve the catalog where none is configured.
- **C-2 — Branch.** The bid assignment, team input and outcome actions accept eligible evidence or a checked private PDF bound to that action. Release and signature actions use their own typed evidence and authority.
- **C-3 — Branch.** The original bid outcome witness includes an optional recorded reception channel alongside its date, note and proof. Earlier records can have no channel.
- **C-4 — Branch.** The assigned project manager records an actual request or block for a named bid team through team-requests. The team-inputs read separates not requested, awaiting reply, blocked and received for the current intake and links the actual receipt.
- **C-5 — Current.** Call POST /work/{work_id}/bid-outcomes/{outcome_id}/followup with action review. It sits between draft and send on the follow-up itself.
- **C-6 — Current.** selection_packet is an opaque snapshot token for the current selected submission and the visible selection inventory. The person checks that exact submission and coverage before setting selection_acknowledged. A new snapshot needs a fresh check.
- **C-7 — Current.** Open /received-bids/{case_id}/receipts/{receipt_id} using the returned IDs. The dedicated /received-bids/assignments queue and /received-bids/{case_id}/assignment cover unassigned bids. A generic work ID is unnecessary for that path.
- **C-8 — Current.** Select the organisation using GET /received-bids/organisations. Send its delegation ID as authority. The optional legacy definition identifies received-bid. context_attested is the person's confirmation of the captured prospect and submission instructions.
- **C-9 — Current.** prospect_name is the name captured on the bid. It does not create or match a client. The organisation list supplies intake authority. Use explicit client and engagement linkage when the workflow has that record.
- **C-10 — Branch.** The fresh bid intake can save a bounded note on the original intake version and returns it with the receipt.
- **C-11 — Current.** The same actor, authority, start key and exact input replay the original receipt. A second intake using the same organisation and reference is blocked with HTTP 422 action_unavailable. The response message explains the duplicate. There is no duplicate-specific code.
- **C-12 — Current.** evidence is required, with an eligible integer ID from the assignment read's proofs. reason is also required. Label it as the reason for the assignment.
- **C-13 — Branch.** Assignment reads return the nominee’s recorded role and the applicable next actions for the current assignment.
- **C-14 — Current.** A completed assignment leaves the dedicated bid assignment queue. The read shows the recorded assignment. A separate factory work item need not exist yet.
- **C-15 — Branch.** The weekly report read includes a bounded authorised list of the week’s evidence and narrative with their source labels and coverage.
- **C-16 — Branch.** The weekly report read supplies the permitted reviewer return note for the exact draft and its review.
- **C-17 — Branch.** The weekly panel links to the authorised exact draft preview. Review-only notes are attached to each applicable section for authorised reviewers. The published document leaves them out.
- **C-18 — Branch.** Use weekly-report-intake action start to begin the recorded work. The background setting controls queueing. A saved intake draft has no factory work ID. After start, use work detail and tracking for observable progress.
- **C-19 — Branch.** Work action reconcile uses the native receipt or effect check. The separate delivery reconciliation command accepts an authorised manual observation with proof and reason when needed. Use the exact action shown by the panel.
- **C-20 — Current.** The detail panel key is weekly-report.
- **C-21 — Branch.** Bid answers use a paginated list with requirement ordering, original source reference and any exact reviewed wording/page citation. The citation write checks the quoted wording against the authorised source.
- **C-22 — Current.** The reviewed source analysis fixes the requirement set for that bid version. bid-answers supports suggest, review and undo; it has no add_requirement action. Correct the source and use the new reviewed version if the requirement set was wrong.
- **C-23 — Branch.** The answer panel supplies counts and review readiness for the current requirement inventory. Keep submission gate checks separate.
- **C-24 — Branch.** The bid answers summary identifies the exact work and recorded Engineering review return reason where there is a current decision. Request the pack review through the separate pack action.
- **C-25 — Branch.** The bid clarification read and write retain the question and actual response against the selected requirement with date and evidence. Staff send it through their chosen channel outside this API.
- **C-26 — Current.** Use the actual reviewed costing rule and its calculation. Keys and units come from that version. Do not assume a fixed Engineering/Security/PM/total list. Resolve a configured display name from the rule where it exists.
- **C-27 — Branch.** The costing read has stable codes for the current Project Manager, Head of PMO and CEO review status. The backend still checks the sequence and source revision.
- **C-28 — Current.** Use /work/{work_id}/reviews with kind bid, subject commercial and the current commercial revision. The CEO decision requires the currently authorised person in that configured step.
- **C-29 — PSL.** With no authorised adjustment rule, the pricing read returns an empty adjustment_targets list and no adjustment currency. Finance needs to approve targets, currency and absolute limits before enabling adjustments.
- **C-30 — Current.** Yes. Delivery plan is a named input bound to the selected planning evidence version alongside the other reviewed sources.
- **C-31 — Branch.** Minutes suggestions expose the cited wording as the proposed title. The extractor supplies no confirmed person or deadline. Those fields stay empty until the meeting reviewer confirms them from the source.
- **C-32 — Current.** Audience is fixed for the selected intake and its source. Confirmation records the meeting content and choices for that intake. A different audience takes its own eligible intake.
- **C-33 — Current.** Confirming the minutes records confirmed actions. Approval of outward minutes is separate and controls what can be released.
- **C-34 — Current.** GET /projects/{case_id}/meetings/{meeting_id} gives reference, purpose, occurred_at and visible participants. Count the visible participants for the card. The minutes panel's confirmed_meeting_version_id is a version ID, so use the native meeting link or list to find its meeting ID.
- **C-35 — Current.** Request outward review through the minutes review-request action. Record the configured reviewer decision with kind document for the exact version. Return acts on that document version and preserves the native confirmed actions.
- **C-36 — Current.** Approving the pack and queueing bid submission are separate. A permitted person starts POST /bid-submission after the current pack passes its checks. Verify the separate submission receipt afterward.
- **C-37 — Branch.** PDF package checks include stable codes and readable explanations for format, count and size findings.
- **C-38 — Branch.** The panel identifies the recorded package sections and sample status, and links the exact verified PDF. Native submission verifies a single PDF package.
- **C-39 — Current.** Use kind bid and subject document for the bid pack's exact controlled version. The review keeps that document's authority and inspection checks.
- **C-40 — Current.** register.value is the official project identifier in the configured namespace and format. The person authorised for registration enters or confirms the value and its planning evidence.
- **C-41 — Current.** key is the operation's idempotency key. Use it unchanged on an exact retry. checked belongs to details and records that the person checked the actual captured details and selected source. assign records the assignment without that checkbox.
- **C-42 — Branch.** Engagement supplies readable sources on its exact agreed packet and named Project, Planning and Money links for scope, plan and Finance price.
- **C-43 — Current.** Route A converts a won bid. Route B is the direct, non-bid engagement route supported by same-case source evidence. Route C requires Product intake evidence. Show those plain names with the route code where it helps.
- **C-44 — Branch.** The department request panel gives its reference, request type, creation date and original received date where recorded. Read the linked source for the original wording.
- **C-45 — Current.** Pick the current evidence record admitted by the project's planning source choices and send its source_id. Planning and bid inputs both reference evidence records, but each line validates its own case, source kind and permission. A file upload ID is insufficient.
- **C-46 — Current.** Planning includes Infrastructure and Product alongside Engineering, QA and Security. Its choices come from the planning line. Earlier bid team inputs use different choices.
- **C-47 — Current.** The planning source-clarifications read provides owner_status and can_assign. Use its eligible assignment command and owner choices when Product is unassigned.
- **C-48 — Current.** prepare_readiness prepares and records the checks. Handoff is a separate human command bound to the current readiness record and the right authority. Neither step substitutes for a separate decision required by the next line.

## D · Delivery, change and leadership screens

Sources include [change rules](../../apps/pmo/changes.py), [release checks](../../apps/pmo/phase_evidence.py), [go-live signatures](../../apps/pmo/go_live_attestations.py), [go-live milestone rules](../../apps/workflows/factory_go_live_milestone.py), and [leadership reporting](../../apps/workflows/factory_leadership.py).

- **D-1 — Branch.** Use the operation that owns the evidence. Go-live sign-off proofs accepts a checked signed PDF for the exact receipt and signer role. The release register accepts a checked PDF on the actual release observation. Minutes file intake retains the extracted notes with their source. Each action retains the exact native evidence ID, and sign-off remains a separate decision.
- **D-2 — Branch.** Issue detail and follow-up give the original opening time and age. Use blocked-milestone to link a recorded project milestone or its currently approved planned stage, with original evidence. Completion remains a separate decision.
- **D-3 — Branch.** Issue detail includes a bounded timeline of visible state changes, acknowledgement, and actual owner message and delivery events. The exact Messages panel retains its own permissions and shows reminder timing.
- **D-4 — Current.** Use issue-followup respond with team_reply when responding to the exact work task and recording its linked team witness. Use /issues/{id}/team-replies for an independently captured team reply. Submit one path for the same reply.
- **D-5 — Current.** For a normal change, Product and Engineering are always required. Client is added when client-facing. Engineering Lead and Security Manager are added when the timeline is affected. Standard and emergency changes use their own rules.
- **D-6 — Current.** The stage codes are source, impact, authorization, notice, execution, go_live, signatures and complete. The frontend can group these into the five visual steps.
- **D-7 — Current.** Record proof of the actual client's decision with real source system, reference, decision ID and version, signer and signed time as required. An authorised PM can record an external signature without a client login. The source identifiers must come from the retained proof or its source record.
- **D-8 — Current.** Put “went well,” “didn't go well” and “lessons” in the retrospective summary. Decisions and actions are separate records. The native retrospective command saves a meeting record; the minutes preparation flow is the separate draft path.
- **D-9 — Branch.** Closure returns the retrospective link with its exact selected version_id. Use that version for the historical record the checklist used.
- **D-10 — Branch.** The overview returns the same six stable Delivery lines for every project, including not_started when no work exists, with recorded state, date, reference and links to each line’s gate checks.
- **D-11 — Branch.** Use delivery-release/v1, delivery-go-live/v1, delivery-hypercare/v1, delivery-handover/v1, delivery-archive/v1 and delivery-closure/v1 from delivery-overview.lines[].key.
- **D-12 — Branch.** The current PMO Lead who is the named approver can approve an eligible PMO-owned Planning exit directly. The backend saves their approval, role and time and enforces the current packet and independent gates.
- **D-13 — Current.** Both paths can prepare readiness. An authorised PM can trigger prepare_readiness. The delivery worker can prepare it when execution is configured and current gates pass. Subsequent acceptance and release observations must still be recorded.
- **D-14 — Current.** Phase names are Initiation, Planning, Execution and Closure. Check statuses are unknown, stale_scope, current, restricted_or_authority_changed and unknown_or_stale. Read allowed commands from the separate actions list and let the server verify the exact transition.
- **D-15 — Current.** Go-live needs two distinct evidence IDs, one for each exact signature. A single uploaded signed copy may be source material only where two distinct, verified signer records can be linked to it. The API does not accept the same evidence ID twice.
- **D-16 — Current.** Use the actual external decision's source system, identifier and version, bound to the signer and exact acceptance. Choose those from the retained external signature or register. Missing source information needs reconciliation before acceptance can be verified.
- **D-17 — PSL.** An authorised policy configurator drafts the mapping from the real project owner's decision evidence. The approved current mapping and verified go-live acceptance are required before milestone completion. Projects without a mapping need an authorised owner to confirm which milestone is completed.
- **D-18 — Current.** Submit a structured stability observation with its actual approved metrics, time and proof. Use the separate issue record for an open issue and display it separately. A free-form note can add context.
- **D-19 — Branch.** The Hypercare read gives a result for each configured time, confirmation, metric and issue criterion using the same checks as its decision.
- **D-20 — Branch.** Archive files expose a stable group and the exact source kind and ID where authorised. Use the source link to open the original.
- **D-21 — Current.** An authorised person reserves the archive from the exact current source IDs. The worker can process the reserved archive. required_source_ids can preselect the list for review. A go-live alone is insufficient to record a completed archive.
- **D-22 — Branch.** GET /support-publication says can_publish and supplies the approved version when ready. An authorised PM uses POST on that route to queue publication. Read the eventual Support receipt separately.
- **D-23 — Branch.** Support replies preserve an optional structured gaps list alongside the reply status and note on the protected exact acknowledgement.
- **D-24 — Branch.** The actual Support recipient reads the exact handover title, version and sections at support-receipt. The read includes the two bound supporting records when the recipient also has source access.
- **D-25 — Branch.** Use GET and POST /projects/{case_id}/delivery/{dossier_id}/finance-confirmation. Finance checks the milestone receipts and records the exact reviewed set, completeness, evidence and note.
- **D-26 — Current.** kind closure targets the controlled closure document with version_id. evidence_id is the eligible evidence for the review decision. The source report, decision proof and document version each retain their own reference.
- **D-27 — Branch.** Closure returns protected debt figures for that project with the Finance observation date and unknown coverage, where the viewer can read Finance data.
- **D-28 — Current.** record_review logs the actual post-implementation assessment. For an applicable retrospective decision use its separate return action. For an outward document use that version's independent review verdict.
- **D-29 — Branch.** Send customers_affected as a non-negative number or null and side_effects as text or null on the outcome. Read them in outcome_impact. Null means there is no confirmed value.
- **D-30 — Branch.** Emergency decisions and the recorded outcome give their named authorised actor and time where stored in the native history.
- **D-31 — Branch.** Use reject for a declined escalation and return for rework. The eligible reviewer can see the reason and exact decision time.
- **D-32 — Branch.** The escalation draft read includes an authorised exact preview and permitted recipients. Sending and delivery receipts remain separate operations.
- **D-33 — PSL.** all_projects_available lets the form submit the selected source domains without listing every record ID, when the approved workspace scope is enabled. Access is still checked per project. PSL needs to confirm whether to enable that scope for the leadership workspaces without it.
- **D-34 — Branch.** Leadership reporting supplies per-source counts from its exact authorised selection manifest, with when it was captured and what it covers.
- **D-35 — Current.** For the monthly executive report, the configured worker can request exact human review while preparing the retained draft. If the review was not requested, the work offers the authorised request-review action once eligible. The internal Tuesday report uses its own review rule.

## E · Finance, payroll and HR screens

Sources include [payroll API](../../apps/core/factory_api/payroll_sources.py), [HR handoffs](../../apps/core/factory_api/hr_handoffs.py), [payments summary](../../apps/finance/payments_overview.py), [month-end](../../apps/finance/month_end.py), [group forecast disclosure](../../apps/finance/group_forecast.py) and the [API contract](../../contracts/psl-factory.openapi.json).

- **E-1 — Branch.** Payroll input options give supported codes and safe readable explanations, including the configured expected sheet where applicable. Protected working rows carry actual import findings.
- **E-2 — Branch.** Download a blank JSON, CSV or XLSX template for the selected provider’s approved schema and file layout.
- **E-3 — Current.** kind is input or run. Combine, match and aggregate use run with that run's ID. An invisible workspace or absent record is 404. An admitted workspace reader without the required payroll grant receives 403. Exact native access is also checked before exposing any working rows.
- **E-4 — Branch.** Payroll inputs return private matched, unmatched, conflict and held counts from the working runs the viewer can read.
- **E-5 — Current.** The recipient report returns approved BU totals and the eligible total, without staff counts or unmatched employee rows. An unmatched row is not given a zero BU entry. Check unresolved matching privately before treating the disclosed totals as complete.
- **E-6 — Current.** POST /payroll-operations with action receive_hr and the exact received snapshot and evidence IDs. Use can_acknowledge to offer this action. If the snapshot was never received, there is no receipt to confirm.
- **E-7 — Current.** age_days measures days past the invoice due date. The reminder balance or applicable project money item gives the due date. The company Payments row does not carry a separate due_date.
- **E-8 — Branch.** A new receipt requires a positive known amount and payment source. Existing incomplete entries can still use the native correction path. Verification and allocation remain separate.
- **E-9 — Branch.** Payments returns verified month-to-date receipts for readable workspaces with currency and coverage, the last source receipt time where known and its verification information. Bank-feed freshness needs a live feed.
- **E-10 — Branch.** For the returned rows in a currency and basis group, null owed means a complete total is unavailable. Use known_owed for the sum of confirmed balances and unknown_owed_count for the number with missing balances.
- **E-11 — Branch.** limited warns that the read was bounded. Label the totals as covering the rows returned and follow cursor for more. The response cannot support a company-wide total when its coverage is incomplete.
- **E-12 — Current.** Accepted actions are send, set_aside, cancel_schedule, check_mailbox and confirm. send accepts an optional scheduled_for. check_mailbox reads an enabled synthetic transport and confirm records actual evidence for a dispatch.
- **E-13 — Branch.** The reminders read gives the configured interval, the earliest allowed follow-up date where calculable and whether it is waiting for the original receipt.
- **E-14 — Current.** Month-end checks readers against each finance line and the exact restricted source or acknowledged aggregate receipt. It omits work the person cannot access, including its labels. A permitted aggregate reader can still see the relevant work summary.
- **E-15 — Current.** The reviewed period rows use Reviewed figures or Needs a fresh review. values contains label, value and unit for the authorised reviewed metrics. An unavailable review gives an empty list. Receivables snapshot status is a separate field.
- **E-16 — Current.** Each returned cash row has a string amount. Unavailable coverage is flagged by cash_unavailable and may leave rows missing. Show 0.00 only for a confirmed zero row.
- **E-17 — Current.** needs has id, reference, version, entity, period, purpose and fields. disclosures has id, need_id, latest_decision and created_at. The exact disclosure detail adds decisions with id, verdict and created_at, and corrections with id, snapshot_id, decision and successor_id.
- **E-18 — Branch.** The authorised HR handoff read surfaces pending corrections across eligible disclosures. Open the original disclosure to decide each request.
- **E-19 — Current.** POST /accounting accepts recheck_reviewers and reassess. review_stations lists each station label and subjects with id, status, review_id, evidence_id and reviewed_at. tasks gives id, revision, label, can_claim, can_decide and allowed verdicts.
- **E-20 — Branch.** Accounting intake and mapping return findings and finding_details with a stable code, original message, and line or field where known. Unclassified legacy messages remain readable.
- **E-21 — Current.** Use kind schedule on /work/{work_id}/reviews, with the exact target_id, current revisions, verdict and note. The schema requires evidence_id, including for approve.
- **E-22 — Branch.** The Finance schedule read exposes an approval hold code when an eligible reviewer or prior step is missing. Setup owners use the existing reviewer configuration.
- **E-23 — Current.** register reviews the source asset register, basis reviews a required justification for the chosen date or calculation basis, and schedule reviews the resulting depreciation schedule. The current review_options sets the purpose and target to offer. A separate basis review is used where required.
- **E-24 — Branch.** The asset panel links directly to the selected accounting note when the person can read the exact Finance mapping. Opening and date proofs retain their own links.
- **E-25 — Current.** result contains status, entity, currency, basis, as_of, findings, expected items, periods and actuals. jobs gives ID, status, receipt IDs and retry/operate permissions. disclosure gives configuration, permitted rows and recipients, evidence choices and selected fields/metadata. matches gives ID, item_key, actual_id and amount.
- **E-26 — Current.** Group recipients get a separate approved projection with only the selected row fields and metadata. The field list excludes staff names, individual pay records and raw payroll input. A payroll-related cash assumption still needs explicit inclusion and review on that exact projection.
- **E-27 — Current.** inputs has mode, payroll_id, source_id, rule_ids and optional comparison with run and metric. result has ID, kind, status, codes, scope and totals. A too-small group holds the publication; use the authorised staff-facing finding. A recipient does not get the private staff counts.
- **E-28 — Current.** POST /business-units accepts prepare_rule, publish and restart. Record the independent approval through /reviews with kind business_unit.
- **E-29 — Branch.** The protected Ledger response gives the latest decision’s reviewer and date, plus a stable hold code when the independent reviewer rule prevents the person from deciding.
- **E-30 — Current.** eligible_total is a confirmed decimal string on an approved publication. The private computation records exclusions and holds an incomplete eligible total when required. No unknown or excluded amount is folded into the recipient’s total. Zainab can disclose the total and BU breakdown only after the recipient acknowledges the exact current report.
- **E-31 — Current.** Operations are working, receive_hr, publish, withdraw, successor and restart. working takes stage combine, match or aggregate. Each station read gives the run ID, kind, complete/held status and codes. Use Working Rows to inspect the private calculation where admitted.
- **E-32 — Current.** Staff BU totals use the exact eligible payroll match run. The published payroll aggregate already lacks the working rows needed to allocate the totals. Intake options return only match runs the current operator can use.

## Backend implementation register

The implementation answers are recorded beside the original question IDs. External email, WhatsApp and live HR remain deferred as agreed. Next.js integration and screen acceptance are with the frontend developer.

## Questions for PSL

These four numbered items need business input if the corresponding policy is absent. Apply an existing approved configuration if the owner can point the team to it. The screen answers record the supported behavior when those values are absent.

1. **Bid loss reasons (C-1).** Which reasons should PMO staff be able to pick when recording a lost bid? The API shows the active catalog to eligible staff when PSL has approved one.
2. **Bid price adjustments (C-29).** Should staff be able to adjust a bid costing line? If yes, which lines, in what currency, and what's the largest permitted change? The adjustment controls stay unavailable without an approved rule.
3. **Go-live milestone (D-17).** For projects without a mapping, which milestone should a signed go-live complete? The responsible project or policy owner needs to confirm it before Finance receives that milestone as completed.
4. **Leadership report coverage (D-33).** Should the Tuesday report, monthly executive report, or both offer a one-click selection for all projects the authorised preparer can already see? This setting leaves the existing PMO and project access rules in force.

Operational reviewer assignments, account invitations, and the deferred HR and external notification connections depend on their existing owners and configuration. The audit carries forward PSL's existing decisions on roles, sharing, payroll disclosure, finance file extraction and review, voice and alerts.

## Verification for this audit

The 224 numbered answers match the original question IDs. The PostgreSQL checks in the test ledger use synthetic data. The Assistant check observed the text and image request sent to the OpenRouter adapter with a test response. Both Railway APIs matched the 1.24.0 snapshot. The production in-app browser confirmed health, contract version, and retirement of the Django sign-in page. [Test ledger](../../BUILD-TESTS.md)
