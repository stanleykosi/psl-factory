# PSL process definition standard

Version 0.2 · 19 October 2026 · Documentation only

Source-context status: recovered BaaS/Finance paragraph extracts, redacted machine transcript and sampled Finance visual evidence have been reconciled for v0.2. This is not continuous video inspection, native-workbook validation or owner approval. See SOURCE-RECONCILIATION-v0.2.md for exact review coverage and missing evidence.

## What this package is for

Explain what each registered activity does, how it connects to other work, and what must be decided before anyone turns it into software. A person should be able to follow the narrative; an agent should be able to retrieve the same rules by stable ID. This package does not authorize a build, external communication, integration, financial posting or deployment.

## Four labels that prevent misunderstandings

- **Source fact:** the cited source says this. A prescribed SOP rule is not proof that it is followed in practice.
- **Inherited evidence:** an earlier review describes this, but the underlying original has not yet been inspected in this pass.
- **Proposed design:** a suggested future way of implementing the work. It is not an approved business rule.
- **Owner decision:** something a responsible business owner must clarify or approve. No guessed answer is executable policy.

Every definition begins with a plain-language explanation, followed by the same stable sections: identity and evidence; purpose and boundary; trigger; inputs; outputs; steps and states; approvals; permissions; exceptions/revisions/recovery; shared records and handoffs; deterministic/human/possible-AI responsibilities; acceptance examples; decisions and scope.

## Exact identity and coverage

The 15 October register is the baseline: B01–B14, F01–F45 and P01–P63, 122 entries. Preserve all six original fields exactly. Entries are a mixture of workflows, controls, outputs, proposals, references and discovery tasks, not 122 standalone automations. Definitions are separate from the source register. Shared workflow families may serve several entries, but every entry must retain its own purpose, evidence, disposition and test/validation route.

## Structured representation

Each departmental JSON file is an array of objects with these stable keys:

id, title, classification, source_owner, family, summary, evidence, facts, proposed_design, decisions, trigger, inputs, outputs, steps, states, approvals, permissions, exceptions, handoffs, automation, tests, scope, readiness.

The automation object separates deterministic, human and ai_proposed lists. Each test has id, scenario, expected and basis. IDs remain stable across revisions. Evidence contains the original filename and a verified page/section, timestamp, sheet/range or paragraph locator where available. An inherited locator is explicitly labelled inherited, never newly verified.

## Shared records, not duplicate business systems

One business record has one authoritative owner. A hub or report can reference it or present a permissioned view; it must not silently become a second ledger, project master, risk register, incident register or invoice system. P12, P34 and F34 describe connected PMO-to-Finance handoff work, not three independent notification engines. Milestone completion, notification delivery, Finance acknowledgement, invoicing, revenue recognition and cash receipt are different facts.

## Test meaning

Acceptance examples specify synthetic inputs, actor/action and expected observable outcomes. Source-derived expectations and proposed technical safeguards are labelled separately. Missing business rules block the affected expected result; a fabricated rate, approval or exception cannot serve as an oracle. Mock tests are specified here, not run against software. Passing a future mock test will not establish live-system correctness.

## Readiness gates

Track documentation coverage, source verification, owner decisions, mock specification and implementation separately. A fully written definition can still be blocked for implementation. Do not mark a process implemented, owner-approved, tested or production-ready because its definition exists. Deferred entries remain documented and accounted for.

## Baseline and future AI

The dated V1 tracker is a historical scope baseline, not permission to start building now. Potential AI assistance is explicitly proposed and outside that baseline unless separately approved. Deterministic calculations and permissions remain deterministic; accountable decisions remain human-owned. No zero-cost, zero-maintenance or autonomous-operation guarantee is implied.

## Version and recovery

Each release contains unchanged source copies, definitions, a coverage workbook, decisions, mock catalogue, an index and SHA-256 manifest. Package relative paths remain the same in the cloud and local copies. Only verified copied bytes count as mirrored. Preserve prior release archives rather than silently overwriting accepted definitions. No passwords, access tokens or raw production data belong in this documentation package.
