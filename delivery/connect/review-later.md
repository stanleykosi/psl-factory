# Merged without review (D-210): review backlog

Each feature below was built, passed the GitHub Actions checks (lint, typecheck, unit tests, build, Django check) and was merged to main with no review agents, on the design engineer's instruction (D-210, 24 Nov 2026). Review each one later, either by the design engineer manually or by the factory from next week. Then close its record.

| Feature | PR | Merge sha | What it changed | Reviews done before D-210 | Still to review |
|---|---|---|---|---|---|
| F-78 mark a milestone complete (SCR-19) | #120 | f7aa2057 | the Mark complete page, the Milestones tab link, the empty completions state | gate, technical, security, QA, UX and UI PASS on 86e1a6cf (round 4) | PMO acceptance; UI-4-1 (empty-state look); live completion once LB-2 is fixed |
| F-119B closure and retrospective (SCR-33) | #119 | eddc1dc1 | retrospective record, versions, decisions and follow-ups, closure checklist strip; UX-5-1 phone Save bar fix | technical, UX, UI and QA PASS on 48221d25 | post-sync re-checks; PMO; live save/version proof (QA-2-1); QA-2-2, QA-2-3 (low) |
| F-103 cash forecast reads (SCR-56), D-202 simpler scope | #121 | 043fd0c7 | live forecast and group disclosure; forecast adapter registered in workspace/lines | gate PASS on 5086ecf9 | all lenses (technical, UX, UI, QA, PMO); proof link and month actuals still to add |
