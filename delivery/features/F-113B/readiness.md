DECISION: READY
RISK: high
SURFACES: ui, api, auth, security, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-44 release gates is 6 states (default, decision, returned, owner-needed, readiness, ready), each drawn as a desktop and a mobile board. That is 12 boards but one responsive screen, so it stays one PR. If the builder finds the release-register writes too large, split them off as F-113C and keep the planning exit here.
- The backend answers settle the data: D-12 (a named PMO Lead approves the planning exit with a note), D-13 (a PM click triggers `prepare_readiness`), D-14 (phase and status values), D-1 (proof rules) and PSL answer 1 (an eligible current PMO Lead may approve their own named planning exit directly).
- Waits on F-113 (part 1), F-85 (shared line adapter) and F-87 (the `Actions` slot) delay the build start only. They do not block readiness.
- Caveat: I did not rerun `design.py check` or re-verify architecture approval. I relied on the lane D context, which says the v9 package and the 13 Nov design approval (with the D-173/D-181 exceptions) cover this screen. The feature record has no acceptance criteria yet, so the spec writer must add them.

## Scope
Binding for the spec writer. Task FE-CONNECT-1, SCR-44 only. SCR-43 stays in F-113. D-185 applies: build what the boards draw where API 1.25.0 or later supplies the data, and hide the rest (D-182 rule). Build the line's adapter mapping in this feature and do not change `frontend/src/features/workspace` (DC-2). Build the write form as `ReleaseActions.tsx` against the F-87 `LineActionsProps` shape.

Reads
- `GET /work/{id}/release-register`: phases Initiation, Planning, Execution and Closure, with D-14 statuses (unknown, stale_scope, current, restricted_or_authority_changed, unknown_or_stale), `readiness_ids[]`, `release{}` and `actions[]`.
- `GET /work/{id}/planning-exit`: `checklist`, `packet`, `blockers[]`, `workaround`, `proofs[]` and `actions[]`.
- `GET /setup/{case}/decision-appointments`: drives the owner-needed state when `GET /work/{id}` returns `state: owner_needed`.
- Client-testing read: show the UAT outcome on the gates list read-only (`outcome`, `proof_current`).

Writes
- `POST /work/{id}/planning-exit`: approve or return, with the current `packet`, `expected_revision` and `case_revision` (DC-1) and a note. Per PSL answer 1, an eligible current PMO Lead can approve their own named planning exit directly. The server enforces the packet and the independent gates, so the frontend adds no approver rule.
  - Evidence follows the binding proof rule. Use the action's own proof route if one exists. Otherwise the person picks from `proofs[]`, nothing is preselected, and the button stays off when the list is empty. Never invent an evidence id.
- `POST /work/{id}/release-register` `prepare_readiness`: a PM click (D-13), offered only when `actions[]` allows it.
- `POST /work/{id}/release-register` `observe_release`: records the release with a checked PDF on that action (D-1).
- Every allowed action comes from the read's `actions[]` (D-14, DC-5), never from a frontend rule.

Out of scope, so hide or defer
- The "Decide" panel figures (stages built, open issues by severity, changes since SOW) and Tola's check (DC-3). Show only the checklist and blockers the API gives.
- Client-testing writes, the `/pack` routes, the workaround link write and the source and gate capture actions (`capture_source`, `verify_source`, `capture_gate`, `verify_gate`, `record_progress`, `record_glpi_request`). The boards do not draw them. Hold them as a later increment unless the design engineer asks.
- Any change to the shared adapter frame. If one is needed, name it as a dependency on lane C.

Unknown values stay unknown and are never shown as 0. Any board and live-data conflict becomes a numbered presentation question for the batch.

## Risk
High, because it records the planning-exit approval and the release record. These are authority-checked governance decisions with packet and revision concurrency, and they are hard to undo (`planning-exit`, `release-register` in the live contract; D-12, D-13, PSL answer 1). Surfaces are ui and api, plus auth and security for the approver checks and proof upload, contract-change for the reshaped operations, and product-decision for the self-approval rule. There is no money or payroll, but the merge goes to the design engineer's merge batch and product acceptance is required, since the flow and copy change from the mock.
