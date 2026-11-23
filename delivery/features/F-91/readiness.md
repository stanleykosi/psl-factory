DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- Read-only follow-up to F-85 (D-185): the work item page shows the station track, six facts, agent activity, reference, who started it and when, and paged history, all from API 1.24.0.
- Task FE-CONNECT-1 (SCR-02). Sources are `tracking_url` on GET /work/{id} and GET /work/{id}/history (kind, cursor). Backend answers A-11 to A-17 settle every field, so no client question is open.
- Build order: F-85 must merge first (its spec is in round 2, adapting to 1.24.0). This is a sequencing dependency that the coordinator confirmed is not a blocker. Branch from main only after F-85 lands.
- Not checked: `design.py check`, per-decision approval status, and the exact `tracking` response schema. The builder must take the schema from contracts/psl-factory.openapi.json 1.24.0 (it names `tracking_url` five times) and not from the answers prose.

## Scope
Outcome: on the work item page, switch on the parts that D-182 (LC-Q1, LC-Q4, LC-Q6) hid in F-85 and that D-185 reverses, as the SCR-02 boards draw them.

In scope (task FE-CONNECT-1, GET /work/{id}, tracking_url, GET /work/{id}/history):
- Station track: station order, recorded status, current owner and next step (A-11). A future station may have no recorded owner, so show it as unassigned and do not invent one. Intake and human decision stations name their recorded actor when available.
- Six facts (drafted, reviewed, approved, sent, receipt, verified) from `tracking.facts` (A-12). Null means unknown and must render as unknown, never as zero or "no". Checklist facts on specialist lines stay in their own panels.
- Agent activity: only what the API supplies, which is `progress` and the optional `current_activity` (A-17). There are no per-step agent logs. Do not derive steps. Polling follows `watching`, work state, progress and the explicit next action.
- Reference and current owner from work detail. Who started it and the intake date from tracking (A-14).
- History: actor kind, actor, station, status, time, filter by kind (worker, decision, evidence), and "older events" cursor paging (A-15). Compose the sentence on the client from those fields. Per-filter counts have no source, so omit them.

Out of scope:
- Amount (A-14: read from the invoice or Finance panel, which belongs to the line features).
- The delivery-observation write (A-13), which belongs to F-87's reconcile work.
- Any other D-185 item (counts, setup, alerts and so on).
- New writes of any kind.

Rules: do not invent business rules. Where the API gives no value, show unknown, not a guess. Reuse the F-85 adapter and types.

## Risk
Medium. It changes how a status the client relies on is shown (a fact shown as done when it is only unknown would mislead), and it touches the shared work-item code that F-85 and other lanes use, with a typed contract change to 1.24.0. It has no writes and does not touch money, identity or migrations. Product acceptance is required because the client sees parts that were hidden before.
