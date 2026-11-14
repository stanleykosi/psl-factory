DECISION: READY
RISK: medium
SURFACES: ui, api, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
COMMIT: none (round 0, no head yet)
REVIEWER: readiness
AUTHORITY: PMO readiness (delivery step 1)

## Summary
- F-12 is now **FE-ALERTS** (slice F-12A) in architecture v7 (architecture/packages/v7/delivery.md:3004-3035): the notifications list, alert settings and their STATES. It has no gate_ids and no unresolved gates, and it is one observable outcome that fits one PR. My v6 NOT-READY (readiness-v6-not-ready.md) is closed. Every field PMO-0-1 (a)-(h) asked for is now in v7: D-NOTIFY-MODEL r3 (model.json:599-611), D-ALERT-PREFS-VIEW r1 (model.json:1463-1490), E-ALERT-PREFS-READ, E-NOTIFICATION-READ, and the extended E-NOTIFICATIONS and E-ALERT-PREFS (openapi.json:9507-10230, 13259).
- These decisions are r1/r3 `proposed`, and v7/reviews.json marks the r2 approval of D-NOTIFY-MODEL `stale`. They count **only** under the design engineer's recorded exception, architecture/sources/decisions-2026-11-14-v2.md (g) and decisions-2026-11-15.md (i), with its limits: the contract mock only, the backend developer may change or refuse any field, and nothing is released. That is why BLOCKING-DECISIONS is `none`. The client approved SCR-15 on 13 Nov (design/review.json, canvas 1794581312-b166).
- The bell and account menu (FE-ALERTS-MENU, gated by D-ALERTS-ENTRY and D-SIGNIN) and the assistant (FE-ASSISTANT) are out. Unlike my v6 scope, F-12A no longer builds an unmounted `NotificationBell` or `AccountMenu`: no board draws the bell. The four WhatsApp and email boards are T-ALERTS message content. They go to the design engineer as an exception request, not as an omission (PMO-0-3).
- Sequencing: FE-ALERTS `depends_on` FE-CONTRACT-V7 (F-13, READY but not merged). As the coordinator directed, F-12 builds in parallel. It keeps proposal types and schemas local, does not touch the repoint files, and treats a missing proposal field as unknown. **It merges only after F-13 has merged and F-12 has been rebased onto it.** That is how the architecture dependency gets met (PMO-0-1).
- Risk is medium. F-12 writes the person's own preferences through a CSRF-bound, revisioned PUT, and it marks alerts read. It shows a masked phone number and alerts that stayed "in app only" because the work is restricted. It sends nothing and does not touch the shell, money or identity.

## Findings
- PMO-0-1 | non-blocking | medium | integration | The architecture dependency FE-CONTRACT-V7 (F-13) is not merged. The base mock loads v4 (`frontend/mock/server.mjs:22`), and its routes come only from that file (`loadRoutes`, server.mjs:154-166). So GET `/api/v1/me/alert-preferences` and POST `/api/v1/notifications/{id}/read` answer 404 on the base. Binding:
  - (a) Copy the v7 path items for E-NOTIFICATIONS, E-ALERT-PREFS, E-ALERT-PREFS-READ and E-NOTIFICATION-READ verbatim into `frontend/mock/proposals/alerts.json`. A test asserts they deep-equal `architecture/packages/v7/openapi.json`, so the overlay cannot drift. Fixtures and request bodies validate against the overlay, and the same bodies with the proposal fields removed must still validate against the base contract for E-NOTIFICATIONS and E-ALERT-PREFS. This is the F-11 PMO-0-2 pattern.
  - (b) Local TypeScript types live in `frontend/src/features/alerts/contract-proposal.ts`. Do not touch `src/api/schema.d.ts`, `package.json` gen:api, `tests/api-schema-drift.test.ts` or `src/api/client.ts`: those are F-13's.
  - (c) The server.mjs seam is listed in build.md and limited to three things: merging the overlay's routes only where the loaded openapi lacks them, the four operation IDs in `M1_OPERATIONS`, and one dispatch line into `mock/alerts.mjs`.
  - (d) Merge precondition: F-13 is merged and F-12 is rebased onto it. The rebase then deletes the overlay route merge and the local types, uses the regenerated v7 `schema.d.ts`, and validates the fixtures directly against v7 (F-13/readiness.md PMO-0-1). The coordinator checks this at integration.
- PMO-0-2 | non-blocking | medium | frontend | "Tolerate absence" has to be a rule, or the builder will guess. Binding: every element that depends on a proposal field renders only when the API returns that field, and is never defaulted or derived.
  - No `total`: no "N ALERTS" line, and never "0". No `unread_count`: no unread count.
  - No `delivered_via`: no delivery line. No `in_app_reason`: no reason text.
  - Search and Filter are shown only when the response carries `total`. This is the same rule the F-06 escalation proposes (OVERNIGHT-DECISIONS.md:24).
  - If E-ALERT-PREFS-READ fails, or returns no `events`, the settings page shows the STATES error card, with no matrix and no Save. Channel and frequency are never presented as a substitute editor, because no board draws one. Record this copy for product acceptance.
- PMO-0-3 | non-blocking | medium | product | The four boards SCR-15-desktop-whatsapp, SCR-15-mobile-whatsapp, SCR-15-desktop-email and SCR-15-mobile-email show messages that the backend alert job renders (T-ALERTS / JOB-ALERTS, I-ALERTS: "no amounts or client details"). delivery/screen-coverage.md:118 maps no frontend task to them. Expected: the coordinator asks the design engineer to record them in `delivery/features/F-12/fidelity-exceptions.json` as "rendered by the backend alert job, not the frontend". This is an exception request, and only the design engineer can approve it. F-12A owns only their in-app targets: "Review now" opens `/work/<work_id>` (after sign-in it returns there through `SignedOutState`'s pathname), and the email's "alert settings" link opens `/settings/alerts`. Both routes must be stable.
- PMO-0-4 | non-blocking | low | frontend | Contract details the builder must not paper over. Binding engineering proposals, listed in build.md for the backend developer:
  - (a) PUT requires `channel` and `frequency` and has no control for them on the board. Send them back exactly as GET returned them. A GET value outside the PUT enums (GET types them as free strings) is a 422 that is shown as returned; it is never remapped.
  - (b) Send `expected_revision` exactly as read. If GET returned no `revision`, omit it.
  - (c) The settings save sends only `events[].{key, whatsapp, email}`, plus `digest_at` and `quiet_hours` from the returned options. Events with a `locked_reason` are shown read-only, and the reason is shown as returned.
  - (d) Opening an alert calls E-NOTIFICATION-READ (CSRF), then goes to `/work/<work_id>`. A failed mark-read does not block the navigation, leaves NEW in place and is not retried in a loop. The `unread_count` shown is the one the API returns.
  - (e) The masked number is shown exactly as returned. It is never unmasked, edited or reformatted.
- PMO-0-5 | non-blocking | low | product | The phone settings board (SCR-15-mobile-settings) draws 4 event rows, no "Everything else", no digest-time select and no WhatsApp number, and it shows quiet hours as text. Binding under the boards-are-spec rule: the phone renders every event row the API returns. The fidelity run uses a board-shaped scenario cookie (precedent: D-04(f), OVERNIGHT-DECISIONS.md:33). Quiet hours appear as the drawn text line, and the phone has no digest select and no number, as drawn. A phone save sends only `events`. The design engineer may ask for the missing controls later. Note this for product acceptance.
- PMO-0-6 | non-blocking | low | integration | The standing rule says agent avatars use `frontend/public/agents/*.png`, but that folder does not exist on the base (`frontend/public/` is empty). The boards embed the avatars as canvas blobs. Expected: if no merged lane supplies the folder when F-12 branches, F-12 adds three avatar files copied unchanged from `design/mascots/transparent/{pmo,finance,hr}-avatar.png` (tola, chidi, zainab, matching the v7 `agent` filter enum). This is an asset step with no dependency. The coordinator reconciles it with any other lane that adds the same files. The builder lists the mapping in build.md.
- PMO-0-7 | non-blocking | low | frontend | The Filter panel (CMP-22) is not drawn open. Its facets are exactly the v7 parameters, `agent` (enum) and `unread`. Do not add more. Their layout is an engineering proposal, flagged for product acceptance.

## Scope
**Binding for the spec writer.**

**Outcome (one, observable):** a signed-in person opens `/notifications` and sees their own alerts. Each alert shows the agent avatar, the text, and how and when it was delivered or why it stayed in the app. NEW shows while an alert is unread. The page has search, Filter (agent, unread) and the count. Opening an alert marks it read and goes to its work item. "Alert settings" opens `/settings/alerts` ("How you're alerted"). There the person turns WhatsApp and email on or off per event, picks the digest time and quiet hours from the returned options, and presses Save settings, which returns a new revision. Then:
- a 409 reloads and shows the newer version, keeping no stale edits;
- a 422 names the field;
- a 401 goes to the signed-out state;
- empty, loading and error follow the STATES boards.

This works at 390px and 1440px on the contract mock. The frontend halves of A-ALERTS (preference saved, notification listed), A-ALERT-PREFS and A-NOTIFICATIONS pass, and so do A-ACCESSIBILITY and the design-fidelity gate (100% of elements after approved exceptions, visual >= 90) on every board in scope.

**Boards in scope (design/canvas/project/):**
- SCR-15-desktop.dc.html
- SCR-15-mobile.dc.html
- SCR-15-desktop-settings.dc.html
- SCR-15-mobile-settings.dc.html
- the SCR-15 empty state, plus loading and error, on STATES-desktop.dc.html and STATES-mobile.dc.html

Out of scope:
- the four WhatsApp and email boards (PMO-0-3);
- SCR-15-desktop-account and SCR-15-mobile-account (FE-ALERTS-MENU).

**In:**
- the routes `/notifications` and `/settings/alerts`, inside the existing AppShell, with the phone "← Notifications" back link placed per D-08;
- CMP-18, CMP-19 and CMP-22 as drawn;
- the switches as real toggles with accessible names ("WhatsApp, A decision is waiting for me");
- CSRF on the PUT and on mark-read;
- the mock handlers, the overlay and the fixtures (PMO-0-1), including:
  - four alerts, one of them restricted "in app only (you are not HR)" and one sent in a daily digest;
  - an empty list;
  - a stale-revision save;
  - a 422;
  - a locked event;
  - a response with the proposal fields absent (PMO-0-2);
- the avatar assets if they are missing (PMO-0-6).

**Out:**
- `src/shell/**`, including any bell, account menu or nav entry (FE-ALERTS-MENU);
- the assistant (FE-ASSISTANT);
- sending anything: WhatsApp or email providers and message templates (T-ALERTS);
- backend and `apps/api`;
- the real API;
- the v7 repoint files (F-13);
- editing `architecture/**` or `openapi.json`;
- new npm dependencies.

**Task IDs:** FE-ALERTS (R-ALERTS), under D-NOTIFY-MODEL r3 and D-ALERT-PREFS-VIEW r1 as working assumptions within exception (g)/(i).

**Endpoints:** E-NOTIFICATIONS, E-NOTIFICATION-READ, E-ALERT-PREFS-READ and E-ALERT-PREFS, all on the contract mock.

**Ownership:**
- **Owns:**
  - `frontend/src/app/notifications/**`
  - `frontend/src/app/settings/alerts/**`
  - `frontend/src/features/alerts/**`
  - `frontend/mock/alerts.mjs`
  - `frontend/mock/proposals/alerts.json`
  - `frontend/mock/fixtures/alerts/**`
  - `frontend/public/agents/*.png` (only if missing)
  - `frontend/tests/alerts*.test.ts(x)`
  - `frontend/e2e/alerts.spec.ts`
- **Shared seams, listed in build.md:** the server.mjs lines in PMO-0-1 (c).
- **Must not touch:**
  - `src/shell/**`
  - `src/api/schema.d.ts` and the other F-13 files
  - `src/app/assistant/**`, `src/features/assistant/**` and `src/features/start-work/**`
  - other lanes' mock files and fixtures

## Risk
Medium.
- **The writes are the person's own, and only two.** One is the alert-preference PUT: CSRF, revisioned, with 409/422 recovery (v7 openapi.json:9774-10165). The other is mark-read (openapi.json:13259).
- **The data is sensitive.** The screens show a masked phone number, and restricted alerts must stay "in app only" with no detail leaking.
- **The contract is a proposal.** The fields come from r1/r3 proposals the backend developer may refuse (D-ALERT-PREFS-VIEW, D-NOTIFY-MODEL), so the screens must not treat a missing field as zero, and the merge waits on F-13's repoint.
- **Nothing is hard to undo.** Nothing touches money, identity, the shell, migrations or a send.

Surfaces:
- `ui`: the SCR-15 list and settings boards, and the STATES boards.
- `api`: the four operations above.
- `security`: CSRF, own records only, masking, and visibility never derived from roles.
- `contract-change`: F-12 consumes the v7 proposal fields through a local overlay until F-13 merges.

Not included:
- `external-messaging` belongs to T-ALERTS.
- `auth` (sign-out) belongs to FE-ALERTS-MENU.
- `product-decision` does not apply: no business rule is set here. Which events exist, which channels are allowed and what quiet hours suppress all come from the backend.

Product acceptance is required. This is a new client-facing flow, and the client has not seen its proposal fields, the absent-field behaviour (PMO-0-2) or the phone layout (PMO-0-5) working.

## Notes
- I did not run `design.py check`. My role has no shell. The coordinator should confirm that it passes for canvas 1794581312-b166 before the spec.
- This file replaces readiness-v6-not-ready.md for F-12. Its PMO-0-2, PMO-0-6, PMO-0-7 and PMO-0-9 now belong to FE-ASSISTANT and FE-ALERTS-MENU, and their own readiness checks will pick them up.

## Questions
None.
