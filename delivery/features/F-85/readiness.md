DECISION: READY
RISK: medium
SURFACES: ui, api, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Read-only work item on live GET /work/{id} plus two shared building blocks (per-line adapter types, evidence picker). The money and client-facing writes now live in F-87.
- Task FE-CONNECT-1 is in the v9 architecture, and the design runs under the recorded exception in design/review.json. The 13 Nov approval still covers the screens, and delivery may continue while the design engineer's later changes await re-approval.
- Not checked: `design.py check`, and decision-by-decision approval status for the architecture package. I did not run the check or read each decision at its latest revision.
- LC-Q1 (station track, six facts and agent steps have no live source) is open, but it does not block. The binding scope below follows the recommended option, which hides those parts. The design engineer may answer differently, and that would mean a later change, not a guess now.
- The evidence picker's route to reviewed_evidence_id (file-draft review path) is the flagged best reading of backend question 1 / D-1. It is built as a tested component, and nothing writes through it in this feature.

## Scope
Outcome: the work item page shows live data, and the shared workspace gains an adapter and an evidence picker. The weekly report panel is the proof that the adapter renders a real line. No money or client-facing writes.

In scope (task FE-CONNECT-1, screen SCR-02, rules DC-1 to DC-5, contract 1.22.0):
- GET /work/{id}: title, state, status_label, next_step, blocker, tasks[] with links to decisions, progress, and current_activity. Poll only while watching/processing.
- GET /work/{id}/history and output_url.
- The permission state uses one wording for "missing" and "not yours". The access-request control for a hidden record is optional.
- In frontend/src/features/workspace: a per-line adapter interface. It maps a panel URL to section objects for the existing renderer, and a step to a typed command descriptor carrying its revision tokens and idempotency key. This is types and tests only, with no write wired.
- The shared evidence picker calls POST /cases/{case_id}/files and returns the upload_id. It exposes the file-draft review path to reviewed_evidence_id, labelled as a proposal pending backend question 1. It is tested against the mock and, where possible, live Django.
- The weekly report panel is read through GET /work/{id}/weekly-report via the adapter.
- Hide the station track, six facts and agent steps (LC-Q1 option 1). Do not derive them from history, and show no "not available" placeholders unless LC-Q1 is answered otherwise.

Out of scope (F-87): reconcile, control resume/cancel, background, release_invoice, invoice information/proof/draft-stop, weekly report review and correct, corrections, coordination retry. Do not invent business rules, and treat unknown values as unknown, not zero.

## Risk
Medium. The work touches shared workspace code that lanes A and B build on, and it fixes a cross-layer contract (the adapter and command descriptor shapes). The picker uploads files to case evidence, which is a security surface. Money, identity and migrations are not touched, since all writes are deferred to F-87. Product acceptance is required because the page hides approved design parts, which changes what the client sees.
