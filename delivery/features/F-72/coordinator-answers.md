# F-72 readiness answers

Coordinator answers (lane B, 23 Nov 2026, under D-180 and delivery/connect/LANES.md):
- Design-engineer questions are batched in delivery/connect/questions-batch.md (lane B, items listed below). Per LANES.md step 2 the build does not wait: it uses the recommended option as its default, the spec names each one, and product acceptance (required) confirms or changes it.
- Backend questions: per LANES.md, build on the best reading of the live contract and flag it in the spec and the PR; where there is no defensible reading, hold that one write or entry path, show it disabled with its reason, and list it. Do not invent values.
- The architecture task FE-CONNECT-1 is the task id LANES.md prescribes for connecting any already-built screen in this push (D-180); this is the explicit exception, not a gap.
- Design gates: the screen is already built and approved on its boards; this feature only changes the data source. Unresolved v9 view gates are covered the same way as F-56/F-57.
- Q1 (B-7, version_id): best reading of the contract; if the Documents tab row gives no defensible link to the version, the spec must say how the page is entered (for example from the work item that carries the document version) and flag it. Hold only the entry path that has no reading.
- Q2 (B-11, delegated): send false for an ordinary reviewer as the best reading, flagged in the spec and PR.
- Q3: batched as B7 (recommended: drop the parts with no live source).
- Q4: batched as B8 (recommended: approve and return, note required on approve, no reject yet).
