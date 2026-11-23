DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Second pass. The coordinator narrowed F-73 to client reads (list and details). That removes the blocked, proof-backed contact write that made r1 NOT-READY and high risk.
- The write is held in this release: the form shows disabled with its reason. It waits for the shared evidence picker and backend question 1 (B-45). It is not a new feature id yet.
- Design questions are defaults, not blockers (D-180, LANES.md step 2). The spec names each default and product acceptance confirms or changes it. B4 hides the owed column, money panel and blocked lines. B5 uses the group key in the route. B6 is the split.
- FE-CONNECT-1 is the task id LANES.md prescribes for this push. The screen is already built and approved, and only its data source changes.
- Not run here: `design.py check`, `oa.py`, and a re-read of the frontend code. I rely on r1 and the answers file. The builder gate must run `design.py check`.

## Scope
Binding for the spec writer. SCR-35 Clients and client details, task FE-CONNECT-1, connection map delivery/connect/screens-b-projects-setup-clients.md. Frontend: src/features/clients.

In:
- `GET /clients`: groups[], projects[] not in a group, `q`, `billing` filter, `clients_page`, `page`, 25 each.
- `GET /clients/groups/{group}`: label, projects[], next_page.
- `GET /clients/{case_id}`: contacts[], revision. `GET .../contacts/history` is read only.
- The `/clients/[clientId]` route accepts a group key, or a workspace `case_id` when the project has no group. Note the caveat: a key can change if grouping changes (B-42).
- The billing tag comes from the live `contacts_needed` and `billing` values (recorded, needed or unknown). Unknown shows as unknown, never as zero or "set". If the meaning is unclear (B-46), use the best reading of the live contract and flag it in the spec and the PR.
- Owed, the money panel and the blocked lines are hidden (default B4). No figure is invented. Money stays at `/projects/{case_id}/money`.
- The mock stays in v7 shape for unconnected screens. If the clients mock moves to the live shape, validate it against the live contract.
- The add-billing-contact form stays visible but disabled, with the reason "waiting for the evidence picker and the backend answer". It must not call the retired v7 `PUT` against live and must not send `POST /clients/{case_id}/contacts`.

Out:
- The contact write (F-73b, held, no id yet).
- Billing identities, project people and workspace-link writes.
- Any backend change.
- Which workspace's billing contact is "the client's" for a multi-project group (B-44). Backend question, not blocking the reads.

## Risk
Medium. The change is read-only and conforms to the approved design. It is still a cross-layer contract change, and the meaning of "client" changes from a record to a group in src/features/clients and in the route id. Per-record access applies to the reads. The high-risk billing-contact write is excluded. Surfaces: ui, api, contract-change, and product-decision for the B4 and B5 defaults. Product acceptance is required because the client sees a changed list, a changed detail page and a disabled contact form.
