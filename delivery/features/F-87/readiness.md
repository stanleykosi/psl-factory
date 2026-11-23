DECISION: NOT-READY
RISK: high
SURFACES: ui, api, payments, external-messaging, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: LC-Q2, LC-Q5
REVIEWER: readiness

## Summary
- Dependency gate: F-85 (the shared adapter, CommandDescriptor and evidence picker that F-87 wires) is still IMPLEMENTING and not merged (delivery/features/F-85/feature.json). F-87 cannot be specced against code that does not exist on main.
- Design gate: F-85 passed on a design EXCEPTION (design_gate.status EXCEPTION, canvas_url null), not a client approval. I did not run `design.py check` for F-87. The write controls (Resume, Cancel, Check what happened, Release, weekly-report review and correct) are drawn on boards, but whether the client has approved the current boards is unconfirmed. The coordinator must confirm it passes, or record a bounded exception.
- Product decisions open: LC-Q2 (reconcile outcome: the design has a delivered / not delivered / unknown choice with proof, live reconcile is only a backend lookup, backend question 10 and C-19) and LC-Q5 (write buttons the boards draw). These change what the client sees, so the client or product owner must answer them before the spec.
- Size: seven writes in one PR across two lines (work item control and weekly report) is too big for one reviewable PR, and it mixes a payments write (release_invoice) with client-facing messaging (reviews). Split below.
- Architecture approval and decision approval status for this feature were not re-verified here (the feature record has no baseline and no operation ids). The spec writer must cite them.

## Scope
Proposed split, each part keeping about 4 boards. All of it builds after F-85 merges. Never invent a business rule, an attempt count or an approver. Unknown stays unknown, never 0.

**F-87a: work item control writes (risk high, surfaces ui, api, contract-change)**
- `POST /work/{id}/actions` `reconcile` (202). Sends no outcome and no proof. One "Check what happened" button, then show the state the backend returns (LC-Q2 option 1, pending client answer). No delivered / not delivered choice and no proof panel.
- `POST /work/{id}/control` `resume` and `cancel` (200), only when listed in `available_control[]`. `adopt_profile` out.
- `POST /work/{id}/background` pause and continue. Confirm it exists in contract 1.22.0 and which boards draw it; the earlier readiness had it out. If it has no board or no contract entry, drop it from this feature.
- All writes through the F-85 CommandDescriptor with the existing `useWorkspaceStep` locking: press lock, uncertain lock after a timeout or 5xx (no retry until reconciled), fresh idempotency key per attempt, `expected_revision` and `case_revision` sent as given, a null token holds the write with a stated reason, 409 reloads the item.
- Out: invoice information, milestone proof, draft-stop, corrections and coordination retry. They belong to the delivery and issues features (DC-1..DC-5, screens-d) and are not drawn here.

**F-87b: release_invoice and weekly report writes (risk high, surfaces ui, api, payments, external-messaging)**
- Prefer release_invoice in its own small feature or first in F-87b, because it is a money write that is hard to undo and needs the payments and security reviewers. It is offered only when the API lists it and needs `expected_revision`. Do not show an amount or `reference`, the API supplies none.
- `POST /work/{id}/weekly-report` `action:"correct"` (`expected_revision`, `case_revision`, `parts`, `reason`), only when `can_correct`. `POST /work/{id}/reviews` kind `document` (`version_id`, approve, return or reject, `note`). Panel key `weekly-report` is C-20: build on it and flag it.
- Show no content the API does not serve (no returned-note text, no cite labels, no assembled text beyond `document_version_id`).
- Out: weekly-report intake and start, every other line, new endpoints or states.

## Risk
High. release_invoice moves money and is hard to undo, reconcile follows an uncertain send, and a document approve or return reaches clients, so a wrong revision token or a retry before reconcile would repeat an effect, which AGENTS.md forbids. The shared adapter in `frontend/src/features/workspace` is the contract all later lines use (contract-change). product-decision is included because LC-Q2 and LC-Q5 change what the client sees. Seven writes with a locking state machine do not land as one reviewable PR.

## Questions
1. LC-Q2: after an uncertain send, may the screen show one "Check what happened" button that runs the backend lookup and then shows the returned state, with the delivered / not delivered / unknown choice and proof panel held until the backend answers (backend question 10, C-19)? Recommended: yes.
2. LC-Q5: once F-87 merges, are the Resume, Cancel and Check-what-happened buttons shown as drawn, with nothing disabled-and-hidden in between? Recommended: show them live only when the API lists the action.
3. Is the client approval of the current SCR-02 and SCR-25 boards recorded, or is the F-85 design exception to be extended to F-87 with its limits written down?
4. Is the split above accepted, and does `/work/{id}/background` have a board and a contract entry?
