DECISION: READY
RISK: high
SURFACES: ui, api
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-115B is part 2 of the SCR-46 hypercare split: the writes that F-115 leaves out. They are logging a stability observation with proof, recording the release with a checked PDF, and setting the criteria. About 6 boards, including `SCR-46-desktop-record`.
- The data and rules are settled by backend answers D-1 (proof), D-18 (structured metric reading by a named owner) and D-19 (per-criterion result, which F-115 already draws). No client question is open. The 13 Nov design approval and the v9 package cover the screen.
- Waits (build-start only, not blockers): F-115 must merge first, because F-115B adds its forms to F-115's adapter. F-85 (shared adapter) and F-87 (`LineAdapter.Actions` slot and `useWorkCommand`) must also be on main. Write the spec against F-85 and F-87.
- High risk: the release record and observations gate go-live and are hard to undo. The merge goes to the design engineer's merge batch, not D-180/D-184.
- Build on API 1.25.0 or later, reading the lane-d worktree contract.

## Scope
Binding for the spec writer. Task FE-CONNECT-1, screen SCR-46, line `delivery-hypercare/v1`.

In scope:
- Log an observation: `POST /work/{id}/stability` with `{configuration_id, owner (Engineering or Infrastructure), observed_at, confirmed, reference, evidence_id, metrics{...}, verify_sample?}` (201). The form shows only the approved metrics from `criteria.metrics` for the chosen owner, limited to the owners in `observation_owners[]`. It is a structured reading, never a free note (D-18). A free-form note may add context only if the contract has a field for it.
- Record the release: `POST /work/{id}/stability/events` with `action:"release"` and `{readiness_id, released_at, reference, evidence_id, note, environment, private_log_id}` (201). Offer it only when `can_record_release` is true. `readiness_id` comes from `readiness_ids[]`. The optional private log comes from `private_logs[]`.
- Proof follows D-1. The person uploads the file to the project, and the release proof goes through the release register's checked-PDF route on the release observation (`POST /work/{id}/release-register`, `observe_release`). The observation proof uses the stability action's own evidence field. Where an action has no proof route, the person chooses from the line read's `proofs[]` or `release_evidence[]`, with nothing preselected, and the button stays off when the list is empty. Never invent an evidence id. Use F-85's unconfirmed `fileToEvidence` only where neither route exists, and flag it.
- Set the criteria: `POST /work/{id}/stability/criteria` with `{case_revision, criteria, evidence_id, effective_from}` (201), shown only when `can_draft_criteria` is true. Review through `POST /setup/{case}/policy-configurations/{id}/review`, only where the line read or the policy configuration read says the viewer may review. No thresholds, owners or approvers are prefilled. The person types the criteria, and the form shows the live validation. If the contract does not tell the form who may review, hold the review step and list it.
- Show the criteria result after each write by re-reading `stability` and `stability/events`. Do not trust the 201 body alone. F-115 draws the result, and this feature adds nothing new to the display.
- Forms are an `XxxActions.tsx` (for example `HypercareActions.tsx`) against F-87's `LineActionsProps`, sent through `useWorkCommand`, with revision tokens and the idempotency key handled by F-87. Register it once F-87 is on main. Do not add the slot in `frontend/src/features/workspace`.
- Follow DC-1 (integer `work_id`, uuid `case_id`, `expected_revision` and `case_revision` as each endpoint's contract demands) and DC-5 (allowed actions come from the line read).
- Map errors per endpoint (409 stale, 403 `csrf_failed`, 422 field messages, 429 and 503). A failed write is never retried by itself and never shown as success. For an uncertain effect (network loss after send), re-read before offering a retry.

Rules:
- D-185: build what the boards draw wherever 1.25.0 supplies the data. Hide any part the API does not supply (D-182) and say so, including "Log an issue" from this screen.
- Unknown values stay unknown. Never invent metric values, attempt counts, amounts, approvers or a day count.
- Mock changes: record any change to `frontend/mock/finance*` or the payments fixtures in build.md for the coordinator. Expect none.

Out of scope:
- All read states, the pause and continue control and the issues list (F-115).
- Go-live acceptance (`action:"acceptance"`) from this screen. It stays with SCR-45 (F-114). Show its state only.
- SCR-47 archive, and any change to the shared frame in `frontend/src/features/workspace` (lane C). A frame need is named as a lane C dependency.
- Backend, contract and migrations.

Board conflicts for the coordinator to batch (each with options, recommendation first):
1. Release proof route. Options: (a) the release register `observe_release` with the checked PDF (recommended, D-1 names it); (b) `stability/events` `evidence_id` from an uploaded file. Context: both exist in the contract, and D-1 says the release register accepts the PDF.
2. Criteria drafting form. No board draws it. Options: (a) one plain form in the record panel, shown only when `can_draft_criteria` (recommended); (b) leave it to Setup and show text only; (c) hold until a board exists. Needs the design engineer's board either way.

## Risk
High. Observations and the release record feed the qualified result and the acceptance and closure gates, and a recorded release cannot be quietly undone (`stability/events` 201, `release-register` `observe_release`). Evidence upload (D-1) and the policy-configuration review (criteria) touch records that other decisions depend on, so the surfaces are ui and api, with the review step needing a deliberate authority check. No money or payroll is involved. Sources: `screens-d-delivery-issues-escalation.md` SCR-46, backend answers D-1, D-18 and D-19, the 1.25.0 contract paths `stability`, `stability/events`, `stability/criteria` and `release-register`, and F-115's spec as the binding part-1 boundary.
