DECISION: NOT-READY
RISK: high
SURFACES: ui, api, product-decision, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: D-COSTING-RULE
REVIEWER: readiness

## Summary
- F-77 is FE-SETUP-COSTING with SCR-39 Setup costing rule (4 boards: default, review, example, review-own). D-COSTING-RULE is still revision 1, status open (architecture/model.json:1780-1806). It covers the rule's shape, review and withdrawal, and the backend move to one studio-wide rule. No later decision settles it.
- Live 1.22.0 has costing endpoints, but they are per project (`/projects/{case_id}/costing...`) and return raw calculator payloads, hashes and ids. There is no organisation-wide read (B-51), no readable rule or worked examples (B-50), and no proposer or reviewer names. The design is an org-wide version list with those names.
- A read-only slice is not worth building yet. The screen's content depends on the open shape of the rule and on B-50 and B-51, so any build would invent what a rule section looks like.
- Writes (propose, withdraw, decide) are financial-rule changes and stay held. The reviewer must differ from the proposer (12 Nov), and PSL has not named the reviewers or the owners.

## Scope
Not for a spec. Unblock by: (1) PSL decides D-COSTING-RULE; (2) backend answers B-50 (readable rule and examples with names), B-51 (which project or workspace carries the org rule), B-52 (what evidence a verdict needs), B-53 (what `POST /work` does for costing). After that, re-run readiness, probably as two PRs: the read (versions, sections, examples) and the review decision (`POST .../costing/proposals/{proposal_id}`: confirm, return, withdraw). Out of scope until then: "New version" (no write is proposed), SCR-27 costing sheet (F-FE-COSTING, same gate).

## Risk
High: a financial rule that prices projects and feeds invoices, with unknown values that must never become zero (G-SCR39-4, "Unknown equals Unknown" is not a match). Contract change is needed for a readable, org-level read. Sources: connect/screens-b-projects-setup-clients.md SCR-39, backend-handoff/gaps-a-project-setup.md:304-317.

## Questions
(Not NEEDS-INFO, since the blocker is a PSL decision.)
1. PSL with the backend developer: the costing rule's shape, who proposes and reviews it, how it is withdrawn, and the named rule and examples owners (D-COSTING-RULE).
2. Backend: B-50, B-51, B-52, B-53.
