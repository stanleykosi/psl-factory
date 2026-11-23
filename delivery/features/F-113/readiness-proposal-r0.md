DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-113 covers SCR-43 (delivery overview, read only) and SCR-44 (release gates, with writes) across 14 boards. The lane D limit is about 8 boards, and it mixes a read-only screen with a decision and record screen, so it is not one reviewable PR.
- The backend answers are enough to build both parts. D-10 and D-11 give the overview with six stable line keys. D-12 to D-14 settle the planning decision, readiness trigger and status values.
- Both screens use the line adapter from F-85 (lane C, PR #101), which is not on main. Part 1 can be composed in the frontend from the overview read. Part 2 needs the adapter merged first (DC-2).
- I did not check the architecture package's approval status or the design approval (`design.py check`) for these boards. The feature record has no acceptance criteria and no brief. Confirm both before the split features are re-submitted.
- Decision: split F-113 into part 1 and part 2. Re-submit each for readiness.

## Scope
Binding for the spec writer. Task FE-CONNECT-1. D-185 applies: build what the boards draw where API 1.24.0 supplies the data, and hide what it does not (D-182 rule).

**Split**
- **F-113a, SCR-43 delivery overview (read only, about 5 boards).**
  - Endpoint: `GET /projects/{case_id}/delivery-overview`.
  - Draw the six lines in order, keyed by `delivery-release/v1`, `delivery-go-live/v1`, `delivery-hypercare/v1`, `delivery-handover/v1`, `delivery-archive/v1` and `delivery-closure/v1`. Show the latest visible work, its reference, state, date and link.
  - A line with no work is "not started", with empty fields.
  - Open a line by linking to its `/work/{id}`.
  - Closure hold reasons come from `closure-checklist` (`ready_to_prepare`, `checks[]`).
  - Hide the parts the API does not supply. These are the gate wording and tone, "3 of 6 done", the DLV file number and Tola's check and "Next" sentence (DC-3). Do not count "done" as a frontend rule unless the board is confirmed.
  - No writes. Replace the `DeliveryTab.tsx` and `model.ts` mock reads (`delivery[]`, `delivery_summary`, `delivery_agent`).
- **F-113b, SCR-44 release gates (about 9 boards).**
  - Depends on F-85 being merged. The adapter turns each line read into sections and the line commands into steps. Do not change the shared frame (DC-2).
  - Reads:
    - `GET /work/{id}/release-register`: phases Initiation, Planning, Execution and Closure; statuses unknown, stale_scope, current, restricted_or_authority_changed and unknown_or_stale.
    - `GET /work/{id}/planning-exit`.
    - `GET .../client-testing`.
    - `GET /setup/{case}/decision-appointments`, for the owner-needed state.
  - Writes:
    - `POST planning-exit` (approve or return/reject) with the current packet and `expected_revision` and `case_revision` (DC-1). D-12: the named PMO Lead approves directly, the note is enough, and the server enforces the packet and independent gates.
    - `POST release-register`, including `prepare_readiness` (D-13, a PM click) and the `observe_release` evidence (D-1: a checked PDF on that action).
  - Allowed actions come from the read's `actions[]`, never from a frontend rule (D-14, DC-5).
  - Hide the "Decide" panel figures (stages built, open issues by severity, changes since SOW) and Tola's check.
  - Client-testing writes and the workaround link are not drawn by the boards. Hold them as a later increment unless the design engineer says otherwise.

## Risk
F-113a is low-risk: it is a read-only screen on one new endpoint. F-113b is medium to high on merge route: it records the planning-exit approval and the release register, which are governance decisions and a release record. They carry authority checks, revision and packet concurrency, and evidence upload (surfaces api, auth, contract-change, product-decision). No money or payroll is involved, but the approval is hard to undo, so F-113b should go through the design engineer's merge batch. Product acceptance is required because the flow and copy change from the mock.
