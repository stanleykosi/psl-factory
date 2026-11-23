# Two-day API connection push: lane runbook (D-180, 23 Nov 2026)

Every lane coordinator follows this runbook. The design engineer chose it in D-180 (`delivery/OVERNIGHT-DECISIONS.md`): three parallel lanes, a lighter review panel, the coordinator merging routine work, and questions batched about twice a day. The goal is every approved screen connected to the live API 1.22.0 within two days.

## Where things are

| What | Where |
|---|---|
| Records project, the only place feature records live | `/Users/Hunchoo/psl-factory-main` (branch `dlv-connect-records`) |
| Feature tool | `python3 /Users/Hunchoo/software-factory/packages/delivery/feature.py --project /Users/Hunchoo/psl-factory-main …` |
| Coordinator procedure | `~/.claude/skills/delivery-workflow/SKILL.md` and `references/run.md` |
| Per-screen mapping | `delivery/connect/screens-*.md`, `README.md`, `backend-questions.md` (records project) |
| Operation viewer | `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/work 3` |
| Live contract and handoff | `contracts/psl-factory.openapi.json`, `handoffs/nextjs/README.md` |
| Builder checklist and agent contract | `/Users/Hunchoo/psl-factory/delivery/builder-checklist.md`, `/Users/Hunchoo/psl-factory-main/delivery/agent-contract.md` |
| Live backend for checks | Postgres 16 on `127.0.0.1:55433` (user and database `psl`, migrated; local test accounts live-none, live-lead, live-multi, live-admin). Run Django API-only from your lane worktree root with `/Users/Hunchoo/psl-factory/.venv/bin/python manage.py runserver 127.0.0.1:<your Django port>` and env `PGDATABASE=psl PGUSER=psl PGHOST=127.0.0.1 PGPORT=55433 PSL_ENV=development PSL_DJANGO_UI=0 PSL_FRONTEND_ORIGINS=http://127.0.0.1:<your next port>` |

## Lanes, worktrees and ports

| Lane | Worktree (slim, no docs/ or delivery/) | Feature ids | Next.js / mock | Django |
|---|---|---|---|---|
| A | `/Users/Hunchoo/psl-factory` (main checkout) while F-58 finishes, then `/Users/Hunchoo/psl-factory-worktrees/lane-a` | F-58 to F-69 | 4960 / 4961 | 8000 |
| B | `/Users/Hunchoo/psl-factory-worktrees/lane-b` | F-70 to F-84 | 4970 / 4971 | 8010 |
| C | `/Users/Hunchoo/psl-factory-worktrees/lane-c` | F-85 to F-99 | 4980 / 4981 | 8020 |
| D (added 23 Nov, D-186) | `/Users/Hunchoo/psl-factory-worktrees/lane-d` | F-100 to F-120 | 4990 / 4991 | 8030 |

The design engineer's own app runs on ports 3000 and 3001 from the main checkout. Never stop, restart or use it. Stop only the processes you start, by their own PIDs.

## Lane D scope (D-186)

Lane D takes the Finance line workspaces from lane B (SCR-32, 53, 54, 55, 56, 57, 58 and payroll SCR-09, 18, 37, 59), and the delivery lines from lane C (SCR-30, 31, 43, 44, 45, 46, 47, 48, 49, 33). Lane B keeps month-end and the payments list (SCR-36, SCR-20). Lane C keeps the PMO lines.

## Per feature

1. **Create.** `feature.py create F-xx --task <task id>`. Use `FE-CONNECT-1` to connect an already-built screen. Use the screen's own v7 task id for a screen that is not built yet (`architecture/packages/v9/tasks.csv`). Then set `outcome` in one plain sentence. Keep each feature to about 8 boards.
2. **Readiness, then spec** (Sonnet). Give the agents the screen ids, the connection-map section for each screen and the open backend questions. If the spec lists board conflicts or product questions, append them to `delivery/connect/questions-batch.md` under your lane heading. Each entry gets the feature, a numbered question, two or three options with the recommendation first, and one line of context. Park that feature and start the next one. Do not wait. The coordinator brings the batch to the design engineer and relays the answers.
3. **Branch.** In your worktree: `git fetch origin && git switch -c <task-id-lowercase>-<short-description> origin/main`. The tool requires the branch to start with the task id. Then set the git fields and advance to IMPLEMENTING.
4. **Build** (Sonnet builder, named `builder-F-xx`). Point it at the checklist, the spec, your ports and Django port, and these rules: run every command from your worktree's `frontend/`; no `npm ci` in builder turns; write `round-N/build.md` in the records project, never in the worktree; end with the worktree clean and pushed, with HEAD equal to the COMMIT line; no Co-Authored-By or AI footer; push with an explicit refspec.
5. **Gate.** `feature.py gate F-xx`. Its `checks.sh` runs `npm ci` in your worktree. Run `npm cache clean --force` after each gate to keep disk free. If the gate fails on a test your change does not touch, re-run once when the machine is quieter, then fix the real cause. Never weaken an assertion.
6. **Lighter review panel (D-180).** The tool still needs every routed lens on the head, so keep each lens lean:
   - Every reviewer reads the diff and the spec and runs only targeted checks.
   - Technical and QA run on Sonnet. Technical and security run on Opus when the risk is high.
   - The fidelity tool runs once, and only when the layout changes. Otherwise the UI reviewer checks the changed area at 1440 and 390.
   - No reviewer copies `frontend/` or runs `npm ci`.
   - Reviewers write their files in the records project, using the agent contract's exact header and `## Verified` line shapes (`- <id> | verified | <evidence>`).
   - Findings start a fix round right away, with no question to the design engineer.
7. **Acceptance.** PMO acceptance on Sonnet. When product acceptance is required, add it to the batch file and move on.
8. **Merge.** Open the PR with the `pr` skill format, with no AI footer, then run the approver and `feature.py decide`.
   - **Routine** (risk low or medium, no auth, payments, security, data-migration or product-decision surface): merge it yourself under D-180. First merge `origin/main` into the branch. If anything came in, re-run the gate. Then run `gh pr merge <n> --squash --match-head-commit <sha>`. Record `human_approval` as "delegated under D-180" in decision.md, then MERGED and DONE.
   - **Risky** (anything else, including a required product acceptance): leave it at AWAITING_USER_APPROVAL and list it in `delivery/connect/merge-batch.md` with the PR link, a one-line summary and the evidence. The coordinator batches these for the design engineer.
9. **Records.** Commit only your own feature folders, plus `events.jsonl` and the batch files, in the records project. Retry if `.git/index.lock` exists. Push with `git push origin refs/heads/dlv-connect-records:refs/heads/dlv-connect-records`, and retry on network errors.

## Rules that never bend

- Check `df -h /System/Volumes/Data` before you spawn any agent. Below 3 GB free, stop and tell the coordinator.
- Never invent business rules, approvers, attempt counts or amounts. Unknown money stays unknown, never 0.
- When a write needs an unanswered backend question (`backend-questions.md`), build it on the best reading of the contract and flag it in the spec and the PR, or hold that one write and list it. New backend questions go under "New from lanes" in `backend-questions.md`, with your lane letter, for example `LB-1`.
- Shared frontend files (`src/features/workspace/*`, `src/api/*`, `src/shell/*`, `src/components/*`): lane C owns the workspace frame and line adapter, and lane A owns the shell. Lane B takes a change in another lane's area only as a separate small commit after `git merge origin/main`, and says so in build.md.
- Never read `.runtime/demo-login.txt` or `.runtime/demo-access.txt`. Never force-push. Never push to main except through `gh pr merge`.
- At the end of every turn, report one line per feature: its state, PR, and what it waits on.
