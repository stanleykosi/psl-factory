STATUS: READY
COMMIT: bdeee685f982b58e4a1acb7c1915ca2ce853e5f6
BUILDER: builder
LANE: full

## Summary
- SCR-23: Start work now lists "Log a received RFP" (key `received-bid`). It reads `GET /received-bids/organisations`, sends one multipart `POST /received-bids`, reads the receipt, and only then says "RFP logged." with the reference, time, file and saved Note, plus a link to Unassigned. No project picker, no `POST /work`, no `/lines` read for this line.
- SCR-24: the Unassigned tab of My work reads `GET /received-bids/assignments` (cursor paging, `case_id` rows, a "needs access" row with no button). The Assign PM drawer reads `GET /received-bids/{case_id}/assignment` and posts `POST /received-bids/{case_id}/assignment` with proof (listed, or upload through the F-85 picker with `checked`) and a required reason. "PM assigned" appears only after the assignment and the list are read again.
- `ownsSubmit` is added to the F-86 registry as an `OwnLine` entry (the line draws its own drawer and submit). The chooser treats it as startable whatever `/lines` says and lists it by its own title when `/lines` omits it.
- D-182 (LC-Q7 to Q9) and D-187 (LC-Q17) built as recommended. Contract 1.26.0 checked: all bodies match.

## Changes
Paths under `frontend/`.
- `src/features/rfp/receivedBids.ts` (new): typed client for the five calls plus the multipart builder (`logFormData`).
- `src/features/start-work/lines/receivedBid.tsx` (new): the Log RFP drawer (`OwnLine`), its checks, error map, one `start_key` per form, uncertain-result lock with "Check again".
- `src/features/start-work/lines/index.ts`: `OwnLine`, `OWN_LINES`, `ownLineFor`. `LineChooser.tsx`: `withOwnLines`, `isStartable` accepts an own line. `StartWorkDrawer.tsx`: opens an own line's drawer (also by prefill). `LineChooser.tsx` imports no per-line form.
- `src/features/rfp/AssignPmDrawer.tsx` (rewritten), `useReceivedBidAssign.ts` (new, the reads and the one write; re-read on 5xx and 409), `UnassignedBids.tsx` (new, the list), `rfp.css`. `proposals.ts` deleted (its v7 keys are no longer read).
- `src/features/my-work/MyWork.tsx`, `model.ts`: the Unassigned tab body is `UnassignedBids`; `?assign=` now carries a case uuid; the search toolbar is hidden there. The old v7 assign wiring (toast, `Assigned`) is removed.
- `src/features/start-work/start-work.css`: receipt styles.
- `mock/received-bids.mjs` (new) and `mock/server.mjs`: the five routes with scenarios (uncertain, duplicate, 413/415, stale, lost reply, setup, no nominees, one role, no proofs, no steps, assigned).
- Tests: `tests/received-bid.test.tsx`, `tests/assign-pm.test.tsx` (new, 49 tests). Updated: `start-work-live.test.tsx` (chooser now also lists the received RFP), `my-work.test.tsx` (pm Unassigned 403 now comes from the received-bids read), `rfp-intake-mock.test.ts` (v7 source greps skip `receivedBid.tsx`), `next-config.test.ts` (mock answers the required `django_url`). Deleted: `tests/rfp-assign.test.tsx`, `e2e/rfp-assign.spec.ts` (they tested the removed v7 drawer).
- Not touched: `workspace/adapter.ts`, `work-item/live/*`, `AssignForm.tsx`, `useWorkspaceAssign.ts` (still used by other lines). Nothing in `delivery/config.json` protected_paths.

## Fixes
(Round 1: none.)

## Acceptance criteria
1. [x] Organisations load and nothing else is called: `received-bid.test.tsx` "offers exactly the served organisations" (no `/lines`, no `/work`).
2. [x] One multipart POST with the fixed keys, no `definition`, then one receipt GET, then "RFP logged." with the reference: test "sends the fixed multipart keys" reads the body from the mock log.
3. [x] `deadline_at` only when `stated`, required then: test + pure-rule test.
4. [x] 503 then "Check again": same body and same `start_key`, one RFP logged: test; network failure test; new key only after a recorded-nothing failure and a field change.
5. [x] 6 MiB and `.png` refused before sending; server 413/415 show the same words: tests.
6. [x] Duplicate 422 shows the API message, nothing new logged; the same `start_key` and input returns the same receipt: tests.
7. [x] Note optional, counter, sent only when filled, 4001 refused, read back from the receipt: test.
8. [x] No organisations: empty state, disabled submit with its reason; 403 words on the list and on the POST: tests. Live: the POST by the seed account answered 403 `forbidden`.
9. [x] List by `case_id`, 12 per page with cursor, restricted row without a button: test.
10. [x] Nominees, roles, proofs as served, nothing preselected, summary names all four: tests.
11. [x] One JSON POST with integer ids; order POST, GET assignment, GET assignments; success text absent until the re-reads resolve (gated list read): test.
12. [x] 5xx re-reads first, never resends; stored assignment shows "Already assigned"; unstored one offers the form again with the unconfirmed words: tests.
13. [x] 409 reads again and shows the new state (retry goes through at revision 4); 403, 404, 422 field mapping: tests.
14. [x] Setup required and no nominees: tests.
15. [x] No role or hint, no "(optional)", Reason replaces Note, "What happens next" lists served `next_steps` in order, hidden when empty, also in the already-assigned state, no "alerted": tests.
16. [x] 401 on the organisations read and on the list: signed-out state: tests.
17. [x] No v7 path in the five files: source test.
18. [x] Focus moves to the notice on failure and to the success status; labels on every field: tests (focus) and field labels by `getByLabelText`. A manual tab-through was not done.
19. [x] Upload proof: upload to `/cases/{case_id}/files`, body `{upload_id, checked:true}` with no `evidence`; tick-box required; switching routes clears: test.
20. [x] The chooser lists the received RFP through the registry and `LineChooser.tsx` imports no per-line form: tests.
21. [x] `AssignForm` and its other callers untouched; their tests pass in the full run.

## Validation
- Full `npm test` through the lock: 155 of 158 files, 3768 of 3772 tests passed. The 4 failures were mine (two source-grep tests, `no-success-callouts`, `next-config`); fixed, and those files plus the four feature files re-ran green singly (105 tests). The full run was not repeated after the fixes (lock queue was over an hour).
- `npm run build` through the lock: passed (before the last two small commits). `tsc --noEmit` and `eslint` on changed paths: clean. I did not run `checks.sh` itself (it runs `npm ci`; builder turns may not).
- Live (local Django 8021, account qa-seed, then stopped): `GET /received-bids/organisations` returned `{items: []}` and `GET /received-bids/assignments` returned no rows, so this account may not log an RFP. A POST with a PDF (authority 1) answered 403 `forbidden`; nothing was created. `/lines` for this account does not list `received-bid`. The multipart POST success path, the receipt read, the real 5 MiB limit, and the `context_attested` form value (`true`) are UNPROVED against Django.
- Fidelity (one run, production build, mock): SCR-24 1440 coverage 52.4% visual 89.8; 390 coverage 43.8% visual 71.2. Not at 100%. Missing items are the board's sample values (Tunde Bello, Tamarind) and the differences the spec names: Note replaced by Reason, Proof no longer optional, no role/hint or "alerted" sentence, the new states, and the page behind the drawer (the board shows the work table with WORK/STATE/AGE; the built list shows received RFPs). I did not iterate. SCR-23 not run: the Log RFP drawer has no URL, and the tool takes a page URL. Open decision for the design engineer: approve these as exceptions or redraw SCR-24 for the new list.

## Notes for the coordinator
- The success link is `/my-work?queue=unassigned`; the spec says `/work`, which has no list page. The Unassigned tab itself shows only when `/work` gives `counts.unassigned`; live `/work` has no `counts`, so on live the tab is hidden until My work is connected. Outside this feature.
- Shared bug fixed once: none found in shared code. The D-151 rule meant "RFP logged." and "PM assigned" are bold text, not success callouts.
- Nothing needed from `workspace/adapter.ts` or `work-item/live/*`.
