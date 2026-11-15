# Decisions relayed by the design engineer, 14 Nov 2026 (third set, applied overnight 14–15 Nov)

Recorded as said in the build session and in delivery/OVERNIGHT-DECISIONS.md; project inputs, not authenticated approvals.

- (h) The approved boards are the spec. A UI review passes only on a design-fidelity check: every element of every board in scope is present (after approved exceptions) and the visual score is at least 90 (design engineer, 14 Nov 2026).
- (i) Overnight, the coordinator continues without pausing: it drafts the contract proposals the boards need and splits features by screen family, so every approved screen has a frontend task (design engineer's instruction to continue overnight, 14 Nov 2026).

These extend decisions-2026-11-14-v2.md items (e)–(g): a drafted field is a proposal for the backend developer to confirm, not a backend commitment; the frontend builds against it on the contract mock only; nothing is released.

Applied in architecture v7 (drafted by the coordinator for the frontend under items (g) and (i)):

- Optional fields, parameters and endpoints for the boards whose content the v6 contract does not carry: the exceptions list, record a response and reconcile, team input and the RFP outcome (including the RFP frame and the drafted follow-up), month-end, setup rules, delegation, people, templates, alert preferences and the notification centre, the assistant, the projects list and journey, the factory floor lines, receivables and clients, assigning an accountable person, and one typed workspace block per line on the work item with one generic step write.
- Every v6 field, required list, enum and parameter is kept, so built screens and their fixtures keep validating.
- Frontend tasks for every screen that had none, and for the slices the readiness checks proposed (responses F-09/F-09B, Finance F-10B..J, Setup F-11B..F, alerts and assistant F-12A/A2/B), plus one task that repoints the frontend contract to v7.

Where the business rule itself is undecided — payment exceptions and receipt allocation, costing rule review, who holds Admin, payroll field visibility, who decides a change request, sign-in, speech input, notification and conversation storage — v7 carries only what a screen needs to display what the backend returns, and the decision stays open for PSL or the backend developer. Nothing here sets a rule, approver, default or financial value; unknown is never 0.
