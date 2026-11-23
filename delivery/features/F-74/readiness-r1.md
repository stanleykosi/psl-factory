DECISION: NEEDS-INFO
RISK: high
SURFACES: ui, api, auth, security, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: B-21, B-25
REVIEWER: readiness

## Summary
- F-74 bundles three differently shaped Setup connections (rules SCR-13, delegation SCR-13, templates SCR-34) plus a new workspace picker. That is too big for one reviewable PR.
- The frontend Setup is organisation-wide. Every live Setup read and write needs `{case_id}`. Which workspace holds organisation-level values is unanswered (B-21, B-27, B-38). Short-list item 4 is still batched to the design engineer.
- Every live policy write needs an integer `evidence_id`, and no live operation creates one (B-25, B-40). Rule saves, delegation drafts and first-template registration cannot be built without it.
- A workspace picker and a draft-then-review save are new flows that are not on the approved boards. The client must see them, so the design is not yet approved for this.
- Reads are connectable now. Writes are held.

## Scope
Binding for the spec writer once the questions below are answered. Do not start before then.

Proposed split (tasks stay under FE-CONNECT-1):
1. **F-74a, Setup workspace frame (ready once Q1 and Q2 are answered).** Workspace picker in `SetupFrame`, filled from `GET /projects?status=active`. The chosen `case_id` goes in the route or a query value so reload and links work. Per-workspace access is discovered by trying `GET /setup/{case_id}/rules` (404 without `policy.read`). The workspace `revision` is carried for writes.
2. **F-74b, Rules and delegation reads.** `GET /setup/{case_id}/rules` (status, version, value, roles; no `can_change`, `component` or counts). `GET .../delegations` plus `.../delegations/options` for names. `GET /setup/primary-roles` for the role list. Set and not-set counts are derived from `status`. Do not show Edit controls until authority is known (B-23).
3. **F-74c, Rule and delegation writes (draft then review).** `POST .../policy-configurations/typed-drafts`, `POST .../policy-configurations/{id}/review`, `POST .../delegations/drafts`. Held until B-22, B-24 and B-25 are answered and the draft-then-activate design is approved.
4. **F-74d, Templates read and replace.** `GET /projects/{case_id}/templates`, `POST .../templates/replacements` (multipart, proof and request key required). First-template registration is out of scope.

Out of scope: `/setup/roles` (only as far as built), staff accounts (SCR-21), costing rule (SCR-39), payroll field visibility, policy scopes and impact. Missing fields stay absent and are not invented. This covers the template line column, the test-template tag, updated-by, versions, delegation reason and status, and "holds N pieces of work". No approvers, policy values or proof stand-ins are to be made up.

## Risk
Setup edits change who may approve what (rules and delegation), so auth and security apply. Every write needs proof evidence that the API cannot create, and the draft-then-review life cycle changes the contract. The affected files are `src/features/setup/api.ts`, `useRuleSave.ts`, `useDelegationAdd.ts`, `useTemplateUpload.ts` and `SetupFrame.tsx`. The change depends on open backend questions B-21, B-22, B-24, B-25 and B-27. Rated high because it touches approval authority and an organisation-versus-workspace scope that is hard to undo.

## Questions
1. (Design engineer, from short-list item 4 / B-21, B-27, B-38) Is it acceptable that Setup always opens on a chosen workspace (a project) and shows that workspace's rules, delegations and templates? Or should it show a fixed workspace that holds the organisation values? If a fixed one, which workspace?
2. (Design engineer) Please approve a workspace picker at the top of the Setup frame. This design is not on the boards yet. It is required whichever way Q1 goes, unless a fixed workspace is chosen.
3. (Design engineer) A rule or delegation save now creates a draft that is not in force until reviewed and activated. Do you accept showing "Saved as draft, waiting for review" and a review step in the UI? Or do the writes stay held until the backend answers B-24 on who may activate?
4. (Backend, B-25 / B-40) How does a client create the `evidence_id` that rule, delegation and template writes require? Until it is answered, only the read parts of F-74b and F-74d can be built.
