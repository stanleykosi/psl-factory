# F-78 readiness answers (r3)

- D-187 (23 Nov 2026, batch answer B31): "Handoff only, Finance starts it". Marking a milestone complete only queues the Finance handoff; it never starts or drafts an invoice. Finance starts the invoice.
- PSL (BUILD-DECISIONS.md on main b8542c79): "The PMO Lead reviews the project and confirms the exact milestone before completion is recorded."
- LB-2 (backend, open): whether POST milestones/completions enforces PMO Lead authority. Per LANES.md, build on the best reading: the control shows only when the options read gives `can_complete: true`, the server decides authority, and the UI never infers a role; flag it in the spec and PR. No UI role check is invented.
- Standing answers otherwise as in delivery/features/F-73/coordinator-answers.md; build against API 1.24.0 (D-185).

## B32 answered (24 Nov 2026, D-195)
The design engineer accepted the recommended option for B32: "All recommended options accepted: … B32 …" (delivery/connect/questions-batch.md, "Answers, batch 4"). Build option 1 of each board change in spec.md "Conflicts with the boards"; option 2 (stage number through the link) is not taken. Product acceptance for these board changes is recorded under D-184 from this answer. F-78 is high risk (it records a completion, which queues the Finance handoff), so its merge still goes to merge-batch.md for the design engineer.

## Batch 5 confirmed (24 Nov 2026, D-202)
The design engineer, in chat, relayed by the main coordinator (records 2d8816cc): "Accept all recs". This covers F-78 batch 5, option 1 (accept all), the same answer D-195 recorded above.
