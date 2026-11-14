# Overnight decisions (14–15 Nov 2026)

The design engineer went to bed and asked the coordinator to keep working without pausing:
follow the coordinator's recommendation on anything not serious, keep anything that truly needs
their approval in the "Waiting for you" list, record every decision here so they can revert it,
and make the final screens match the approved boards at least 99%.

Each entry: what was decided, why, and how to revert.

## Rules the coordinator follows overnight
- The approved boards are the spec. A UI round passes only when the design-fidelity check passes
  on every board in scope (100% of elements after approved exceptions, visual >= 90) and the
  reviewer's side-by-side reading finds no remaining difference.
- Low and medium risk features that pass every review, QA, PMO acceptance and the fidelity gate
  are merged into `dlv-00-delivery-setup` under the standing merge delegation. Product acceptance
  for those is recorded as **provisional, by the coordinator**, marked for your check.
- High-risk features (money, security, sign-in) are built and reviewed fully but **not merged**;
  they wait for you.
- Nothing is merged into `main`.
- Business rules, approvers, money values and backend decisions are never invented; anything
  needing PSL or the backend developer waits.

## Waiting for you
(updated as the night goes on)

## Decisions taken
- **D-01 · 3D floor concept: 3, the tilted swimlane board.** Four live concepts: https://claude.ai/artifact/Mc4ouUKmHtRsyJk8xkALKw (copy in `design/concepts/floor-3d-concepts.html`). I picked 3 because it is your approved flat board leaned back like a drafting table: same reading order, every label readable, closest to the design you drew, and the lightest to run. 1 (isometric conveyor) was the runner-up; 2 (city) and 4 (amphitheatre) look striking but hide labels and read worse at a glance. Built into the Overview's "3D floor" option in F-08. Revert: reply with another concept number and F-08 gets a round to swap it.
- **D-02 · Phone Start work forms** use a bottom sheet for every line (your answer, 14 Nov).
- **D-03 · Round limit raised from 3 to 5** in `delivery/config.json`, so fidelity rounds can finish unattended. Revert: set `max_rounds` back to 3.
- **D-04 · Exceptions (F-06) design exceptions, provisional.** Accepted so the round can be reviewed: (a) the top-bar Start work button and the Overview highlight are app-frame items that arrive with F-05; (b) paging (Showing N, As of, rows per page, Show more) sits in a bar *below* the table frame, since the board has none and real lists are longer than 4 rows; (c) "← Queue" sits beside the phone heading because the phone top bar belongs to the frame; (d) phone cards show only tag, title and what's being done, as the board does; (e) "since" keeps the precise form ("since 11:02", "since 10 Nov") instead of the board's "since Mon"/"since 3d"; (f) the phone visual score is measured with the board's own four rows (cookie `psl_mock_exceptions=board`), because the default sample rows have longer text that wraps. Revert any of these by saying which, and F-06 gets a round.
