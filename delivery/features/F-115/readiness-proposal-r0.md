DECISION: NOT-READY
RISK: high
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-46 hypercare has 12 boards and is rated effort L in the connection map. That is too big for one reviewable PR, so it needs the split below.
- The backend answers are in hand (D-1, D-18, D-19), so no client question blocks it. The only gates are the split and the shared line adapter.
- The shared line adapter (F-85, lane C, PR #101) is not on main yet. Both parts depend on it, and F-115 must not change the shared frame.
- Hypercare moves from one generic workspace read to its own endpoints (`stability`, `stability/events`, `release-register`). Observations become metric readings by a named owner, not free-text notes.
- Part 1 is read-only and can merge as a routine change. Part 2 records releases and evidence, so it goes to the design engineer's merge batch.

## Scope
Binding for the spec writer. Build only part 1 under F-115. Part 2 becomes a new feature and needs its own readiness check.

Common to both parts:
- Task FE-CONNECT-1, screen SCR-46, line `delivery_hypercare`.
- Follow DC-1 (integer `work_id`, uuid `case_id`; writes need both `expected_revision` and `case_revision`) and DC-5 (allowed actions come from the line read).
- Follow D-185: build what the boards draw wherever API 1.24.0 supplies the data.
- Where the API supplies nothing for a board, hide that part (D-182) and say so. This covers Tola's step cards (DC-3), "Day 10 of 30" (live has `minimum_hours` and `due_at` only) and "Log an issue" from this screen.
- Do not invent a day count, attempt counts or amounts. Unknown stays unknown.

Part 1 (F-115, read states, about 6 boards):
- Read `GET /work/{id}/stability`.
- Draw the Setup-needed state (`criteria: null`, `can_draft_criteria`), the evaluating state (`qualified` null), the qualified state (`qualified` true) and the not-met state (`qualified` false).
- Show the per-criterion MET / NOT MET result that D-19 says the read now gives for each time, confirmation, metric and issue criterion.
- Show `checks[]` (release, acceptance, stability; ready or held, with a finding) and `findings[]`.
- List the observations as metric readings by owner (Engineering or Infrastructure).
- Show open issues separately from the readings, per D-18, using the issue record and `issue_clearance`.
- Read the release evidence and acceptance state from `stability/events`.
- Add the pause and continue control for Tola's evaluation (`POST /work/{id}/background`, 202). It is internal and routine.
- Write the line adapter mapping inside the F-115 feature folder.

Part 2 (new feature, about 6 boards, to be created):
- Log an observation: `POST /work/{id}/stability`, with a structured metric reading by a named owner, a time and a proof (D-18). It needs the evidence path from D-1.
- Record the release: `POST /work/{id}/stability/events` with `action:"release"`, a checked PDF on the actual release observation, and the optional private log. `release-register` `observe_release` is the alternative route.
- Set the criteria: `POST .../stability/criteria`, then `policy-configurations/{id}/review`.
- Acceptance from this screen (`action:"acceptance"`) stays with SCR-45 (F-114). Do not duplicate it here beyond showing its state.

Out of scope for both parts: SCR-45 sign-off, SCR-47 archive, and the shared frame in `frontend/src/features/workspace`.

## Risk
Part 1 alone is medium: it is read-only and cross-layer, with a new adapter and a reshaped read contract. It touches no money. The whole of F-115 is rated high because the release record, the evidence upload (D-1) and the acceptance state gate go-live and are hard to undo. The sources are `screens-d-delivery-issues-escalation.md` SCR-46 and backend answers D-1, D-18 and D-19. Whichever part holds the writes goes to the design engineer's merge batch.
