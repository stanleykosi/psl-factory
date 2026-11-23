DECISION: NOT-READY
RISK: high
SURFACES: ui, api, security, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- As worded, the outcome is two features in one: reading clients (low-medium risk) and adding a billing contact with proof (blocked). Split it.
- The write needs an integer `evidence_id`. The shared evidence picker (README item 7) does not exist yet, and backend question 1 (B-45) is unanswered: no live call turns a file or note into an evidence id for a client contact. A builder would have to guess a business rule.
- The map itself says to hold SCR-35 writes until the backend answers (screens-b, "Connect first").
- The read half can start. D-173 lets delivery continue on the current design, and F-56/F-57 are merged and set the live client and session pattern.
- The design draws things live cannot fill: an owed column, a money panel, "blocked" lines, a one-person contact (name and email only), and a stable client id. Each needs a recorded design-engineer ruling (drop, hide or show as "not available"). This check cannot invent one.
- Not run here (no shell): `design.py check` and `oa.py`. I read the connection map, `feature.json` and the contract path list instead. The builder gate must run `design.py check`.

## Scope
Binding for the spec writer. Task FE-CONNECT-1. Replace the F-73 outcome with the first slice below. Do not build the second until its gate clears.

**F-73 (this feature, re-scoped to reads, READY once the design ruling in Questions 1 and 2 is recorded):**
- `GET /clients` (groups[], projects[] not in a group, `q`, `billing` filter, `clients_page`, `page`, 25 each).
- `GET /clients/groups/{group}` (label, projects[], next_page).
- `GET /clients/{case_id}` (contacts[], revision) and `GET .../contacts/history`, read only.
- The `/clients/[clientId]` route accepts a group key or a workspace `case_id`. Billing tag comes from the live `contacts_needed` and `billing` recorded, needed or unknown values. Unknown is shown as unknown, never as zero or "set".
- Owed, money panel and blocked lines show "not available" or are hidden, as the design engineer rules. No figure is invented. Money stays at `/projects/{case_id}/money`.
- Mock stays in v7 shape for unconnected screens. If the clients mock moves to the live shape, it is validated against the live contract.
- The billing contact form stays visible but does not send the old `PUT`. It must not call the retired v7 route against live.

**F-73b (new feature, NOT started):** `POST /clients/{case_id}/contacts` {purpose "billing", customer, client_name, name, email, role, evidence_id, expected_revision} with options from `GET .../contacts/options?purpose=billing`. Needs the shared evidence picker and the answer to B-45 and backend question 1. The new customer and role fields change the approved form, so they need a design change approved by the client.

**Out:** billing identities, project people and workspace-link writes (live-only, undrawn). Any backend change. Group-key stability (B-42) is a risk to note, not a blocker for reads.

## Risk
High as worded: the contact write records a billing party and needs proof, which is identity and data that is hard to undo, and its contract is not settled (backend question 1, `contacts` `evidence_id`). The read slice alone is medium: a cross-layer contract change, and the meaning of "client" changes from a record to a group in `src/features/clients` and in the route id. Surfaces are ui, api, security (proof-backed write, per-record access), contract-change and product-decision (what replaces owed and blocked). Product acceptance is required because the client sees a changed list, a changed detail page and a changed billing-contact flow.

## Questions
1. Design engineer: for the owed column, the money panel and the "blocked" lines, which do you choose: hide, or show "Not available in the live data yet"? (Live has money only per project.)
2. Design engineer: may the client id in the route be the group key (or a workspace id when the project has no group), with the caveat that a key can change if grouping changes?
3. Design engineer: do you accept the F-73 / F-73b split, with the billing contact write held until the evidence picker and the backend answer to question 1 (B-45)?
4. Backend (for F-73b, not blocking F-73): which workspace's billing contact is "the client's" when a group has several projects (B-44), and what do `contacts_needed` and `billing` recorded, needed or unknown mean for the "billing contact set" tag (B-46)?
