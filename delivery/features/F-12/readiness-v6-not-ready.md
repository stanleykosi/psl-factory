DECISION: NOT-READY
RISK: medium
SURFACES: ui, api, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: D-NOTIFY-MODEL, D-CONVERSATION-MODEL
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-12 is FE-M4 in architecture v6. It is too big for one PR and its contract does not carry the approved boards, so it is NOT-READY as a whole. I propose three slices: **F-12A** alerts inside the app, **F-12A2** the bell and account menu in the top bar (after F-05 merges), and **F-12B** the assistant. The four WhatsApp and email boards go to the backend alert job (T-ALERTS); the frontend's only part is the links they open.
- The header rates the first slice, F-12A: medium risk; `ui, api, security, contract-change`. The whole of FE-M4 is **high** risk because of the assistant (see Risk). BLOCKING-DECISIONS lists the gate for each slice: D-NOTIFY-MODEL for F-12A and F-12A2, D-CONVERSATION-MODEL for F-12B.
- These gates pass: FE-M4 has no gate_ids (delivery.md:1165-1196). It depends only on T-FRONTEND-SHELL, which is merged (F-01). D-NOTIFY-MODEL r2 and D-CONVERSATION-MODEL r2 are approved as working assumptions (architecture/packages/v6/reviews.json). The client approved SCR-05 and SCR-15 on 13 Nov (design/review.json, canvas 1794581312-b166). D-ALERT-PROVIDERS and D-AGENT-PROVIDER are still open, but they gate only T-ALERTS and T-ASSISTANT. The frontend calls no provider, and runs on the mock only.
- What fails: under the standing rule (boards are the spec, nothing omitted), every SCR-15 and SCR-05 board shows things the v6 contract does not carry. D-NOTIFY-MODEL r2 is one channel and one frequency per person. The approved settings boards are a per-event WhatsApp/email matrix with digest time, quiet hours and a verified WhatsApp number. There is also no way to read preferences (only PUT). The assistant has no conversation list, no step status or step references, and no draft object. A builder could only invent these or omit them. Decisions (f) and (g) (architecture/sources/decisions-2026-11-14-v2.md) set the route: the frontend drafts the missing fields as proposals, they are recorded in the next architecture revision (v7), the same way D-START-INTAKE was recorded in v6, and the slice is built against the mock.
- F-12A becomes READY once v7 carries D-NOTIFY-MODEL r3 as listed under PMO-0-1 and the design engineer accepts it as a working assumption. Nothing in F-12A needs a client answer. The product questions below (PMO-0-6 to PMO-0-9) block only F-12A2 and F-12B.

## Findings
- PMO-0-1 | blocking | high | backend | The alert contract does not carry the approved SCR-15 boards. The frontend should draft D-NOTIFY-MODEL r3 as an additive proposal under (g), to be recorded in architecture v7. It needs:
  - (a) a read operation, GET `/api/v1/me/alert-preferences`, returning the same shape PUT accepts, plus a `revision` (PUT already declares 409 for a stale revision but has nothing to send it with);
  - (b) `events[]` with `key`, `label`, `whatsapp: bool`, `email: bool` and a read-only `timing` (immediate or daily digest). The board rows are: "A decision is waiting for me", "Information is requested from me", "Work I started is stuck", "Work I started is verified" and "Everything else";
  - (c) `digest_at`, and `quiet_hours` with `options[]` for both selects (desktop: "08:00", "20:00 to 07:00, and weekends");
  - (d) `whatsapp: {masked_number, verified}`, read-only (the number is shown masked, "+234 803 *** 4412 · verified");
  - (e) a decision on whether the v6 `channel`/`frequency` fields stay as optional summaries or are replaced. Today they are `required` in PUT, so dropping them is not additive;
  - (f) on E-NOTIFICATIONS items: `delivered_via[]` (whatsapp, email, in_app), `digest_at` (when it went out in a digest), and `in_app_reason` (e.g. "you are not HR"). The board lines are "WhatsApp and email · 10:42", "Email · 09:00 daily digest", "In app only (you are not HR)" and "In app · yesterday";
  - (g) on E-NOTIFICATIONS itself: a `q` search parameter, filter parameters, a `total` ("4 ALERTS") and an `unread_count` for the bell;
  - (h) a mark-read operation, or a rule that opening an item marks it read. The contract has `read` but nothing that changes it, and the NEW tag depends on it.

  Every value stays backend-owned: which events exist, which channels a restricted alert may use, and what quiet hours suppress. The frontend only shows and saves what the API returns.
- PMO-0-2 | blocking | high | backend | The assistant contract does not carry the approved SCR-05 boards. The frontend should draft D-CONVERSATION-MODEL r3 for v7. It needs:
  - (a) a conversation list: title, status line (e.g. "Drafted · ready to start", "Working · step 3 of 5", "Can't share"), agent, day group ("TODAY");
  - (b) on the conversation: `agent`, and a status of working, answered, cannot_answer or drafted. Today the status exists only on the POST reply, so a page reload loses it;
  - (c) steps as `{text, state: done|now|next, reference}` instead of strings;
  - (d) a `handoff` note ("Tola passed this to him");
  - (e) sources with a link target;
  - (f) a draft object: title, label/value rows, "DRAFTED · NOT REVIEWED", start label, a "next" line, and what to start (line, case, case_revision, intake prefill) through the normal E-WORK-START (D-CONVERSATION-MODEL r2: "drafts are created only through the normal line start"), plus the started work reference;
  - (g) the side-panel context, project and "Your access";
  - (h) the agents this person may talk to (E-CONVERSATION-NEW: "the agent must serve the person's role"; the PMO board shows all three);
  - (i) `mentions[]` on E-MESSAGE, and a search for projects and records to mention;
  - (j) attachments (reuse E-EVIDENCE-UPLOAD or not).
- PMO-0-3 | blocking | medium | pmo | FE-M4 is too big for one reviewable PR: 20 boards, 5 endpoints, edits to the shared shell and a cross-feature start. It is split as set out in Scope. F-12A alone is one observable outcome.
- PMO-0-4 | non-blocking | medium | backend | Four boards show messages outside the app: SCR-15-desktop-whatsapp, SCR-15-mobile-whatsapp, SCR-15-desktop-email and SCR-15-mobile-email. The frontend cannot draw a WhatsApp chat or an email client, so these boards are the content spec for the T-ALERTS / JOB-ALERTS message templates (external-messaging, I-ALERTS data rule: "no amounts or client details").
  - F-12A owns only the in-app ends of those boards: "Review now" opens `/work/<work_id>` and returns there after sign-in (the existing `SignedOutState` pathname), and "alert settings" in the email opens the stable `/settings/alerts` route.
  - Expected: the coordinator records these four boards in `delivery/features/F-12/fidelity-exceptions.json` as "rendered by the backend alert job, not the frontend", so the UI gate does not fail on them. Only the design engineer can approve that.
- PMO-0-5 | non-blocking | medium | integration | The contract repoint. F-05 moves the mock and `schema.d.ts` from v4 to v6 (F-05/readiness.md PMO-0-4). F-12A must start from a base that already has F-05's repoint, and do the v6 to v7 repoint itself: `frontend/mock/server.mjs` OPENAPI_PATH, `package.json` gen:api, a regenerated `src/api/schema.d.ts`, `tests/api-schema-drift.test.ts`, and the version comment in `src/api/client.ts`.
  - This happens only if no other lane is assigned v7 first. The coordinator names one lane.
  - Every existing fixture must still pass `tests/mock-contract.test.ts` against v7.
- PMO-0-6 | non-blocking | medium | product | No board draws the bell. Only the site map says "Bell, top right" (SITEMAP-desktop.dc.html), and every top bar on the approved boards, SCR-15 included, has none. The account menu offers "Alert settings" but not "Notifications". So `/notifications` has no drawn way in. F-12A2 cannot pass the fidelity gate on something that was never drawn.
- PMO-0-7 | non-blocking | medium | product | The account menu boards (SCR-15-desktop-account, SCR-15-mobile-account) have gaps:
  - "My roles" and "Delegate while away" link to `#`. No screen is drawn for them; E-DELEGATION is Setup's.
  - "Sign out" has no operation in v6 (endpoints.csv has no session or logout endpoint).
  - The phone board is a page with "← Home", but no phone board shows how it is opened.
  - Settle these before F-12A2's readiness. Sign-out adds `auth`.
- PMO-0-8 | non-blocking | low | product | The phone settings board (SCR-15-mobile-settings) has 4 event rows, no "Everything else", no digest-time select and no WhatsApp number. Quiet hours are shown as text. On a phone those cannot be changed. Under the standing rule F-12A builds each width exactly as drawn. If that is not what the design engineer intends, the boards need a fix or a fidelity exception, decided before the UI round.
- PMO-0-9 | non-blocking | medium | product | The SCR-05 composer has "Speak your request". Browser speech recognition can send audio to the browser maker's servers, which is an external connection, and none is authorised. Before F-12B: built and wired to nothing, built against an approved local engine, or a recorded fidelity exception?
- PMO-0-10 | non-blocking | low | frontend | The filter panel for notifications (CMP-22 on SCR-15) is not drawn open. When D-NOTIFY-MODEL r3 is drafted, its filter facets (engineering proposal: agent, unread) are proposals and are flagged for product acceptance. The builder must not add facets beyond the proposal.

## Scope
**Binding for the spec writer once PMO-0-1 is closed.** Until then F-12A must not be specced.

**Boards in scope, by file name (design/canvas/project/), with their slice. Nothing on a board may be omitted.**

| Board | Slice |
|---|---|
| SCR-15-desktop.dc.html | F-12A |
| SCR-15-mobile.dc.html | F-12A |
| SCR-15-desktop-settings.dc.html | F-12A |
| SCR-15-mobile-settings.dc.html | F-12A |
| STATES-desktop.dc.html, STATES-mobile.dc.html (the SCR-15 "empty" state, plus loading and error) | F-12A |
| SCR-15-desktop-account.dc.html | F-12A2 |
| SCR-15-mobile-account.dc.html | F-12A2 |
| the bell, when drawn (PMO-0-6) | F-12A2 |
| SCR-15-desktop-whatsapp.dc.html | T-ALERTS (backend); F-12A owns only the "Review now" target |
| SCR-15-mobile-whatsapp.dc.html | T-ALERTS (backend); F-12A owns only the "Review now" target |
| SCR-15-desktop-email.dc.html | T-ALERTS (backend); F-12A owns the "Review now" and "alert settings" targets |
| SCR-15-mobile-email.dc.html | T-ALERTS (backend); F-12A owns the "Review now" and "alert settings" targets |
| SCR-05-desktop.dc.html, SCR-05-mobile.dc.html | F-12B |
| SCR-05-desktop-thread.dc.html, SCR-05-mobile-thread.dc.html | F-12B |
| SCR-05-desktop-draft-started.dc.html, SCR-05-mobile-draft-started.dc.html | F-12B |
| SCR-05-desktop-cant.dc.html, SCR-05-mobile-cant.dc.html | F-12B |
| SCR-05-desktop-working.dc.html, SCR-05-mobile-working.dc.html | F-12B |

**F-12A, alerts in the app (first slice).**
- **Outcome (one, observable):** a signed-in person opens `/notifications` and sees their alerts. Each alert shows the agent avatar, the text, how and when it was delivered, NEW while unread, search, Filter and the count. Opening an alert goes to its work item. "Alert settings" opens `/settings/alerts` ("How you're alerted"), where they change WhatsApp and email per event, the digest time and quiet hours, and press Save settings. Then:
  - a 409 reloads and shows the newer version, keeping nothing stale;
  - a 422 names the field;
  - a 401 goes to the signed-out state;
  - empty, loading and error follow the STATES boards.

  This works at 390px and 1440px on the v7 contract mock, and the frontend half of A-ALERTS (preference saved, notification listed), the design-fidelity gate on every F-12A board, and A-ACCESSIBILITY pass.
- **In:**
  - the two routes;
  - CMP-18, CMP-19 and CMP-22 as drawn;
  - the switches as real toggles with accessible names ("WhatsApp, A decision is waiting for me");
  - the CSRF header on the save;
  - the masked WhatsApp number shown exactly as returned, never unmasked or edited;
  - the mock handlers and fixtures from the v7 proposal, including a restricted "in app only" alert and a daily-digest alert;
  - `NotificationBell` and `AccountMenu` built and exported from `src/features/alerts/`, unit-tested, and not mounted;
  - the repoint (PMO-0-5).
- **Out:**
  - `src/shell/**` (F-05 owns it until it merges);
  - the bell and account-menu mount (F-12A2);
  - sending anything; WhatsApp or email providers; message templates (T-ALERTS);
  - the assistant (F-12B);
  - backend and `apps/api`;
  - the real API (FE-CONNECT-1);
  - editing `architecture/**` or `openapi.json` in the feature branch (v7 comes from the architecture stage);
  - new npm dependencies.
- **Task IDs:** FE-M4, alerts part (R-ALERTS; D-NOTIFY-MODEL r3 as a working assumption once recorded). **Endpoints:** E-NOTIFICATIONS, E-ALERT-PREFS and the v7 read and mark-read operations from PMO-0-1, all on the contract mock.
- **Ownership:**
  - Owns: `frontend/src/app/notifications/**`, `frontend/src/app/settings/alerts/**`, `frontend/src/features/alerts/**`, `frontend/mock/alerts.mjs`, `frontend/mock/fixtures/alerts/**`, `frontend/tests/alerts*.test.ts(x)` and `frontend/e2e/alerts.spec.ts`.
  - Shared seams, listed in build.md: one line each in `server.mjs` (`M1_OPERATIONS` and the dispatch) and the repoint files in PMO-0-5.
  - Must not touch: `src/shell/**`, `src/app/assistant/**`, `src/features/assistant/**`, `src/features/start-work/**`, or other lanes' mock files.

**F-12A2, bell and account menu in the top bar (after F-05 merges).** It does its own readiness once PMO-0-6 and PMO-0-7 are answered. It mounts the exported `NotificationBell` and `AccountMenu` in `src/shell/TopNav.tsx` and `src/shell/PhoneBar.tsx`, and edits nothing else in the shell. It replaces the TopNav comment "No Start work, bell or account menu in this release" and updates `tests/shell.test.tsx`. It must start from a base that already has F-05's merge, because F-05 is the only lane that edits the shell until then. Expected surfaces: `ui, api, auth` (sign-out).

**F-12B, assistant (SCR-05, all five states).** It does its own readiness once PMO-0-2 and PMO-0-9 are settled and F-05 has merged:
- the draft's start goes through F-05's exported start-work entry and E-WORK-START, never a separate start path;
- it owns `frontend/src/app/assistant/**` (replacing the `DestinationPage` placeholder), `frontend/src/features/assistant/**`, `frontend/mock/assistant.mjs`, `frontend/mock/fixtures/assistant/**`, and its own tests and e2e;
- it runs on the mock or synthetic agent only, with no provider, key or external call;
- the agent pose and avatar images must be exported from the canvas into `frontend/public/` (an asset step, no dependency).

## Risk
F-12A is **medium**:
- It writes the person's own alert preferences. That is a CSRF-bound PUT with a revision and 409/422 recovery (handoff.md:8436-8634).
- It shows personal data: a masked phone number, and alerts that must say "in app only" for restricted work.
- It does the shared v6 to v7 contract repoint for every lane.
- It does not send, pay, or touch identity or the shell.

Its surfaces:
- `ui`: SCR-15 list and settings, and the STATES boards.
- `api`: E-NOTIFICATIONS, E-ALERT-PREFS and the v7 read/mark-read.
- `security`: CSRF, own-records-only, masking, nothing derived from roles.
- `contract-change`: the consumer of the D-NOTIFY-MODEL r3 proposal, and the repoint.

`external-messaging` belongs to T-ALERTS, because the frontend sends nothing. `auth` belongs to F-12A2 (sign-out).

The whole of FE-M4 is **high**. The F-12B assistant shows agent output that cites restricted records (A-ASSISTANT: payroll "cannot answer, says why"; I-AGENT data rule). It shows invoice amounts in drafts (SCR-05 thread: "₦6,800,000.00"). It starts work through E-WORK-START. It carries the open D-AGENT-PROVIDER and a possible external speech connection. That adds `payments` and `product-decision`.

Product acceptance is required for every slice. These are new client-facing flows, and every field drafted under PMO-0-1 and PMO-0-2 is a proposal the client has not seen working.

## Notes
- I did not run `design.py check`. My role is read-only and has no shell. The coordinator should confirm it passes for canvas 1794581312-b166 before the spec.
- The coordinator relayed the standing rule (boards are the spec, mock data from a contract proposal where the API lacks fields, fidelity at 100% coverage and visual >= 90). Only part of it is recorded, in delivery/OVERNIGHT-DECISIONS.md. The "mock data from a proposal" part should be recorded next to decisions (f) and (g), so that the v7 proposal step has a written source.

## Questions
None for F-12A. The product questions (PMO-0-6 to PMO-0-9) gate only F-12A2 and F-12B and are listed under Findings.
