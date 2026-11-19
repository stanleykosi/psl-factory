STATUS: READY
COMMIT: d12c2769dbd23763f89f3e176de2f5f1d8d94417
BUILDER: builder
LANE: full

## Summary
- `/work/W-3201`…`W-3204` show SCR-52's drafting, review, Tuesday and received states. Everything on them comes from the `workspace` block of the E-WORK-ITEM response (`line_key: "leadership_report"`). Desktop and phone show the same sections, one column on the phone.
- The leadership review is decided on the page through F-33's `InlineDecide` and the F-16 `useDecision`: one claim, then one decision. The buttons appear only when `tasks[].you_can_act` is true. "Sent", "delivered" and "received" appear only when the re-read item says so. An uncertain decide reads "Monthly report v1: result not confirmed".
- The reviewer and audience are not set. W-3207 shows the backend's hold, with no control, no request and no reviewer named. "Send for leadership review" appears only where the backend sends that step (W-3205, W-3212).
- Added: two line sets that replace F-33's income-only checks; an information banner on this line; "Started 01 Nov 08:00" in the agent card footer. Also 12 fixtures plus 6 sidecars, unit, mock and e2e tests, and a backend handoff section. No mock server change, no contract change, no change to shared decide or response code.
- Base 6f14afbf contains F-33 (merge 4059b84a / PR #64), F-31 and F-32.

## Changes
- `frontend/src/features/workspace/labels.ts`: `AGENT_BESIDE_LINES` (`income_schedules`, `leadership_report`) and `STATION_LINES` (`income_schedules`).
- `frontend/src/features/workspace/Workspace.tsx`:
  - The stations and the working agent beside the sections now come from these sets.
  - `REPORT_LINE` banner tone (Conflicts 12): verified is success, stopped or uncertain is problem, agent or neutral is `info`, anything else is warning.
  - `LineAgent` takes `day`, so the footer uses `formatDayTime` on this line (Conflicts 13).
- `frontend/src/features/work-item/WorkItemOverview.tsx`: the same sets replace F-33's income checks for the screen-reader track and agent card, and for the `already_decided` task filter.
- `frontend/src/features/workspace/Sections.tsx`: `SectionView` `banner` also accepts `info` (additive).
- No CSS changed.
- Fixtures `frontend/mock/fixtures/work/W-3201…W-3212.json`, plus sidecars `W-3202.approve`, `W-3202.return`, `W-3205.next`, `W-3205.steps`, `W-3209.approve`, `W-3212.steps`. All are `sample: true` and have no `context.project`, `case_id`, money, `reconcile` or `allowed_actions`.
  - Builder deviation from the spec table: the review steps do not carry `sends: true`. The shared `Consequence` turns `sends` into "This sends to the client.", which is wrong for an internal report. The basis sentence already says what approving does. This is listed for the backend.
  - The W-3205 and W-3212 drafts do not carry the Ask Tola link (agent done). Only W-3201 carries links.
- Tests:
  - New: `tests/leadership-report.test.tsx` (33 tests), `tests/leadership-report-mock.test.ts` (10 tests), `e2e/leadership-report.spec.ts` (38 tests).
  - Two fixture-scope guards were widened, because they enumerate fixture ids and would otherwise fail on the new fixtures:
    - `tests/mock-contract.test.ts:677`: links are allowed on `W-3201.json`.
    - `tests/income-schedule-mock.test.ts:106`: the verdict overlay is allowed on `W-32xx`.
  - These are the only edits to existing tests.
- `delivery/BACKEND-HANDOFF.md`: "## Added during F-35: leadership report (19 Nov)".
- Factory files (main project):
  - `delivery/features/F-35/fidelity-exceptions.json`: 23 exceptions and 8 visual waivers, all `approved_by: "builder proposal, pending design engineer"`.
  - `round-1/fidelity/` (run.sh, scores.txt, the reports).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Four states from data: unit tests on W-3201…W-3204 check the status, tone, sections, card, recipients and Next. `grep -rn "YOUR REVIEW\|PUBLISHED · NO REVIEW\|RECEIVED BY EVERY RECIPIENT\|PMO staff\|Leadership reviewer\|paid is reported by Finance" frontend/src` returns nothing, and a unit test walks src for the same strings. I looked at the pages at 1440 and 390 on the dev server.
2. [x] Computes nothing: a modified "4 OF 5" changes only that row, and a changed Tuesday receipt leaves the sentence and header as they were. `git diff -U0 frontend/src | grep -nE "parseFloat|Number\(|\.reduce\("` returns nothing.
3. [x] W-3210 shows "Unknown" for Open escalations (no 0, blank or dash), the coverage line, and "3 OF 5". No title from `projects/list.json` appears in the page or the fixture.
4. [x] SAMPLE DATA shows on all 12 fixtures when the label is switched on, and not on a copy with `sample: false`.
5. [x] W-3207 hold: SETUP NEEDED, the "Leadership reviewer · NOT SET" fact and the `next` sentence. There is no Decide panel, no button, zero POSTs, and no "Ifeoma" or "Approve and send".
6. [x] W-3202 and W-3210 show both buttons under "Decide · Leadership reviewer" with the basis. W-3206 shows the `prepared_by_you` copy and W-3208 the `not_your_role` copy, with no claim sent. W-3201, W-3203, W-3204 and W-3211 have no decide control. Personas ceo, pm and finance_lead get the same controls. `git diff frontend/src | grep -n "useMe\|/me\b"` returns nothing.
7. [x] W-3201 (unit and e2e):
   - At 1440 the card is in `.ws-side`, with "step 3 of 4", the steps, sources and WORKING.
   - "Send for leadership review" is a `.psl-step`, not a button, and nothing is written.
   - Ask Tola links to `/assistant`.
   - "Started 01 Nov 08:00" shows in Lagos time.
   - Under reducedMotion the card has no animation.
8. [x] W-3203 shows PUBLISHED · NO REVIEW, and Sola Martins is the `psl-tag--waiting` CHECKING tag.
   - "received" appears nowhere among the page's own words. The backend's Next line "…before marking it received" is board text, so the test excludes the `next` lines.
   - W-3211 and W-3209.approve never say received or "delivered to all".
   - RECEIVED BY EVERY RECIPIENT appears only on W-3204.
   - A decide that answers 200 while the re-read still serves the review says neither sent nor received.
9. [x] There is no Resend, Send again, Try sending or Confirm what happened control on W-3203, W-3209 after approve, W-3211 or W-3212. The e2e request logs show no `/actions` POST.
10. [x] W-3202 and W-3204 have no report link and nothing pointing to `/reports`. W-3204 shows "Read it any time on Overview.".
11. [x] Approve and send, unit and e2e: one claim to T-3202, then exactly one decision `{verdict: "approve", expected_revision: 1}` with CSRF `mock-csrf-ceo`, valid against the schema. A double press sends one. The re-read shows SENT · CHECKING DELIVERIES with four "Not yet" rows, and the "is approved" notice appears only after it.
12. [x] Return: an empty or blank note shows "Add a note to return it.", announced (aria-invalid and describedby), with focus on the field. A 2001-character note is refused. With a note, one POST is sent with the trimmed note, and the re-read shows DRAFTING · RETURNED with the quote. In e2e no decision is sent without a note.
13. [x] W-3206, W-3207 and W-3208 send zero task POSTs (e2e request log).
14. [x] 403 gives the read-only copy and no "approved". 409 gives the stale view; the note is kept and the next press carries revision 2. 422 shows the message under the note. Mock: a stale revision is 409, and W-3206 and W-3208 are 403.
15. [x] W-3209: the decide answers `effect_uncertain`. The page then shows "Monthly report v1: result not confirmed", SENT · DELIVERY NOT CONFIRMED, and Finance Lead CHECKING. A 500, a network failure or a timeout re-reads the item first and shows `UncertainNotice`. With fake timers there is still one POST after 60 s. e2e covers W-3209 and a routed abort on W-3202.
16. [x] W-3205 shows the consequence. One step POST carries exactly `{expected_revision: 3, step: "send_for_review", idempotency_key}` (a UUID) with CSRF. A retry after a 500 reuses the key. The re-read is AWAITING LEADERSHIP REVIEW with the `prepared_by_you` copy. W-3212 shows the checking notice after a re-read, never "sent for review", and sends no second POST.
17. [x] A 401 on read or decide shows signed-out with `next=/work/<id>`. 403 and 404 look the same, with no title, recipient or sentence. Persona `none` sees the not-open view with no work read.
18. [x] At 390 the pages are one column with the same words, including the access note on W-3201 and the recipients and Next on W-3203.
    - The Decide bar is `position: fixed` with both steps.
    - Return opens the Drawer. Escape and Cancel close it and return focus.
    - There is no sideways scroll.
    - All targets are at least 44 by 44 on W-3201, 3202, 3203, 3204 and 3205 (sentence links and the F-17 History link are exempt, as in F-33).
19. [x] Fidelity: one run on a production build. All 8 boards are at 100% coverage after exceptions. Visual is 71.9 to 86.6, so all 8 need waivers citing D-83, all at or above 70. The scores are below.
20. [x] Axe is clean (wcag2a, 2aa, 21a, 21aa, 22aa) at 1440 and 390 on:
    - W-3201 to W-3207;
    - W-3209 after approve;
    - the open Drawer and the note error;
    - the uncertain notice (aborted decide, W-3212);
    - the not-open view.
21. [x] No CSS or colour literal was added, and no local component copy. The banner is the shared `Callout` `info`, checked by its `psl-callout--info` class.
22. [x] `tests/leadership-report-mock.test.ts` covers:
    - every fixture and sidecar is schema-valid with `verdict` and `links` stripped;
    - claim then approve serves `W-3202.approve`;
    - return without a note is 422;
    - a stale revision is 409;
    - W-3206 is 403;
    - W-3209 answers `effect_uncertain`;
    - the W-3205 step serves `.next`;
    - the W-3212 step answers `effect_uncertain`;
    - reset clears.
23. [x] `git diff --stat 6f14afbf` shows no change under `src/api`, `src/features/decide`, `src/features/response`, `src/shell`, the mock `.mjs` files, any existing fixture, `apps`, `architecture`, `design` or the protected paths.
24. [x] checks.sh passes (below). All listed tests pass. The only existing tests touched are the two fixture-scope guards named under Changes.
25. [x] This file.

## Validation
- `npx vitest run tests/leadership-report.test.tsx`: 33 passed. `tests/leadership-report-mock.test.ts` and `tests/income-schedule-mock.test.ts`: 18 passed. `tests/mock-contract.test.ts`: passed.
- First `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` (under the shared lock, load 12.6): exit 1.
  - The only failure was `tests/start-work.test.tsx:492`, a focus assertion in a file this branch does not touch.
  - It passed alone (61 of 61).
- Second checks.sh run (under the lock, load 13.8): exit 0. Django check found no issues; lint, typecheck and build passed; 109 files and 2489 tests passed.
- `cd frontend && E2E_PORT=4988 MOCK_PORT=4989 npx playwright test e2e/leadership-report.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/income-schedule.spec.ts`: 119 passed (5.1 min). `test-results` was deleted afterwards.
- Fidelity: one run, with the shared tool unmodified (`/Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs`), using `round-1/fidelity/run.sh`.
  - Setup: production build with `API_ORIGIN=http://127.0.0.1:4986 FRAME_FIXTURES=1`, `next start` on 4987, mock on 4986 reset before each board, persona ceo.
  - The 23 exceptions were written before the run from the spec's Conflicts. Some were not needed because the tool's fuzzy match found the text (the access sentence, the phone titles, "Started 01 Nov", REVIEW).
  - The 8 visual waivers were added after the run with its measured scores. No exception was added after the run.
  - The servers on 4986 and 4987 were stopped by PID afterwards, and nothing is listening on 4986 to 4989.

| Board | Coverage | With exceptions | Visual |
|---|---|---|---|
| SCR-52-desktop-drafting 1440 | 76.2 | 100 | 85.9 |
| SCR-52-desktop-review 1440 | 76.2 | 100 | 81.6 |
| SCR-52-desktop-tuesday 1440 | 84.2 | 100 | 86.6 |
| SCR-52-desktop-received 1440 | 78.9 | 100 | 86.3 |
| SCR-52-mobile-drafting 390 | 62.5 | 100 | 84.9 |
| SCR-52-mobile-review 390 | 80 | 100 | 77.5 |
| SCR-52-mobile-tuesday 390 | 40 | 100 | 80.7 |
| SCR-52-mobile-received 390 | 40 | 100 | 71.9 |

Exceptions, by Conflicts number:
- 2: the board's "named as left out" sentence.
- 5: "Open the full report" and "Open the report".
- 9: the phone titles and statuses.
- 10: the phone one-line summaries on tuesday and received.
- 11: crumbs, the signed-in names, Setup, "← Overview" and "← My work".
- 13: "Started 01 Nov".
- 14: "Note (needed to return or refuse)" and its parenthetical.
- 16: "Drafting the monthly report" and "Tola · PMO agent · step 3 of 4".

Each waiver names its board's remaining gaps. All are "builder proposal, pending design engineer" (D-118 accepted the recommendations; the per-board waivers are signed at sign-off).

## Notes for reviewers
- Overlay proposals (mock only):
  - `workspace.steps[].verdict` (approve, return), reused from F-33.
  - `workspace.links` `assistant` (Ask Tola).
  - Figures as `value` strings; `coverage` and the left-out sentence as backend text.
  - "5 PMO staff" and "5 deliveries confirmed, 1 still checking" as backend text.
  - "verified" and "received" only from `state` and `status`.
- Backend items, listed in BACKEND-HANDOFF:
  - G-SCR52-3 to -7;
  - the `setup_needed` reviewer hold shape;
  - the state and view names;
  - a "not applicable" fact status;
  - `sends` wording on a decision step;
  - who confirms an uncertain internal delivery;
  - the E-TASK-DECIDE idempotency key;
  - readiness questions 1 to 5.
- Held (from "What is sent"): reviewer, monthly and Tuesday audiences, the Tuesday no-review rule, whose visibility builds the report, the delivery channel (D-REPORT-DELIVERY, D-ALERT-PROVIDERS), and who confirms an uncertain internal delivery. Part 2: the setup boards, Start the report, the report page and the Overview list.
- Frame behaviour I left as it was:
  - W-3207 (`setup_needed`) and W-3209.approve and W-3211 (`effect_uncertain`) show the shared "See all exceptions" link.
  - The uncertain items show the shared "We are checking what happened. Nothing was sent again." notice with Reload. Neither is a resend or confirm control.
  - W-3205's draft-ready note uses the default warning tone (status tone `person`); the spec names info only for agent or neutral.

## Blocked
None.
