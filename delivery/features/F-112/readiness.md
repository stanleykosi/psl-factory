DECISION: READY
RISK: high
SURFACES: ui, api, auth, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-31 (change request detail) has 18 boards, which is too many for one PR. This readiness covers part 1 only (F-112). Part 2 becomes F-112B.
- Part 1 is the change request from log to authorisation: the change list and log, the stage track, impact assessments, the five deciders, and recording the authorisation.
- Part 2 (F-112B) is notice, execution, go-live note, signatures and close, plus retry, cancel and restart. It depends on F-112 merging.
- The data is settled: D-5, D-6 and D-7 are answered, API 1.24.0 supplies the reads and writes, and D-185 says to follow the backend answers.
- The build waits on F-85 (lane C, PR #101) being on main. That delays the builder start but does not block readiness. The spec is written against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Not checked: I did not open the design boards or run `design.py check`. I relied on the lane context for design approval (13 Nov approval, with the D-173/D-181 exceptions). The spec writer must assign the 18 boards to the two parts. Any board that does not clearly belong to part 1 goes to F-112B.

## Scope
Task FE-CHANGE, part 1. Line key `change_request` on the `/work/{id}` frame, through a lane D adapter in this feature's own folder. The shared frame in `frontend/src/features/workspace` stays unchanged. If the frame needs a change, that is a dependency on lane C.

In part 1:
- Change list and "log a new change": `GET/POST /projects/{case_id}/ordinary-changes`. `capture` takes `{reference, category, module, description, reason, evidence_id}`. Standard changes use `preapprove` and `bind_standard`. The change reference, category (Standard or Normal) and module are shown.
- Detail read: `GET /work/{work_id}/change`. Shows `stage`, `finding`, `next_action`, `can_authorize` and `impact[]`. It also shows `assessors[]`, `decisions[]`, `authorization_id`, `authorization_choices[]` and `deployment_authorized`.
- Stage track. D-6 gives the codes: source, impact, authorization, notice, execution, go_live, signatures, complete. The adapter groups them into the five visual steps (authorisation, notice, execution, go-live note, signatures). Part 1 draws the track for every stage and makes only source, impact and authorization actionable.
- Impact assessments for Engineering, QA, Infra and Security. Write: `POST /work/{id}/change` with `action: assess`. Show the cost, timeline, client-facing and production impact fields, and `effort_person_days` as a string.
- Deciders and verdicts. Write: `decide` `{role, verdict approve/return/reject, evidence, note}`. D-5: Product and Engineering are always required. Client is added when the change is client-facing. Engineering Lead and Security Manager are added when the timeline is affected. Standard and emergency changes use their own rules. The screen must not require all five for every change.
- Authorisation. Write: `authorize` `{commercial: id or null}`.
- Every write sends `expected_revision` and `case_revision` (DC-1) and handles the 201 response and revision conflicts. Roles and actions come from the line read (`can_authorize`, `roles[]`, `verdicts[]`), not `you_can_act` (DC-5).

Out of part 1 (F-112B):
- Notice and go-live note documents: `document_review`, `documents[]`, `jobs[]`, receipts.
- Execution evidence: `execution` with its four typed steps.
- Close with PM and client signatures: `close`, including mode `owner_applicability`.
- `operate_delivery` (retry or cancel) and `restart`.
- The `change-milestone-link` call and the `GET /projects/{case_id}/change-versions/{version_id}` read.

Shown as hidden, not invented (D-182):
- "Authorised by Kemi Adebayo · change authoriser · 13 Nov 10:00" as a typed record. `authorize` takes no person or time. Show only what `GET change` returns.
- Tola's step-by-step card, `agent_note` and the cited records (DC-3). Show a one-line status and times only.
- Any "milestone scope now includes ..." line.
- Unknown money and effort stay unknown, never 0.

D-1 (turning an upload into an `evidence_id`) applies to the proof upload on `assess`, `decide` and `capture`. If the evidence path is not available for a change proof, build on the best reading of the contract, flag it, and list the write as held.

## Risk
High. `authorize` commits a commercial and scope decision, and `decide` and `assess` feed it. Both are role-gated (`can_authorize`, `roles[]`) and revision-gated, and they are hard to undo. The part 2 notice would be an external client message and `close` records signatures. Those stay out of this PR. SURFACES are ui, api, auth (role-gated actions) and product-decision (authorising a change). It is a new flow, so product acceptance is required. The merge goes to the design engineer's batch, not the D-180/D-184 routine route.
