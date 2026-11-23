# Connection map: frontend screens to the live API

**What this is.** For each of the 59 approved screens, this map lists what the frontend reads and writes today, the live call that replaces each one, how the fields line up, and what has no live source yet. Builders use it to rewire screens without guessing. [backend-questions.md](backend-questions.md) collects everything we need the backend developer to answer.

**Baseline.** Live API: OpenAPI 1.22.0 (`contracts/psl-factory.openapi.json`, main `9bac3109`, 22 Nov 2026), 379 operations on 268 paths, served by Railway design acceptance. Frontend: `fe-upload-field-concept-a` at `f8b28059`. It is typed on the practice contract v7 (`architecture/packages/v7/openapi.json`) and runs on the v7 mock. Written 23 Nov 2026.

**How it was made.** Every operation path and field was checked against the live contract. Where the contract types an item as a bare `object`, the Django source in `apps/` was read. The fit columns are research, not test results: nothing here has been run against Railway yet. "Likely" in a row means it was inferred and has a matching question.

## Where we stand

- **Calls.** Of the 43 operations the frontend calls, 1 matches live exactly (`POST /tasks/{task_id}/claim`). 22 exist with a different shape, and 20 are not at that path. Most of those 20 moved to a workspace-scoped or line-specific path.
- **Screens.** 36 are built, 7 partly built and 16 not built. Effort to connect: 28 large, 28 medium, 3 small or small-to-medium.
- **The biggest structural change.** v7 drew every line workspace from one `workspace` block on `GET /work/{id}` and wrote through one `POST /work/{id}/steps`. Live has neither. Each line has its own read (reached through `panels[].url`) and its own typed commands, with their own revisions and 200, 201 or 202 results. The shared workspace frame stays, but it needs one adapter per line.
- **What breaks on main today.** Main's `frontend/src/shell/AppShell.tsx` swaps our whole shell for the retired Django `<psl-work-client>` widget whenever `/me` has `work_desk_url`, which live always has. That widget's script now returns 404, and `next.config.ts` forwards unknown paths to Django pages that return JSON 404. There are no sign-in, recovery or invitation pages yet (SCR-17).
- **Correction to the first read (22 Nov).** The live API does have the cross-project lists: Exceptions is `GET /work?queue=exceptions`, Payments is `GET /payments` and Month-end is `GET /month-end`. What is missing there is detail and counts, not the lists themselves.

## Foundation work before any screen (engineering proposal)

1. **Remove the embed.** Delete `src/shell/FactoryDesk.tsx` and the `native` branch in `AppShell.tsx`. In `next.config.ts`, drop the `/accounts`, `/factory-forms`, `/factory-assets` and `/static` rewrites and the catch-all fallback. Keep `/api/v1` and the mock reset, and add the six authenticated download routes. Details: [Cluster A, App frame](screens-a-frame-core.md#app-frame-and-session).
2. **Live types next to the mock.** Generate `src/api/live-schema.d.ts` from `contracts/psl-factory.openapi.json` and add a live client. Each screen switches over as it is rewired. The v7 mock stays for design review. Tests for connected screens use live-shaped fixtures taken from the backend's state crosswalk.
3. **Session and errors.** Sign in with `GET`/`POST /session`, then sign out. Refresh the CSRF token after sign-in, sign-out and password change. Treat `csrf_failed` and `forbidden` as different 403s. Give 429 and 503 their own wording. Read `fields` on every 422. Rename `idempotency_key_reused` to `idempotency_conflict`.
4. **Ids and paging.** Work ids are integers and project ids are UUIDs, so routes, the mock and tests change once. Lists page by `page`/`next_page`. Show coverage from `limited`, `evaluated` and `deferred`.
5. **Queued results.** Many writes return 202. Show the progress state, poll while `current_activity.watching` is true, and show "verified" only on a confirmed business output.
6. **Line adapter pattern.** The workspace frame takes a per-line adapter: read the panel URL and produce sections, then map each step to its typed command with its tokens. Lock, stale-reload, uncertain and unknown-is-not-zero handling stay shared.
7. **Evidence picker.** One shared control for "attach proof" that ends in an `evidence_id`. It waits on backend question 1.

## Design changes to decide (design engineer)

The live API changes what some approved boards can show. Each point needs a decision: change the board, or wait for the backend answer named in brackets.

- **My work.** The tabs become needs me, waiting, started by me, active, decisions, exceptions, unassigned and verified. Pages are a fixed 8 rows with no tab counts (short-list 5). The station bar, the Decide/Do/Fix tag and the reference have no source (2, 7).
- **Work item.** There is no station track, six-fact strip or Tola step card (2). Line content comes from each line's own panel.
- **Decisions.** Most human decisions now need a proof and a note. Revoke is only available on payment controls and reviews (1).
- **Alerts.** Settings shrink to email and WhatsApp on or off, plus recent deliveries. Quiet hours, digest and per-event choices have no source (12).
- **Assistant.** A conversation belongs to one project. @mentions become a source picker, and answers arrive queued.
- **Clients.** A client is a group of workspaces, with no amount owed. Adding a billing contact needs a proof.
- **Setup.** It needs a workspace picker (4). A save becomes a draft followed by a review.
- **Record a response (SCR-16).** It splits into commercial response, team input, client testing and RFP outcome. Follow-ups gain draft, review and send steps.
- **Document review.** There is no claim step, compare view or per-section agent notes (12).
- **Delivery.** A hypercare observation becomes a metric reading. Go-live needs two signature evidences. Release gates become typed phases. There is no Delivery overview read, no Publish to Support step and no Finance confirmation record (12).
- **Finance.** Unknown money is `null`, with `basis` and `currency` on every figure. "Known part plus Unknown" totals have no source (11). Payroll is a different model from the boards: a request, two provider inputs, name-by-name comparison and a reviewed aggregate for the named recipient.
- **Overview.** The floor gets only a count per line.

## Connection order

Each wave is one or more delivery features, run one branch at a time through the usual gate and review. Waves 1 to 4 rewire built screens. Wave 6 builds the remaining screens straight on live, with no v7 mock first.

| Wave | Screens | Why this order |
|---|---|---|
| 0 Foundation | the items above | Nothing works signed in without it |
| 1 Sign in and frame | SCR-17, SCR-15 | First thing a person sees; well-defined endpoints |
| 2 Core desk | SCR-01, 02 (header and history), 10, 14, 03, 22, 29, 12 | Lists and reads, few writes |
| 3 Start work and first lines | SCR-04, 23, 24, 16, 30, 48, 52, 36, 20 | The closest shapes; proves the line adapter and evidence picker |
| 4 Remaining built lines | SCR-25, 26, 28, 40, 41, 42, 43, 44, 46, 51, 32, 54, 55, 56, 58, 07, 08, 11, 38, 05, 06 | One adapter each, on the proven pattern |
| 5 Setup and clients | SCR-13, 34, 35, 21, 39 | Wait on short-list questions 1 and 4 |
| 6 Not built yet | SCR-19, 27, 31, 33, 45, 47, 49, 50, 09, 18, 37, 53, 59, 57 | SCR-57 is still blocked on PSL; payroll waits on short-list 3 |

## Every screen

Effort: S, M or L to connect, from each screen's section. "Live operations" is the count the backend mapped to the screen. "States" is the count in the backend's 262-state crosswalk.

| Screen | Built today | Effort | Wave | Live operations | States | Details |
|---|---|---|---|---|---|---|
| SCR-01 · My work (work queue) | yes | L | 2 | 6 | 5 | [A](screens-a-frame-core.md#scr-01--my-work-work-queue) |
| SCR-02 · Work item | yes | L | 2 | 22 | 16 | [A](screens-a-frame-core.md#scr-02--work-item) |
| SCR-03 · Decision | yes | M | 2 | 22 | 8 | [A](screens-a-frame-core.md#scr-03--decision) |
| SCR-04 · Start work | yes | L | 3 | 28 | 17 | [A](screens-a-frame-core.md#scr-04--start-work) |
| SCR-05 · Assistant | yes | L | 4 | 10 | 5 | [A](screens-a-frame-core.md#scr-05--assistant) |
| SCR-06 · Overview: factory floor | yes | M | 4 | 1 | 1 | [A](screens-a-frame-core.md#scr-06--overview-factory-floor) |
| SCR-07 · Project journey | yes | L | 4 | 5 | 1 | [B](screens-b-projects-setup-clients.md#scr-07--project-journey) |
| SCR-08 · Document review | yes | M | 4 | 4 | 2 | [B](screens-b-projects-setup-clients.md#scr-08--document-review) |
| SCR-09 · Import and reconcile | no | L | 6 | 12 | 2 | [E](screens-e-finance-payroll.md#scr-09--import-and-reconcile-restricted-payroll-inputs) |
| SCR-10 · All exceptions | yes | S–M | 2 | 16 | 1 | [A](screens-a-frame-core.md#scr-10--all-exceptions) |
| SCR-11 · Registers (issues, changes, RFPs) | yes | M | 4 | 10 | 1 | [B](screens-b-projects-setup-clients.md#scr-11--registers-issues-changes-rfps) |
| SCR-12 · Report with drill-down | yes | M | 2 | 8 | 1 | [B](screens-b-projects-setup-clients.md#scr-12--report-with-drill-down-money-tab) |
| SCR-13 · Setup: roles, rules, delegation | partly | L | 5 | 26 | 8 | [B](screens-b-projects-setup-clients.md#scr-13--setup-roles-rules-delegation-plus-payroll-fields-delivery-and-finance-rules) |
| SCR-14 · Verified outputs | partly | M | 2 | 14 | 1 | [A](screens-a-frame-core.md#scr-14--verified-outputs) |
| SCR-15 · Alerts and notification settings | yes | M | 1 | 6 | 5 | [A](screens-a-frame-core.md#scr-15--alerts-and-notification-settings) |
| SCR-16 · Record a response | yes | L | 3 | 19 | 13 | [C](screens-c-rfp-planning-reports.md#scr-16--record-a-response) |
| SCR-17 · Sign in | no | M | 1 | 12 | 4 | [A](screens-a-frame-core.md#scr-17--sign-in) |
| SCR-18 · Restricted payroll matching | no | L | 6 | 17 | 2 | [E](screens-e-finance-payroll.md#scr-18--restricted-payroll-matching) |
| SCR-19 · Mark a milestone complete | no | M | 6 | 6 | 1 | [B](screens-b-projects-setup-clients.md#scr-19--mark-a-milestone-complete) |
| SCR-20 · Payments and follow-up | partly | M | 3 | 14 | 2 | [E](screens-e-finance-payroll.md#scr-20--payments-and-follow-up) |
| SCR-21 · Staff accounts | no | L | 5 | 19 | 3 | [A](screens-a-frame-core.md#scr-21--staff-accounts) |
| SCR-22 · Project list | yes | S | 2 | 2 | 1 | [B](screens-b-projects-setup-clients.md#scr-22--project-list) |
| SCR-23 · Log a received RFP | yes | M | 3 | 3 | 1 | [C](screens-c-rfp-planning-reports.md#scr-23--log-a-received-rfp) |
| SCR-24 · Assign the accountable PM | yes | M | 3 | 4 | 1 | [C](screens-c-rfp-planning-reports.md#scr-24--assign-the-accountable-pm) |
| SCR-25 · Weekly client update | yes | L | 4 | 9 | 6 | [C](screens-c-rfp-planning-reports.md#scr-25--weekly-client-update) |
| SCR-26 · RFP response workspace | yes | L | 4 | 8 | 6 | [C](screens-c-rfp-planning-reports.md#scr-26--rfp-response-workspace) |
| SCR-27 · Costing sheet | no | M | 6 | 6 | 4 | [C](screens-c-rfp-planning-reports.md#scr-27--costing-sheet) |
| SCR-28 · Confirm the minutes | yes | L | 4 | 11 | 6 | [C](screens-c-rfp-planning-reports.md#scr-28--confirm-the-minutes) |
| SCR-29 · Project actions | yes | S–M | 2 | 7 | 1 | [B](screens-b-projects-setup-clients.md#scr-29--project-actions) |
| SCR-30 · Issue detail | yes | L | 3 | 13 | 4 | [D](screens-d-delivery-issues-escalation.md#scr-30--issue-detail) |
| SCR-31 · Change request detail | no | L | 6 | 9 | 9 | [D](screens-d-delivery-issues-escalation.md#scr-31--change-request-detail) |
| SCR-32 · Payment reminder | yes | M | 4 | 8 | 1 | [E](screens-e-finance-payroll.md#scr-32--payment-reminder) |
| SCR-33 · Project retrospective | no | M | 6 | 7 | 1 | [D](screens-d-delivery-issues-escalation.md#scr-33--project-retrospective) |
| SCR-34 · Setup: templates | yes | M | 5 | 3 | 1 | [B](screens-b-projects-setup-clients.md#scr-34--setup-templates) |
| SCR-35 · Clients and client details | yes | L | 5 | 13 | 2 | [B](screens-b-projects-setup-clients.md#scr-35--clients-and-client-details) |
| SCR-36 · Month-end | yes | M | 3 | 3 | 1 | [E](screens-e-finance-payroll.md#scr-36--month-end) |
| SCR-37 · Payroll corrections (restricted) | no | L | 6 | 14 | 1 | [E](screens-e-finance-payroll.md#scr-37--payroll-corrections-restricted) |
| SCR-38 · Project milestones | yes | M | 4 | 8 | 2 | [B](screens-b-projects-setup-clients.md#scr-38--project-milestones) |
| SCR-39 · Setup: costing rule | no | L | 5 | 8 | 4 | [B](screens-b-projects-setup-clients.md#scr-39--setup-costing-rule) |
| SCR-40 · RFP submission | yes | M | 4 | 9 | 4 | [C](screens-c-rfp-planning-reports.md#scr-40--rfp-submission) |
| SCR-41 · Engagement | yes | M | 4 | 5 | 2 | [C](screens-c-rfp-planning-reports.md#scr-41--engagement) |
| SCR-42 · Planning | yes | L | 4 | 11 | 5 | [C](screens-c-rfp-planning-reports.md#scr-42--planning) |
| SCR-43 · Delivery overview | yes | M | 4 | 4 | 1 | [D](screens-d-delivery-issues-escalation.md#scr-43--delivery-overview) |
| SCR-44 · Release gates | partly | L | 4 | 16 | 6 | [D](screens-d-delivery-issues-escalation.md#scr-44--release-gates) |
| SCR-45 · Go-live acceptance | no | L | 6 | 13 | 5 | [D](screens-d-delivery-issues-escalation.md#scr-45--go-live-acceptance) |
| SCR-46 · Hypercare | partly | L | 4 | 11 | 6 | [D](screens-d-delivery-issues-escalation.md#scr-46--hypercare) |
| SCR-47 · Archive | no | M | 6 | 9 | 3 | [D](screens-d-delivery-issues-escalation.md#scr-47--archive) |
| SCR-48 · Handover to Support | yes | M | 3 | 9 | 4 | [D](screens-d-delivery-issues-escalation.md#scr-48--handover-to-support) |
| SCR-49 · Closure | partly | M | 6 | 7 | 5 | [D](screens-d-delivery-issues-escalation.md#scr-49--closure) |
| SCR-50 · Emergency change | no | L | 6 | 17 | 5 | [D](screens-d-delivery-issues-escalation.md#scr-50--emergency-change) |
| SCR-51 · Escalation | partly | M | 4 | 9 | 6 | [D](screens-d-delivery-issues-escalation.md#scr-51--escalation) |
| SCR-52 · Leadership report | yes | L | 3 | 9 | 5 | [D](screens-d-delivery-issues-escalation.md#scr-52--leadership-report) |
| SCR-53 · Management accounts | no | L | 6 | 13 | 11 | [E](screens-e-finance-payroll.md#scr-53--management-accounts) |
| SCR-54 · Income detail and schedules | yes | M | 4 | 10 | 7 | [E](screens-e-finance-payroll.md#scr-54--income-detail-and-schedules) |
| SCR-55 · Fixed asset (PPE) schedule | yes | M | 4 | 12 | 7 | [E](screens-e-finance-payroll.md#scr-55--fixed-asset-ppe-schedule) |
| SCR-56 · Cash forecast and actuals | yes | L | 4 | 12 | 7 | [E](screens-e-finance-payroll.md#scr-56--cash-forecast-and-actuals) |
| SCR-57 · Business-unit totals | no | L | 6 | 9 | 7 | [E](screens-e-finance-payroll.md#scr-57--business-unit-totals) |
| SCR-58 · Ledger source reference | yes | M | 4 | 10 | 6 | [E](screens-e-finance-payroll.md#scr-58--ledger-source-reference) |
| SCR-59 · Payroll run (restricted) | no | L | 6 | 11 | 9 | [E](screens-e-finance-payroll.md#scr-59--payroll-run-restricted) |

## Files

| File | Holds |
|---|---|
| [screens-a-frame-core.md](screens-a-frame-core.md) | App frame and session, SCR-01 to 06, 10, 14, 15, 17, 21 |
| [screens-b-projects-setup-clients.md](screens-b-projects-setup-clients.md) | SCR-07, 08, 11, 12, 13, 19, 22, 29, 34, 35, 38, 39 |
| [screens-c-rfp-planning-reports.md](screens-c-rfp-planning-reports.md) | SCR-16, 23 to 28, 40 to 42 |
| [screens-d-delivery-issues-escalation.md](screens-d-delivery-issues-escalation.md) | SCR-30, 31, 33, 43 to 52 (shared rules DC-1 to DC-5 at the top) |
| [screens-e-finance-payroll.md](screens-e-finance-payroll.md) | SCR-09, 18, 20, 32, 36, 37, 53 to 59 |
| [backend-questions.md](backend-questions.md) | The 13-point short list, then all 222 questions by screen |
| [screen-index.json](screen-index.json) | Per screen: boards, frontend tasks and features, live operations, state ids, built, effort, wave |
| [oa.py](oa.py) | Condensed view of any live or v7 operation: `python3 delivery/connect/oa.py live GET /api/v1/work 3`, or `... live list REGEX` |

Backend sources: [Next.js handoff](../../handoffs/nextjs/README.md), [screen-to-API map](../../handoffs/nextjs/factory-api-screen-map.json), [262-state crosswalk](../../handoffs/nextjs/screen-state-crosswalk.csv), [API notes](../../docs/design/frontend-api.md). Our earlier gap list: [BACKEND-HANDOFF.md](../BACKEND-HANDOFF.md).
