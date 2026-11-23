DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Second pass. The coordinator cut F-74 to reads only (r1 F-74a, F-74b and the read half of F-74d) and held every write. That removes the evidence_id blocker (B-25/B-40) and the draft-then-review blocker (B-22/B-24).
- Design-engineer questions B1 to B3 are batched in delivery/connect/questions-batch.md. Under D-180 and LANES.md the build uses the recommended option as its default. The spec must name each default, and product acceptance confirms or changes it.
- This is a recorded exception with limits: it covers reads only, the F-56/F-57 treatment of unresolved v9 view gates applies, and FE-CONNECT-1 is the prescribed task id.
- The size is one reviewable PR: a picker frame and three read connections on already-built screens.

## Scope
Binding for the spec writer. Task: FE-CONNECT-1. Screens: SCR-13 (rules, delegation) and SCR-34 (templates). Connection map: delivery/connect/screens-b-projects-setup-clients.md. Code: src/features/setup.

In:
1. **Workspace picker in SetupFrame.** This is default B1/B2. Setup always opens on a chosen workspace, and the picker sits in the Setup header. It is filled from `GET /projects?status=active`. The chosen `case_id` stays in the address (route or query) so reload and links work. Where `GET /setup/{case_id}/rules` returns 404 (no `policy.read`), show a plain "no access to this workspace" state. Carry the workspace `revision` for later writes.
2. **Rules and delegation reads.** `GET /setup/{case_id}/rules` (status, version, value, roles). `GET .../delegations` and `.../delegations/options` for names. `GET /setup/primary-roles` for the role list. Set and not-set counts are derived from `status`.
3. **Templates read.** `GET /projects/{case_id}/templates`.

Writes are held (default B3). Edit, add-delegation and template-replace controls render disabled with the reason "Saving rules is not available yet". Name the endpoints held: `POST .../policy-configurations/typed-drafts`, `.../{id}/review`, `.../delegations/drafts`, `.../templates/replacements`. No write call is made. Do not wire `useRuleSave`, `useDelegationAdd` or `useTemplateUpload` to the network. List the held writes in the spec and the PR.

Out: all writes, first-template registration, `/setup/roles`, SCR-21 staff accounts, SCR-39 costing rule, payroll field visibility, policy scopes and impact. Fields the API lacks (`can_change`, `component`, the template line column, the test-template tag, updated-by, versions, delegation reason and status, "holds N pieces of work") stay absent. Do not invent them, approvers or policy values.

## Risk
Reads only, so no data change. Medium because the workspace scope for organisation-wide Setup is an unconfirmed default (B-21, B-27, B-38), the contract is cross-layer (several endpoints, plus 404-as-no-access handling), and the rules screens expose approval-authority data, so an access leak is possible. Surfaces: ui, api, contract-change, product-decision (the picker and the reads-only default). Risk drops from r1's high because the evidence_id and draft-activate paths are no longer in scope.
