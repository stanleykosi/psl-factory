# Coordinator handoff (15 Nov 2026, fourth session)

## Fourth session (15 Nov, later) — read this first
- **Done and on main:** follow-ups 02 (PR #31), F-20 Setup templates (PR #34), F-19 Clients (PR #37), F-21 Weekly update part 1 (PR #39), line work item frame passes 1 and 2 (PRs #33, #36). dlv-00 was merged into main (PR #32, then #35, #38, #40); main and dlv-00 are identical. **The backend developer builds on main** (D-80): after each merge into dlv-00, bring dlv-00 into main with a PR.
- **Backend handoff:** `delivery/BACKEND-HANDOFF.md` plus `delivery/backend-handoff/` (board-vs-v7 gaps for every unbuilt screen, 45 open questions, F-21 additions at the end). The frontend is NOT connected to a real API: main's Django app has no `/api/v1` endpoints yet.
- **New rules:** D-83 standing waiver for line screens (coverage 100 after exceptions + UI reviewer finds no fixable gap + visual >= 70, signed per board). D-76: no new features started until the design engineer lifts the pause (the handoff pack is out, so ask).
- **Process lessons:** reviewer prompts must give the tool's exact header words (`VERDICT: PASS|CHANGES`, `REVIEWER: reviewer-<lens>`, full 40-char COMMIT). After a base sync every lens must re-confirm on the new head, each by its own reviewer role (one agent writing for several roles is refused, rightly). Run PMO after the other confirmations land. Read back review files: a reviewer once reported a write that didn't happen. Gates fail on load-sensitive timeouts (decide-board, setup-rules, mock-contract) when builders run in parallel; re-run when quiet — a follow-up to raise testing-library's async timeout is worth doing.
- **Next (when the pause lifts):** F-21b (SCR-25 returned, received); FE-LINE-MINUTES (SCR-28, split); FE-ASSISTANT (SCR-05); FE-SETUP-DELEGATION; FE-M3-PROJECT-TABS; the other line screens per `delivery/screen-coverage.md` and the remaining-tasks list in BACKEND-HANDOFF.md.
- **Waiting for the design engineer:** DE-5 (the phone "+ Start" in the bar). Board corrections listed in BACKEND-HANDOFF.md.

## Third session notes (kept)

Read first: `delivery/OVERNIGHT-DECISIONS.md` ("Waiting for you" + decisions D-01…D-58). Feature state: `python3 /Users/Hunchoo/software-factory/packages/delivery/feature.py --project . status` and `next <F-id>`. Cost: `feature.py --project . cost`.

## Where things stand
- F-01 … F-18 and the follow-up fixes (PR #28) are merged into `dlv-00-delivery-setup` and DONE in the tool. F-18 is PR #29 and F-17 is PR #30 (merge commit 9cfaa27), both merged on 15 Nov on the design engineer's approval. `main` is untouched. There are no open worktrees.
- F-17 took a 6th round as a continuation of round 5 (D-66, D-67). It fixed QA-5-1 (the phone Decide bar covered "Record and continue") and QA-5-5 (a reload during an uncertain send re-enabled "Approve and send"; the lock now comes from `item.reconcile`).
- Local preview: `npm run dev -- -p 3000` in `frontend/` (mock on 4010).

## Rules in force
- Cost policy (D-64, replaces D-39): features hold at most ~8 boards; builders run on Sonnet except the first build of a high-risk feature (Opus); a builder runs the fidelity check once at the end of its round and doesn't chase gaps the design reviewer confirms are forced; later rounds re-run only the review lenses the diff touches; design review on Opus for a screen's first review, Sonnet when verifying fixes; QA on Opus; readiness, spec, approver, technical, UX and PMO on Sonnet; security on Opus only for high risk and only when the diff touches it. Spec writers list layout conflicts too. 2–3 builders at a time. Hand over to a fresh coordinator session every 2–3 features.
- Disk: `df -h /System/Volumes/Data` before spawning; stop under 3 GB. Never link node_modules between worktrees (D-37). Reviewers never copy frontend/ or build.
- Design: the board is the spec; the fidelity tool gates UI review (100% coverage after exceptions, visual ≥ 90 at 1440 and 390). Exceptions and visual waivers need the design engineer's sign-off. Spec writers list board conflicts up front; bring them to the design engineer before building (worked well for F-15 and F-16).
- Review findings start a fix round without asking. Wait for all routed reviews, then one batched fix round.
- Merge into dlv-00 only low-risk work (no money, sign-in, security, contract or product decision) after all gates; everything else waits for the design engineer's "merge …". Never main.
- No AI co-author trailers and no "Generated with Claude Code" in commits or PRs (global rule).
- Never read `.runtime/demo-access.txt`. If a subagent reports a permission refusal, surface it to the design engineer; don't work around it.

- Give each parallel QA agent its own scratch subfolder and ports, and have it stop its servers by its own PIDs. On 15 Nov a shared PID file let one QA agent kill the other's mock.
- Lean reviewers often write into the worktree instead of the main folder, or leave out the header lines (VERDICT:/COMMIT:/REVIEWER:/AUTHORITY:, `## Verified` with `- ID | verified | …`). Spell both out in the prompt.

## Merge recipe (keeps the board moving to Done)
1. Merge the current `origin/dlv-00-delivery-setup` into the branch; run `delivery/checks.sh`, plus the relevant e2e if the base brought frontend changes. Expect small integration test fixes when features overlap (frame buttons, shared mock ids, the bell's `/notifications` read — use `tests/bell-feed.ts`).
2. Push, open the PR (no footer), wait for GitGuardian (it may say "skipping" on merge-only commits), then `gh pr merge --merge --match-head-commit <sha>`.
3. Remove the merged worktree (clean and pushed) — the tool reads the head from it. Then set pr_url/pr_number/ci_status, `advance PR_OPEN`, `decide`, set human_approval/merge_status/merge_sha, and advance AWAITING_USER_APPROVAL → APPROVED → MERGED → DONE.
4. Start shared review copies with `FRAME_FIXTURES=1` (as playwright.config.ts does) or two frame e2e specs fail. Retry pushes; the network drops often.

## Next work, in order
0. Done 15 Nov: F-17/F-18 lean reviews, QA and PMO (below kept for reference).
1. (done) F-17 and F-18, lean (D-64): one Sonnet `reviewer-ui` per feature that only verifies F-17 UI-3-1 (round-4 fidelity files) and F-18 UI-2-1 and UX-2-1 (round-3 files), without re-running the full check. Re-use the passed technical/UX/security results; the tool lists them as pending on the new head, so tell each reviewer to read only the diff since its last pass and confirm. Then QA (Opus) and PMO acceptance (Sonnet), then the approver. Both wait for the design engineer's "merge" (F-17 has a contract proposal; F-18 is high risk). F-17 has no rounds left: anything blocking needs the design engineer to allow a 6th round or a follow-up.
2. Merge order: F-17 first, then rebase or merge F-18 onto it (both touch `WorkItemOverview.tsx` with a few lines).
3. Next (start here): v7 tasks with dependencies met, each kept to at most ~8 boards (split larger ones): FE-ASSISTANT, FE-SETUP-DELEGATION, FE-SETUP-TEMPLATES, FE-CLIENTS, FE-M3-PROJECT-TABS, FE-M3-REPORT; and the line screens (F-17 is merged) (FE-LINE-WEEKLY, FE-LINE-MINUTES, FE-ENGAGEMENT-PLANNING, FE-DELIVERY-*, FE-FIN-*).
4. Follow-up batch (Sonnet): My work tabs 48px → 44px (boards); F-17 "UNKNOWN · Unknown" doubled in the checklist chip; F-17 QA-5-3 (uncertain callout below the fold on phones), QA-5-4 (note-length message shown twice), UX-5-1/TECH-5-2 (a hint for a viewer who can't reconcile), the literal 30px in flow-mode padding (make it a token); and the phone "← Setup" target once the design engineer answers.

## Waiting for the design engineer
- "Go" on three follow-up recommendations: leave the wordmark under 380px, keep the board's proof box wording (F-09 UX-3-2), and point phone "← Setup" at Setup rules until a phone Setup home is drawn.
- DE-5: the frame's "+ Start" in the phone bar (now also lowers SCR-22 phone and SCR-15 settings phone).

## Waiting on others
- Backend developer, new from F-17 round 5: server-side refusal of a resend while delivery is uncertain, plus idempotency (SEC-5-C1), before any real send is switched on; confirm that a viewer without the reconcile grant should see every step off (TECH-5-2). The full list is in F-17 round-5/acceptance-pmo.md and PR #30.
- PSL: D-SIGNIN (sign-in, sign-out, account menu), D-ADMIN-AUTHORITY, D-PAYROLL-VISIBILITY, D-COSTING-RULE, D-CHANGE-DECIDERS, D-RECEIPT-ALLOCATION, D-SPEECH-INPUT, D-DECISION-VARIANTS (payment exception, CEO costing and CTO emergency decide boards).
- Backend developer: `needs_you` on notifications (D-53); a `waiting` line-status tone (D-46); `recorded.station` on responses (D-38); idempotency for E-RESPONSE and for Start work after leaving (PMO-0-2); duplicate proof by sha256; upload limits; permission checks before field checks; the PROPOSAL `presentation` and `decide_presentation` blocks.
- Backend developer, new from F-17/F-18: a section-page read for workspace paging; form prefill (current answer) and a deciding role on workspace steps; the "Try again" revision vs idempotency answer (F-17 TECH-1-4); a reused idempotency key with a different body must be refused; optional proof on "unknown" RFP outcomes; whether outcomes take several proof files; a colour field for row and lesson tags; the planning-packet agent; currency beyond NGN.

## Fifth session (16 Nov 2026): design-system conformance merged

- D-91 conformance is DONE: PR #44 (ds-integrate → dlv-00, merge 7f788014). Every built screen uses the shared library in `frontend/src/components`; design-system README/tokens/specs match the boards (D-93). Records in `delivery/design-system-conformance/` (audit, build notes, four reviews all PASS on 59799cb8, integration-build-note.md with the before/after fidelity table and remaining raw-px list).
- New decisions: D-94 (next milestone: closed "—", open Unknown; "All I can see" needs a per-row open/closed field from the backend), D-95 (links inside a sentence exempt from 44px).
- Follow-ups (not started): UI-3-1 decide warning icon wraps on desktop (drop flex-wrap in decide.css:96); shared one-box date-time, compact file row and boxed radio so the response/RFP forms can use the library (UX-05); phone filter chips wrap vs board's sideways-scroll row (ask design engineer); raise testing-library async timeout (gate flakes).
- Feature pause (D-76) still on: ask the design engineer to lift it. Next features: F-21b, FE-LINE-MINUTES, FE-ASSISTANT, FE-SETUP-DELEGATION, FE-M3-PROJECT-TABS, other line screens.

### F-22 follow-ups (non-blocking, routed 16 Nov)
- SEC-1-3: shared ReconcilePanel copy says the client "is never invoiced twice" (invoice wording on a report; a promise the mock can't keep). Reword per line.
- UI-1-4: pinned phone bar shows the consequence line above the button (F-21 behaviour); board shows only the button.
- UX-1-1: next line for failed/unknown delivery (backend handoff). UX-1-3 / QA-2-2: unknown work id gets the mock's default item (mock should 404).
- UX-1-4, UX-3-1 (multi-cite pickers truncate), UX-4-1, TECH-1-2 (frame change already listed): polish.
- Fidelity tool: labels that are entirely data bindings ({{…}}) can't be matched (F-24 "Start this invoice"); frame names like "Back to Home" vs board "← Home". Match by role and position, or allow per-board exceptions.

### F-24 follow-ups (non-blocking)
- QA-3-1: a second start of the same draft shows Start work's generic 409 text and re-enables start; show the backend's message and offer only Close once the 409 shape is confirmed (backend handoff, Added during F-24).
- TECH-3-1: tighten the e2e dock assertion to the real viewport height. TECH-1-3: prefill option search stops after 5 pages.

### F-23 follow-ups (non-blocking)
- QA-3-2: shared decision copy "Paid is tracked separately by Finance" shows on minutes approves; make the decide copy line-specific (with F-22 SEC-1-3 and F-23 UX-1-2/1-3).
- QA-4-1 / UX-4-1 / UI-4-1: the uncertain decision notice says "We couldn't confirm your decision" though the decision was recorded and the send is uncertain; point to "Confirm what happened" on the work item; don't stack two amber notices when the reload also fails.
- TECH-2-2 (task-card hiding rule is general), TECH-3-1/3-2 (warn_lines guard and ordering), UI-3-1.
### Process lesson (17 Nov)
- Several features running full test suites at once drove load past 500 and made untouched tests time out. Run full checks one at a time; the coordinator re-runs them quietly before each merge. Merge dlv-00 into a branch before the final reviews, not after. Write the backend-handoff section during the build, not after PMO asks.
- F-23 also routed (non-blocking, many fixed in later rounds): TECH-1-1..1-4, UX-1-2..1-8, UI-1-5/1-6, TECH-2-2, UX-2-1, UI-2-3, SEC-2-1, TECH-3-1/3-2, UI-3-1/3-2, SEC-3-1, TECH-4-1 — see each round's reviews; contract items are in BACKEND-HANDOFF "Added during F-23".

## Sixth session (16–17 Nov 2026): six features merged
- Merged to dlv-00 and main: F-22 weekly returned/received (PR #46), F-24 assistant part 1 (#48), F-26 Money tab (#50), F-27 Setup delegation (#52), F-23 minutes part 1 (#54), F-25 project tabs (#56); main synced after each (#47, #49, #51, #53, #55, #57). No worktrees open; disk 18 GB free.
- Decisions D-96..D-110 in OVERNIGHT-DECISIONS.md (pause lifted; conflicts, waivers and product acceptances for each feature).
- Next candidates (deps now met): minutes part 2 (SCR-28 internal, published), assistant "can't" (SCR-05), document review (SCR-08), mark milestone complete (SCR-19, needs FE-M2A-PROOF), issue detail (SCR-30), engagement/planning (SCR-41/42), the delivery line screens SCR-43..51, the Finance workspaces SCR-53..58, leadership report (SCR-52). Held by PSL: SCR-17, 20, 21, 27, 31, 39 and payroll (09, 18, 37, 59).
- How to run: ≤3 builds at once; one full test suite at a time (load >30 makes untouched tests time out); merge dlv-00 into a branch before the final reviews; write the backend-handoff section during the build; re-pin reviews after any head change.

## Seventh session (17–18 Nov 2026): three features merged
- Merged to dlv-00: F-28 minutes part 2 (SCR-28 internal and published, PR #58), F-29 document review (SCR-08 and the Documents tab, #59), F-30 issue detail (SCR-30, #60). Main is synced by one PR after all three. No worktrees open; disk about 12 GB free.
- Decisions: D-111 (spec conflicts as recommended) and D-112 (every waiver and exception signed, including floor exceptions for SCR-08-mobile 69.1 and SCR-30-mobile-verified 68.5; product acceptance for F-29 and F-30; the shared timeline row and NEXT heading kept on the issue page).
- Merge practice that worked: one shared checks lock (`psl-factory-worktrees/.checks.lock`) plus a wait for 5-minute load < 14 before any full suite. Since then, no flaky failures. After each merge of dlv-00 into a branch, one Sonnet impact reviewer re-pins all round reviews; PMO re-runs only if its last verdict was CHANGES.
- Follow-ups (not started): F-29 UX-2-1 (disabled "Ask Tola to draft v3" reads as plain text); F-30 PMO-3-5 (flaky `setup-rules`/`rfp` tests: raise testing-library's async timeout), PMO-3-6 (UX-1-2..1-4, TECH-1-1 non-blocking); F-30 PMO-3-3 note: some exceptions cover sample data and times (signed as a set by D-112); the backend panel title for "Owner follow-up" (UI-1-7).
- Next candidates: assistant "can't" (SCR-05), mark milestone complete (SCR-19, needs FE-M2A-PROOF), engagement/planning (SCR-41/42), delivery line screens SCR-43..51, Finance workspaces SCR-53..58, leadership report (SCR-52). Still held by PSL: SCR-17, 20, 21, 27, 31, 39 and payroll.

## Eighth session (18 Nov 2026 evening): handed off mid-wave — read this first

Merged into dlv-00 today: F-31 #62, F-32 #63, F-33 #64, flaky-test fix #65, F-47 #66, F-41 #67, F-42 #68.
Main synced through PR #61 (user merged). Next dlv-00 → main sync PR needs the user. Deadline: Friday 20 Nov.
Full action log: `delivery/NIGHT-LOG-2026-11-18.md` (sign-off lists 1–3). Decisions D-112..D-120 in `OVERNIGHT-DECISIONS.md`.

State at handoff (check `feature.py status` and each worktree; the agents below were started by the old
session and report only there, so read their output files / worktree commits instead of waiting):

| Feature | State | Next |
|---|---|---|
| F-34 hypercare | signed D-119; builder a8d96d0120b9daa3a merging dlv-00 + PMO-3-1/3-2 housekeeping | impact re-pin 7 round files + build.md COMMIT → PR → merge recipe → DONE |
| F-36 RFP intake | signed D-120; builder a7f8dd4d5a60e4d45 merging dlv-00 | same merge recipe |
| F-35 leadership report | round 2: security, technical, UX, UI all PASS (UI-2-1 Ask Tola link 51x20, inherited from F-33 footer; UX-2-1/2/3 non-blocking; UX-2-3 green banner on partial delivery → put on user's sign-off list 3) | advance to INTEGRATED_QA → QA (demo 4987, mock 4986) → PMO → approver → sign-off list 3 |
| F-39 escalation | round 1: technical PASS; UX CHANGES (UX-1-1 blocking: desktop NOT ESCALATED page layout broken vs board; UX-1-2..6 non-blocking); UI review a6459e063fc7d322d still running when handed off | wait/read UI review-ui.md, then CHANGES_REQUESTED → round 2 builder fixes UX-1-1 (+ UI findings) |
| F-37 RFP response | building, agent aff21ac6671c86c11, ports 4994-4997 | gate → reviews |
| F-43 cash forecast | building, agent ad9305d22b02637a4 (Opus), ports 4894-4897 | gate → reviews |
| F-48 assistant "can't" | builder a0ac9b1aac696b8f7 finished (result unread) | read its build.md / output, gate → reviews |
| F-38, F-40, F-45 | specs accepted (D-118), not started | start builds as slots (max 3–4) and disk (stop < 3 GB; was 4.8 GB) allow |
| F-36 part 2 (SCR-23), FE-MILESTONE-COMPLETE (SCR-19), F-47B | newly unblocked | readiness → spec |

Agent output files: `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/0986a60c-391e-48d6-b2da-79de8713a755/tasks/<agentId>.output`.
If a builder died mid-merge, resume by spawning a new builder on the same worktree with the round's instructions.

Recipes (unchanged): gate wrapper waits on `/Users/Hunchoo/psl-factory-worktrees/.checks.lock` and loadavg field `$2`;
merge recipe = builder merges origin/dlv-00 → impact reviewer re-pins → `gh pr create` (no AI footer) → `F set ci_status`
→ PR_OPEN → decide → `gh pr merge --merge --match-head-commit` → AWAITING_USER_APPROVAL → approved → APPROVED → MERGED → DONE
→ remove worktree. Stop on any tool refusal. Never merge to main without the user.

Also requested by the user at handoff: a PDF of every decision PSL still has to take — what each means in plain business
terms and where in the product it is taken (screen / configuration page / process ID). Sources: guide/10-POLICY-CONFIGURATION.md,
BUILD-DECISIONS.md, delivery backend-handoff + readiness/spec "blocked by PSL" notes, memory product-decisions-2026-11.

## Ninth session (18–19 Nov 2026): wave 3, usage limit, cost plan — read this first
Merged into dlv-00 since the eighth-session notes: F-34 #69, F-36 #70, F-35 #71, F-39 #72. 40 of 50 tasks are DONE.
Also delivered: the decisions pack, delivery/psl-decisions/PSL-DECISIONS.pdf (71 decisions; regenerate with build_decisions.py).
The weekly usage limit stopped all agents at ~05:10 on 19 Nov. It resets **Sun 22 Nov 03:00 (Africa/Lagos)**.
From then on, follow **D-123** (OVERNIGHT-DECISIONS.md) and **delivery/builder-checklist.md**:
- Sonnet builders. UI and QA reviews on Sonnet. Opus only for high-risk security and technical review.
- PMO and the approver run as one pass.
- One fidelity run per round.
- 2–3 builds at a time; features touching the same shared files go one after another.

State when the agents stopped. Their saved work can be resumed with SendMessage after the reset, but only from the session that spawned them. From a new session, start fresh agents that pick up from the worktree and round files.
| Feature | State | Next |
|---|---|---|
| F-43 cash forecast | INTEGRATED_QA round 2, head 5020a86b; all 4 reviews pass; QA cut off | QA (Sonnet) → PMO+approver → sign-off. Before merging, take in dlv-00 (brings the shared stale fix) and add a two-reviewer test |
| F-45 ledger source | IN_REVIEW round 1, head 4dba97ab; 4 reviews cut off | reviews (security and technical on Opus: high risk) |
| F-40 handover | IN_REVIEW round 1, head b051cfa7; demo 4975/4974 | reviews (security routed by plan) |
| F-37 RFP response | IMPLEMENTING round 2 (UI-1-1..1-5 plus the desktop-hides-all-task-panels note); builder cut off mid-fix | finish round 2 (checks were running), gate, UI re-review |
| F-48 assistant "can't" | IMPLEMENTING round 1, build.md READY at 0a7196f6; node_modules removed for disk | npm ci, gate, reviews |
| F-38 RFP submit | READY (re-check 19 Nov), not started | build after F-37 merges (shares RfpFrame tab links) |
| F-36 part 2, FE-MILESTONE-COMPLETE, F-47B | unblocked | readiness → spec |
| F-44, F-46 | BLOCKED (PSL/backend) | — |
Then the dlv-00 → main sync PR. Ask the user before merging into main.
Follow-ups: F-33 income line needs its own two-reviewer stale test, and still says "approved" before the re-read; TECH-2-1 (F-43 tags on F-33/F-42 NOT SET facts); QA-4-1 (W-3602 send-for-review fixture); F-35 stale-notice polish (UX-3-1..3, TECH-3-1).

## Remaining work after this wave: what is blocked, and what unblocks it (19 Nov 2026)
Buildable now: F-38 (RFP submit, round 2), F-49 (log a received RFP, building), F-51 (fixed-asset proof field, after F-49). Then the dlv-00 → main sync PR (needs the user).

**Whole tasks not started.** Source: architecture/packages/v7/model.json tasks and readiness files. PSL decisions are explained in delivery/psl-decisions/PSL-DECISIONS.pdf.
| Task | What it is | Blocked by |
|---|---|---|
| FE-FIN-BU (F-44) | Business-unit totals (SCR-57) | PSL: D-PAYROLL-VISIBILITY (may Finance see staff count and cost per BU); backend G-SCR59-9, G-57-1 |
| FE-MILESTONE-COMPLETE (F-50) | Mark a milestone complete (SCR-19) | PSL: who may press "Mark complete", and whether it starts the invoice draft; backend: the completion endpoint is missing |
| FE-DECIDE-VARIANTS | Payment-exception, CEO final costing and CTO emergency decision screens | PSL: D-DECISION-VARIANTS |
| FE-COSTING | Costing sheet (SCR-27) | PSL: D-COSTING-RULE (the costing formula, rates, margin) |
| FE-SETUP-COSTING | Costing rule setup (SCR-39) | PSL: D-COSTING-RULE |
| FE-CHANGE | Change request detail (SCR-31) | PSL: D-CHANGE-DECIDERS (who decides a change) |
| FE-PAYMENTS-RECEIPT | Record a payment (SCR-20 record) | PSL: D-RECEIPT-ALLOCATION (how a payment is allocated) |
| FE-SIGNIN | Sign-in, reset, account set-up (SCR-17), plus the account menu's sign-out | PSL/engineering: D-SIGNIN |
| FE-SETUP-ROLES | Roles and staff accounts (SCR-13) | PSL: D-ADMIN-AUTHORITY (who administers roles) |
| FE-SETUP-PAYROLL-FIELDS | Payroll field visibility (SCR-13 fields) | PSL: D-PAYROLL-VISIBILITY |
| FE-FIN-PAYROLL-IMPORT, -CORRECTIONS, -RUN | Payroll inputs, corrections, run (SCR-09/18/37/59) | Readiness not yet run. Expected to wait on D-PAYROLL-VISIBILITY and the payroll rules (unset Setup) |
| FE-FIN-ACCOUNTS-INTAKE, -PUBLISH | Management accounts (SCR-53) | Readiness not yet run. Backend answers G-SCR04P-1/3 (the money field); publication recipients (D11) |
| FE-ASSISTANT-SPEECH | "Speak your request" in the assistant | PSL: D-SPEECH-INPUT |
| FE-CONNECT-1 | Connect the app to the real backend API | Backend: the real API for My work, work item and decide (T-* tasks) |
Not work: FE-M2, FE-M3 and FE-M4 are retired umbrella tasks (split into the features already built).

**Later parts of shipped features.** These are from readiness notes, not exhaustive; each needs its own readiness check when unblocked.
| Part | From | Blocked by |
|---|---|---|
| Planning readiness, held/ready (SCR-42, 6 boards) | F-31 | PSL rule G-42-6 (who accepts readiness; what makes planning verified) |
| RFP response part 2 | F-37 | PSL: Engineering Lead review rule G-26-9; D-RETURN |
| Income detail part 2 (SCR-54 held, export) | F-33 | Backend/PSL: G-54-1, G-54-2 (Income detail rules NOT SET) |
| Delivery part 2 (SCR-33 retrospective, SCR-49 blocked, 4 boards) | F-40 | Readiness to run (no gate named yet) |
| Delivery closure part 3 (SCR-49, 8 boards) | F-40 | PMO Lead decision screens; expect NEEDS-INFO, high risk |
| Hypercare and release part 3 (reconcile, response) | F-32, F-34 | Readiness to run |
| Cash forecast part 3, actuals (SCR-56) | F-43 | PSL: D-RECEIPT-ALLOCATION, D-DECISION-VARIANTS, D-PAYROLL-VISIBILITY; backend G-56-5..8 |
| Escalation part 2 (review, received, client send; CTO pre-authorisation) | F-39 | PSL decisions on escalation and the alert provider |
| Leadership report setup (part 2) and a reports page | F-35 | Setup rules (reviewer, audience, skip-review); backend G-SCR52-5b |
| Start work management-accounts fields (F-47C) | F-47 | Backend G-SCR04P-1/3 |
| Alert WhatsApp/email templates | F-12 | PSL/engineering: D-ALERT-PROVIDERS |

## Tenth session (19–20 Nov 2026): wave complete — read this first
- **DONE since the ninth-session notes:**
  - F-43 (#73), F-45 (#74), F-37 (#76), F-40 (#77), F-48 (#79), F-49 (#82), F-38 (#83), F-52 follow-up batch A (#84), F-51 (#85).
  - Test-reliability PRs #75, #78, #80, #81.
  - F-46 CLOSED as a duplicate of F-12. That used the new CLOSED state, factory commit 05e2cd9.
- **Every buildable task is DONE.** BLOCKED: F-44 (D-PAYROLL-VISIBILITY plus backend) and F-50 (PSL "Mark complete" authority plus the backend completion endpoint). The full blocked list and what unblocks each item is in "Remaining work after this wave" above.
- **Main sync PR #86** (dlv-00 → main, F-34 to F-52): open, mergeable, waiting on the user. NEVER merge it without the user.
- **Cost policy D-123** is in force and in the software factory (commit 6798f28 on factory-running, local only; ask before pushing):
  - Sonnet builders and reviews;
  - Opus only for high-risk security and technical review;
  - PMO and approver as one pass;
  - one fidelity run per round;
  - the builder checklist.
- **Lessons:**
  - Builders hand back early. Resume them with explicit "don't hand back until build.md".
  - After a dlv-00 merge into a branch, move git.base_sha to the merged dlv-00 commit, or the gate flags the protected delivery/config.json.
  - Union scoring penalises tall drawers or pages; the UI reviewer must judge capture limits versus real differences.
  - In zsh, never use a `for x in "a b c"` loop with set --; use a function with explicit arguments.
  - Never kill processes broadly. Kill only by port.
- **Open follow-ups:**
  - F-38: reconcile "arrived" with an upload; per-persona access in the mock.
  - F-51: a wrong-case upload gives 422, not 404 (backend).
  - Start work: the scroll-capture driver needs the fixed-viewport approach.
  - F-48 stopgap: G-SCR05-9 (backend).
