DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-115 is part 1 of the SCR-46 hypercare split: the read states and the background pause only, about 6 boards. Part 2 (F-115B) holds all the writes.
- The backend answers D-1, D-18 and D-19 settle the data, so no client question is open. The 13 Nov design approval and the v9 architecture cover this screen.
- Wait: the shared line adapter F-85 (lane C, PR #101) is not on main yet. The coordinator holds the builder until it merges. This delays the start only. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Hypercare moves from the generic workspace read to its own `stability` and `stability/events` reads. This is a read-only contract change.
- The pause and continue control is internal and routine, so the PR can merge under D-180/D-184.

## Scope
Binding for the spec writer. Task FE-CONNECT-1, screen SCR-46, line `delivery_hypercare`.

In scope:
- Read `GET /work/{id}/stability`.
- Draw four states: Setup-needed (`criteria: null`, `can_draft_criteria`), evaluating (`qualified` null), qualified (`qualified` true) and not-met (`qualified` false).
- Show the per-criterion MET / NOT MET result for time, confirmation, metric and issue criteria (D-19).
- Show `checks[]` (release, acceptance, stability; ready or held, with a finding) and `findings[]`.
- List the observations as metric readings by owner (Engineering or Infrastructure).
- Show open issues separately from the readings (D-18), using the issue record and `issue_clearance`.
- Read the release evidence and acceptance state from `stability/events`. This is display only.
- Add the pause and continue control for Tola's evaluation: `POST /work/{id}/background` (202).
- Write the line adapter mapping inside the F-115 feature folder.

Rules to follow:
- DC-1: integer `work_id` and uuid `case_id`. The background POST needs both `expected_revision` and `case_revision`.
- DC-5: allowed actions come from the line read.
- D-185: build what the boards draw wherever API 1.24.0 supplies the data.
- D-182: hide what the API does not supply, and say so. This covers Tola's step cards (DC-3), "Day 10 of 30" (live has `minimum_hours` and `due_at` only) and "Log an issue" from this screen.
- Never invent a day count, attempt counts or amounts. Unknown stays unknown.

Out of scope:
- All writes other than the background pause. These are the observation log, the release record, the criteria setup and its review. They belong to F-115B.
- Acceptance actions (SCR-45, F-114).
- SCR-47 archive.
- Any change to the shared frame in `frontend/src/features/workspace` (lane C). If a frame change is needed, name it as a dependency on lane C.

## Risk
Medium. The work is read-only apart from one internal pause call, but it is cross-layer. It adds a new adapter and moves from one generic read to dedicated endpoints (`stability`, `stability/events`). It touches no money, identity or data migration. Sources are `screens-d-delivery-issues-escalation.md` SCR-46 and backend answers D-1, D-18 and D-19. The release record and evidence writes that gate go-live are the high-risk part. They sit in F-115B, which goes to the design engineer's merge batch. Product acceptance is required because the client sees the changed hypercare states and metric/issue presentation.
