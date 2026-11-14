# Coordinator handoff (15 Nov 2026, end of day)

Read first: `delivery/OVERNIGHT-DECISIONS.md` ("Waiting for you" + decisions D-01…D-58). Feature state: `python3 /Users/Hunchoo/software-factory/packages/delivery/feature.py --project . status` and `next <F-id>`. Cost: `feature.py --project . cost`.

## Where things stand
- F-01 … F-16 are all merged into `dlv-00-delivery-setup` and recorded DONE. No open PRs, no feature worktrees, no review copies running. `main` is untouched.
- Merged today: #13 F-13 contract v7, #11 F-06 Exceptions, #14 F-08 Overview, #18 F-12 Alerts, #16 F-10 Finance month-end, #20 F-11 Setup rules, #21 F-09 Responses, #22 F-14 Work item, #23 F-05 Start work, #24 F-07 Projects, #25 e2e fixes, #26 F-15 Alert bell, #27 F-16 Decision page.
- Local preview for the design engineer: `npm run dev -- -p 3000` in `frontend/` (mock on 4010). Restart it after merges.

## Rules in force
- Model policy (D-39): Opus only for a screen's first build, design (reviewer-ui) review and QA; Sonnet for fix rounds, small changes, readiness, spec, approver, technical/UX/PMO; security Opus only for high risk. 2–3 builders at a time. The tool's plan still lists `ui haiku`: always spawn UI review on Opus.
- Disk: `df -h /System/Volumes/Data` before spawning; stop under 3 GB. Never link node_modules between worktrees (D-37). Reviewers never copy frontend/ or build.
- Design: the board is the spec; the fidelity tool gates UI review (100% coverage after exceptions, visual ≥ 90 at 1440 and 390). Exceptions and visual waivers need the design engineer's sign-off. Spec writers list board conflicts up front; bring them to the design engineer before building (worked well for F-15 and F-16).
- Review findings start a fix round without asking. Wait for all routed reviews, then one batched fix round.
- Merge into dlv-00 only low-risk work (no money, sign-in, security, contract or product decision) after all gates; everything else waits for the design engineer's "merge …". Never main.
- No AI co-author trailers and no "Generated with Claude Code" in commits or PRs (global rule).
- Never read `.runtime/demo-access.txt`. If a subagent reports a permission refusal, surface it to the design engineer; don't work around it.

## Merge recipe (keeps the board moving to Done)
1. Merge the current `origin/dlv-00-delivery-setup` into the branch; run `delivery/checks.sh`, plus the relevant e2e if the base brought frontend changes. Expect small integration test fixes when features overlap (frame buttons, shared mock ids, the bell's `/notifications` read — use `tests/bell-feed.ts`).
2. Push, open the PR (no footer), wait for GitGuardian (it may say "skipping" on merge-only commits), then `gh pr merge --merge --match-head-commit <sha>`.
3. Remove the merged worktree (clean and pushed) — the tool reads the head from it. Then set pr_url/pr_number/ci_status, `advance PR_OPEN`, `decide`, set human_approval/merge_status/merge_sha, and advance AWAITING_USER_APPROVAL → APPROVED → MERGED → DONE.
4. Start shared review copies with `FRAME_FIXTURES=1` (as playwright.config.ts does) or two frame e2e specs fail. Retry pushes; the network drops often.

## Next work, in order
1. Small follow-ups (one Sonnet fix branch, low risk):
   - F-16 UI-2-1: "Paid is tracked separately" twice on phone done.
   - F-07: "1 PROJECTS" pluralisation; stale contract-body stripping in mock-contract.test.ts.
   - F-15 TECH-2-1: focus flag after same-page navigation; narrow wordmark size below 380px.
   - F-14 UI-4-1: secondary button above the main action (owner/setup-needed desktop); QA-4-1: W-1711 reconcile mock fixtures.
   - F-12 QA-1-1: phone warning under the pinned Save bar. F-09 UX-3-2: proof box wording. F-11 TECH-3-1 / QA-3-1 / UX-3-1. D-21 Tola poses.
2. Next v7 tasks with dependencies met (architecture/packages/v7/tasks.csv): FE-WORKSPACE-FRAME, FE-M2B-RFP, the Finance and Setup sub-slices, FE-ASSISTANT (F-05 is merged). Create features as capacity allows.
3. DE-5 for the design engineer: the frame's "+ Start" in the phone bar costs about 1.7 visual points on every phone board.

## Waiting on others
- PSL: D-SIGNIN (sign-in, sign-out, account menu), D-ADMIN-AUTHORITY, D-PAYROLL-VISIBILITY, D-COSTING-RULE, D-CHANGE-DECIDERS, D-RECEIPT-ALLOCATION, D-SPEECH-INPUT, D-DECISION-VARIANTS (payment exception, CEO costing and CTO emergency decide boards).
- Backend developer: `needs_you` on notifications (D-53); a `waiting` line-status tone (D-46); `recorded.station` on responses (D-38); idempotency for E-RESPONSE and for Start work after leaving (PMO-0-2); duplicate proof by sha256; upload limits; permission checks before field checks; the PROPOSAL `presentation` and `decide_presentation` blocks.
