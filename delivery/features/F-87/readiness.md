DECISION: READY
RISK: high
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-87a is the narrowed feature: three work-item writes (reconcile, resume/cancel, background) through the shared adapter, with the press lock, uncertain lock, fresh key per attempt and 409 reload. Release invoice and the weekly-report correct/reviews moved to F-89, so the money and client-messaging writes are out.
- LC-Q2 and LC-Q5 are closed by D-182. Reconcile is one "Check what happened" button running the lookup (202). It has no delivered / not delivered choice and no proof panel. Resume, Cancel and Check are shown live only when the API lists them.
- Build-order dependency, not a blocker: F-85 (CommandDescriptor, shared adapter) must merge first, as for F-86 and F-88.
- Design gate: F-85 runs on a recorded design EXCEPTION (design_gate EXCEPTION, canvas_url null). F-87a inherits it only under the same limits, which are conformance to the SCR-02 and DC-1..DC-5 boards as drawn, with no new screens, copy or states. I did not run `design.py check` here. The coordinator must confirm it passes or that the F-85 exception limits cover F-87a, under the D-180 push.
- `feature.json` has no baseline, operation ids or approval refs yet. The spec writer must fill them from the architecture package and cite decision approval status.

## Scope
Binding for the spec. Task FE-CONNECT-1. Contract `contracts/psl-factory.openapi.json` 1.22.0. Maps: `delivery/connect/screens-a-frame-core.md` SCR-02 Writes, and DC-1..DC-5 in `screens-d-delivery-issues-escalation.md`.

In:
- `POST /work/{id}/actions` with `reconcile`, answered 202. It sends no outcome and no proof. One "Check what happened" button runs the lookup, then the screen shows the state the backend returns. The button is shown only when the API lists the action.
- `POST /work/{id}/control` with `resume` and `cancel` (200), only when listed in `available_control[]`. `adopt_profile` is out.
- `POST /work/{id}/background` with `{expected_revision, enabled}` (202), to pause or continue. It is in contract 1.22.0 (line 20876) and drawn on the SCR-02, planning and delivery boards.
- All writes go through the F-85 CommandDescriptor and `useWorkspaceStep`:
  - a press lock;
  - an uncertain lock after a timeout or 5xx, with no retry until reconciled;
  - a fresh idempotency key per attempt;
  - `expected_revision` and `case_revision` sent as given;
  - a null token holds the write and states the reason;
  - a 409 reloads the item.
- The server decides who may act and returns 403 or 409. Show those as given. Invent no approver, attempt count or business rule. Unknown stays unknown, never 0.

Out (F-89 or elsewhere): `release_invoice`, weekly-report `correct`, `/reviews`, invoice information, milestone proof, draft-stop, corrections, coordination retry, `adopt_profile`, new endpoints or states.

## Risk
High, because reconcile follows an uncertain send, and a retry before reconcile or a wrong revision token would repeat an effect that AGENTS.md forbids. Cancel is hard to undo. The shared adapter in `frontend/src/features/workspace` is the contract the later lines use (contract-change). product-decision stays because the Check button and the live-only-when-listed behaviour change what the client sees (D-182, LC-Q2, LC-Q5), so the client must see the result. There are no payments or external-messaging writes in this slice.
