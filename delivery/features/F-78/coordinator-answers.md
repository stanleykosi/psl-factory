# F-78 readiness answers (r3)

- D-187 (23 Nov 2026, batch answer B31): "Handoff only, Finance starts it". Marking a milestone complete only queues the Finance handoff; it never starts or drafts an invoice. Finance starts the invoice.
- PSL (BUILD-DECISIONS.md on main b8542c79): "The PMO Lead reviews the project and confirms the exact milestone before completion is recorded."
- LB-2 (backend, open): whether POST milestones/completions enforces PMO Lead authority. Per LANES.md, build on the best reading: the control shows only when the options read gives `can_complete: true`, the server decides authority, and the UI never infers a role; flag it in the spec and PR. No UI role check is invented.
- Standing answers otherwise as in delivery/features/F-73/coordinator-answers.md; build against API 1.24.0 (D-185).

## B32 answered (24 Nov 2026, D-195)
The design engineer accepted the recommended option for B32: "All recommended options accepted: … B32 …" (delivery/connect/questions-batch.md, "Answers, batch 4"). Build option 1 of each board change in spec.md "Conflicts with the boards"; option 2 (stage number through the link) is not taken. Product acceptance for these board changes is recorded under D-184 from this answer. F-78 is high risk (it records a completion, which queues the Finance handoff), so its merge still goes to merge-batch.md for the design engineer.

## Batch 5 confirmed (24 Nov 2026, D-202)
The design engineer, in chat, relayed by the main coordinator (records 2d8816cc): "Accept all recs". This covers F-78 batch 5, option 1 (accept all), the same answer D-195 recorded above.

## Carry-over fixes from F-71 (lane coordinator, 24 Nov 2026)
F-71 merges with three non-blocking items on the Milestones tab and the Money e2e that F-78 builds on. Fix them in F-78 as separate small commits named in build.md:
- QA-2-1: `frontend/e2e/money.spec.ts:85` still expects the old idle aside name "Choose an amount to see where it comes from."; round 2 (UI-1-3) made the head "Where a figure comes from" with the prompt as the body. Update the spec.
- TECH-2-1 / QA-2-2: the Proof button in MilestonesTab.tsx doesn't collapse on a second press, and `aria-expanded` dips to false during the re-read. Make it a real toggle with a steady `aria-expanded`.
(F-71 round-2/review-qa.md and review-technical.md.)

## LB-2 on live (24 Nov 2026, main coordinator)
LB-2 is the backend developer's to fix, through role mapping (the PMO Lead gets `milestone.complete`). It's on the design engineer's note for Stanley. F-78 builds to the contract, with "Mark complete" driven only by `can_complete`. In the PR and PMO evidence, record it as: "live: hidden for every staff role until LB-2 is fixed". It is not a frontend gap.

## B36 answered (24 Nov 2026, D-207)
The main coordinator approved B36 under D-207:
- (1) "HB-M2" is signed as board sample data.
- (2) The breadcrumb style, "← Lagoon Health" against the frame's back link, and the not-gating shell extras are signed as frame items.
- (2, not signed) The grey disabled "Mark complete". The answer: per D-202 batch 5 option 1, "Mark complete" shows on uncompleted rows only when the server allows it, with one hold line above the table. If the build shows a disabled button when can_complete is false, round 3 hides it and shows the hold line. If the build already hides it and only the board draws it grey, it's signed as a board difference.
  Lane B check: the round-2 UI review saw no button under holds or with no authority. The grey state is SCR-19's submit before a proof and the confirmation tick are chosen, so it is a form state, raised again with the coordinator.
- (3) A visual waiver for both runs is signed at whatever score round 3 leaves, if it's still under 90 and the UI reviewer confirms no styling gap of the build's own.
- B36 follow-up (main coordinator, D-207): the disabled submit before a proof and the tick is correct behaviour; keep it. The round-3 UI fidelity run captures the ready state (proof chosen, tick set) so it compares like with like against the board's filled blue button. Any score difference left from the disabled-until-ready state elsewhere is signed as a board state difference under D-207.
