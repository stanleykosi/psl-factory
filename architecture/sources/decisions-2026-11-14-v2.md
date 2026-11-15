# Decisions relayed by the design engineer, 14 Nov 2026 (second set)

Recorded as said in the build session; project inputs, not authenticated approvals.

- (e) Build the remaining screens in parallel.
- (f) Split features where the contract is missing: the part the contract carries is built now; the part it does not carry waits as its own feature.
- (g) The frontend drafts contract proposals for the backend developer to confirm. A drafted field is a proposal, not a backend commitment; the backend developer may change or refuse it, and the frontend builds against it on the contract mock only.

Applied in architecture v6 (drafted by the frontend under item (g) and decisions-2026-11-13-v3.md item (a)):

- Start work (SCR-04): typed intake fields, option lists read from the backend, the case each line starts on, proof attached by evidence id, line subtitle and "what happens next", and line keys in /me.
- Record a response (SCR-16) and reconcile (SCR-02 awaiting reconciliation): the case and its revision on the work item, per-task response options supplied by the backend, the actions the backend allows on the work item, and recording an RFP outcome.
- Project tabs (SCR-38, SCR-12, SCR-11, SCR-29, documents): typed rows per tab.
- Frontend tasks split to match: FE-M2A (core Start work), FE-M2A-PROOF, FE-M2B (exceptions only), FE-M2B-RESPONSE, FE-M3-PROJECT-TABS and FE-M3-REPORT.

Which response actions a task accepts, who may record an RFP outcome, which actions a person may take on a work item, and every amount, are backend business rules. The contract carries only what the backend returns; nothing here sets a rule, approver or financial value.
