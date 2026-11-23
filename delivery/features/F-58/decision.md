RECOMMENDATION: ESCALATE
COMMIT: 57ae81e83de4ca0de7560998684f6e419241185e
APPROVER: approver

## Summary
- F-58 adds sign-in, the plain error state and sign-out. It also repoints the shared signed-out state, which about 30 screens use.
- Round 2 gate, security, technical, UX, UI and QA reviews, and PMO acceptance all PASS on this head. Live QA covered the main journeys.
- Product acceptance is "Accept and merge" from the design engineer (D-183), recorded for this head.
- The diff is on the merge policy's always-human lists. The surfaces are auth, security and contract-change. It also touches `architecture/*` (the v9 package, model and sources) and changes 68 files, against a cap of 15.

## Why
The code and evidence look merge-ready, and the design engineer has already accepted it. The policy still sends auth work, `architecture/*` changes and a diff this large to a human, and the merge script would lower an AUTO_MERGE anyway. I am not putting my own sign-off on this. The human only needs to confirm that D-183 covers the merge.

## Acceptance criteria
1. Page and layout: met. The round-2 fidelity run covers all four boards. Coverage is 100% after the approved exceptions, and D-179 waives the visual scores.
2. Sign-in and error behaviour (empty fields, fixed wording, CSRF re-read, `safeNext`): met. 111 sign-in unit tests passed in the security review, and live QA matched.
3. Live behaviour (wrong password and unknown user return identical 422s, open redirect, remember cookie, token rotation, sign-out, not-admitted): met. QA ran these against the real stack.
4. Not proved live: 429, 500 and 503, the alert write after sign-in, and a second persona replacing the first name. Unit and mock tests cover them. I did not re-run anything myself.

## For the human
Decision needed: confirm that your D-183 "Accept and merge" is enough to merge F-58 (PR #100), given the auth surface, the architecture v9 files and 68 changed files. If it is, merge by hand or lift the file cap for this PR.

Files to look at:
- `frontend/src/features/sign-in/`
- `frontend/src/shell/signInNext.ts`
- `architecture/packages/v9/`
- `delivery/features/F-58/round-2/review-qa.md`

SEC-1-1 (sign-out does not clear the app's memory until a reload) stays a non-blocking follow-up.

## Merge record
- Human approval: the design engineer (hunchoweb), "Accept and merge", D-183, 23 Nov 2026, relayed by the main coordinator. Recorded as git.human_approval=approved.
- Pre-merge sync: origin/main (30 commits) merged into the branch cleanly as f3716842; `delivery/checks.sh` re-run on f3716842: exit 0, 158 test files, 3827 tests passed, lint, typecheck and build passed. CI (GitGuardian) passed on that head.
- Merge: `gh pr merge 100 --squash --match-head-commit f371684264973205ca669f1b5c49318f00269714`, merge commit 8f562602199901411810dd1f845dfc39145cb323, merged by hunchoweb.
- Follow-ups carried: SEC-1-1 (sign-out is an in-app move, not a fresh load), TECH-1-1 (mock 401 scenario on POST /session).
