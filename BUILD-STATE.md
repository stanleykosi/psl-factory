# PSL Operations Factory build state

## Staff names and employment · 21 November 2026

PSL chose the live HR system as Zainab’s source for checking staff names and employment dates. Both checks are on hold until it is connected.

## Finance document review · 21 November 2026

Finance can upload a PDF, spreadsheet, Word or text file from its project records. Chidi proposes the figures, units and source locations. A Finance member or Finance lead reviews the original and approves or returns the file. Approved figures become available to Chidi and can be submitted to management accounts. [Checks](docs/design/finance-document-checks-2026-11-21.md)

## Payroll totals in Zainab · 21 November 2026

A named recipient who acknowledges a current report can ask Zainab for both the overall staff cost and every published business-unit amount. The answer links to that exact report. A person on the same Finance team who did not receive it cannot open the link. [Browser checks](docs/design/payroll-chat-checks-2026-11-21.md)

## Original bids and client conversations · 21 November 2026

The bid owner can record a client conversation and choose who can use the original bid. Other PMO teams can open a public bid and ask Tola about it from their own workspace. Switching back to Private closes the shared link and hides earlier replies that relied on it. [Browser checks](docs/design/bid-sharing-checks-2026-11-21.md)

## Department assistants · 21 November 2026

Tola, Chidi and Zainab use the signed-in person's role. PMO and Finance heads can open one conversation for their whole department or choose a project. Project staff see just their assigned projects. Staff using the new roles can read departmental records on incoming projects without an individual project approval. The database enforces one PMO head per organisation. HR's live connection is pending. [Browser checks and test scope](docs/design/department-role-checks-2026-11-21.md)

## My work and role headings · 21 November 2026

The existing My work page is the signed-in workspace for every staff role. It shows the person's role as its heading. Team invitation and staff administration links sit beside the heading, and scoped assignments and decisions use the workspace's existing work views. The former Role dashboard address redirects to My work. Existing workspace access, decision authority and team invitation rules govern the actions shown.

## Frontend handoff repairs · 21 November 2026

The separate frontend now opens the signed-in work desk, pages through authorised records and displays Finance decisions with their evidence. The two clients share the same desk. Source selection, specialist reviews and complex intakes open their existing factory forms. The screen map correctly assigns the weekly update to SCR-25 and Planning to SCR-42. The new document review and replacement template operations call the existing document services.

The original handoff added four project settings under **Business rule settings → Project data permissions and Finance units**. PSL’s subsequent decisions appear above. The older, direct trial-balance import still supports source-specific conversion rules. [Checks and screenshots](docs/design/frontend-handoff-review-2026-11-21.md)

## Shared factory navigation for role accounts · 21 November 2026

All signed-in staff use the standard factory shell and see the complete Start work catalogue. Workspace and record checks determine which projects and actions they can actually use. Staff keep their own assignments, and leads see the native work started by current people in their exact team and workspace. Django and the API use the same scope. Lead access to private file drafts is limited to the actor's own uploads and human review of the pinned output. Native decision and external effect permissions still govern approvals and release.

This change uses the existing test workspace and accounts. No policy values or nominations were added. The current Railway check is recorded in the test ledger and handoff.

Current release108 PMO/Finance IDs; preserve122 IDs/13 families and existing14 BaaS IDs/behaviour. HOD people/policies deferred. No main merge.

## Current implementation and verification

The Railway test site has a clean **PSL Role Testing** workspace with three active accounts. Admin lands on staff and team management. PMO Lead and Finance Lead land on their own team dashboards. All three public sign-ins and five focused PostgreSQL checks passed. The former test database and 42 private test uploads were removed after verifying the new site. The new workspace starts without work or business policy appointments. [Current handoff](HANDOFF.md#clean-railway-role-testing--21-november-2026).

The Railway staff application requires a workspace role for new accounts. Current PMO, Finance, HR and Admin team leads invite members of their own team from the role dashboard. Delegated Admins set up teams and appoint their leads and standalone CEO and CTO roles. Team lead authority is checked again at acceptance. Older access-only links need a role invitation before account setup. Scoped-only staff appear in the authorised roster and person details. The expanded run and fixture retest verified 60 distinct PostgreSQL checks. The web and worker are active, and Codex checked the live account setup, Staff and invitation contract. Existing grants, admissions and HOD decisions remain subject to their own reviewed paths.

Existing staff can move to a team or standalone scope through an Admin review. The move shows the permissions removed and the open actions carried forward. It preserves the person’s account, action ownership, history and separately authorised workspaces. Active work handovers and claimed decisions must be resolved first. Role dashboards now expose assigned native decisions and link authorised specialist desks. The Railway PostgreSQL batch and targeted rerun verified 21 distinct checks, including separate publication and sign-off, with both preservation probes passing. The preview web applied the three identity migrations and the matching worker is active. Codex checked health, Staff, the role dashboard, the Payment exceptions link and the live API. See [handoff](HANDOFF.md) and the [frontend API](docs/design/frontend-api.md#primary-roles).

Setup lists six built-in primary roles, including HR. An Admin with current staff delegation can review and confirm a workspace role assignment or add a workspace role. The HR project tab and its API bring together the HR-to-Finance handoff, staff matching corrections, staff-cost questions and Zainab where available. The HR role grants handoff access for the assigned workspace. Private records and decisions require the existing policies and permissions. [Role setup and API](docs/design/frontend-api.md#primary-roles).

The Railway preview is serving this increment. All 69 isolated PostgreSQL tests and both preservation probes passed. Codex verified the six-role catalogue, the HR tab, the equivalent API links and the handoff, staff-cost questions and Zainab pages. Owner decisions still cover who authorises disclosure, who answers corrections and questions, and which source fields and recipients each purpose permits.

The initial [role-based team model](guide/11-FULL-PRODUCT.md#role-based-work-and-supervision) checkpoint introduced scoped invitations, six role dashboards and exact ownership checks for native action work. Leads see their team’s actions and decision status. Its initial role desk supported controlled documents, Finance schedules and HR corrections. All 89 focused PostgreSQL tests passed. Codex verified the live dashboard and API with the existing trial session.

The versioned Django contract covers 61 operations across 52 paths, with typed intake for the 25 current factory work definitions and an audited cutover map for all 262 design states. API and Django share native workflow services. The map identifies the remaining domain details and commands served by Django forms. [Frontend API](docs/design/frontend-api.md).

**262 of 262 scoped design walkthroughs complete.** Codex in-app browser acceptance used synthetic data and scoped accounts on Railway. The final bid pack Return on work 239 preserved its original rationale alongside the exact draft and document version. The returned pack had no submission or receipt. Candidate 292 passed all five focused commercial PostgreSQL tests and both preservation probes. Matching web and worker are healthy, with no new migrations. [State ledger](docs/design/screen-state-acceptance.md).

The 233 Railway preview wakes the existing background request after human minutes confirmation. All 48 grouped PostgreSQL tests and both preservation probes passed. Web and worker are healthy. Work 177 verified the exact private client test pack, independently checked delivery and removed the due reminder after the fictional client replied. Work 176 reached verified internal minutes version 113 with the action's owner and deadline still unknown. Work 178 exercised valid, missing and unsupported notes at phone width. Identity `0011`, Finance `0082` and Project `0074` remain applied and immutable.

Implementation and acceptance now run in [workflow batches](docs/design/batch-acceptance.md). Candidate 201 finished all 487 PostgreSQL tests across 36 modules in 7,478.882 seconds. The final result was four failures, three errors and exit 1. The seven traces cover the bid form, Standard Change fixture authority, invoice test setup and database scope, and the fixed-asset linked-note authority check.

Candidate 202 groups the corrections, release and archive progress, in-page handling of unsaved edits, exact bid costing, Finance progress and same-file unit confirmation. All seven baseline failures passed their focused reruns. Candidate 203 completed 518 tests with 517 passes and one returned forecast disclosure error. Candidate 204 passed its three Finance tests and 30 project tests, including the returned forecast, accounting queue, change closure and escalation authority. One older escalation test still expected the old heading. Candidate 205 corrects that assertion and adds the missing private opening-source readback. Bid costing adjustments, Security estimate dispatch and additional source scales remain engineering. Authority, limits, routes and unit conversion remain owner choices.

The grouped 205 PostgreSQL regression passed all 520 tests. Candidate 206 passed all four Finance tests and found three Project test setup errors. Candidate 207 corrected them together and passed all ten Project tests and both original receipt probes. The 208 PostgreSQL regression verified that preparation finds the original sample after a second native report was created in its workspace.

Railway 236 passed 20 grouped PostgreSQL tests and both original preservation probes. It separates the customer's expected decision date from the internal follow-up and wakes the existing Finance schedule or Business Unit worker after reviewed source changes. Schedule verification now accepts exact supplied input without an optional override. The 237 group adds schedule history privacy, precise reminder times, staff access and explicit minutes submission for review. [Actual test evidence](BUILD-TESTS.md).

The final grouped Trial session verified both invoice reviews, corrected Accounting source, Payroll replacement receipt and staff match Return, corrected project closure, both asset schedules and the bid pack Return rationale. The last asset and staff-match actions ran at desktop width after the in-app phone viewport control timed out. Device widths are recorded in the state ledger.

Candidate 287b passed 25 PostgreSQL checks and applied core 0008 and Finance 0086. Candidate 288 passed 13 for private bank receipt, independent costing examples and exact Emergency decision. Candidate 289 had two isolated fixture errors and hosted only its checked 25-file subset. Candidate 290 corrected both fixtures and passed all 131 PostgreSQL tests and both preservation probes. Railway applied Finance 0087. All five guarded setup commands passed. Actual owner, route and financial values remain deferred.

Candidate 291 completed the Project and Commercial groups with one fixture error each. The broad Finance tail was replaced after half an hour. Candidate 291b hosted the checked sign-in, invitation and bid paths. Candidate 291c passed eight PostgreSQL tests and both preservation probes and is hosted. Both guarded Payroll samples passed. The separately admitted preparer completed the corrections. Trial completed the independent decisions and receipt without another sign-in.

Verified 274 is running on the isolated web preview and applied additive core 0006. Seven PostgreSQL cases and both preservation probes passed for role-aware usage controls, client billing identity and the next leadership and cash specimens. The project directory is being checked separately after 273 returned Unknown on one bounded review count. The Finance corrections and Go-live evidence in the preparer’s queue remain assigned to that account. Live owner choices remain deferred. [Actual test evidence](BUILD-TESTS.md).

In the signed-agreement browser journey, sample case11f14978 retained the exact receipt and private Word proof. It refused future response time and adoption before both signatures were checked. The model cited the original sample file, a human reviewed the draft, and separate human signature checks preceded adoption and the Finance intake receipt. Desktop and phone checks passed. The revised-agreement branch, historical recovery and browser correction cases stay open.

The previously pushed recovery and agent handoffs are recorded in checkpoint 02bee295. See BUILD-TESTS.md for the PostgreSQL and browser results.

All eight file agents have explicit original-uploader recovery with current account/source checks, exact stopped-attempt pin, reason and acknowledgement of an unknown earlier provider result. Fresh claims/matching settlement fence stale workers; late replies stay interrupted, old workers cannot reserve new work, reviewed evidence cannot reset. Bounded readable history and automatic progress preserve unsaved edits. Native human-reviewed output still needs its separate downstream business controls.

18614PGPASS/25.963s;18718PASS/65.263s.18921PASS/26.131s but later fixture failed/final1;190 corrected only the isolated fixture assumption, passed2/1.168s/migration/fixture/final0 on identical app runtime.188’s fixture failure is also retained.1914PASS/23.011s/provenance/final0. External failures are mocked in automated tests; native services/DB/concurrency are real.

Actual browser: initial A02 outage explicitly simulated in additive fixture; human recovery→real DeepSeek Flash attempt2→human-edited evidence2089→current validation source3. A08 draft arrived automatically, typed quality edits survived while A04 ran, evidence2090→quality package2. A04 evidence2091 correctly held without initial intake; after the label correction, actual A01job25/evidence2092→intake21 then A04job24→Planning2094 succeeded. Native Planning showed all five carried questions unresolved with unknown sources/stakeholders. Original source/model/human edits remain. Desktop/phone fit, screenshots inspected, viewport reset/CUA complete. No business authority bypassed.

Client ordinary testing is complete for its synthetic scope: exact target224 and approved/changes/rejected/workaround responses225–228, private proof/real A07 advice/fresh human review, immutable corrections/history and reason-required delivery successor. Work119 waits for independent GLPI approvals. No release, go-live, milestone, invoice or payment inferred. Active SAMPLE1045 unchanged by undecided draftversion2.

Agents0012/0013, pmo0070–0072 and Finance0080/0081 are applied in testDB and preview, immutable. Preserve all prior migrations, especially identity0006–0010/pmo0064–0069. Never reset test_design_archive_20261117 or older synthetic/source clocks.

## Broader product and pilot work

The design inventory has zero open functional walkthroughs. Separate follow-up includes aggregate-only Payroll access through the Assistant, authorised HR source extensions, reviewed reuse of past winning bid answers and further simplification of supporting Planning forms. Live private-file model access and provider delivery need approved source and destination contracts. Track infrastructure readiness and wider role and device coverage separately in the [backlog](BUILD-BACKLOG.json).

## Owner decisions and external evidence

Actual owners/admin scopes/login profiles, audiences, calendars, financial oracles/rules, thresholds, requiredness and permitted source/disclosure contracts await HOD answers. Live integration/destination evidence is separate. Missing configuration holds only dependent operations; these choices do not excuse remaining engineering.

[HANDOFF.md](HANDOFF.md) has exact restart steps/records. [BUILD-TESTS.md](BUILD-TESTS.md) keeps actual passes, failures and mock/live distinctions. Earlier state is preserved byte-for-byte in [the before192 archive](docs/build-history/BUILD-STATE-2026-11-19-before-192-agent-forms.md).
