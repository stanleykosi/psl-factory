DECISION: NOT-READY
RISK: high
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: D-COSTING-RULE
REVIEWER: readiness

## Summary
- Re-check on main b8542c79 and API 1.24.0: D-COSTING-RULE is still unsettled. The 23 Nov PSL decision "Finance staff can adjust any pricing line in NGN, with the lines and amounts reviewed by the Finance Lead before the revised bid proceeds" is about pricing lines on a revised bid. It says nothing on the studio-wide rule's shape, who proposes or reviews a new version, or how a proposal is withdrawn. It does not settle D-COSTING-RULE.
- B-50 to B-53 do not unblock the screen. B-50: public reads give the structured rule and worked-example results but no prose summary and not all proposer or reviewer names, which the design shows. B-51: no org read; start from Setup scopes and the authorised workspace's organisation policy, and do not pick a project. B-52: a verdict needs a current case evidence ID, the verdict and a reason, checked against reviewer authority. B-53: costing proposals are not a work definition.
- Withdrawal is not answered anywhere, and reviewer and owner names are still not given. Writes stay held.
- A read-only slice still invents what a rule section and the missing names look like, so it is not worth building.

## Scope
Not for a spec. Unblock by PSL deciding D-COSTING-RULE (rule shape, who proposes and reviews, withdrawal, named owners), and the backend confirming how an org-level read is reached (B-51 gives a direction, not an endpoint) and whether names will be returned (B-50). Then re-run readiness, likely as two PRs: the read (versions, sections, examples), then the review decision (confirm, return, withdraw). Out: "New version" and SCR-27.

## Risk
High. A financial rule that prices projects and feeds invoices, with unknown values that must not become zero. Contract change is likely for a readable org-level read. Sources: architecture/model.json D-COSTING-RULE (open), BUILD-DECISIONS.md 23 Nov, backend-answers.md B-50 to B-53.

## Questions
(Not NEEDS-INFO: the blocker is a PSL decision plus backend work.)
1. PSL with the backend developer: the costing rule's shape, who proposes and reviews it, how it is withdrawn, and the named owners (D-COSTING-RULE).
2. Backend: the org-level read route and proposer and reviewer names (B-50, B-51).
