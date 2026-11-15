RECOMMENDATION: ESCALATE
COMMIT: a4a906cadfbafced2c20f8535467cb32db06c3eb
APPROVER: approver

## Summary
- F-19 adds the clients list and client detail with set-billing-contact (SCR-35, 4 boards) on the contract mock. All changes are under frontend/ (31 files, +2339/-2).
- Round-3 technical, UI, UX, QA and PMO reviews all PASS and name head a4a906ca. The head only adds a merge of dlv-00 over the reviewed 95903eeb (D-84 records that no F-19 file changed). QA re-ran e2e/clients.spec.ts on the synced head: 16 passed. A synced checks log exists for a4a906ca.
- The change stays in readiness's Scope. D-CLIENTS-VIEW stays a proposal, with no backend claimed.
- Two hard-rule triggers apply: the surface list includes contract-change (an always-human surface), and 31 changed files exceed the 15-file auto-merge cap.
- D-84 (OVERNIGHT-DECISIONS.md) already records the design engineer's "Merge" on 15 Nov.

## Why
The work looks sound and I found no scope or product-decision problem. Because policy puts contract-change and a change this size with a person, I recommend ESCALATE so the merge rests on the recorded human approval and not on an automatic merge. The question is a confirmation only.

## Acceptance criteria
1. Desktop and phone fidelity on the four boards, with limited and explained exceptions: met. PMO acceptance and the UI review PASS on this head, and the exceptions file carries design engineer approvals (D-71). I did not re-run fidelity myself.
2. List from the data only, owed shown as "Unknown" or "Not given" and never 0, count line and paging, list states: met. QA and technical review PASS, and the unit and e2e suites cover them. I confirmed the clients e2e, mock and component test files exist in the diff.
3. Detail, and set billing contact with expected_revision, CSRF, no auto-retry, and 409/422/401/403/404 handling: met. QA exercised 409, 403, 502, network failure and reload-failure cases at both widths (140 checks passed at 95903eeb).
4. Mock handlers validate against the schema, and existing projects, work item and shell tests stay green: met per the gate (GATE: PASS) and the synced checks log. Note that round-3/checks.md names 95903eeb, and the synced head's evidence is checks-synced-a4a906ca.log.

## For the human
Decision needed: confirm the merge of PR #37 into dlv-00-delivery-setup under your D-84 approval. The surface is contract-change, and the diff is above the 15-file cap. D-CLIENTS-VIEW (architecture/model.json:1607) stays proposed, and the mock fields are not binding on the backend developer.
Files to look at: delivery/OVERNIGHT-DECISIONS.md (D-84), delivery/features/F-19/readiness.md (Scope), frontend/src/features/clients/, frontend/mock/clients.mjs.
