DECISION: READY
RISK: low
SURFACES: ui, api
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-113 is now SCR-43 delivery overview only (about 5 boards, read only). SCR-44 release gates moved to F-113B, which depends on this feature merging.
- Data is settled: one endpoint, `GET /projects/{case_id}/delivery-overview` (API 1.24.0, D-10 and D-11), with six stable line keys. D-185 switches the overview on.
- The build waits on F-85 (lane C, PR #101, the shared line adapter, not yet on main). That wait delays the build start only and is not a blocker. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Architecture and design approval are covered by the v9 package and the 13 Nov client design approval (D-173/D-181 exceptions in `design/review.json`), per the lane D rules. I did not re-run `design.py check` in this pass.
- Parts the API does not supply are hidden (D-182 rule), listed under Scope.

## Scope
Binding for the spec writer. Task FE-CONNECT-1. SCR-43 only. No writes.

- Endpoint: `GET /projects/{case_id}/delivery-overview`.
- Draw the six lines in this order, keyed by `delivery-release/v1`, `delivery-go-live/v1`, `delivery-hypercare/v1`, `delivery-handover/v1`, `delivery-archive/v1` and `delivery-closure/v1`.
- For each line show the latest visible work: its reference, state, date and link.
- A line with no work shows "not started" with empty fields.
- Opening a line links to its `/work/{id}`.
- Closure hold reasons come from `closure-checklist` (`ready_to_prepare`, `checks[]`).
- Replace the mock reads in `DeliveryTab.tsx` and `model.ts` (`delivery[]`, `delivery_summary`, `delivery_agent`).
- Any line mapping lives in this feature's folder. Do not change the shared frame in `frontend/src/features/workspace`. If a frame change is needed, name it as a dependency on lane C (DC-2).
- Hide, because the API does not supply them (DC-3): gate wording and tone, "3 of 6 done", the DLV file number, and Tola's check and "Next" sentence. Do not count "done" as a frontend rule.
- Unknown values stay unknown, never 0. Do not invent states, approvers or counts.
- Out of scope: SCR-44 release gates, planning-exit, release-register and client-testing (F-113B). Also out of scope: any write.

## Risk
Low: a read-only screen on one new endpoint, with no money, identity, migration or sensitive data. It follows the existing line adapter pattern, and the only cross-layer contract is the overview response shape, which the live contract fixes. Surfaces are ui and api. Product acceptance is required because the overview flow and copy change from the mock. It can merge under D-180/D-184 once the build is on F-85.
