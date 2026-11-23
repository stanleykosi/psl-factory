# F-78 readiness answers (r3)

- D-187 (23 Nov 2026, batch answer B31): "Handoff only, Finance starts it". Marking a milestone complete only queues the Finance handoff; it never starts or drafts an invoice. Finance starts the invoice.
- PSL (BUILD-DECISIONS.md on main b8542c79): "The PMO Lead reviews the project and confirms the exact milestone before completion is recorded."
- LB-2 (backend, open): whether POST milestones/completions enforces PMO Lead authority. Per LANES.md, build on the best reading: the control shows only when the options read gives `can_complete: true`, the server decides authority, and the UI never infers a role; flag it in the spec and PR. No UI role check is invented.
- Standing answers otherwise as in delivery/features/F-73/coordinator-answers.md; build against API 1.24.0 (D-185).
