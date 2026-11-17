STATUS: READY
COMMIT: 521bbf184e45598b765b3c59c8625e20cd335980
BUILDER: builder
LANE: full

## Summary
- Contract mock only: nothing is sent, filed or created. No email, WhatsApp, recipient, real template (it stays a TEST TEMPLATE), filing or action record exists. Every "sent", "delivered" and "filed" word is fixture text. This is not a working minutes line, delivery, duplicate-send protection or filing (D-LINE-WORKSPACE is proposed; D-ALERT-PROVIDERS, D-RETURN and the audience-skips-review rule stay open).
- The F-17 frame now ends the minutes line at two reloaded views: "Filed · Internal" (W-2310) and "Published" (W-2311 to W-2314): returned sentence, actions table (action, owner, due, state, OWNER NEEDED only where returned), Sent to with per-person receipts, Next, Open actions.
- Reached through existing calls only: W-2301 confirm with audience Internal (new audience branch in the mock) and the F-16 approve on W-2309.
- Uncertain send (W-2312) keeps the lock: only the reconcile panel acts; one POST to /actions; no resend.
- Fidelity: coverage 100 after exceptions on all 4 boards; visual 76.9, 85.8, 81.5, 89.9, all under 90, so a D-83 visual waiver is requested (open for the design engineer).

## Changes
- `frontend/src/features/workspace/proposals.ts`: link kind `project_tab` (PROPOSAL, G-SCR28-3), only for a key in `PROJECT_TABS` and a valid case id; links to `/projects/{case_id}{tab path}`. Reason: "Open actions".
- `frontend/src/features/workspace/Links.tsx`: draws `project_tab` as a `Link`.
- `frontend/src/features/workspace/labels.ts`: `RECORD_ID` exported (reused, not new).
- `frontend/src/features/workspace/Sections.tsx`: a recipients row with a `channel` and no receipt or tag reads "Unknown" instead of blank (AC 6, never blank). A row with no channel (F-21's "Approved by" line) is unchanged.
- `frontend/mock/workspace.mjs`: `inputs.audience` serves `<id>.next.<audience>` when it exists, else `<id>.next`.
- Fixtures `frontend/mock/fixtures/work/`: W-2309 (+ `.approve`), W-2310, W-2311, W-2312, W-2313 (+ `.steps`), W-2314, `W-2301.next.internal`. No existing fixture edited.
- Tests: `tests/minutes-end.test.tsx` (42), `tests/minutes-end-mock.test.ts` (9), `tests/mock-contract.test.ts` (project_tab link schema checked alone; new F-28 describe; the F-23 describe's regexes narrowed to W-2301..2308 so its "8 items" count still means the same eight), `e2e/minutes-end.spec.ts` (22).
- `delivery/BACKEND-HANDOFF.md`: "Added during F-28".
- Factory files (project folder, uncommitted): `fidelity-exceptions.json`, `round-1/fidelity/**`.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Desktop boards coverage 100 with exceptions: 100 and 100. Visual 76.9 and 81.5 are under 90: waiver requested, not signed (open design engineer decision).
2. [x] Phone boards: coverage 100 with exceptions; visual 85.8 and 89.9, waiver requested, not signed.
3. [x] Exceptions limited: 16 entries, each maps to Conflicts 2, 4, 5, 7 or 11; none covers a data value. Their `approved_by` is "builder proposal, pending design engineer".
4. [x] Internal from data: minutes-end.test.tsx; sentence "3 actions" over two rows shown unchanged.
5. [x] Published from data: component test; e2e at 1440 and 390.
6. [x] Per-person receipts over all five values plus absent; no "Delivered" or "delivery confirmed" in `src/features/workspace` (grep empty).
7. [x] Lock: component test (recording fetch) and e2e at 1440 and 390 incl. reload: one POST to /actions, none to steps, claim, decision.
8. [x] No claim beyond data: component test with every recipient not_yet.
9. [x] OWNER NEEDED and Unknown: component tests on W-2311/W-2314, including row text "owner Tunde".
10. [x] Links from data only: table of valid and refused targets (unknown tab, no case, dot segments, slash, absolute, protocol-relative, encoded, leading dot, whitespace, query); W-2312 sends one GET /documents/D-2304/versions/1.
11. [x] Reaching internal: component and e2e (both widths); Client still ends on drafted.
12. [x] Reaching published: e2e at both widths with F-16 requests only; reload sends no non-GET.
13. [x] Owner assignment built (W-2313): one POST, expected_revision 8, UUID key, blank left out, 422 under the field, 409 reloads. Not on W-2310/2311/2314.
14. [x] 403/404 show no title/client/id; 401 shows the signed-out callout.
15. [x] Personas pm, ceo, finance_lead see the same controls; no /me read added.
16. [x] No request on a timer (60 s fake time); all e2e requests to localhost; no new resend/send-again text (grep hits are existing comments).
17. [x] a11y e2e (axe wcag2a to 22aa, one h1, no sideways scroll, focus, 44px phone targets, no wrapped tags or buttons, reduced motion) pass for W-2310..W-2314 at both widths.
18. [x] No new colour literals (CSS untouched); no new local components.
19. [x] No change in `src/api`, `apps`, `architecture`, `design` or protected paths; fixtures need only the project_tab and existing proposal keys stripped.
20. [x] minutes-end-mock.test.ts and mock-contract pass.
21. [x] This file states the overclaim limits above.
22. [x] Existing tests unchanged in assertion, `delivery/checks.sh` rc=0; e2e minutes.spec.ts and weekly-returned-received.spec.ts 43 passed.
23. [x] See this file.

## Validation
- `cd f-28 && bash delivery/checks.sh` (under the shared lock): rc=0, production build ok.
- `npx vitest run tests/minutes-end.test.tsx tests/minutes-end-mock.test.ts tests/mock-contract.test.ts`: pass.
- `E2E_PORT=4792 MOCK_PORT=4791 npx playwright test e2e/minutes-end.spec.ts`: 22 pass. `e2e/minutes.spec.ts e2e/weekly-returned-received.spec.ts`: 43 pass. (Ports swapped from the spec per coordinator: mock 4791, app 4792.)
- Fidelity on `next build` + `next start -p 4792`, mock 4791, two runs (the first to list missing items for the exceptions): see `round-1/fidelity/scores.txt`.
  - SCR-28-desktop-internal 1440: coverage 63 (100 with exceptions), visual 76.9
  - SCR-28-mobile-internal 390: 40 (100), 85.8
  - SCR-28-desktop-published 1440: 63 (100), 81.5
  - SCR-28-mobile-published 390: 40 (100), 89.9
  Remaining gaps are the frame's panel layout and the added Owner/Due columns, Sent to list and full phone sections. A heading hierarchy or green banner restyle was not attempted (frame change outside this lane).
- Servers on 4791/4792 stopped; `frontend/test-results` removed.

## Exceptions (fidelity-exceptions.json)
Conflicts 11 (crumbs, tab bar and counts), 5 (phone back link, bar tags, phone short sentences), 2 and 7 (returned sentence not read inside a list row; panel not a band), 4 (phone composition). Conflicts 1, 3, 6, 8 to 10, 12 add extra items (Sent to, Owner and Due columns, Open actions placement); the tool reports them as extras, not missing. Decisions made under D-111 as recommended: Option A everywhere.

## Frame changes and reasons
project_tab link (Open actions); Unknown for a recipient on a channel with no receipt (spec AC 6 says never blank; F-21's channel-less "What happened" line is unchanged, so the rule keys on `channel`).

## Proposals and backend items
G-SCR28-3 `project_tab` (built, stripped in the contract test); `link.action_id` not built. Recorded in BACKEND-HANDOFF: G-SCR28-6, -7, -8, G-SCR25-1, the audience rule, unbuilt endpoints and idempotency, SEC-5-C1, D-RETURN, tab counts. Held list from the spec "What is sent": all seven items remain held.
Fixture note: internal facts that do not apply (reviewed, approved, sent, receipt) are `not_yet` because the schema has no not-applicable fact status.

## Blocked
Not blocked. Open for the design engineer: sign the four D-83 visual waivers (76.9, 85.8, 81.5, 89.9) and the 16 exceptions.
