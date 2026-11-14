# Coordinator handoff (15 Nov 2026)

Read first: `delivery/OVERNIGHT-DECISIONS.md` ("Waiting for you" + decisions D-01…D-39). Feature state: `python3 /Users/Hunchoo/software-factory/packages/delivery/feature.py --project . status` and `next <F-id>`. Cost: `feature.py --project . cost`.

## Rules in force
- Model policy (D-39): Opus only for a screen's first build, design (reviewer-ui) review and QA; Sonnet for fix rounds, small changes, readiness, spec, approver, technical/UX/PMO; security Opus only for high risk. 2–3 builders at a time.
- Disk: `df -h /System/Volumes/Data` before spawning; stop under 3 GB. Never link node_modules between worktrees (D-37). Reviewers never copy frontend/ or build.
- Design: board is the spec; fidelity tool gates UI review (100% coverage after exceptions, visual ≥ 90 at 1440 and 390). Review findings start a fix round without asking.
- Merge into dlv-00-delivery-setup only low-risk (no money, sign-in, security, contract, product decision) after all gates; everything else waits for the design engineer. Never main.
- Never read `.runtime/demo-access.txt`. No AI co-author trailers.

## In flight when this was written
- **F-09 Recording responses** — round 2, integrated QA running against review copy :4911/:4912 (worktree f-09). Next: PMO → provisional product acceptance → PR → approver (high risk → hold). D-32 phone fields held for the design engineer.
- **F-14 Work item design rebuild** — round 1 builder running (worktree f-14, ports 4501/4502). Next: gate → reviews (technical sonnet, UI opus, UX sonnet) → QA → PMO → PR; medium risk, ui only → can merge under delegation if all pass. After it merges, re-score F-09's SCR-02 boards.

## Next work
1. D-26: the same design rebuild for the decision page (F-04, SCR-03) — create F-15 like F-14.
2. Next v7 tasks with dependencies met: workspace frame, M2B RFP, Finance and Setup sub-slices; FE-ASSISTANT needs F-05 merged.
3. Follow-ups: F-12 QA-1-1 (D-27), F-11 TECH-3-1 / QA-3-1 / UX-3-1, D-21 Tola poses, F-06 preview on Overview after F-06 merges, F-07 pluralisation.

## Review copies running
F-06 :3611/:3612, F-08 :3811/:3812, F-11 :4111/:4112, F-12 :4211/:4212, F-09 :4911/:4912. Stop each once its PR is merged or closed.
