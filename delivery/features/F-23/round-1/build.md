STATUS: READY
COMMIT: d5046515521bca99b4b7de220c4d524838cfff1f
BUILDER: builder
LANE: full

## Summary
- The minutes line (W-2301..W-2308) renders on the shared F-17 workspace frame, contract mock only. No minutes page, route or copy in `src/`.
- Frame changes (all general): `items_default` initial ticks; one cross-section `items` control in the workspace row; decision (`task_id`) links honour the page lock (INV-RESEND); a links row with an E-DOCUMENT panel; `item_ids` on item-scope steps; a `choice` field opens on its named value.
- D-LINE-WORKSPACE is `proposed`: contract mock only. Nothing is released. There is no real send, template, recipient, meeting record or notes parsing. This build makes no claim of a real backend, of duplicate-send prevention, or that the minutes line works. The template is a test template. D-ALERT-PROVIDERS gates the real client send; D-RETURN gates what a return does to confirmed items.
- Fidelity: 8 boards, one run, coverage 100 after exceptions on all. Visual 69.7 to 84.7. One board is under 70 (see below).

## Changes
- `src/features/workspace/proposals.ts` (new, PROPOSAL): typed reader for `steps[].items_default` and `workspace.links[]`.
- `Links.tsx` (new): links row. `assistant` links to `/assistant`; `document` reads E-DOCUMENT once and shows a Panel with a "Test template" tag only when `test_template` is true. `body_url` is a link only if `isAppPath` accepts it. 403/404 show "You can't open this document."; other failures show a retry of the read only.
- `Workspace.tsx`: ticks are the PM's explicit choice, else the step's `items_default` (so a new item after a 409 reload starts ticked). An `items` step with targets in more than one section is one control in the Decide/Next row. The form's `item_ids` are the ticked ids at submit, so the set sent is the set on screen (deviation from "captured at press": a 409 keeps the form open, and a press-time set would send items the PM no longer saw). Unticking everything while the form is open sends nothing. Item-scope steps now send `item_ids: [that item]`.
- `Steps.tsx`: the `task_id` link becomes an `aria-disabled` button with no `href` while `off` (write in flight, `item.reconcile` / uncertain item, failed refresh). This is the required fix (AC 19).
- `StepForm.tsx`: a `choice` field opens on `value` when it is one of its options (audience "Client").
- `workspace.css`: link row; `.ws-tablewrap` is positioned so the table header's hidden text does not widen a 390px page (found by the e2e).
- Mock: `fixtures/work/W-2301..W-2308` plus sidecars (`.next`, `.steps`, decide `.approve`/`.return`), `fixtures/E-DOCUMENT.json`, `start-work/options/owner.json`; `start-work.mjs` `STEP_RECORD_FIELDS.minutes`; `server.mjs` adds E-DOCUMENT, answering only D-2304 v1 and 501 for any other document (so the existing "D-1 answers 501" test is unchanged).
- Tests: `tests/minutes.test.tsx`, `minutes-mock.test.ts`, additions to `mock-contract.test.ts` (proposal keys checked on their own, stripped; `document_id`/`version` path values), `e2e/minutes.spec.ts`.
- Factory: `delivery/features/F-23/fidelity-exceptions.json`, `round-1/fidelity/**`.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Desktop boards: coverage 100 after exceptions on all four; visual 69.7 (default), 81.3, 84.7, 79.2. Default is 0.3 under the D-83 floor of 70: open design-engineer decision (see Open items). `scores.txt` lists the rows.
2. [x] Phone boards at 390: coverage 100; visual 73.7, 82, 82.5, 71.6, each with a waiver entry (pending signature).
3. [x] `drive-states.mjs` resets the mock, presses the real "Confirm and create actions" control, and freezes only (values to attributes, scripts removed, `<base>`).
4. [x] Exceptions: 36 entries with role, name, category, reason, approved_by. Conflicts 1-5 items are "design engineer, 16 Nov 2026 — D-98"; the rest are "builder proposal, pending design engineer". Mapping: Conflicts 1 (checkbox "Keep this decision"); 3 (Note box and "needed to return or refuse"); 6 (decision words and source not found as separate items in the side-column card); 8/9 (WORKING, DONE, step-of, Started/Drafted lines); 10 (phone DECISION/ACTION rows, back links, "No owner yet"); 11 (crumb links, project tabs, Overview/Setup, Kemi Adebayo, "Decide · PMO Lead"). Caveat: the decision text and "From Notes" cites are supplied by data and appear on the page, but the tool did not match them as separate items; they are excepted as Conflicts 6 (pending design engineer), not as missing data.
5. [x] One fidelity run this round.
6. [x] Default from data: minutes.test.tsx "default from data".
7. [x] Pre-ticked from data only: W-2301 all five ticked; W-2308 none ticked and confirm `aria-disabled`; removing `items_default` unticks all.
8. [x] Exact set: one POST, CSRF, revision 4, `item_ids` in returned order, `inputs.audience`, UUID key, validates against the request schema.
9. [x] No POST on load, tick, Edit open or cancel; 60 s fake timers; grep for "accept all|auto-confirm" under `features/workspace` returns nothing.
10. [x] Edit, Remove, Add, 422 under `text` with focus, new key. Owner options from `minutes/owner` with hints.
11. [x] Audience `choice` (W-2301) vs `display` (W-2307, no `inputs`).
12. [x] Stale confirm on W-2306: version 5 message, fourth action ticked, new key, revision 5.
13. [x] 500 on Save for later offers Try again with the same key.
14. [x] W-2302 quiet; reduced motion checked in e2e.
15. [x] W-2303 and Send for review. `grep -rn "TEST TEMPLATE" frontend/src` finds only `components/SampleLabel.tsx` (existing, not this feature).
16. [x] Open the minutes: one GET, Test template tag, 404 no title, `body_url` family (`//`, `javascript:`, `/\`) never a link.
17. [x] Review shows version, recipients "Not yet", consequence, decision links; no POST from the work page.
18. [x] Return needs a note at 1440 and 390 on the F-16 page (blank and 2001 characters refused with no request; a valid note sends one `return`).
19. [x] W-2305: links `aria-disabled`, no `href`, forced click sends nothing; reconcile is one POST to `/actions`; holds before and after reload at 1440, 390 and 320. The same lock holds while a write is in flight and after a failed refresh (component tests).
20-23. [x] 403 step, no-access, personas (pm, ceo, finance_lead identical), Unknown/restricted, notes text grants nothing (component tests).
24. [x] e2e at 1440 and 390 for all eight: axe clean, one h1, no sideways scroll, 44px on the phone for buttons, links and checkboxes.
25. [x] Components and tokens: new UI uses `@/components`; the CSS diff has no hex, rgb or hsl.
26. [x] `git diff --stat` touches no `src/api`, `apps`, `architecture`, `design` or protected path.
27-30. [x] Mock tests and the F-17/F-21/F-22/F-16 suites pass.
28. [x] Every e2e request goes to localhost or the mock (an afterEach asserts it).

## Validation
- `bash delivery/checks.sh`: exit 0.
- `npx vitest` (new and touched): minutes.test.tsx 36, minutes-mock 12, mock-contract (+3), workspace-step, plus the weekly and decide suites, all pass.
- Playwright (4761/4762): minutes, weekly, weekly-returned-received, workspace, decide, decide-board: 146 passed.
- Fidelity: `round-1/fidelity/run.sh`; final scores:

| board | width | coverage | with exceptions | visual |
|---|---|---|---|---|
| desktop default | 1440 | 77.8 | 100 | 69.7 |
| desktop suggesting | 1440 | 57.1 | 100 | 81.3 |
| desktop drafted | 1440 | 61.3 | 100 | 84.7 |
| desktop review | 1440 | 53.1 | 100 | 79.2 |
| mobile default | 390 | 52.6 | 100 | 73.7 |
| mobile suggesting | 390 | 50 | 100 | 82 |
| mobile drafted | 390 | 80 | 100 | 82.5 |
| mobile review | 390 | 83.3 | 100 | 71.6 |

## Base merge
The coordinator merged dlv-00 (F-22 and F-24) into the branch; head is d5046515521bca99b4b7de220c4d524838cfff1f (my last own commit was 2c183f087f8232332edef2897407a31e9d818576). I checked the one conflict resolution in `frontend/mock/server.mjs`: `M1_OPERATIONS` keeps `'E-DOCUMENT'` and `...ASSISTANT_OPERATIONS`, and the D-2304-only E-DOCUMENT guard is intact. Merged-head checks.sh and 180 e2e pass (`merge-checks.log`, `merge-e2e.log`). Fidelity was not re-run. F-24 changed `src/shell/PhoneBar.tsx` and `AppShell.tsx` (the phone bar), so the four phone boards could move: SCR-28-mobile, -suggesting, -drafted and -review (all at 390; the pinned Decide bar and the phone bar share the bottom edge). The desktop boards should not move. The scores above are from before the merge.

## Open items for the coordinator and design engineer
- **Spec conflict, existing assertion changed.** AC 10 requires item steps (`edit_item`, `remove_item`) to send `item_ids: [that item]`. F-17's test "an item step acts on its own item only, with no item_ids" (`workspace-step.test.tsx`, W-2002 `accept_answer`) asserted the opposite. Without an id the backend cannot know which row was pressed, so I built the spec and changed that assertion to `item_ids: ['S-08']`. Please confirm.
- Desktop default visual 69.7 is under the D-83 floor of 70 even with a waiver entry; needs a design-engineer decision. Waivers and 30 of 36 exceptions are "builder proposal, pending design engineer".
- Deviation: the confirm set is read at submit, not at press (reason above).
- Deviation: drafted fixture has no `version` byline (the panel head already says "Minutes v1 · client version"; showing both would repeat it). Extra fixture step `edit_decision` (text only) because a decision's Edit has different fields from an action's `edit_item`. Edit forms do not prefill the row's current text (item-scope descriptors are per step, not per item).
- Conflicts 4 (phone note): built as proposed (Return opens the F-16 page, which owns the note). Conflicts 1-5 as D-98.
- Backend items, unimplemented: G-SCR28-1 to 9, D-RETURN, the meeting source, E-WORK-STEP, the `workspace` block, E-DOCUMENT and E-LINE-OPTIONS, the idempotency promise, server-side refusal of a resend while delivery is uncertain (SEC-5-C1), verdict words (X-VERDICTS), and `work_id` on E-LINE-OPTIONS (G-SCR28-4).
- Housekeeping: `frontend/test-results` deleted; servers stopped by PID; the coordinator merges dlv-00 before the final reviews.
