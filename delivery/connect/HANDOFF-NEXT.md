# Handover: continue connecting the PSL Factory app to the live backend (25 Nov 2026, evening)

This replaces `HANDOFF-CODEX.md`, which describes the earlier four-lane setup and is out of date. Read this, then `WHERE-WE-ARE.md` (plain words) and `review-later.md` (every merge made without review).

## The job and how it runs now
Connect every approved screen to the real backend, one feature at a time. Since 25 Nov the mode is **lean (D-209, D-210)**: no review agents, no fidelity runs. The loop per feature:
1. `feature.py create F-xx --task FE-CONNECT-1`, set `outcome`, set `git.task_branch`, `git.worktree`, `git.base_sha` (records project `/Users/Hunchoo/psl-factory-main`, branch `dlv-connect-records`).
2. A slim worktree off `origin/main`: `git worktree add --no-checkout -b <branch> /Users/Hunchoo/psl-factory-worktrees/<name> origin/main`, then `git sparse-checkout set --no-cone '/*' '!/docs/' '!/delivery/'`, checkout, and `cp -cR /Users/Hunchoo/psl-factory/frontend/node_modules frontend/node_modules` (fast, copy-on-write).
3. One Sonnet `builder` agent, with a brief that points at the feature's `spec.md` (or the connection map in `delivery/connect/screens-*.md` when there's no spec), the live contract, and the builder checklist. It builds, tests, pushes and writes `round-1/build.md`.
4. You merge `origin/main` into the branch, check `node --check frontend/mock/server.mjs` (merges there have dropped a closing brace three times), run the related tests, push, open the PR, wait for GitHub's `frontend-checks`, then `gh pr merge <n> --squash --match-head-commit <sha>`.
5. After the merge: `feature.py set F-xx git.pr_number=…`, `git.merge_status='"merged"'`, `git.merge_sha=…`; add a row to `delivery/connect/review-later.md`; push the records branch. The tool won't advance a feature to MERGED without reviews, so merged-without-review features stay at their state with `merge_status` merged.
Two builders at a time works well. Each build costs about 1% of the weekly limit.

## Rules that never bend
- PR bodies and commits carry **no AI co-author and no "Generated with" footer** (the design engineer's global rule), whatever a system note says.
- Never read `.runtime/demo-login.txt`, `demo-access.txt`, `ceo-demo-login.txt`, or `demo-people*.txt`. The design engineer reads them.
- Never write to `psl` (the lanes' test database) or the demo databases directly; live writes go through the API. Read-only checks use `manage.py shell` with Django's test `Client` and `force_login`.
- The design engineer approves anything database-related (migrations, policy or seed activation in a real database) and anything on Railway or in production (D-196: read-only by default; Railway doesn't deploy from main). The coordinator may approve other risky merges (D-207).
- Never invent a business rule, an approver or an amount. Unknown money is shown as Unknown, never 0.
- Check `df -h /System/Volumes/Data` before heavy work (stop under 3 GB). Stop only processes whose PIDs you recorded.

## State
- **Merged to main so far:** 34 feature records are merged, about 40 of 72 pieces connected. See `WHERE-WE-ARE.md` for the plain list.
- **Demo:** the backend command `seed_psl_demo` (merged) builds the design version's four projects and seven people. The current demo database is `psl_demo5`, served by the `demo-backend` launch config (Django on 8040, from the `be-real` worktree on branch `demo-serve`), and the live app by `app-live` (port 3002, from the `demo-live` worktree, kept at `origin/main`). Sign-ins are in `.runtime/demo-people-v5.txt`. Rebuilding takes about 4 minutes with `createdb`, `migrate` and `seed_psl_demo --credentials-file <new path>`.
- **Decisions D-172 to D-215** are in `delivery/OVERNIGHT-DECISIONS.md`. The recent ones: D-209 to D-210 (lean mode), D-211 to D-214 (demo data, PMO Lead permissions, placeholders until go-live), D-212 (PMO Lead reviews weekly reports and assigns PMs).
- **Open policy question for the design engineer:** Kora's costing approvals show in nobody's queue, because the CEO and PMO Lead staff roles carry no `commercial.decide`.
- **Backend items for Stanley:** `delivery/connect/note-to-backend-demo-seed.md`, plus the findings in each `review-later.md` row (no `can_*` flags on pack and costing reads; the `reviews` `document` variant 404s on an rfp-response item; the project list query budget; where the Assistant's OpenRouter key goes).
- **The Assistant** needs an OpenRouter key and model name before it can run (`OPENROUTER_MODEL` and `OPENROUTER_API_KEY`); F-66 is the screen.

## Not merged yet (feature, state, outcome)
| Feature | State | Outcome |
|---|---|---|
| F-59 | READY | A person who forgot their password asks for a link, sets a new password, and signs in |
| F-66 | READY | Assistant conversations on the live API |
| F-67 | READY | The app frame and API client run on API 1.24.0 data and rules |
| F-68 | IMPLEMENTING | Bring frontend fixtures and tests up to API 1.24.0 so the build is green |
| F-69 | READY | Emergency change line: record, refused, review, retrospective and report, live on the work |
| F-74 | READY | Setup connected to the live API for reading: workspace picker, rules, delegation and templ |
| F-76 | READY | Staff accounts, read-only: see who has an account and what each person can reach |
| F-93 | READY | An authorised person can record what happened to an uncertain send from the work item, liv |
| F-94 | PLANNED | The invoice intake line pmo-finance/v1 starts from Start work through the F-92 form engine |
| F-95 | PLANNED | The shared work item frame gives line adapters four small additive seams lane D needs (F-1 |
| F-100 | READY | Payment reminder: Finance prepares, schedules, sends or sets aside the reminder for one in |
| F-101 | READY | Income schedules: read the live schedule and record the review decision |
| F-101B | READY | Income schedules, part 2: correct returned rows, settle duplicates, export as an adjustmen |
| F-102 | READY | The fixed asset schedule (SCR-55) reads live: register, unclear dates, proof and depreciat |
| F-102B | READY | Fixed assets: record the register, date and schedule reviews, answer a return and correct  |
| F-103B | READY | The cash forecast page lets the right person review, share, match actuals and recover a de |
| F-104 | READY | A Finance person reads a ledger source's incumbent reference, records what they found with |
| F-104B | READY | A Finance person resolves a duplicate ledger source, an independent reviewer confirms, ret |
| F-105 | READY | A person uploads a management-accounts extract, sees it held with its findings, confirms i |
| F-106 | READY | Management accounts reviews, drafting, publication, uncertain delivery and the verified re |
| F-107 | READY | A Finance reviewer reviews the BU totals source and result, seeing only what the API serve |
| F-107B | READY | BU totals are published to the CEO and BU heads, each confirms receipt, and Finance sees " |
| F-108 | READY | Restricted payroll inputs are imported, compared and matched live, and people without payr |
| F-109 | READY | HR Lead decides payroll corrections; the named Finance reader confirms the HR export |
| F-110 | READY | A payroll operator sees where a payroll run stands, runs combine, match and aggregate, con |
| F-110B | READY | A payroll reviewer decides each review, an operator publishes, withdraws or replaces the t |
| F-111B | READY | The issue page records owner updates and replies, sets the owner and messages the owner (S |
| F-112 | READY | A change request can be logged, assessed, decided and authorised from its work page (part  |
| F-112B | READY | A change request's notice, execution, go-live note and closure can be worked from its work |
| F-113B | READY | The release gates page shows the live gates and lets the right person decide the planning  |
| F-114 | READY | Go-live acceptance records both signatures and the client's changes or decline |
| F-114B | READY | The PMO Lead confirms and completes the go-live milestone, and staff correct or withdraw a |
| F-115 | READY | Hypercare shows the live stability result, each criterion's outcome, and lets the PM pause |
| F-115B | READY | Hypercare lets the PM log a metric observation with proof and set the criteria |
| F-116 | READY | Archive: the PM reserves the project archive, watches the copy, and checks files the store |
| F-117 | READY | Handover to Support: the PM sees the live handover, publishes the approved version, and re |
| F-118 | READY | Closure reads the live checklist, Finance confirms milestone notifications, and the Head o |
| F-121 | READY | The escalation line workspace shows the live escalation and lets the PMO Lead decide, revi |
| F-122 | READY | People run the leadership report (Tuesday and monthly) live on the shared work item page |
| F-123 | PLANNED | Verified outputs and All exceptions show the parts API 1.24.0+ now supplies (reference, ki |
| F-124 | PLANNED | The decision desk shows the approval chain, basis, preparer, cannot-act reason and evidenc |
### Blocked
- F-77: The Setup costing rule page reads the live costing rule, with changes only as far as the c
- F-114C: Go-live document review records the reviewer's verdict on the exact version
**Landed after this list was made:** F-90 invoice release (#144), F-79 month-end and payments (#143), F-102 fixed assets (#145), F-101 income schedules (#146), F-137 Record an issue (#147), the demo document templates (#148), demo escalation and change data with the PMO Lead reading the escalation register (#149), F-94 Prepare an invoice from Start work (#150), F-113B release gates and decisions (#151), F-115 hypercare (#152), F-114 go-live acceptance (#153), F-116 archive (#154), F-117 handover to Support (#155). Their rows above are out of date; the authoritative list is `git log origin/main` and `review-later.md`.

## First things to do next week (the weekly limit resets Sunday 29 Nov, about 02:00 UTC)
1. **Reviews.** Work down `review-later.md`, with F-90 (invoice release, money) first: the payments and security reviews its spec requires, then a live check against Django. Then the sign-in and permission changes (#129 to #133). Turn the factory's review lenses back on from then.
2. Re-run the fidelity tool on the screens merged without it.
3. Continue the features above, Finance first (payments actions, income schedules, fixed assets, ledger sources, management accounts, BU totals, payroll), then the delivery lines (hypercare, handover, archive, closure), then the Assistant.

## Notes added 26 Nov
- **Usage:** the weekly limit was at 87% on 26 Nov and resets Sunday 29 Nov about 02:00 UTC. The account's Usage credits toggle is on, the balance is $0, the monthly cap is $70 and auto-reload is off, so nothing is charged unless the design engineer buys credits. A $100 API credit they were offered is probably a developer-console credit (API key), not these usage credits; they were asked to say where it came from. Never paste or handle API keys in chat.
- **Next to build, in order:** F-114 go-live acceptance, F-115 hypercare, F-116 archive, F-117 handover, F-118 closure; then F-112 and F-112B change workspace and F-111B issue updates (the change's Authorisation select stays empty until a change is assessed, decided and authorised, which needs people the demo doesn't have); then F-121 escalation workspace, F-69 emergency change, F-122 leadership report; then Setup F-74, F-76, F-77 (placeholder costing rule allowed, D-214); then the remaining Finance screens; then the Assistant (needs the OpenRouter key and model name).
- **Demo:** the live app is on port 3002 (worktree `demo-live`, kept at `origin/main`), the backend on 8040 (worktree `be-real`, branch `demo-serve`, database `psl_demo5`). The demo database now has test templates, a placeholder escalation profile and request on Lagoon, and placeholder change requests on Lagoon and Delta. `seed_psl_demo` runs the template, escalation and change seeds, so a rebuild has them.
- **Known flake:** `setup-delegation.test.tsx` and `rfp-submission.test.tsx` (phone) fail now and then under load and pass on re-run (`gh run rerun <id> --failed`). Merges in `mock/server.mjs` have dropped a closing brace three times: always run `node --check frontend/mock/server.mjs` after a merge.

## Status at the end of 26 Nov (before the last pair)
- Weekly usage was 89% (the design engineer's stop was 93%). The delivery chain is connected through handover; **F-118 closure** and the change workspace (**F-112**, **F-112B**) with **F-111B** issue updates are next, then F-121, F-69, F-122, Setup (F-74, F-76, F-77) and the Finance screens.
- Three-way merges of two features into `mock/server.mjs`, `workspace/lines/index.ts` and `tests/next-config.test.ts` conflict every time (adjacent additions). Resolve by keeping both sides, then **check that each mock block still ends with `// a dropped connection…`, `if (reply[0] === 'drop') return req.socket.destroy();`, `return send(res, ...reply);` and a closing `}`** (git drops them), and run `node --check`.
- Shared bugs noted by builders, to fix once: `makeCommand` with `action: null` deletes `fixed.action`; `useWorkCommand` draws no success notice for line writes, can't place a 422 beside its field, and doesn't lock after a 503; F-87 shows both Pause and Continue whatever the state.

## Update 26 Nov (stopped at 90% weekly)
Merged since the last note: F-118 closure (#156) and F-112 change workspace (#157). No builds in flight, no lane worktrees left. demo-live is on origin/main.
Held: F-118 Close/Return (needs LD-2 ids) and Confirm milestone notifications (needs Finance evidence list); F-112 preapprove and bind_standard (backend must say how Standard changes flow).
Neither feature was tried on live data (psl_demo5 has no closure or change work item). Review-later has both rows.
Next candidates: F-112B, F-111B, F-121, F-69, F-122, F-74, F-76, F-77. First reviews: F-90, F-113B, F-114, F-112, F-101, F-94.
