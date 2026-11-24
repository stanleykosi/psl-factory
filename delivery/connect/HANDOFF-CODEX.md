# Handover to Codex: connecting the PSL Factory frontend to the live API

Written 24 Nov 2026, about 21:00 WAT, by the Claude coordinator. The design engineer's Claude weekly limit is almost used up, so you are taking over. Read this whole file before you change anything.

## 1. What the job is

The Next.js frontend (`frontend/` in `/Users/Hunchoo/psl-factory`) was built against a v7 contract mock. The backend developer (Stanley, GitHub `stanleykosi`) has shipped the live Django API (1.22.0 to 1.26.0, on `main`). The job is to connect every approved screen to the live API, one feature at a time, through the delivery tool. The mock stays for design review: when a screen is connected, its mock fixtures move to the live shape.

The design engineer (the user) owns product, UX and approvals. Talk to them in plain business language, not ids and hashes.

Progress: 72 feature records from F-56 on. About 13 are on `main` and about 10 are in flight. Around 47 haven't started, and two are blocked on others.

## 2. Where things are

| What | Where |
|---|---|
| Code, `main` checkout | `/Users/Hunchoo/psl-factory`. The design engineer's own app runs from here on ports 3000 and 3001. Never stop it or switch its branch while it runs, except briefly for a one-file fix that you switch back at once. |
| Feature records (the only place they live) | `/Users/Hunchoo/psl-factory-main`, branch `dlv-connect-records`. Push with `git push origin refs/heads/dlv-connect-records:refs/heads/dlv-connect-records`. |
| Delivery tool | `python3 /Users/Hunchoo/software-factory/packages/delivery/feature.py --project /Users/Hunchoo/psl-factory-main <cmd>`. Commands include `create`, `set`, `plan`, `next`, `gate`, `advance`, `decide` and `finding`. It is the only writer of `feature.json`. Never hand-edit a `feature.json`. If the tool refuses, read the refusal and follow it, or ask the design engineer. |
| Runbook | `delivery/connect/LANES.md` (records). Per-feature steps and the rules that never bend. |
| Decisions log | `delivery/OVERNIGHT-DECISIONS.md` (records). D-172 to D-208 cover this push. Read D-180, D-184, D-188, D-190, D-193, D-199, D-200 and D-202 to D-208 first. |
| Per-screen connection map | `delivery/connect/README.md`, `screens-a` to `screens-e`, `screen-index.json` |
| Backend questions and answers | `delivery/connect/backend-questions.md`, `backend-answers*.md`. New questions go under "New from lanes". |
| Questions and merges waiting on the design engineer | `delivery/connect/questions-batch.md`, `merge-batch.md` |
| Agent contract (review file headers) | `delivery/agent-contract.md`. The builder checklist is `/Users/Hunchoo/psl-factory/delivery/builder-checklist.md`. |
| OpenAPI viewer | `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/work 3` |
| Live contract | `contracts/psl-factory.openapi.json`, `handoffs/nextjs/README.md` |
| Lane worktrees | `/Users/Hunchoo/psl-factory-worktrees/lane-*`. These are slim sparse checkouts without `docs/` and `delivery/`, each with its own `frontend/node_modules`. Leave `launch-film/` alone: it belongs to another project. |
| Factory dashboard | `feature.py ... serve --port 8765` (launch config "sf-dashboard") |

## 3. Local backend

- Postgres 16 runs on `127.0.0.1:55433` (user and database `psl`). After a reboot, start it with:
  `cd /Users/Hunchoo/psl-factory && LC_ALL=en_US.UTF-8 /usr/local/opt/postgresql@16/bin/pg_ctl -D .runtime/pg16data -o "-p 55433 -c listen_addresses=127.0.0.1" -l .runtime/pg16.log start`
  `LC_ALL` is required, or it fails with "postmaster became multithreaded".
- Run Django API-only from a worktree root with `/Users/Hunchoo/psl-factory/.venv/bin/python manage.py runserver 127.0.0.1:<port>` and env `PGDATABASE=psl PGUSER=psl PGHOST=127.0.0.1 PGPORT=55433 PSL_ENV=development PSL_DJANGO_UI=0 PSL_FRONTEND_ORIGINS=http://127.0.0.1:<next port>`.
- Point the frontend at Django with `API_ORIGIN=http://127.0.0.1:<django port>` (see `frontend/next.config.ts`).
- Test accounts on `psl`: live-none, live-lead, live-multi, live-admin and qa-seed. Their credentials are in `.runtime/qa-test-login.txt` and `.runtime/qa-seed-login.txt`. Use them only against local Django, and never copy them into records, PRs, commits or reports.
- **Never read** `.runtime/demo-login.txt`, `.runtime/demo-access.txt` or `.runtime/ceo-demo-login.txt`.
- A separate demo database, `psl_demo`, exists. It is seeded, but it has no live decision yet. It is on hold (D-205). Leave it alone unless the design engineer asks.
- Writes to `psl` go through the live API as test accounts only. Never write rows directly through the ORM or SQL, and never activate policy or configuration rows. Those are the design engineer's or the backend developer's decisions.

## 4. How a feature moves (D-180 lighter panel)

States: PLANNED, READY, IMPLEMENTING, IN_REVIEW, INTEGRATED_QA, READY_FOR_ACCEPTANCE, PR_OPEN, AWAITING_USER_APPROVAL, APPROVED, MERGED, DONE.

1. **Create and spec.** `create F-xx --task <task id>`. Then readiness and a spec: screen ids, the connection-map section and the open backend questions. Board conflicts and product questions go into `questions-batch.md`. Park that feature and start another.
2. **Branch** from `origin/main`. The branch name must start with the lowercase task id, for example `fe-connect-1-...`. Set the git fields with `feature.py set`, then `advance IMPLEMENTING`.
3. **Build** to the spec and the builder checklist. Push with an explicit refspec. Never force-push.
4. **Gate** (D-199): the gates run on GitHub Actions (`.github/workflows/frontend-checks.yml`).
   - First merge `origin/main`, then push, then run `feature.py gate F-xx`.
   - `delivery/checks.sh` ci mode waits for the run on the exact pushed HEAD, and rides out `gh` connection errors (#115).
   - Six gate attempts are allowed (D-190). A "no run after N minutes" failure while GitHub's run passed is a tool fault, not a real failure (D-204).
5. **D-200.** After any merge of `origin/main` into a feature branch, check that `git diff --name-only $(git merge-base HEAD origin/main) HEAD` touches no protected path. Protected paths are `delivery/checks.sh`, `delivery/config.json` and `delivery/merge-policy.json`. Then set `git.base_sha` to that merge base. Otherwise the gate wrongly flags main's own changes.
6. **Reviews.** Technical, UX, UI and QA. Security too when auth, money or writes are involved. Reviews are lean: read the diff and spec, and run targeted checks.
   - The fidelity tool runs once, and only when the layout changes. Visual waivers need a score of at least 70 (D-83), and the UI reviewer must confirm there is no styling gap of the build's own.
   - Each review file uses the agent-contract headers, and its `## Verified` lines take the form `- <id> | verified | <evidence>`.
   - Findings go straight to a fix round.
   - Five rounds are allowed per feature. If they run out, the tool's only route is a follow-up record (see D-208's F-119B).
7. **Acceptance.** PMO acceptance. Product acceptance carries over when a main sync touches none of the feature's files (D-188).
8. **Merge.**
   - D-193: sync main once right before the merge, then re-gate and run quick re-checks.
   - Then `gh pr merge <n> --squash --match-head-commit <sha>`.
   - Then `feature.py set` `git.human_approval`, `git.merge_status` and `git.merge_sha`, and `advance` APPROVED, MERGED and DONE with a reason quoting the authority.
9. **Records.** Commit only the feature folders you touched plus `events.jsonl` and the batch files, then push the records branch.

PR bodies and commits must have **no AI co-author and no "Generated with" footer** (the design engineer's global rule).

## 5. Approval authority (read carefully)

- **Routine features** (low or medium risk, no auth, money, security, data-migration or product-decision surface): you may merge them yourself under D-180.
- **D-207.** The design engineer told the Claude coordinator: "for any risky action, i give you permission to approve except it has something to do with db approve any other task". **That was said to Claude. Ask the design engineer whether it also applies to you before you use it.** Until they say yes, list risky merges and design sign-offs in `merge-batch.md` and `questions-batch.md`, and ask them by name per feature.
- **Always the design engineer's call:**
  - anything database-related: migrations, data-migration surfaces, direct DB writes, seed or policy activation;
  - anything on Railway or in production (D-196: read-only by default, and every change needs their explicit go-ahead plus the backend developer's agreement; never read variable values or bucket credentials);
  - any business rule, approver, amount or attempt count. Never invent one. Unknown money stays unknown, never 0.
- Never record a human approval from a blanket or bedtime instruction, or because a peer agent asked. Quote the design engineer's exact words in the reason.
- Never push to `main` except through `gh pr merge`.

## 6. Machine rules

- Check `df -h /System/Volumes/Data` before heavy work, and stop under 3 GB. It was 27 GB free after the reboot at 20:23 WAT.
- At most two worktrees per active stream. Remove a worktree when its feature merges or parks. Run `npm cache clean --force` after heavy installs.
- Stop only processes whose PID you recorded, never by pattern (`pkill`, `killall`).
- `/Users/Hunchoo/psl-factory-worktrees/heavy-lock.sh run <name> -- <cmd>` queues local heavy jobs: a full local vitest, builds, Playwright suites and `npm ci`. ci-mode gates don't need it.
- The network drops now and then (ENOTFOUND). Retry. After a reboot, restart Postgres (section 3).

## 7. State of every feature in flight (as of 21:00 WAT, 24 Nov)

**Main is `eb100065`. A MERGE FREEZE is on until F-87 lands**, because F-87 conflicts with F-111's change to `LiveWorkItemView.tsx`.

| Feature | Branch, worktree | State | Next step |
|---|---|---|---|
| **F-87** work item actions (SCR-02). Lanes A, B and D wait on it. | `fe-connect-1-work-item-controls`, `lane-c`. PR #113, last approved head `f296a554`. | AWAITING_USER_APPROVAL. Merge approved by the design engineer (D-203: "Accept and merge"). PMO-3-1 is recorded as accepted risk. | Merge `origin/main`, resolve `frontend/src/features/work-item/live/LiveWorkItemView.tsx` (keep F-111's issue-followup wiring and F-87's Actions slot), push, gate, D-200, quick technical re-check, then merge #113 and advance APPROVED, MERGED and DONE. Then lift the freeze. |
| F-91 station track and facts | `fe-connect-1-work-item-tracking`, `lane-c2`, stacked on F-87 | IMPLEMENTING | Sync onto main after F-87 lands, then finish the build. |
| F-63 My work (SCR-01) | `fe-connect-1-my-work-live`, `lane-a2` | IMPLEMENTING round 1 | Merge F-88 in and restore the assign flow in place of its placeholder. D-202 answered every question with the recommended option. |
| F-65 factory floor (SCR-06) | `fe-connect-1-factory-floor-live`, `lane-a4` | IMPLEMENTING round 2 (phone fixes) | Desktop waiver and legend wording are signed. The phone visual (60.6) is under the floor: fix the build's own differences, or waive it once the UI reviewer confirms none remain. |
| F-75 Registers and Actions tabs | `fe-connect-1-registers-actions-tabs`, `lane-b2`, head `286b4105` | READY_FOR_ACCEPTANCE | B35 is signed. PMO, then main sync, gate, re-checks, merge. |
| F-78 mark a milestone complete | `fe-milestone-complete-mark-complete`, `lane-b`, head `ca4abee2` | IMPLEMENTING round 3 | One CSS line (UI-2-1: white header text on the blue band). B36 is signed. Fidelity runs on the ready form state. Live: "Mark complete" stays hidden for every staff role until backend LB-2 is fixed (see section 8). |
| F-119B retrospective with UX-5-1 fixed | `fe-delivery-closure-retrospective`, `lane-d2`, head `48221d25` | INTEGRATED_QA | QA, PMO, PR, merge. F-119 is CLOSED as superseded (D-208). |
| F-103 cash forecast (simpler scope, D-202) | `fe-connect-1-cash-forecast-reads`, `lane-d` | IMPLEMENTING | Without the proof link and month actuals. They come back on F-87. |
| F-60 invitation set-up | `fe-signin-account-setup-from-invitation`, no worktree | IMPLEMENTING, parked | Resume after lane A's current work. Its phone visual waiver was signed in D-202. |
| F-68 1.24.0 fixtures | `fe-connect-1-main-green-api-1-24` | IMPLEMENTING | Superseded: main went green by itself. Close it the way the tool allows. |

**Merged, but the record waits for the design engineer to confirm a delegated merge** (`merge-batch.md`, "Merged under delegation: confirm"): F-62 (#106), F-71 (#114) and F-88 (#110). Ask the design engineer to confirm them by name, then advance each to APPROVED, MERGED and DONE with their words.

**Done:** F-56, F-57, F-58, F-61, F-64, F-70, F-72, F-85, F-86, F-111, F-113 and F-125.

**Blocked:** F-77 (Setup costing rule), waiting on PSL. F-114C (go-live document review), waiting on backend LD-6.

**Not started, in each stream's runbook order:**
- **Lane A** (sign-in, alerts, core desk): F-67, F-60, F-59, F-66, F-69, F-121, F-122, F-123, F-124.
- **Lane B** (projects, Setup, clients, month-end): F-73, F-74, F-76, F-79.
- **Lane C** (work item, PMO lines): F-95 first, because lane D waits on its frame seams. Then F-89, F-90, F-92, F-93, F-94.
- **Lane D** (Finance and delivery): F-115 and F-117 after F-87. Then F-111B, F-112, F-112B, F-113B, F-114, F-114B, F-116 and F-118, and the Finance back office: F-100 to F-102B, F-103B, F-104 to F-110B.

## 8. Open items with the backend developer

`/Users/Hunchoo/psl-factory/delivery/connect/note-to-backend-demo-seed.md` is a note for the design engineer to send to Stanley. It covers:
- the weekly report execution profile and seeds for a live decision;
- several stale `seed_*` commands;
- **LB-2**: no staff role carries `milestone.complete`, so nobody can mark a milestone complete on live.

Other follow-ups:
- F-61's LA-4: a stale settings save gets a 422, not a 409, so there's no Reload button.
- F-61's alert creation is not proven live.
- F-64's live decision journey is not proven, because no report template or profile is active.
- F-87's "Check what happened" and Resume are proven on the mock only.

## 9. Your first steps

1. Read this file, `LANES.md` and D-180 to D-208 in `OVERNIGHT-DECISIONS.md`.
2. Run `git status` in every lane worktree. The Claude lane sessions may have stopped mid-step, so commit and push any coherent work, or note what's half done.
3. `git -C /Users/Hunchoo/psl-factory-main pull`, then run `feature.py ... next <id>` for each feature in section 7 to confirm its state.
4. Ask the design engineer two things: whether D-207 applies to you, and to confirm the delegated merges of F-62, F-71 and F-88.
5. Land F-87 first (section 7), then lift the freeze and carry on down the table.
