# Development and restart

This is the partial application underpinning PSL’s AI agent operations factory. The current staff screens and tested native workflows are supporting foundations; a complete factory console and connected agent/human/output acceptance are still planned. See IMPLEMENTATION-PLAN.md and BUILD-STATE.md for actual scope. This synthetic local environment is not production. Starting the web server does not activate a factory-wide orchestrator or authorise workers, external effects or owner policies.

## Installed and locked

Python 3.13, Django 5.2.18, psycopg 3.3.6, PostgreSQL 16.15. requirements.lock records the exact installed dependencies. Django 5.2 supports Python 3.13: https://docs.djangoproject.com/en/5.2/releases/5.2/. The PostgreSQL project links the vendor-provided portable archives: https://www.postgresql.org/download/windows/ and https://www.enterprisedb.com/download-postgresql-binaries. These sources support compatibility/download selection, not application acceptance.

## Clean setup

Run in the repository root in PowerShell:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.lock
```

Provide PostgreSQL using your own server and PGDATABASE/PGUSER/PGPASSWORD/PGHOST/PGPORT environment variables, or use the local portable instance. The installed local binaries and database live under ignored .runtime. This session downloaded https://get.enterprisedb.com/postgresql/postgresql-16.15-1-windows-x64-binaries.zip and extracted pgsql/bin, pgsql/lib and pgsql/share under .runtime. To recreate it, download that archive over HTTPS and extract those directories with Python zipfile or your archive utility. Do not download or extract it into the source reference folders.

```powershell
./scripts/start-dev-postgres.ps1
.venv/Scripts/python manage.py migrate --noinput
.venv/Scripts/python manage.py check
.venv/Scripts/python manage.py seed_demo
.venv/Scripts/python manage.py runserver 127.0.0.1:8000 --noreload
```

Optionally run `.venv/Scripts/python manage.py complete_demo` after seeding and then `work_outbox --limit 50` to populate the connected synthetic baseline/handoff/extraction/source-preview example using real services. This command refuses already completed demos.

The demo command creates two synthetic cases with explicit action grants and prints a random password once. It refuses to reset an existing account or overwrite its cases. The existing session account is studio-demo; its generated credentials are stored locally in ignored .runtime/demo-access.txt. Do not commit that file. No real business approvers are created. A database administrator can provision users and explicit record grants with Django's shell; identity administration UI remains to be built.

The portable database uses loopback-only trust authentication for disposable synthetic development. Use authenticated database access, managed secrets, TLS and separately isolated infrastructure for staging/production. The application refuses its development secret outside PSL_ENV=development. Deployment hardening and restore rehearsal are still outstanding. Docker was unavailable in the initial environment; the portable server avoids a system service installation.

## Worker and tests

```powershell
.venv/Scripts/python manage.py work_outbox --limit 50
.venv/Scripts/python manage.py test tests --noinput --verbosity 2
.venv/Scripts/python manage.py makemigrations --check --dry-run
```

Run the bounded worker repeatedly from a separate process/scheduler; a permanently supervised worker and timer/task runtime are future work. TestCase integration tests use a separate PostgreSQL test_psl database with real application services; TransactionTestCase exercises two database connections claiming one intent. Timeout/provider faults are synthetic. No SQLite fallback exists. Do not point tests at an operational environment.

Internal Finance delivery is the implemented adapter. It creates one inbox receipt per milestone with a stable operation key and compares the payload on reconciliation. Timeout-after-accept and lookup failure fixtures exercise uncertainty. No email, accounting write, invoice posting, GLPI change, credit, payment or deployment effect is implemented or performed.

## Inspect the connected flow

1. Open http://127.0.0.1:8000 and use the synthetic demo account.
2. In the project case, inspect seeded evidence. Prepare the baseline using the plan/costing/SOW evidence IDs. Detailed planning evidence precedes signature.
3. Configure human-role references and the D05 component using the examples below. Every value remains explicitly synthetic. Record PM, Head of PMO and CEO decisions in order; record PMO Lead document quality decision separately; attach the signature evidence.
4. Complete a milestone with completion evidence. Run the outbox worker. The same case now shows the Finance receipt. Start preparation intake; this does not issue an invoice.
5. Use cited extraction on evidence. The synthetic provider quotes existing source lines and cannot invoke approval tools. Real provider setup/evaluation remains outstanding.
6. Open the support workspace to record a response, resolution and reopen evidence. Document review works on exact evidence versions.
7. Add financial_input evidence using the CSV schema below; capture it into Finance source intake. Preview remains usable without source policy. Validation reports D06 dependencies precisely. No management accounts are calculated.

## Component configuration examples

The workbench persists incomplete drafts and exposes all 57 source component schemas. It validates the complete checked-in envelope schema before activation. History is append-only in PostgreSQL. The original four semantic validators are: D04.iana_timezone, D05.role_principal_assignments, D06.source_schema_ref and D06.unit_sign_currency_period. Four additional validators now support D05.delegation_rules, D05.decision_action_matrix, D11.recipient_grant_refs and D11.template_storage_retention_rules. The other 49 semantic implementations are explicitly unfinished engineering; their drafts can be captured but activation reports the missing reviewed validator.

For role assignments, first register immutable domain references (for example ref demo:pm, schema_ref schema:psl/role-assignment/v1, content {"role":"PM","user_id":1}) with the case's policy_decision evidence ID. The actual ID must identify an active local user. Array references resolve to immutable version 1; use a fresh ref identifier to change an assignment, then a new component version. Supported costing/document roles are PM, Head of PMO, CEO and PMO Lead. An administrator flag supplies no record/action grant. Multiple roles assigned to one person are allowed only in isolated synthetic cases until real dual-role policy exists.

The D05 value is an array of those registered references, not free-text role claims. The envelope has component_id D05.role_principal_assignments, slot_id D05, component_schema_ref schema:psl/policy-component/D05.role_principal_assignments/v1, subject_scope {"kind":"project","ref":"CASE_UUID"}, schema_version "1", policy_revision 1, lifecycle draft, effective_from with a timezone offset, effective_until null, evidence_refs and human_decision_ref pointing to evidence:ID on this case, implementation_id psl.reference-validation, implementation_version "1", reviewed_implementation_ref code:apps/policy/services.py#reference-validation-v1, fixture_scope synthetic_test and the value. The application assigns the next revision; validation and activation are distinct authorized operations. New policy versions supersede prior active versions. Revocation and expiry never fall back to an old version. Re-recording decisions under new authority preserves the old decisions.

Timezone uses value "Africa/Lagos" (or another valid IANA identifier), with component_id D04.iana_timezone and its matching slot/schema references. It activates without configuring all of D04.

Source schema uses a registered record with schema:psl/controlled-csv/v1 and content {"columns":["account","amount","currency","period"]}. D06.source_schema_ref has that record's ref as its value. This is an engineering interchange, not a claimed QuickBooks export format.

Source conventions use a registered schema:psl/source-conventions/v1 record with explicit currency, unit major_currency, period YYYY-MM and sign_convention debit_positive or credit_positive. Its component value is the checked-in artifact-ref object (artifact_ref, artifact_version, sha256, schema_ref). This declares input conventions only; it does not apply a financial formula. Actual source samples and owner decisions are required for operational use.

```csv
account,amount,currency,period
100,1234.56,NGN,2026-10
200,,NGN,2026-10
```

The second amount is unknown and makes source validation incomplete. Duplicate source content is rejected. Import evidence, rows, validation policy IDs and findings remain immutable. No account mappings, financial formulas or reconciliation success are inferred from a valid CSV.

## Recovery and shutdown

For an unknown handoff, run the worker again: it looks up the stable operation key before considering dispatch. An expired lease can be reclaimed; an expired worker cannot finalize the newer fence. Revoked authority or exhausted budgets produce held jobs. Held-job retry/cancel operator UI is not yet implemented; inspect the audit and receipt, then implement/perform an explicitly reviewed recovery instead of editing payloads. PostgreSQL rejects identity/payload changes to reserved intents and changes to confirmed handoff receipts.

Stop the development web process with Ctrl+C. Stop the portable database without deleting it:

```powershell
.runtime/pgsql/bin/pg_ctl.exe -D .runtime/pgdata stop -m fast
```

Operational backup/restore, export, supervised deployment, retention, SSO, monitoring, real integration contracts and provider evaluation remain on BUILD-OPS. Existing PACK-MANIFEST.json/VALIDATION.json document the original pack baseline and are not application acceptance checks.


## Controlled-document and PMO-gate continuation

After the existing synthetic project is provisioned, run:

```powershell
.venv/Scripts/python manage.py seed_documents_demo
.venv/Scripts/python manage.py work_publications --limit 50
```

The fixture is restricted to synthetic-demo cases and refuses to overwrite an existing document demo. It registers a controlled template, explicit synthetic recipient/storage component versions, a candidate and synthetic QA-source result, then produces a reviewable gate packet, a synthetic PMO Lead decision and a pending publication. The separate worker delivers to the real local recipient inbox only. It also creates a cited agent draft; the browser demo requested human review and left that task open. No actual approver appointments or external messages are implied.

Open the case's Controlled documents link. Templates and drafts have separate version histories. Internal source fields are separate from the outward preview; client templates cannot expose internal_notes and must contain executive_summary. Required sections/citations hold review requests, not draft storage. Each client publication needs PMO Lead review bound to the exact projection hash. Internal audiences follow an explicit template review rule; internal_review_required=false permits a template-selected internal document without an invented PMO Lead gate.

New typed reference schemas (all examples are synthetic engineering fixtures, not real business policy):

- schema:psl/document-recipient/v1: {"audience":"client","user_id":123}. The user needs a current document.receive:client grant on that case; ordinary case access is not required for the recipient-only inbox.
- schema:psl/document-storage/v1: {"template_ids":[1],"repository":"internal-versioned","retention_days":30}. D11.template_storage_retention_rules uses its artifact-ref/hash/version object. Template IDs must identify immutable versions on this case. Retention is recorded intent; purge/archive automation is not implemented.
- schema:psl/decision-actions/v1: {"rules":[{"role":"PMO Lead","actions":["return","reject"]},{"role":"PM","actions":["withdraw"]}]}. This drives document decisions only; apply it explicitly when other domains implement those actions. No executable policy text is supported.
- schema:psl/decision-delegation/v1: {"role":"PMO Lead","principal_id":123,"delegate_id":456,"valid_from":"2026-10-20T09:00:00+01:00","valid_until":"2026-10-20T17:00:00+01:00"}. Both people must be active, distinct, and the original principal must currently hold the role. Delegation is an explicit review option, not impersonation. Its component value is a list of registered refs, each resolving to immutable version 1.

Configuration UI remains case policy workbench → reference registration → component draft → validate → activate. The four new validators reuse the original envelope implementation ID/version and require their exact schema/content/hash/source evidence. Missing return/reject/delegation policy leaves direct source-prescribed approval and drafting usable. Missing D11 only holds publication reservation. Every dispatched new effect rechecks pinned policy versions, live recipients, current source/review authority and version. Policy changes require a new reviewed document version instead of silently modifying a reserved payload.

`work_publications` leases a bounded batch; repeated runs reconcile unknown outcomes before any new dispatch. Held tasks have audited retry/cancel staff controls. Confirmed receipts cannot be cancelled or rewritten. Recipient /documents/inbox/ exposes only the projected content and checks current audience grants again when read.

The PMO panel captures candidate-bound references for P29–P33 owners. A record is reported/unverified until checked against a source adapter. Synthetic cases can use the deterministic source adapter; operational verification reports the missing authoritative target adapter while capture continues. A07 checks and packets explicitly do not authorize release. Missing critical-defect counts stay unknown. Gate changes invalidate queued packets, requiring new drafting/review. Actual QA severity/oracle/source contracts, release services, other phases and real target integration remain unfinished.


## Formal minutes, action commitments and reporting continuation

After `seed_documents_demo`, run these in the explicitly synthetic local project:

```powershell
.venv/Scripts/python manage.py seed_meetings_demo
.venv/Scripts/python manage.py work_reports --limit 1
.venv/Scripts/python manage.py work_publications --limit 50
```

The seed refuses to overwrite existing meeting history. It installs only case-isolated synthetic policy, templates and grants; creates one meeting and three commitments including one unknown owner/deadline; and prepares reviewed minutes/manual reporting plus an armed recurring report schedule. The reporting worker creates a draft and human review task. It never publishes. The publication worker delivers reviewed reserved versions to the actual local recipient inbox; no external transport is configured.

Use the case's Meetings/actions/reports link (`/cases/<case UUID>/meetings/`). Capture meeting_notes/change_request evidence on the main case first. Meeting participants and action owners require active case grants. Capture explicit timestamp offsets, e.g. 2026-10-20T09:00:00+01:00; naive local times are rejected. Owner and deadline can remain unknown. Only the current authorized owner records work completion; managers explicitly assign, reset, reopen or cancel with evidence/reason. Link existing commitments to later meetings without rewriting their origin. Meeting change references do not amend signed scope.

Derive minutes or choose a manual reporting period and audience. Manual drafts need no calendar policy. Follow the document link to inspect the exact projected version, request review, record a granted human decision and reserve publication. Changed meeting/action/report sources hold older queued documents; revise and review again. Published receipts preserve the historical snapshot. The reporting adapter explicitly covers local recorded PMO data only, not a full Finance or external-system report.

Three additional reviewed typed reference schemas are implemented (11/57 component validators total; 46 remain engineering work). These examples illustrate shape, not actual business values:

- `schema:psl/working-calendar/v1`: `{"weekdays":[0,1,2,3,4],"holidays":[],"due_time":"17:00"}`. ISO holiday dates and explicit working weekdays/time are required.
- `schema:psl/action-clock/v1`: `{"action_anchor":"assignment_at","pause_behavior":"extend_elapsed"}`. Anchors are meeting_at/assignment_at; pause modes are not_permitted/no_extension/extend_elapsed. At least one independent property is required. No default pause policy is inferred.
- `schema:psl/deadline-parameters/v1`: `{"action":{"unit":"working_days","amount":2,"anchor_day":"exclude"}}`. Working-day calculations require explicit anchor_day (exclude/include_if_working). Elapsed_hours is also supported. Action calculations consume the original workflow.clock.evaluate dependencies and retain policy lineage.
- The same deadline-parameters schema independently supports `{"reporting":{"internal_tuesday":{"time":"09:00","holiday_treatment":"calendar","coverage":"preceding_7_days","coverage_anchor":"scheduled_time"}}}`. Tuesday is source-prescribed. weekly_client requires weekday (0 Monday to 6 Sunday); monthly_executive requires day and month_end_rule (last_day/skip_month). Profiles require time, holiday_treatment (calendar/next_working_day), coverage (preceding_7_days/previous_calendar_month) and coverage_anchor (scheduled_time/effective_due). next_working_day additionally consumes the working calendar. DST ambiguity/nonexistent local times hold calculation.

The meeting workbench can save independent D04 drafts from explicit owner evidence and typed values. Validate/activate in the policy workbench; saving never activates. Operational values remain unconfigured. Existing commitments are not silently restated when policy changes. A paused action with revoked/changed policy requires evidenced explicit reset if resume cannot use its pinned rule.

Save schedule drafts before clocks are available, then arm with explicit after timestamp once its required components are active. Policy/grant changes hold dependent generation; pause/re-arm is audited. PostgreSQL case locks, occurrence uniqueness, cursor updates and persisted review waits prevent duplicates across concurrent/restarted workers. The bounded command is an implemented reporting-timer subset; supervised deployment and a general SLA/escalation engine remain unfinished. A02/A04 exact-quote proposals leave owner/deadline for humans; A04/A08 investigation reports missing information/timing without automatic escalation. Provider acceptance and real meeting/report target adapters remain pending.

Verification: RUN-11 full PostgreSQL suite 99 passed; RUN-12 staff source/UI test passed; RUN-13 scheduler hardening/process tests passed. Raw logs and browser preview are under docs/test-evidence. See BUILD-TESTS.md for exact commands, earlier corrected failure and evidence boundaries.


## Commercial revisions, controlled changes and authoritative issues

```powershell
.venv/Scripts/python manage.py seed_commercial_demo
.venv/Scripts/python manage.py work_publications --limit 20
.venv/Scripts/python manage.py seed_issues_demo
```

These commands create separate synthetic-demo cases for the existing demo user and refuse overwrite. They install no operational policy. The commercial seed ends at reviewed/reserved outward SOW; use its exact delivered receipt and matching synthetic signature in `/cases/<id>/commercial/`, then adopt. The existing local fixture has already advanced through notice/go-live/closure using real services; do not replay it. The issue seed intentionally leaves an owned Critical issue In Progress with a root-cause gap. Credentials remain in ignored .runtime/demo-access.txt.

Commercial workflow: capture requirements, Engineering and Security estimates, plan/cost/SOW evidence and requirements/feedback/CR context; propose; record source-prescribed human costing order and separate PMO Lead decision; derive SOW; review/publish in the controlled-document workbench. Client responses reference exact actual receipt and signature/feedback evidence. PM attestation is explicit, not a provider authenticity check. Signed adoption preserves before/after and creates the real local Finance intake atomically. Its agreed billing schedule remains null; no invoice created. Once versioned commercial work starts, legacy baseline commands cannot bypass it. Manual unbound client SOW publication is held.

Optional reuse: register `schema:psl/commercial-revision/v1`, e.g. `{"unchanged_subject_reuse_roles":["PM","Head of PMO","CEO"],"changed_cost_requires_full_chain":true}` from actual owner evidence, draft D05.revision_invalidation_rules with the exact artifact version/hash/schema envelope, validate/activate. Select reuse explicitly on the proposal. Changed cost never reuses its chain; unchanged subjects reuse only listed current valid decisions. Missing reuse policy affects only this optional operation. Existing D05 return/reject/withdraw/delegation rules remain independent. Twelve component semantic validators now exist; 45 remain engineering work.

Change workflow (`/cases/<id>/changes/`): log exact category and source, with incident reference for Emergency. All four source contributors record cost/timeline/client-facing impact true/false/unknown. Unknowns hold authorization. Normal changes require Product/Engineering; client-facing adds Client; timeline impact adds Engineering Lead/Security Manager; cost impact needs the linked approved commercial proposal. Current role mappings come from actual D05 policy. No real people are appointed by the build. Standard/Emergency execution and GLPI policy remain unfinished; capture/assessment is usable.

After linked signed adoption where applicable, record updated plan, Engineering completion, QA validated testing and documentation. Prepare an explicit-audience notice and client go-live document, then review/publish each through controlled documents. Client/timeline impact needs client notice; otherwise internal notice is supported. Go-live binds exact latest execution IDs; changing implementation holds old QA/go-live until new validation/review. Close with exact delivered go-live receipt and distinct captured PM/Client signature refs plus verification rationale. This records external owner evidence; it never dispatches deployment or creates a new acceptance approval. Closed versions reject mutations/new workflow effects. Use a new version rather than rewrite history. Roster-change reaffirmation/recovery remains to be completed.

Issue workflow (`/cases/<id>/issues/`): authoritative ID is unique within tenant, owner requires current issue.own grant, next action is mandatory. Intake can await PM severity policy; classification uses exact source Critical/High/Medium/Low. Owners acknowledge then record progress/fix; Critical resolution needs root_cause evidence. QA and PM update closure log against the same resolution. There is no closure approval task. For a permitted reopen, owner configuration explicitly lists a role/action in `schema:psl/decision-actions/v1`, e.g. `{"rules":[{"role":"PM","actions":["reopen"]}]}`; this shape is an example, not an actual appointment. Missing configuration holds only reopen. Historical closure remains immutable; reopened work clears active acknowledgement/resolution/fix/RCA and requires new evidence.

External issue references are bounded typed JSON lists of kind risk/incident/change, source_ref and evidence_id. Use risk_reference/incident/change_request evidence from the owning sources; PMO never becomes the Security risk or Engineering incident master. Bounded commercial/issue investigations identify exact source/version/authority or root-cause gaps and cannot approve, escalate, change scope or calculate prices. Reports now include local issue/change histories; refresh older source manifests before new publication. Existing receipts remain historical.

Actual verification: RUN-18 full 134 PostgreSQL tests, RUN-19 11 final guard/UI/issue tests and RUN-20 closed-change test passed. Real local adapters/two-connection concurrency were exercised. Real signature/source/transport/model providers, operational policy/UAT, backup/restore, security/load and deployment remain unvalidated. See BUILD-TESTS.md and HANDOFF.md for exact scope and next work.


## Issue escalation, human decisions and urgency scans (21 October)

```powershell
.venv/Scripts/python manage.py seed_escalations_demo
.venv/Scripts/python manage.py work_publications --limit 10
.venv/Scripts/python manage.py work_escalations --limit 100
```

The seed extends only the existing synthetic issue case, refuses an existing escalation fixture, and ends with an explicitly synthetic reviewed/reserved client message. It configures only fixture values/roles. The publication command creates a real local audience receipt, not an external client message. The urgency worker records signals only, never decisions, requests or publication effects. It persists a cursor, advances past stale/non-due profiles, wraps and is idempotent for current profile/kind/policy identity. Actual separate-process and concurrent PostgreSQL tests cover this path. --limit accepts 1 to 1000.

Open `/cases/<id>/escalations/` from the issue register. Capture the exact current issue state, unclassified/internal/client-dependent classification, explicit yes/no/unknown delivery impact, optional actual trigger with offset, evidence and rationale. Any issue state or later profile change makes older communication bindings stale; recapture facts, request and decisions. Existing delivered receipts remain history. Manual escalation/de-escalation capture and drafting do not need any clock policy.

Client escalation AND de-escalation need a current PMO Lead or Head of PMO decision. The outward document then follows the ordinary PMO Lead exact-version quality review and audience publication path; source communication authority and document review are distinct. Return/reject and finite delegation use their existing independent D05 components. Returned/rejected immutable requests need new source facts/request. An internal PMO/CTO request has no invented escalation decision gate; template-selected internal review still applies. Publication checks that an actual configured internal recipient currently has the requested PMO/CTO role. Role assignments, audience grants and template/recipient policy must come from actual owners, not the example fixtures.

Optional issue clock shapes extend the existing v1 typed references. D04.clock_anchor_pause_rules uses `schema:psl/action-clock/v1`, e.g. `{"issues":{"anchor":"trigger_at","basis":"elapsed_hours","pause":"no_pause"}}`. Anchor is logged_at or trigger_at; missing required trigger remains unknown. Existing action_anchor/pause_behavior fields continue to work independently. These issue fields express the only implemented issue algorithm; another business clock/pause interpretation requires a reviewed engineering extension. Reopened work can use an explicit trigger rather than assume the original log clock restarted.

D04.deadline_parameters uses `schema:psl/deadline-parameters/v1`, e.g. `{"issues":{"acknowledgement_hours":2,"internal_24h_routes":{"Critical":"CTO","High":"PMO","Medium":"PMO","Low":"PMO"}}}`. These numbers/routes are shape examples, never installed operational policy. Acknowledgement duration and routing may be configured independently. Positive acknowledgement hours produce pending/on-time/late/overdue status from actual timestamps. All-severity routing accepts only PMO/CTO. No Critical-to-P1 mapping is implied. Source-prescribed 24/48-hour thresholds cannot be edited through these parameters.

Save independent drafts in the escalation workbench, then validate/activate in policy configuration. Saving never activates. Missing/revoked/expired timing policy leaves manual source capture, decisions and drafting available. Elapsed UTC-instant comparisons do not require IANA timezone or working calendar. Immediate timeline impact stays known even when clocks are unavailable; elapsed/destination/SLA unknowns remain null. Signals pin the applicable component versions; changed policy creates a new lineage record instead of editing old signals. Injected scan observation clocks are allowed only in labelled synthetic tests, never operational scans.

Review actual delivery history separately from drafts, decisions and urgency. Head/PMO Lead decision permissions are rechecked and their grant rows join publication delivery locks. Issue/profile/authority/recipient changes hold queued messages; use existing publication retry/cancel controls and fresh reviewed source versions, not payload edits. The bounded A03/A04/A08 investigation cites exact profile/state/evidence and clock/routing gaps without decisions or sending. Local PMO reports include escalation history IDs/actual receipt counts; refresh older report manifests before new delivery.

Real source/transport/model acceptance, operational owner policy and broader workflow/timer algorithms remain unfinished. D01 Standard/Emergency/GLPI/retrospective controls are the next connected build increment. Full product/family completion remains unclaimed. See BUILD-TESTS.md/HANDOFF.md for actual evidence.


## Standard catalogue continuation

Use /cases/<id>/changes/ to draft two independent Standard components. Catalogue JSON is an array of entries conforming to schema:psl/standard-catalogue-entry/v1; gate map is schema:psl/standard-satisfied-gates/v1. See apps/policy/change_validators.py and fixtures/standard-changes.json for exact fields. Procedure evidence must be a case-owned change_procedure with an exact SHA-256, not an unverified string claiming approval. The draft form stores immutable references; saving never validates or activates. The policy workbench performs explicit validate/activate/revoke. Whole component replacement needs all intended entries/maps.

Capture change_preapproval evidence for mapped Product/Engineering human decisions, and change_procedure_match evidence for PM applicability. Required grants: change.preapprove and the current D05 human role; PM match needs change.manage and PM role. Existing change.read/manage/assess/authorize/execution/document grants remain. agent.changes plus change.read permit bounded investigation, not decisions or deployment. No default operational principal or procedure is installed. Duplicate keys, null/mismatched impacts, wrong case/hash, unmapped/unsupported gates and release waivers fail validation/runtime checks.

seed_standard_demo --case <synthetic-demo-project-uuid> uses only tenant synthetic-demo, refuses overwrite and requires existing human role/grants. It installs explicitly synthetic fixture conditions, records real local service decisions/match/authorization and performs no implementation or publication. The existing commercial synthetic case has change version #2 / authorization #2 / preapprovals #1–2 / match #1. Browser investigation #12 is audited. Operational policy and external authenticity remain unverified.

The current semantic total is 14/57 with partial D01 Standard-only scope; earlier counts in historical checkpoints above are not current. Emergency/GLPI authorizing semantics and retrospective clocks are still engineering work.


## Emergency/GLPI and retrospective controls

Open /cases/<id>/changes/ → Emergency/GLPI workbench (/emergencies/). Capture incident_classification, emergency_decision, change_implementation and post_implementation_review evidence normally. Existing candidate/gate UI owns authoritative source references; source verification remains synthetic-only until an operational source adapter is reviewed. Unknown P1 is not PM Critical. Human prescribed role evidence can be captured without GLPI/clock configuration; only dependent authorization/reconciliation holds. Actual outcome logging remains available without preauthorization and records that exception.

Policy workbench/schema code: apps/policy/emergency_validators.py, change_validators.py and clock_validators.py; synthetic examples fixtures/emergencies.json. D01 relationship explicitly selects mode, incident_lead_role, overlap, exception_roles and explicit incident-P1 basis. Defer additionally needs deferred_checkpoint=before_retrospective_reconciliation. Coexist requires current source-verified three GLPI gates before preauthorization. Defer/replace need each configured human exception decision; defer also needs gates before P62 reconciliation. Same-person v1 support is only Engineering Lead explicitly acting in both capacities; other operational dual-role algorithms remain unimplemented. No financial or deployment grant follows.

D01 gate-map v2 accepts independent emergency and/or existing standard namespaces; v1 Standard artifacts still work. To replace a whole component preserve all needed namespaces. D04 clock_anchor_pause_rules.emergency requires implemented_at/no_pause/explicit anchor_day. D04.deadline_parameters.emergency.retrospective_working_days is 1 or 2; log threshold is fixed 24h. Timezone/working calendar are separate active components. Saving policy drafts never activates them. Missing clock does not block manual review/decisions. Known clock-policy changes require human decision reaffirmation and preserve earlier timing/lateness evidence.

Current role/action grants: emergency.read/manage/decide/authorize/record_outcome/review/retrospective_decide, agent.emergencies plus normal document/candidate/policy grants. Security Lead is now a supported D05 role. A domain action grant plus current configured role is required for human decisions; admin flags confer no authority. P62 reconciliation is a deterministic evidence check, not a new approval or full change closure. Post-outcome preauthorization and future claimed implementation are rejected. Missing/stale historical authorization is retained and held for explicit recovery; do not backdate.

Run work_emergency_obligations --limit 100 from a separate process. The worker uses the current profile actor's emergency.manage grant, advances a persisted cursor past unavailable records and stores immutable missing-authorization/late-log/retrospective-deadline signals with duplicate protection. It never decides, publishes, sends or deploys. UI shows pending evidence; operational worker supervision/diagnostics remain future work. Normal publication worker/reconciliation handles reviewed reports. Source changes require a fresh exact reviewed report; cancel only a confirmed-undispatched obsolete reservation.

seed_emergency_demo creates a separate tenant synthetic-demo case and refuses overwrite, using only isolated synthetic roles/conditions/provider fixtures. Current case 81a8408f-0335-4355-94e6-b5966dc5668a has P62 record #1 and actual local recipient receipt #8. Initial report job #8 held after code added more source-grant bindings; fresh browser draft/review/reservation #11 produced job #9 and receipt #8. Old job #8 cancelled with audit. No actual client/GLPI/incident/deployment/financial effect. Web was restarted after code changes; restart --noreload after Python/cached template edits, then reload browser. Current semantic count 15/57 with partial variant gaps; 42 components have no semantics yet.


## Historical authority and Emergency follow-up

/cases/<id>/authority/ is linked from Emergency and commercial/change workbenches. Required independent grants: authority.read/request/decide/finalize, agent.authority and emergency.followup; current configured roles remain required for decisions and PM follow-up work. Admin flags grant no domain rights. Capture recovery evidence, select exact Emergency outcome or signed adoption, then record every explicitly configured current human role decision and finalize. Decisions, original times and delivery receipts stay immutable. Changes to role/grant/recovery policy suspend old recovery; create a fresh request, do not backdate. A new request suspends previous recovery even before approval. Changed original evidence/D01 or originally missing preauthorization requires its own correction path and cannot use authority-only recovery.

D05.revision_invalidation_rules schema:psl/commercial-revision/v2 keeps unchanged_subject_reuse_roles and changed_cost_requires_full_chain:true; optional historical_authority accepts emergency_outcome and/or signed_adoption objects with roles (nonempty supported role list), scope:authority_only, original_times:preserve and financial_release_controls:independent. No actual roles default. fixtures/authority-recovery.json is synthetic only. Saving in UI registers a draft; validate/activate separately. V1 remains supported. Whole-component replacement must retain intended reuse/recovery namespaces. Revoked/expired/future components hold dependent recovery only.

Create a fresh ordinary follow-up from an actual Emergency outcome. Continue impact/approval/commercial work in changes and commercial workbenches. It creates no execution and never copies historical implementation. Link newer current revisions of the same ordinary request explicitly; old links and decisions remain. Completion requires the exact ordinary closure and signed adoption when cost-impacting; it does not alter P62 or project/release/Finance status. Reports bind recovery/follow-up histories. A changed recovery requires a fresh exact outward review.

seed_authority_demo --case <synthetic-demo-case-uuid> prepares isolated policy/grants/evidence on an existing synthetic-demo case, refuses an existing fixture or active revision policy, and creates no decisions/effects. Current Emergency demo has synthetic policy #29 / evidence #62 and follow-up request evidence #63. Browser recorded recovery request/decision/record #1 and ordinary follow-up #1/version #4. Original P62 #1/receipt #8 retained; no source grant was revoked in the demo. Post-change web process must restart with --noreload. Full actual test acceptance and next engineering work remain in BUILD-TESTS.md/HANDOFF.md.


## Connected delivery, release evidence, hypercare and closure

Open /cases/<id>/delivery/ from the case workbench. Independent grants: delivery.read/manage/source/verify/planning_decide/release_request/release_record/support_receive/finance_confirm/closure_decide and agent.delivery. PM, PMO Lead and Head of PMO actions additionally require current D05 role authority. Source owner labels are not assignments. Support receives its own exact internal publication receipt; Finance explicitly confirms complete milestone notification coverage. Admin flags confer none of these rights.

Capture case evidence using new kinds deployment_checklist, incident_reporting, rollback_plan, technical_document, test_results, project_artifact, support_document, escalation_document and closure_report. Open a candidate dossier on prepared plan/cost/SOW; signature is not required for Planning. Capture/verify registration, baseline, Product/Design UI applicability and conditional design signoffs plus Engineering/QA/Product planning references. Actual verification is currently synthetic-only; operational source capture remains available. PMO Lead decides Planning exit; actual kickoff links an existing formal kickoff meeting after that approval. For GLPI request capture current candidate QA/UAT/Go gates first, then bind all three GLPI sources to the exact request reference. Evidence readiness grants no deployment permission. Record actual Infra/DevOps outcome even if readiness is missing; no later readiness can repair earlier implementation.

Use a project_artifact template exposing checklist in scope, incident reporting in risks and rollback in next_steps for reviewed client go-live. Capture two distinct exact PM/Client signature attestations of the delivered version. D11.hypercare_criteria_ref (schema:psl/hypercare-criteria/v1) independently configures elapsed hours/Engineering or Infrastructure confirmation owners and finite metrics with explicit units/operators/thresholds. Capture actual aware observation times and nullable values; evaluate only when configured. Unknown/failed observations never qualify. No owner period/threshold defaults. D11.template_storage_retention_rules schema:psl/document-storage/v2 retains existing fields and optionally adds closure_inventory required_kinds and archive_mode:immutable_local_manifest; it must include technical_document/test_results/project_artifact. V1 remains valid for document publication, but does not enable archive completeness evaluation. Preserve intended namespaces when superseding whole components.

Archive is an immutable local evidence/hash index with recorded retention intent. Engineering source finalization must bind its exact technical document. Controlled internal handover includes support/escalation documents. Configure actual internal recipients with delivery.support_receive and document.receive:internal; each acknowledges its own receipt or gaps. No separate handover approval; template quality review remains independently configured. Closure needs current qualified hypercare, archive, every intended actual Support receipt without gaps, an actual current retrospective, explicit Finance inventory confirmation over exact delivered notification receipts, and Head of PMO decision on the exact PM closure report. No paid-invoice gate/debt waiver is added. Closure blocks additional mutations in that delivery dossier; it is not physical retention purge or deployment authority. New baseline/candidate, historical correction/reopen and multiple-release variants require future engineering.

work_delivery_obligations --limit 100 resumes a bounded persisted cursor and creates immutable missing-policy or due hypercare signals. It acts under the dossier actor's current delivery.manage grant, skips unavailable dossiers while advancing, and never approves/sends/deploys/closes. Operator ownership reassignment/supervision and general timer engine remain unfinished. Source/policy changes hold queued delivery documents and shared reports; prepare fresh exact reviewed versions, preserving old receipts.

seed_delivery_demo requires existing studio-demo actor, creates a separate synthetic-demo case and refuses overwrite. Its explicit zero waiting period/metric values/principals are only fixtures. Current synthetic case c1510e5a-a3ea-4bff-9717-cc53d31e0cdc has dossier #1, controlled local receipts #9/#10 and browser-completed closure report #14. No real deployment, external message, signature authenticity or financial transaction occurred. Restart --noreload web after Python/cached template edits. Actual test outcomes and remaining work are in BUILD-TESTS.md and HANDOFF.md.


## RFP response studio

Open /cases/<case UUID>/rfp/ in a fresh project workspace with explicit per-record grants: rfp.read/intake/assign/prepare/review/submit/outcome/dispose, rfp.contribute:Engineering/QA/Security/Product and agent.rfp. Normal evidence/commercial/document/policy grants remain independently required. An administrator flag supplies none. Register actual source evidence first, including rfp_intake, rfp_deadline when stated, qa_estimate, product_input, rfp_response, explicit public rfp_commercial_terms, rfp_outcome and loss rfp_lessons. Received/outcome timestamps are actual aware timestamps; only a source-stated deadline has a deadline source/time. Select unknown while awaiting evidence, or explicitly attest not_stated.

Use the RFP policy draft form to save D05.decision_action_matrix schema:psl/decision-actions/v2 with independently optional rfp.assignment_roles/outcome_roles plus optional existing rules for return/reject/withdraw. D11.adapter_configuration_refs takes an array of schema:psl/rfp-submission-route/v1 objects: kind rfp_submission, unique key, method internal_recipient_inbox, opaque destination_ref, exact client recipient_ids and sender_roles. See fixtures/rfp.json for an explicitly synthetic interface example; replace placeholder IDs with actually scoped records. Drafts are immutable references; validate and activate separately in the normal policy screen. No CEO/relationship owner/sender is appointed by default.

The assigned PM prepares a cited mapping [{key,evidence_id,response,disposition}], with disposition addressed/clarification/out_of_scope and exact selected requirement/current intake sources. Engineering/QA/Security/Product contribute inputs. PMO Lead and Engineering Lead review the exact response in either order before costing PM -> Head of PMO -> CEO in the commercial screen. Use a controlled template with document_type rfp_response, public executive_summary/scope/requirements_mapping/commercial_terms. Its client projection must expose all four sections. Existing bound project_artifact demo templates remain readable. Draft controlled submission, then request/obtain separate outward PMO Lead review and reserve publication in the documents screen. Run the existing publication worker. Only the local recipient-inbox method is implemented; a destination reference is not an external email/portal adapter.

Record actual submission from the exact controlled binding after all recipients have matching receipts. Capture actual relationship-owner outcome with current configured authority. Pending/unknown cannot convert. Won records Route A on the same case and leaves ordinary project commercial approval/signature requirements intact; lost requires lessons and records an immutable local archive manifest. Source/policy/authority changes hold new effects; actual historical receipts remain captureable and idempotent. Post-disposition correction/reopen, remote incoming/outgoing/authenticity and archive/export/physical retention remain engineering work.

`python manage.py seed_rfp_demo` requires the existing studio-demo actor and refuses overwrite. It creates separate synthetic won-ready and lost-archived workspaces through real local services/receipts. The command performs no external submission. Browser can convert the won example and run the bounded investigation. Use `python manage.py test tests.test_rfp --keepdb --noinput` against real PostgreSQL; never run two test commands concurrently against test_psl.

Public commercial terms are selected explicitly in response preparation. Their evidence ID/hash is bound in the derived draft source; the client projection contains those authored terms, not internal costing contents or an inferred quotation. The old synthetic seeded versions are historical legacy examples; new drafts/publications require the new explicit terms binding. Adding an outcome-role permission later, with assignment permission unchanged, does not force another submission. Original assignment/outcome policy versions remain in immutable lineage, with current chosen-role permission/grant checks at runtime.


## Finance analysis continuation

Use [Finance analysis runbook](finance-analysis.md) for supplied-source capture, typed mapping/formula/BU rules, current configured human reviews, aggregate publication and bounded investigation. This is a partial local implementation; real owner values/workbook oracles and QuickBooks/HR authenticity are separate. See BUILD-TESTS.md for actual PostgreSQL results and HANDOFF.md for exact resume/test process state.


## Finance budget, performance and historical rework

Use [Finance performance runbook](finance-performance.md) for budget versions/basis, reviewed monthly seals, explicit fiscal/YTD/prior inventories, monthly/annual-weight comparisons, configured human review, signed charts and preserved historical replacement. New seed_finance_performance_demo creates an isolated synthetic example and refuses overwrite. Actual local test outcomes and current process state are in BUILD-TESTS.md/HANDOFF.md; original workbook/native-budget/provider acceptance and actual owner values remain separate.

Finance billing preparation subset and next invoice/cash boundaries: see [finance-billing.md](finance-billing.md). Current final test evidence is RUN-58/59; historical prior checkpoints above remain history.

Finance invoice/cash/receivable connected subset: [finance-settlement.md](finance-settlement.md), RUN-62/63 actual tests. Earlier checkpoint descriptions remain history; current work/next steps are HANDOFF.md.

Finance canonical note and corrected cash successor continuation: [finance-corrections.md](finance-corrections.md). Final RUN66 passed219 PostgreSQL tests761.370s, no failures/skips; earlier runs overlap. Finance0016/0017, current server/demo and exact remaining forecast/BaaS work in HANDOFF.md. No actual operational policy or external financial effect claimed.

Forecast/actual/owned-priority and reviewed aggregate publication path: [finance-forecast.md](finance-forecast.md). RUN67/68 evidence and final sequential regression status in BUILD-TESTS/HANDOFF. Finance0018-0023; synthetic seed adds forecast records to a named synthetic Finance case without changing original cash/debt.

BaaS supplied-source reconciliation and Engineering-mediated corrective requests: [baas-reconciliation.md](baas-reconciliation.md). New BaaS0002/0003 create eight append-only records plus durable jobs/SQL guards. Actual tests and current demo/server/next work are in BUILD-TESTS.md and HANDOFF.md. D09 contributes two partial semantic interfaces; current total44/57 partial,13 without semantics. Missing operational policy holds only dependent actions; no local financial or business-queue execution.

Partner SLA/renewal intent, onboarding ageing/follow-up and activity-to-Finance subset: [partner-operations.md](partner-operations.md). BaaS0004/0005 add immutable source/decision/history/report/follow-up/receipt/meter claims and durable Finance jobs with PostgreSQL guards. Current partial semantic coverage46/57,11 without semantics; all122 process identities retained. D04/D10 profiles can preserve existing namespaces. Actual tests/current server/demo and next BUILD-D13 work are in BUILD-TESTS.md/HANDOFF.md; no operational rule values, external notice/renewal or invoice execution inferred.


D13 local payment assessment/human exceptions/independent controls: [payment-controls.md](payment-controls.md). Finance0024/0025 add4 immutable guarded records. Actual tests and source/database integrity are in BUILD-TESTS.md/HANDOFF.md.52/57 original components have partial semantics;5 remain without semantics plus supplemental costing. Native dispatch and actual owner policies remain separate; local reservation receipts never deploy or waive debt.


AF13 evidence/owner validation/selected acceptance: [evidence-validation.md](evidence-validation.md). Documents0005/0006 add6 guarded append-only records and version/operation uniqueness. Supplemental AF13 schemas compose with the frozen57-component catalogue at runtime (59 total,55 partial semantics,4 none). Original57 includes P14; D04 IANA already had a validator. Actual tests, case IDs and current server are in BUILD-TESTS.md/HANDOFF.md. Native replay/source authenticity and actual appointments/acceptance remain separate from local supplied-result comparison. Next connected packet work is BUILD-F33.
