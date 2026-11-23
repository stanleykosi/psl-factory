# F-73 readiness answers

Coordinator answers (lane B, 23 Nov 2026, under D-180 and delivery/connect/LANES.md):
- Design-engineer questions are batched in delivery/connect/questions-batch.md (lane B, items listed below). Per LANES.md step 2 the build does not wait: it uses the recommended option as its default, the spec names each one, and product acceptance (required) confirms or changes it.
- Backend questions: per LANES.md, build on the best reading of the live contract and flag it in the spec and the PR; where there is no defensible reading, hold that one write or entry path, show it disabled with its reason, and list it. Do not invent values.
- The architecture task FE-CONNECT-1 is the task id LANES.md prescribes for connecting any already-built screen in this push (D-180); this is the explicit exception, not a gap.
- Design gates: the screen is already built and approved on its boards; this feature only changes the data source. Unresolved v9 view gates are covered the same way as F-56/F-57.
- Scope decision (coordinator): F-73 is the client reads only (list and details). The add-billing-contact write is held in this release (shown disabled with its reason) until the evidence picker and backend question 1 (B-45) exist; it is not split into another feature id now.
- Q1: batched as B4 (recommended: hide owed, money panel and blocked lines).
- Q2: batched as B5 (recommended: group key in the route).
- Q3: answered by the scope decision above; also batched as B6.
- Q4: backend, not blocking the reads.
