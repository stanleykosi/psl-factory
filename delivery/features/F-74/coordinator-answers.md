# F-74 readiness answers

Coordinator answers (lane B, 23 Nov 2026, under D-180 and delivery/connect/LANES.md):
- Design-engineer questions are batched in delivery/connect/questions-batch.md (lane B, items listed below). Per LANES.md step 2 the build does not wait: it uses the recommended option as its default, the spec names each one, and product acceptance (required) confirms or changes it.
- Backend questions: per LANES.md, build on the best reading of the live contract and flag it in the spec and the PR; where there is no defensible reading, hold that one write or entry path, show it disabled with its reason, and list it. Do not invent values.
- The architecture task FE-CONNECT-1 is the task id LANES.md prescribes for connecting any already-built screen in this push (D-180); this is the explicit exception, not a gap.
- Design gates: the screen is already built and approved on its boards; this feature only changes the data source. Unresolved v9 view gates are covered the same way as F-56/F-57.
- Scope decision (coordinator): F-74 is your proposed F-74a, F-74b and the read half of F-74d in one feature: the Setup workspace picker frame, rules and delegation reads, and the templates read. All writes (typed drafts, review, delegation drafts, template replacement) are held in this release, shown disabled with their reason, until B-22, B-24 and B-25 are answered and the draft-then-review design is approved. No other feature id is created.
- Q1: batched as B1 (recommended: Setup always opens on a chosen workspace).
- Q2: batched as B2 (recommended: simple picker in the Setup header, workspace kept in the address).
- Q3: batched as B3 (recommended: reads only, edit controls disabled with the reason).
- Q4: backend; it holds the writes, as above.
