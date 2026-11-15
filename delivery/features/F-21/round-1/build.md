STATUS: READY
COMMIT: 051ea680069845119aff88212c1b2779cde8bf9e
BUILDER: builder
LANE: full

## Summary
- The weekly report line (W-2201 to W-2208) runs on the F-17 workspace frame with no weekly-specific page, route or renderer: default, invalid, assembling and review states, the four-part form (Option A, D-69), the 422 per part, approve/return, the uncertain-send lock and the decision-link step.
- Contract mock only (D-LINE-WORKSPACE, `proposed`): no real send, no real client template, no real recipient. The template is a test template ("TEST TEMPLATE" comes from the data). This build does not claim a real backend, idempotency, or that the weekly line works.
- Four small general frame changes were needed (listed under Changes); the F-17 uncertain-send lock and every F-17 test are untouched and green.
- NOT READY on one gate, named for the design engineer: visual score is 68 to 77 on all 8 boards (needs 90). Coverage with approved exceptions is 100 on all 8. See "Open decision".
- Returned and received boards: nothing built.

## Changes
Frame (`frontend/src/features/workspace/`, all general, none weekly-specific):
- `StepForm.tsx`: (1) a text / long_text field opens with the descriptor's `value` (saved draft words); needed so "pressing Send opens the form with the saved parts" (AC 7). Records `value` is a string in the contract and cannot carry a list of cites, so cites do not prefill (contract proposal below). (2) Escape inside an open record picker closes only the picker list; before, the form's native Escape listener closed the whole form and dropped the typed words (first real use of pickers in a step form; found while driving the board). (3) A 422 `message` that equals a message for a field the form does not show is told once (dedupe, see Conflict below).
- `Sections.tsx`: a checklist item's `tag` is drawn after its words (the assembling board's "TEST TEMPLATE"; the contract allows `tag`, the renderer ignored it for checklists).

Mock (additive): `mock/start-work.mjs` serves E-LINE-OPTIONS for the four cite step fields of `weekly_report` (`STEP_RECORD_FIELDS`, `OPTION_FILES`); `mock/fixtures/start-work/options/records.json` (this week's six records, same references as the panel and the cited chips).

Fixtures `mock/fixtures/work/W-2201..W-2208` (+ `.next`/`.steps` sidecars for 2201, 2202, 2204, 2205, 2206). W-2208 is W-2009's decision fixture with ids changed (T-2208, T-2209) and the review workspace whose `approve_send` carries `task_id`. No existing fixture or test assertion edited. `W-2204.next.json` not needed (the handler's default is already the same item at revision + 1).

Tests: `tests/weekly.test.tsx` (22), `tests/weekly-mock.test.ts` (10), a new describe at the end of `tests/mock-contract.test.ts`, `e2e/weekly.spec.ts` (25).

Factory files (main checkout only): `fidelity-exceptions.json`, `round-1/fidelity/{drive-states.mjs,run.sh,scores.txt,frozen/,SCR-25-*}`. Note: `serve-frozen.mjs` is not kept; it was the F-18 file with ports changed to 4741/4743 (third port 4743 used briefly for frozen pages; the spec names only 4741-4742).

## Fixes
None (round 1).

## Acceptance criteria
1. [ ] Desktop boards at 1440: coverage with exceptions 100 on all four; visual 69.1, 70.2, 76.6, 68.2 (< 90). Not met on visual; see Open decision.
2. [ ] Phone boards at 390: coverage with exceptions 100 on all four; visual 72.5, 71.5, 69.1, 73.8 (< 90). Not met on visual.
3. [x] Driven states are the real UI: `round-1/fidelity/drive-states.mjs` resets the mock, uses the real controls (open Send, type the four parts, choose cites through the real pickers; invalid: press Send and take the real mock 422), freezes only by copying values to attributes, removing scripts and adding `<base>`. `frozen/*.html` present.
4. [x] Exceptions: 62 entries, each with role, name, category, reason, approved_by; none covers a value the data can supply (intro sentence, subtitle, record labels, "3 overdue" note, week-end sentence and TEST TEMPLATE are returned by the fixtures). Mapping below.
5. [x] One fidelity run: a discovery run with an empty exceptions file was used to list the gaps (needed to write the exceptions); the scores above are the single recorded run with the exceptions file on the final head (fixtures and src unchanged after it; only tests, lint typing and commit followed).
6. [x] Default state from data: `weekly.test.tsx` "W-2201 draws the title..."; omitted field draws nothing.
7. [x] Form carries the words: test "opens four labelled text areas ... cite pickers offering only the returned records" (recording fetch shows only `/api/v1/lines/weekly_report/fields/status_cites/options`); no suggest/generate control, fixtures carry no suggestions.
8. [x] Write request: exact body asserted, validates against the generated schema, UUID key, CSRF, no note, no evidence_ids; Save draft same shape (`weekly.test.tsx`; mock in `weekly-mock.test.ts`).
9. [x] Nothing judged client-side: "TBD" and empty cites are sent; no `aria-invalid` appears.
10. [x] 422 per part: W-2202 test and e2e (messages under risks and next_steps_cites, aria-invalid, aria-describedby, focus on the first, inputs kept, new key, top message once). Strings are in fixtures only.
11. [x] Send moves to assembling: test and e2e (one reload, three progress lines as words, TEST TEMPLATE, disabled step with reason, activation sends nothing).
12. [x] Assembling quiet and accessible: e2e with `reducedMotion: 'reduce'` (no running animation), `aria-disabled` test.
13. [x] Review state: test (title, four parts, references, consequence, two buttons).
14. [x] Approve: one POST, double click one, done reloads once, no retry after 60 s (fake timers); e2e reads `/__mock/workspace-log` (one send per key, mock evidence only).
15. [x] Return needs a note: blank refused, 2001 chars refused, valid note sent as `note`.
16. [x] Uncertain send keeps the lock: tests (warning, steps off, ReconcilePanel, one POST to /actions, none to /steps, locked on a page opened in the reconcile state, "We are checking..." with Reload only) and e2e at 1440, 390 and 320 incl. forced clicks before and after a reload and "Record and continue" hit-test.
17. [x] 409 / 500: W-2206 tests (version 5, re-based, new key; save_draft Try again same key; approve_send no resubmit).
18. [x] Access: 403 line, 404 shows no title, client or id (tests); no `/me` use added (`git diff` touches no `/me` code).
19. [x] Decision step: W-2208 link test and e2e (no POST to /steps; page opens).
20. [x] Unknown, restricted, empty: W-2207 test.
21. [x] Returned and received not built: no file or string added; test and `git diff --stat`.
22. [x] Accessibility and layout: e2e, 8 fixtures at 1440 and 390: axe (wcag2a/aa, 21a/aa, 22aa) clean, one h1, no sideways scroll, 44px controls; focus to the form heading on open and back to the step on Escape (e2e).
23. [x] Tokens only: no CSS edited; `grep` of `features/workspace/*.css` for colour literals returns nothing from this diff.
24. [x] Contract not extended: `git diff --stat` touches nothing in `src/api`, `apps`, `architecture`, `design`; fixtures validate unstripped (`mock-contract.test.ts`).
25. [x] Mock matches the contract: `weekly-mock.test.ts` (bad body 422, wrong revision 409, unknown step 404, repeated key replay, scripted answers).
26. [x] No real send: every e2e request goes to localhost/127.0.0.1 (asserted); limits stated here.
27. [x] Existing behaviour: `checks.sh` green (51 files, 1404 tests); `e2e/workspace.spec.ts` and `e2e/start-work.spec.ts` pass (46 tests). No assertion removed or loosened; no existing fixture edited. F-17's region driver was not re-run (frame touched only by the changes above; recommend the coordinator or UI review re-run it).
28. [x] New tests run in `checks.sh` (vitest) and `e2e/weekly.spec.ts` ran separately: 25 passed.
29. [x] This file.

## Validation
- `cd worktree && bash delivery/checks.sh` (main's copy): exit 0 (django check, npm ci, lint, typecheck, 1404 tests, production build). Lint and typecheck were fixed once after a first failure in `weekly-mock.test.ts` (`any`), then green.
- `E2E_PORT=4741 MOCK_PORT=4742 npx playwright test e2e/weekly.spec.ts`: 25 passed. `e2e/workspace.spec.ts e2e/start-work.spec.ts`: 46 passed. `frontend/test-results` deleted.
- Fidelity (production build `next build`, `next start -p 4741`, mock 4742, persona pm), 8 boards, `round-1/fidelity/scores.txt`:
  desktop 1440: default 46.8/100/69.1, invalid 51.6/100/70.2, assembling 57.1/100/76.6, review 53.1/100/68.2;
  mobile 390: default 16.7/100/72.5, invalid 22.2/100/71.5, assembling 57.1/100/69.1, review 80/100/73.8
  (coverage raw / with exceptions / visual). `pass` is false on all 8 for visual only.
- Servers I started (mock 4742, app 4741, frozen 4743) were stopped by their own PIDs.

## Exceptions mapped to Conflicts (`fidelity-exceptions.json`, 62 entries)
- Conflict 1 (D-69, "design engineer, 15 Nov (D-69)"), category `frame form`, 16 entries: board's open text, "Cites:", "+ cite a record", cite names and the four part words, which the page shows inside text areas and the picker.
- Conflict 2 and 4, `frame layout`: the records panel (checkbox rows, "3 overdue" text, panel title) and the phone wording; Conflicts 5 and 6 for all phone-only wording ("✓ cited", "to write", "Tap to write and cite", shortened lines).
- Conflict 4 (and 11), `frame item`: project tab bar, Projects / Lagoon Health crumb links, Setup, signed-in name, phone back links.
- Conflict 7, `frame vocabulary`: invalid board's messages and saved words (same words are on the page under a different role or inside controls).
- Conflict 9, `no field`: "Ask Tola", "Started 12 Nov 09:05", "Tola · PMO agent · step 3 of 4" (returned inside the checklist note).
- Conflict 10, `no field` / `frame vocabulary`: "Open the report as the client will see it", "Decide · PMO LEAD", the note label.
All except Conflict 1 carry `approved_by: "design engineer, 15 Nov (D-71)"`.

## Open decision (design engineer)
Visual stays 68 to 77 on every board even with 100 coverage. Cause (side-by-side images in `round-1/fidelity/*/side-by-side.png`): the work item page keeps its own facts strip, station track and agent card above the workspace (F-17 Conflicts 2 and 3, approved as `frame item`), which pushes the board's content about 400 px down at 1440, and the board's top bar, tab bar and column positions differ. The visual score cannot reach 90 without changing the work item page or the boards. Options: accept the visual gap for SCR-25 as an exception to the 90 bar (as the frame chrome is an approved exception for coverage), or approve a work-item-page change in a separate task. Not fixed here (out of lane).

## Conflict found: spec AC 10 vs an F-17 test
AC 10 wants the 422 `message` shown above the form together with field messages. F-17's UX-1-1 test (`workspace-step.test.tsx`, "a message for a field the form has is shown once, under its input, and not on top") requires that a general message is NOT shown on top when every named field is in the form. I did not weaken it. W-2202's 422 therefore also names a field the form does not show (`parts`) with the same sentence; the frame shows unmatched messages on top, and (new) tells identical sentences once. The coordinator or backend should decide whether the real 422 should name a whole-form field this way or whether the F-17 rule should change.

## Contract proposals (for the backend developer; the frame extends nothing)
- Conflict 1 / Option B: `steps[].inline: boolean` ("open this form at load, in the main column"), only if the design engineer wants the board's always-open form (D-69 chose Option A).
- Cite options: E-LINE-OPTIONS must serve this week's records for the step fields `status_cites`, `risks_cites`, `timeline_cites`, `next_steps_cites` of `weekly_report` (the mock does so through a hook; the panel and the options must agree).
- `steps[].fields[].value` is a string; saved cites for a `records` field cannot prefill. Proposal: allow a list of option values (with labels) for `records`.
- Conflict 6: a per-part state tag ("✓ cited" / "to write") and tap-to-expand rows on the phone board; `text` item `tag` is not drawn today.
- Conflict 9: fields for "step n of m", the start time, and "Ask Tola" (a link or step kind to the assistant).
- Conflict 10: a link field for "Open the report as the client will see it" (no document route exists).
- The week-end rule and which source returns the week-end sentence (`note`) are the backend's.
- Backend items, not blocking: E-WORK-STEP and the `workspace` block are unimplemented; the idempotency promise is unbuilt; the mock's one-send-per-key is mock evidence only.

## D-LINE-WORKSPACE limits (binding on the PR description)
D-LINE-WORKSPACE is `proposed`; F-21 consumes it only under the recorded exception (decisions-2026-11-15 items (g), (i)): contract mock only. The backend developer may change or refuse any field. Nothing is released; no real send, client template or recipient. The template is a test template. No claim of idempotency, a real backend, or a working weekly line.
