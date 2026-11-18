DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-30 is SCR-30 Issue detail: 8 boards (default, overdue, no-owner, verified, each desktop and phone). That is exactly the D-64 cap of about 8. It is one outcome, the issue page inside the shared line workspace, so one PR.
- Gates are met. FE-ISSUE in architecture v7 has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2078-2108). SCR-30 is in the client-approved screen list (design/review.json:43). Dependencies FE-WORKSPACE-FRAME (F-17) and FE-M3-PROJECT-TABS (F-25) are merged, as the coordinator confirms. The M-6 milestone gates (D-CHANGE-DECIDERS, D-DECISION-VARIANTS, D-LINE-WORKSPACE) do not list this task.
- The screen is a thin view over the F-17 workspace block: E-WORK-ITEM (GET /api/v1/work/{work_id}), E-WORK-STEP and E-WORK-ASSIGN. All three exist in frontend/src/api/schema.d.ts. The backend handoff (delivery/backend-handoff/gaps-a-project-setup.md:145-163) says most of the page is covered by v7 as is.
- Two gaps are listed as blocking in that file (G-SCR30-1 escalation prefill, G-SCR30-3 team or outside-party owner). They block the real write, not the screen. Both are built on the contract mock only, as in F-25 and F-27. Nothing is released.
- I did not run `design.py check` (no shell in this role). The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a person following an issue opens its work item (from the Issues register row's `work_id`) and sees what it is, what has happened, and how it is being chased. The person recording for the owner can post an owner update, record a reply, or set an owner, in the four states. Contract mock only.

**Boards (8):** SCR-30 desktop and mobile in default, overdue, no-owner and verified (design/canvas/project/SCR-30-*.dc.html).
- Default: status "FIX IN TESTING", facts OWNER / RAISED / AGE / BLOCKS, severity, "What has happened" timeline, "Chasing" (asked, reminder sent, escalate by), the "Owner follow-up" step (`update_type`, `update`), agent note.
- Overdue: "NO RESPONSE · 3 DAYS", "Record a reply" and "Raise an escalation".
- No-owner: "OWNER NEEDED", "Set an owner" (E-WORK-ASSIGN).
- Verified: "FOLLOW-UP VERIFIED", read-only, with "Open the issue register".

**Task and endpoints:** FE-ISSUE (R-WORKITEM), acceptance A-WORKSPACE. E-WORK-ITEM, E-WORK-STEP (POST /work/{work_id}/steps), E-WORK-ASSIGN (POST .../assignment), E-PROJECT for the tab bar and counts.

**Reuse, not rebuild:** the F-17 workspace frame and its section, step and field renderers; the F-25 registers (the row that opens this page); `frontend/src/components/` (D-91); the `frontend/mock` workspace scenarios plus an overlay in the proposals file for the items below. Add only the issue-specific scenarios (default, overdue, no-owner, verified).

**Buildable now on the mock:** everything drawn on the 8 boards. That covers the status and tone, facts, severity, timeline and "Chasing" with times, the owner-update step, the agent note, the "Next" lines, the assign form, the 401, 403/404 (the same), error and retry, the stale 409 and the "Unknown" display. Phone is a single column with 44px targets (D-92c).

**Contract proposals (mock overlay only; record in build.md for the backend developer):**
- G-SCR30-1: `steps[].starts_line:{line_key, prefill}`. Until confirmed, "Raise an escalation" is a link to Start work and the page does not claim the escalation was started.
- G-SCR30-2: `workspace.links[]`, so "Open the issue register" and "Set an owner in the issue register" can link out. Until confirmed, they are plain text or a link built only from ids already in the response. Nice-to-have.
- G-SCR30-3: owner may be a team or outside party ("Engineering (recorded by PM)"). Until confirmed, the form offers only `assign.candidates[]`, with no free-text owner. The 13 Nov no-login decision means team owners must be supplied by the backend as options.
- G-SCR30-4 and 5: confirm a reply is a step; a reminder to a no-login team uses a named `channel`, and an unknown send result shows `receipt: uncertain` with `reconcile` before any resend.
- G-SCR30-6: the default board has no tab bar and the crumb "ISSUES"; the other three have the tab bar and "REGISTERS / ISSUES". Settle at spec time and list it in the exceptions file for the design engineer.

**Out:** closing the issue, changing severity or state (the register's job, with QA and the PM); creating the escalation (backend); the Changes (SCR-31) and other line workspaces; backend, OpenAPI, schema.d.ts regeneration, `architecture/**`, `src/shell/**`.

## Binding rules for the spec
1. Every control (step, assign, escalate) shows only when the response sends it; roles never grant a control (INV-ACCESS). 403 and 404 look the same.
2. Writes send CSRF, `expected_revision` as read (workspace.revision) and an `idempotency_key` for steps. A failed or timed-out write does not show "recorded". Re-read before offering a retry (reconcile uncertain effects).
3. Show "recorded by PM" and the actor as the backend returns them; do not present the owner as having logged in. Agent text (Tola's note, "I'll remind the owner...") is displayed as returned and is never a verified outcome. "Verified" appears only from `state`/`facts` of `verified`.
4. Unknown values show "Unknown", never blank or zero. Dates and ages are rendered from returned values, not recomputed to decide overdue status. The state and tone come from the backend.
5. Tokens and components only; labels on every field; errors announced; reduced motion respected.
6. Fidelity (D-64): one design-fidelity run per round over all 8 boards, score at least 90, every element present after approved exceptions. Axe at 390 and 1440. Differences go in the exceptions file for the design engineer.

## Risk
Medium. The page has several behaviours (four states, three writes) and sits on the shared workspace block (F-17), so a cross-layer contract is involved, with two additive proposals. It touches no money, migration or identity change, and the owner assignment is limited to the candidates the backend returns. SURFACES are ui, api and contract-change (G-SCR30-1 and -3). Auth is not ticked because no new authority rule is added: the controls follow the response. PRODUCT-ACCEPTANCE is required because the owner-update, reply, escalate and set-owner flows and their wording are new to the client.

## Questions
None. The open items are backend confirmations (the proposals above and the three questions at delivery/backend-handoff/gaps-a-project-setup.md:160-163). They hold the real write, not this build.
