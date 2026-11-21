# Start work and specialist handoffs

## Scope and routing contract

O01 owns the lifecycle of a work item. A department assistant answers questions using the signed-in reader's permitted sources. A01–A08 perform bounded tasks for O01. PostgreSQL retains task identity, attempts, source versions, citations, human decisions and native receipts. Private object storage holds document bytes. A model response can propose a reading or action. The native service decides whether that action is available and verifies its result.

The definition for **each of the 122 processes** is the join by exact process ID of [process intake and outputs](../../contracts/process-map.json), [specialist task assignments](../../reference/08-agent-architecture/process-agent-assignments.json) and [current execution bindings](../../reference/12-payment-exception-policy/process-execution-bindings.json). Each assignment specifies the primary specialist, conditional supporting tasks, permitted judgement, tools, deterministic checks, human decisions, prohibited actions, entry criteria, fallback and acceptance examples. Current payment and release amendments take precedence over historical descriptions. The [per-process routing book](specialist-process-routes.md) renders the resulting tasks and waits. The 14 BaaS IDs retain their contracts and stay outside release activation.

## Execution design

The current assignments call for two roles on 38 processes, three on 83 and four on P28. O01 can combine successive groups across a work item. A source review creates one durable task per permitted specialist and source. The current route book is the source for membership. Changed membership requires a reviewed contract change.

1. The existing business intake binds the case, sources, current principal and native work definition. It requests background progress. O01 observes current work and selects from its eligible activities. A specialist may receive only a role assigned to the actual process. The assignments catalogue describes capability. Authority comes from the current native record, action grants and policy.
2. O01 dispatches a traceable child with the exact process, specialist, task description, source pins, work identity and command. Repeated attempts retain their identity and native business keys. The child uses the existing domain tool. Approval, missing information, timed follow-up and uncertain external effects each retain their native wait. An approval wakes the same work item.
3. A specialist can interpret permitted source material into a private working document. The coordinator checks source identity, citations and the result contract. An extractively checked quotation, a proposed interpretation, a human decision and a verified native outcome have different meanings. An ordinary model cannot promote a draft to approved or issued.
4. Store report bytes under a case-bound private object key. PostgreSQL retains its digest, source and authorisation references. An authorised reader retrieves the exact file and verifies the digest. Department assistants receive scoped findings or native outcome citations with a link to the exact work. Every read rechecks current scope. Historical receipts retain their timestamp and version.
5. Staff interact with the project, its files and the business decision in My work. Pause, return, correction and recovery remain available on that work. An unavailable provider or private source pauses the dependent analysis. External calls with an unknown result require reconciliation before retry.

At a join, O01 records every member, source digest, cited line and private file receipt. Independent readings can run concurrently. A pending member keeps the dependent handoff waiting. An insufficient result, a failed reading or competing values for the same field on one source needs a written resolution from the configured information reviewer. The next native command records the exact packet it consumed. Finance approval, issue, delivery and cash receipt keep their own authorities and evidence. A department assistant can reuse checked excerpts from an uncontested consumed packet and cite a separately verified native outcome.

For private weekly reporting, the domain reader checks the selected inventory, its signed intake and all client citations before projecting the four human-supplied client sections. Other native private envelopes keep their own readers. The public source reader accepts only explicitly bound, bounded text. Release scope and live provider acceptance for each route are separate entries in the build records.

### Native department handoffs

The following 63 processes have individual domain adapters. Saving a matching source creates a durable event keyed by process, native model and source record. Once a project has selected execution and disclosure rules, the background worker enrolls that original event with O01. A second save cannot start duplicate work. Historical or bulk-loaded records can be reconciled by exact identity with `manage.py work_native_stations --process PROCESS --subject ID --actor USER`. The command checks current native visibility and project recovery authority.

The source adapter returns only the approved projection, original evidence version and any matching downstream receipt. O01 fans out to the process's assigned specialists. Findings return to the project in a reviewed handoff. Internal consuming commands recheck the current source and packet inside their own transaction. PostgreSQL records which actor used the packet and requires an observed downstream record before completion. Independent project-view acknowledgements and incoming customer replies can be recorded as they arrive. PMO consults the customer reply's reviewed findings during signed-baseline adoption. Protected HR fields stay behind the original HR reader.

The case page links to Department handoffs. A current reader can inspect the source, findings and receipt there. Department assistants reuse current, permission-checked excerpts and receipt metadata. Operational reviewers, models and disclosure scope require recorded project decisions. For synthetic deployment checks, run `python scripts/railway-native-stations.py` on the isolated checks service. The three suites use separate databases and require receipts for every process listed below. [Per-process routes](specialist-process-routes.md)

| Source processes | Domain event and evidence boundary |
| --- | --- |
| P01, P02, P08, P09, P19, P20 | Commercial submission, costing revision and signature events. Bind the exact document version, department decision sequence, client response and signed handoff. |
| P04, P05, P13, P15 | Reporting, shared visibility and operational validation. Bind the reporting period, approved procedure or owner-validated evidence packet. Preserve audience and record access. |
| P10, P11, P52, P53 | Controlled documents. Bind the template revision, external audience, review verdict and exact published artifact. |
| P17, P18, P21, P22, P23, P24, P25, P27 | Planning and delivery kickoff. Bind each stakeholder input, estimate, alignment record or gate decision to its planning baseline. |
| P12, P29, P30, P31, P38, P63 | Delivery and closure. Bind the actual milestone, quality exit, user acceptance, go-live decision or retrospective. Preserve the release and Finance receipt boundaries. |
| P45 | Bid intake. Associate the received request, its original channel receipt and the recorded project manager assignment. |
| P51, P54, P55, P56, P58 | Issue and change management. Recheck the Security or Engineering reference, issue revision, classification and applicable approvals. |
| F02, F04, F05, F06, F08, F10, F11 | Management accounts. Bind the reviewed import, accounting period and formula lineage to the exact statement or budget version. |
| F14, F15, F19, F20, F24, F25, F26, F27 | Business-unit reporting. Bind reviewed allocations, period coverage and adjustment/rework history. Keep restricted payroll behind its own reader. |
| F28, F31, F32, F34, F45 | Usage, billing and receivables. Bind the original handoff, contract/service period, invoice, receipt and allocation as separate records. |
| F33, F35 | Revenue recognition and HR handoff. Require the approved progress packet or HR-authorised disclosure and check the named Finance recipient. |
| F36, F37, F38, F40, F41, F42, F43 | Forecasting. Bind sources and horizon, human prioritisation, actual matches, rollover and internal/group audience separately. |

The engineering precedents are manager-owned specialist calls with structured outputs and persisted human waits with replay-safe side effects. PSL retains its current Django coordinator, PostgreSQL jobs and domain authority. [Agents SDK manager pattern](https://openai.github.io/openai-agents-python/agents/#manager-agents-as-tools) · [LangGraph persisted interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
