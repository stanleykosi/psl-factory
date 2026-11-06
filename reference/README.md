# PSL Product Studio process definitions

Version 0.6 · 19 October 2026 · Human payment exception policy; approver role unconfigured

## Current v0.6 human payment exception policy

The user confirmed that a below-80% payment exception can be given and its approver must be human, but cannot yet identify the role. Authority is explicitly UNCONFIGURED. Proposed request preparation and tracking can proceed; exception approval or payment-waiver authorization cannot. A deployment exception does not waive debt or replace Engineering/Security and other release controls.

Read the [compact addendum](12-payment-exception-policy/PSL-Payment-Exception-v0.6.pdf), [updated decision workbook](12-payment-exception-policy/PSL-Payment-Exception-v0.6.xlsx), or [current policy and schema guide](12-payment-exception-policy/README.md). Fourteen decision groups remain recorded: D02 resolved and thirteen wholly or partly open, often requiring evidence/configuration rather than answers from the user personally. D13 now records confirmed exception capability and human-only approval, with role and remaining assessment basis still pending. The current source namespace combines the v0.5 register with U07/U08 in folder12. The working draft in folder11 and earlier unresolved wording are superseded, not current instructions. All122 IDs are preserved. No build or live action is authorized.

## Preserved v0.5 planning and billing amendment

The user clarified that detailed planning and costing precede signed SOW, the requested document/evidence tooling is to be provided by PSL, and PMO establishes milestone completion while Finance issues invoices and records receipts. Read [the new reference](10-billing-workflow-amendment/PSL-Billing-Workflow-v0.5.pdf) or [companion workbook](10-billing-workflow-amendment/PSL-Billing-Workflow-v0.5.xlsx). The [current all-process bindings](10-billing-workflow-amendment/process-execution-bindings.json) preserve 122 IDs and explicitly override affected historical dependencies.

Three contract-specific payment stages and irregular partial receipts are modelled separately from milestones and invoices. There is no assumed 50/30/20 split. At least 80% paid before deployment is a recorded expectation; hard-block versus exception policy remains unanswered. D02 is resolved; D11 is narrowed; D12-D14 capture genuine remaining terms and treatment. Fourteen decision groups are retained, one resolved and thirteen open. Twenty-two typed billing operations specialize the existing eight execution mechanisms; 31 new mock cases are specified, not run. [Decision history](10-billing-workflow-amendment/DECISION-HISTORY.md), [source clarification](10-billing-workflow-amendment/USER-CLARIFICATION.txt), schemas and independent review are included. Earlier files remain historical and unchanged, except this navigation and the changelog. No application build, live action or scope/timeline change is authorized.

## Preserved v0.4: concrete execution contracts

Read [the execution-contract reference](09-execution-contracts/PSL-Execution-Contracts-v0.4.pdf) and [the companion workbook](09-execution-contracts/PSL-Execution-Contracts-v0.4.xlsx). Eight reusable mechanisms now specify 62 typed commands, recovery paths and 48 mock cases. All 122 IDs are bound to these mechanisms. The [source-rule register](09-execution-contracts/SOURCE-RULES.md) records 47 evidence-qualified claims; the [11 remaining decision groups](09-execution-contracts/OWNER-DECISIONS.md) distinguish missing evidence from conflicts, rather than asking again for rules already supplied.

[Decision history](09-execution-contracts/DECISION-HISTORY.md) records user direction and supersessions. [Build-reference instructions](09-execution-contracts/BUILD-REFERENCE.md), three JSON schemas and process-execution-bindings.json provide agent-readable interpretation. The [independent review](09-execution-contracts/INDEPENDENT-REVIEW.md) passed its bounded documentary checks. Mock cases are specified, not executed. This does not authorize a build or establish operational effectiveness. Existing v0.3 architecture and budget files, historical scope and all source/departmental definitions are unchanged.

## Preserved v0.3: agents and workflows

Start with [the executive architecture brief](08-agent-architecture/PSL-Executive-Architecture-v0.3.pdf), then [the technical design](08-agent-architecture/PSL-Technical-Architecture-v0.3.pdf). The [122-process assignment workbook](08-agent-architecture/PSL-Agent-Workflow-Assignments-v0.3.xlsx) makes the proposed human, agent and deterministic responsibilities explicit. The [editable budget](08-agent-architecture/PSL-Architecture-Budget-v0.3.xlsx) models hypothetical demand, with missing operating quotes left unpriced rather than zero.

This is an architecture overlay, not a rewrite of historical evidence or deadlines. The user's latest direction puts meaningful agents and workflows into the proposed V1 architecture. Earlier dated source documents and v0.2 definitions retain their original AI-exclusion/scope wording as historical context, not as the current architecture instruction. No scope or timeline replanning is included. No application has been built or agent workflow executed.

Agent-readable entry points: [process assignments](08-agent-architecture/process-agent-assignments.json), [capability contracts](08-agent-architecture/capability-contracts.json), [task schema](08-agent-architecture/task-envelope.schema.json), [architecture evaluations](08-agent-architecture/architecture-evaluation-catalogue.json), and [dated pricing inputs](08-agent-architecture/research/pricing-data.json). Every proposed executable action still needs a valid configured grant and deterministic validation; an assignment is not permission.

The overlay covers all 122 original IDs with eight reusable specialist capabilities and a bounded AI manager. Its 488 process examples include selected earlier examples plus new agent examples, not 488 entirely new tests; the original 266 per-ID and 19 cross-process scenarios remain unchanged. Architecture evaluations and examples are specified, not run.

## Start here

This package explains the original 122 registered activities before any software is built. It is intended to work in two ways: a person can read the summaries and examples; an agent can follow stable IDs, structured JSON and explicit source/decision labels.

1. Read [the definition guide](00-control/PSL-Definition-Guide.pdf) for the rules, glossary and cross-department connections.
2. Open [the master coverage workbook](02-coverage/PSL-Master-Coverage.xlsx) to find any original ID, its definition, source-verification limit, inherited scope, questions and mock scenarios.
3. Read the relevant department: [BaaS](03-definitions/BaaS.md), [Finance](03-definitions/Finance.md), or [PMO](03-definitions/PMO.md). PDF and JSON versions sit beside each Markdown file.
4. Use [the shared handoff definitions](04-shared-contracts/RECORDS-AND-HANDOFFS.md) rather than treating each entry as a separate system.
5. Resolve [owner decisions](05-decisions/WORKSHOP-GUIDE.md) before relying on uncertain business rules. The [mock-test guide](06-mock-tests/TEST-SPECIFICATION-GUIDE.md) explains how to validate the later implementation.

## Checkpoint at a glance

- 122 definitions: 14 BaaS, 45 Finance and 63 PMO.
- 266 per-ID mock scenarios plus 19 cross-process safeguards, all specified and not run.
- Source reconciliation and independent documentation checks do not constitute owner validation.

## Important limits

- The immutable baseline is the 15 October register: 14 BaaS, 45 Finance and 63 PMO entries. These are workflows, controls, outputs, references, proposals and discovery tasks, not 122 standalone automations.
- Source facts, inherited review evidence, proposed design and owner decisions are separate. A written SOP is not proof of actual operational practice.
- Recovered BaaS/Finance document extracts, the redacted Finance machine transcript and sampled-video evidence have now been reconciled. See [exact coverage and remaining limits](00-control/SOURCE-RECONCILIATION-v0.2.md). The visual review was sampled, not continuous; private Finance workbooks and operating procedures remain missing. The original PMO recording was not reviewed. No claim of complete operational or owner validation is made.
- Definitions and mock scenarios are documentation, not executed tests. No application, production integration, accounting write, external message or deployment is authorised or completed by this package.
- The dated V1 scope remains a historical planning baseline. The user's latest instruction is to define the work first. Potential AI assistance is proposed and not automatically added to that baseline.
- Business owners still need to validate calculations, roles, exceptions, handoff contracts and expected outcomes. No zero-cost or zero-maintenance claim is made.

## File map

- **00-control:** definition standard, glossary, source inventory, guide and release status.
- **01-sources:** six unchanged cloud originals plus the recovered redacted evidence addendum and its extracts. The four recovered raw originals remain local only. Source inventory includes stable Library IDs where applicable, byte counts and SHA-256 hashes.
- **02-coverage:** exact register JSON and master coverage workbook. Recovered extracts preserve paragraph identifiers and redaction limits; they are not new policies.
- **03-definitions:** detailed per-department Markdown, PDF and JSON, with original IDs preserved.
- **04-shared-contracts:** common records, boundaries and handoffs.
- **05-decisions:** inherited Q01–Q16 and process-specific questions; suggested owners are not confirmed appointments.
- **06-mock-tests:** per-ID test catalogue and cross-process safety cases, all unexecuted.
- **07-release:** versioned recovery archive and release evidence.

## Agent use

Read DEFINITION-STANDARD.md before consuming the JSON. Match definitions to register.json by ID; never infer that a paragraph labelled “proposed” is an approved rule. Preserve original register wording. Scope fields are historical context. Missing source evidence or owner decisions must remain visible. Do not generate application code or operate production systems from this package without a separate user instruction.

## Recovering and comparing copies

Extract the versioned release ZIP into a new folder. Compare each relative file path, byte count and SHA-256 against the manifest. Preserve previous releases before edits. The local and cloud copies should contain the same release, not independently edited versions. Cloud persistence is recorded when upload succeeds; a local copy is verified only after its bytes are checked. The local reviewer verified and unpacked the v0.1 cloud archive against its SHA-256. The v0.2 local mirror remains pending. Four recovered raw DOCX/MP4 originals are preserved locally, not uploaded here; redacted derived evidence is distinct from original copies. Therefore the cloud and local source collections are not claimed to be identical.

## Updating a definition

Record the new source or owner decision, affected IDs, changed interpretation and affected tests. Keep the prior version and its evidence. Update Markdown, JSON, PDF and workbook together, rerun coverage checks, then create a new manifest/archive. A source update must never silently rewrite what the original register said.
