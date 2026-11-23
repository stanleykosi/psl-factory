STATUS: READY
COMMIT: de279c08b01dca4c09872c4a4eb68a25c71e6ad4
BUILDER: builder
LANE: full

## Summary
- New page `/projects/[caseId]/retrospective` (query `dossier`, `meeting`, `version`) reads and writes the project retrospective through the live project-meetings operations. Every save is a recorded version; there is no draft anywhere.
- The three boxes pack into one `summary` under three headings and parse back out (`summary.ts`); a summary with no headings is shown whole and saved back unchanged. The checklist strip names the exact `version_id` the checklist used and says when a newer version exists.
- Writes: first save, new version (same `meeting_id` and locked `reference`, previous decisions carried with `change_evidence_id`), and a follow-up action (`POST /actions/create` with `meeting_id`, never the link call). Failures: 409, 422 on its field, csrf, 429, and "We couldn't confirm it saved" after 503 or network (one POST, re-read, Save off until the re-read shows the result).
- Mock (`mock/retrospective.mjs`) covers cases 2001 to 2008 as in the spec plus a 30-row case; 22 Playwright tests pass against it.
- Not on a production build: main's typecheck fails in `tests/shell-live.test.tsx` (lane A), so `next build` cannot finish here. See Validation.

## Changes
- `frontend/src/features/retrospective/summary.ts`: write, parse, round trip, heading-line check, 16000 limit.
- `.../model.ts`: types from `live-schema.d.ts`, save and action body builders, problems per field, status words, null wording (`Not recorded`, `No deadline set`, `No owner`).
- `.../useRetrospective.ts`: reads (project, list, options, detail, checklist, version used), the two writes, failure mapping, unconfirmed-save handling.
- `.../RetrospectiveView.tsx`, `RetroForm.tsx`, `SavedVersion.tsx`, `ActionForm.tsx`, `ChecklistStrip.tsx`, `retrospective.css`: the page.
- `frontend/src/app/projects/[caseId]/retrospective/page.tsx`: the route (static segment, not a project tab).
- `frontend/mock/retrospective.mjs`: mock of the live meetings, options, detail, create action, closure checklist and a small admin (`/__mock/retrospective/bump`, `/log`).
- `frontend/e2e/retrospective.spec.ts`, `frontend/tests/retrospective-summary.test.ts`, `frontend/tests/retrospective-model.test.ts`.
- Shared files, one small separate commit (f8d45934): `frontend/mock/server.mjs` (import, one reset line, one hook block before the workspace log route) and `frontend/src/api/types.ts` (seven type aliases appended). Nothing in `src/workspace`, `src/shell`, `src/api` (other than types.ts), `src/components` or generated files was changed.

## Fixes
- None (round 1).

## Acceptance criteria
1. [x] Case 2001 shows title, three empty boxes, Who took part, Notes file, "Save retrospective", no "draft": e2e "an empty project shows the form..." searches the page text for `draft` (0); `grep -ri draft src/features/retrospective` finds only a comment about "no draft".
2. [x] First save sends one POST with `kind`, `meeting_id:null`, `revision:41`, a `Retrospective <date>` reference and `summary` exactly `## What went well\nUAT finished on time.`; "Saved hh:mm WAT, version 1." appears after the re-read (request order asserted): e2e "a first save...".
3. [x] Three boxes in order under headings: `summary.test.ts` and e2e "all three boxes...".
4. [x] Parsing: headings fill boxes, no headings shown whole (v1 of 2002 as "Retrospective"), case and curly apostrophe parse, text before the first heading is "Other notes", round trip including blank lines: `summary.test.ts` (22 cases). Saving a no-headings summary writes the text back unchanged (`model` test "sends a summary with no headings back unchanged").
5. [x] Case 2002 save sends `meeting_id:301`, the same read-only `reference`, page shows version 3: e2e "a new version...".
6. [x] Case 2002 dossier 5002 shows "The checklist used version 1 (saved 10 Nov 2026)" and "A newer version has been saved..."; no request carries `retrospective_id` or `latest`: e2e "the strip names the exact version...".
7. [x] `?meeting=301&version=9001` shows "Version 1, not the current version", no Save new version, no action button: e2e.
8. [x] Stale save (mock bump, 409) shows the sentence, re-reads, keeps boxes, participant and file; the next press succeeds on the new revision: e2e.
9. [x] 422 `fields[name=reference]` shows under Reference (aria-invalid), Save re-enabled: e2e.
10. [x] 503 after sending: "We couldn't confirm it saved.", re-reads, Save disabled while the re-read is held, then "It was not saved. Press Save again."; exactly one POST: e2e (the re-read is held with a route gate).
11. [x] Double click sends one POST: e2e.
12. [x] Save off with the reason shown for: no box text, no file, over 16000, heading line, proofs empty (case 2004 text): e2e and `model` tests.
13. [x] Decision rows need text and file; previous decisions load and are sent unchanged with `change_evidence_id: 90`: `model` test and e2e on 2002 (request body asserted).
14. [x] Follow-up action: one `POST /actions/create` with `meeting_id:301`, `due_at:null`, `owner_id:null`; row reads "No owner" and "No deadline set"; no `/meetings/{id}/actions` request; server 422 (reserved reference "Retro action 9") shows under Reference: e2e (two tests).
15. [x] Case 2003: versions read-only, no Save button, no action button, options 403 not shown as an error: e2e.
16. [x] Case 2008 and a random uuid both show only "This record is unavailable.": e2e.
17. [x] Signed out (`psl_mock_session=out`) shows the sign-in link with `next=`: e2e. The link comes from the shared frame state `SignedOutState(pathname + search)`.
18. [x] Dossier 5009 (503): strip hidden, "The closure checklist is unavailable.", form still saves: e2e.
19. [x] 30 rows: 25 then "More" loads the rest and the button goes: e2e.
20. [x] 390px: no horizontal scroll, Save, checkbox row and Notes file select at least 44px high, order title, boxes, who took part, notes file, Save, strip: e2e phone test and screenshot checked by eye.
21. [ ] Against Django 8031: NOT checked. I have no credentials for the local test accounts (the runbook forbids reading the demo login files) and did not start Django. The page types come from the 1.25.0 contract, so the shapes are right by construction. Needs a person with a `meeting.record` account; see Blocked/Open.
22. [x] No money, client message, approver or count is drawn; nulls read "Not recorded", "No owner", "No deadline set": `model.test.ts` and e2e.
23. [x] New tests exist: `summary` (write, parse, round trip, no headings, oversize), `model` (body builders, null handling, status words), `retrospective.spec.ts`.

## Validation
- `npx vitest run tests/retrospective` : 44 passed.
- `npx playwright test e2e/retrospective.spec.ts` against `next dev` on 4992 and the mock on 4993: 22 of 22 pass (first run 18, four test or copy issues fixed, the four re-run and pass). Not run on a production build, see below.
- `npm run lint` (whole frontend): passes.
- `npx tsc --noEmit`: only errors are in `tests/shell-live.test.tsx` (lane A's file, `positions` missing from the `me` fixture). None in my files. Because `next build` type-checks that file, `npm run build` and the Playwright config's production build fail on main for the same reason. I did not touch it. Everything else in `delivery/checks.sh` (django check, lint, test) is the same as base; typecheck and build are blocked only by that file. `npm ci` was not run, as instructed.
- `manage.py check`: no issues.
- Full `npx vitest run` did not finish in 30 minutes (machine load average above 100), so I stopped it. Subset run: api-schema-drift, api-live-schema-drift, projects-mock, demo-mock, delivery-hypercare-mock and my two test files: 110 passed, 1 failed. The failure is `tests/demo-mock.test.ts` "creates one project when the RFP is verified" (projects response missing `totals` and `next_milestone`); it fails identically on the base commit d906028a, so it is not from this branch. The gate's `npm test` will show it.
- Fidelity tool, one run per board on the dev page (case 2001, dossier 5001), no exceptions file: SCR-33 desktop at 1440: coverage 36% (18/50), visual 79.7. SCR-33 mobile at 390: coverage 27.3% (3/11), visual 78. Reports are in the scratchpad `fid-1440` and `fid-390`.

## Fidelity gap (open design-engineer decision)
Both boards are above the 70 waiver floor on visual and below 90; coverage is below 100% because of these differences, which I propose as approved exceptions:
- "Cites:" chips, "Save draft", and Tola's panel are not drawn (D-182, D-8, no live source).
- Board sample text (Sabi Market boxes, "Tunde Bello (PM), Lagoon Health ... (recorded)", `retrospective-notes-sabi.docx · Uploaded · 36 KB`) is sample data, not UI. The notes file is a select of recorded proofs (DC-4 open); recorded outside parties are not offered.
- Checklist words: board "Go-live accepted DONE / Hypercare qualified DONE / Archive DONE / Handover received DONE / Retrospective NOW / Finance confirmation UNKNOWN" are the API's titles and status words (Closed, Recorded, Not yet, Unknown).
- The tool reads the boards' three box labels as plain text and mine as form-field labels, so "What went well", "What didn't" and "Lessons for next projects" count as missing text though they are on the page as labels. Same for the mobile board's "← Sabi Market" back link and subtitle (the shell shows the breadcrumb on phone).
- Added, not on the board: When it was held, Reference, Decisions, Saved retrospectives list, version label, follow-up actions.
The run is on the dev server because the production build is blocked (above). Re-run on a production build once lane A's typecheck fix lands.

## Notes for the coordinator
- A `git stash pop` I ran in this worktree popped another lane's `autostash` (stash is shared across worktrees) and conflicted. I reset my worktree to HEAD; the entry stayed in `git stash list` as `stash@{0}: autostash`, unchanged, so its owner can still pop it. My branch is clean and pushed.
- The live 422 body uses `fields[].name` (live-schema `Error`), not `field` as the spec wrote; the page and mock follow the contract.
- One deviation from the spec's three headings: `## Other notes` is also a recognised heading, written last when a saved summary had text outside the three boxes, so a new version never drops it. Any other `## ` line inside a box is refused on Save with the same sentence as the three headings, so text always round-trips. Both are in `summary.ts` and tested.
- The checklist strip's "used version" read uses the meeting id from `retrospective_url`, else the list row with that `version_id`.
- A "More" for follow-up actions beyond 25 is not built; the page only says more exist.
- Nothing here is a recurring shared bug.
- The 503 test button name changes to "Saving…" while the re-read is pending (Button busy label); Save is disabled throughout.

## Blocked
Not blocked. Open: criterion 21 (live Django check) needs credentials; typecheck/build need lane A's `tests/shell-live.test.tsx` fix.

## Coordinator: sync with main
The coordinator merged origin/main (e6c24e70, API 1.26.0, green per lane A) into the branch after the build, on lane A's word. Merge commit de279c08. The builder's last commit was 9992f8c8. The feature's own code is unchanged.
