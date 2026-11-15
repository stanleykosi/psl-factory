# Coordinator handoff (15 Nov 2026, second session)

Read first: `delivery/OVERNIGHT-DECISIONS.md` ("Waiting for you" + decisions D-01…D-58). Feature state: `python3 /Users/Hunchoo/software-factory/packages/delivery/feature.py --project . status` and `next <F-id>`. Cost: `feature.py --project . cost`.

## Where things stand
- F-01 … F-16 and the follow-up fixes (PR #28, D-61) are merged into `dlv-00-delivery-setup`. `main` is untouched.
- **F-17 line workspace frame** (FE-WORKSPACE-FRAME, medium risk, contract proposal): round 5 of 5, IN_REVIEW, head f91bc63, worktree `../psl-factory-worktrees/f-17`. Design signed off at measured scores (D-59, D-62, D-63, D-65). Technical, UX and security passed in rounds 2–3; round 4 changed CSS only, round 5 changed records only.
- **F-18 RFP team input and outcome** (FE-M2B-RFP, high risk, client email): round 3, IN_REVIEW, head 9d0fc66, worktree `../psl-factory-worktrees/f-18`. Design signed off at measured scores (D-60, D-65). Technical, UX and security passed in round 2; round 3 changed phone CSS and one card line only.
- Local preview: `npm run dev -- -p 3000` in `frontend/` (mock on 4010).

## Rules in force
- Cost policy (D-64, replaces D-39): features hold at most ~8 boards; builders run on Sonnet except the first build of a high-risk feature (Opus); a builder runs the fidelity check once at the end of its round and doesn't chase gaps the design reviewer confirms are forced; later rounds re-run only the review lenses the diff touches; design review on Opus for a screen's first review, Sonnet when verifying fixes; QA on Opus; readiness, spec, approver, technical, UX and PMO on Sonnet; security on Opus only for high risk and only when the diff touches it. Spec writers list layout conflicts too. 2–3 builders at a time. Hand over to a fresh coordinator session every 2–3 features.
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
1. F-17 and F-18, lean (D-64): one Sonnet `reviewer-ui` per feature that only verifies F-17 UI-3-1 (round-4 fidelity files) and F-18 UI-2-1 and UX-2-1 (round-3 files), without re-running the full check. Re-use the passed technical/UX/security results; the tool lists them as pending on the new head, so tell each reviewer to read only the diff since its last pass and confirm. Then QA (Opus) and PMO acceptance (Sonnet), then the approver. Both wait for the design engineer's "merge" (F-17 has a contract proposal; F-18 is high risk). F-17 has no rounds left: anything blocking needs the design engineer to allow a 6th round or a follow-up.
2. Merge order: F-17 first, then rebase or merge F-18 onto it (both touch `WorkItemOverview.tsx` with a few lines).
3. Next v7 tasks with dependencies met, each kept to at most ~8 boards (split larger ones): FE-ASSISTANT, FE-SETUP-DELEGATION, FE-SETUP-TEMPLATES, FE-CLIENTS, FE-M3-PROJECT-TABS, FE-M3-REPORT; and, after F-17 merges, the line screens (FE-LINE-WEEKLY, FE-LINE-MINUTES, FE-ENGAGEMENT-PLANNING, FE-DELIVERY-*, FE-FIN-*).
4. Follow-up batch (Sonnet): My work tabs 48px → 44px (boards); F-17 "UNKNOWN · Unknown" doubled in the checklist chip; and the phone "← Setup" target once the design engineer answers.

## Waiting for the design engineer
- "Go" on three follow-up recommendations: leave the wordmark under 380px, keep the board's proof box wording (F-09 UX-3-2), and point phone "← Setup" at Setup rules until a phone Setup home is drawn.
- DE-5: the frame's "+ Start" in the phone bar (now also lowers SCR-22 phone and SCR-15 settings phone).
- "Merge" for F-17 and F-18 once QA and PMO pass.

## Waiting on others
- PSL: D-SIGNIN (sign-in, sign-out, account menu), D-ADMIN-AUTHORITY, D-PAYROLL-VISIBILITY, D-COSTING-RULE, D-CHANGE-DECIDERS, D-RECEIPT-ALLOCATION, D-SPEECH-INPUT, D-DECISION-VARIANTS (payment exception, CEO costing and CTO emergency decide boards).
- Backend developer: `needs_you` on notifications (D-53); a `waiting` line-status tone (D-46); `recorded.station` on responses (D-38); idempotency for E-RESPONSE and for Start work after leaving (PMO-0-2); duplicate proof by sha256; upload limits; permission checks before field checks; the PROPOSAL `presentation` and `decide_presentation` blocks.
- Backend developer, new from F-17/F-18: a section-page read for workspace paging; form prefill (current answer) and a deciding role on workspace steps; the "Try again" revision vs idempotency answer (F-17 TECH-1-4); a reused idempotency key with a different body must be refused; optional proof on "unknown" RFP outcomes; whether outcomes take several proof files; a colour field for row and lesson tags; the planning-packet agent; currency beyond NGN.
