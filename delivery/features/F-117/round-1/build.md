STATUS: READY
COMMIT: 5d2cd92c39a9e833376250ce5f4a14d1db5754c7
BUILDER: builder
LANE: full

## Summary
- A `delivery-handover/v1` work item at `/work/[id]` now draws from its own live reads: `support-publication`, `support-replies` and `support-receipt`. It no longer reads the v7 workspace object.
- The PM sees the state sentence, Support's reply per recipient and the numbered gaps. Publish to Support shows only when `can_publish` is true. It sends the exact `version_id` the read returned. The page says "Queued for Support" only from the re-read.
- Record Support's reply posts all eleven contract keys, `gaps[]` only for Gaps found. Support's own acknowledgement posts for a row with `can_acknowledge`.
- Held, not built: "Ask Tola to draft v2" (no served source ids), Start for `delivery-handover/v1`, and the "Replaced" row. Reasons are below.
- Mock results only: no message is ever sent to Support. The live check against `psl_demo5` was not run (not needed to build; see Validation).

## Changes
- `frontend/src/features/delivery-handover/handoverModel.ts` (new): types from the live schema, status sentence, sections (state, Support's reply, gaps, Support receipt, document for the real recipient), gaps parser, reply and acknowledge form rules and body builders, command descriptors.
- `.../handoverAdapter.ts` (new): registers on panel key `support-replies`. Its read fetches all three reads in parallel. A 403 or 404 on one read is "no view of that part", not an error. If all three fail, the page's Try again shows.
- `.../HandoverActions.tsx`, `HandoverForms.tsx`, `Press.tsx` (new): Publish block ("Next" plus the board's consequence line), Record Support's reply form, Support's own acknowledgement form. Writes go through `useWorkCommand` (one press, one POST, lock on a lost answer, result from the re-read).
- `frontend/src/features/workspace/lines/index.ts`: one import line (F-117). No other shared file changed.
- `frontend/mock/handover-live.mjs` (new), `mock/server.mjs` (import, reset and route, same shape as hypercare), `tests/next-config.test.ts` (allow-list entry `handover-live.mjs`, one line).
- Tests: `tests/handover-model.test.ts`, `tests/handover-live.test.tsx`, `e2e/delivery-handover.spec.ts`.
- Panel key: the work read lists `support-receipt`, `support-replies` and `support-publication` (backend `STATION_PANELS`, `work.py:396`). The adapter takes `support-replies`; the other two keys have no adapter and draw nothing.
- Mock ids: the spec's 4201 to 4208 are taken on main, so the fixtures are 6101 to 6108 (spec number plus 1900). No clash with the listed used ids.
- Design check (`design.py check`) was not run; no board changed.

## Departures from the spec (read the backend, not the spec's guess)
- `previous_id`: the spec says it is the row's own `id` when the row already has a status. The backend (`apps/core/factory_api/support_replies.py`) serves `receipts[].id` as the delivery receipt id and `previous_id` as the earlier reply record's id (`ack.pk`). So the form sends `receipt_id` = row id and `previous_id` = the row's served `previous_id` (null while no reply). This is read from the code and not exercised against live Django. If live disagrees, it is a backend question.
- "Replaced" row: not built. Rows are one per delivery receipt, and a replaced reply is not listed, so there is nothing to mark. AC 12's "earlier gaps record reads Replaced" is therefore not met. The latest reply is shown, and the gaps list and Open tag follow it.
- "Check what happened": the work item's own control row already draws it when `actions` lists reconcile, sending the same `POST /actions {expected_revision, action:"reconcile"}`. The panel adds only the uncertain sentence and draws no second button. The e2e (6106) shows one request.
- Error words for 403, 409 and 422 are `useWorkCommand`'s shared words ("You can't do this", "This changed while you were working", the server message plus the first field message), not the spec's per-field messages beside each field. I did not change the shared hook. The form keeps what was typed, since the form state is local and stays mounted (tested for 403 and 409).
- Tag text is "Open" in normal case.

## Fixes
None (round 1).

## Held, and why
- Ask Tola to draft v2 (`POST corrections`): the body needs `source.inputs {template_id, support_document, escalation_document}`. No read this page uses serves them, and the spec says to hide the button then, not send nulls. Hidden. Needs the backend to serve the three ids (or the work read to).
- Start (`POST /work` with `delivery-handover/v1`): the Start chooser has no delivery line yet (F-113B, F-114, F-115 did not add theirs either), and the `inputs` shape and the source picker were not verified here. Not built. A follow-up in `start-work/lines` is needed.
- Proof for Support's reply: chosen from `proofs[]` only, with no upload (Questions 1, option 1). With no proofs the field reads "No proof records available to attach yet" and Record stays off.
- Not drawn, as the spec says: Tola's step card, "Review needed?", attachments for the PM, the "Open question for PSL" note, the Delivery sub-nav and project tabs, any recorder name, any per-gap status.

## Acceptance criteria
1. [x] 6101 waiting plus Publish with the consequence line; 6104 has none: e2e and `handover-live.test.tsx` "reading".
2. [x] Publish body is exactly `{expected_revision, case_revision, version_id}` from the read, then "Queued for Support" from the re-read: unit and e2e assert the body.
3. [x] A double click makes one POST, and the button is disabled while the re-read runs: unit (gated) and e2e `dblclick`.
4. [x] 409 re-reads with no second POST; 422 shows the message and first field message; 403 csrf gives "Press the button again." and refreshes the session; a dropped answer locks Publish with "We couldn't confirm that this happened. Check the page before trying again." and no resend: unit tests.
5. [x] `version_id` null or `can_publish` false gives no command and no button, and no "why not" text: model test.
6. [x] 6106 shows the uncertain sentence, "Check what happened" (the work item's control), no Publish, one reconcile POST accepting 202: unit and e2e.
7. [x] 6103 form: Who replied (empty), fixed role, five channels in words, When, What Support said, Note, Proof ("signature v1"); Record off until filled: unit.
8. [x] Gaps trimmed, in order, blanks dropped; none, over 10 or over 400 characters keeps Record off; Received sends no `gaps` key: model tests and e2e.
9. [x] Record body has the contract's keys with both revisions from the read; a null revision stays null and disables the write: model tests. `previous_id` follows the served row (see Departures).
10. [x] `can_record` false gives no form; 403 and 409 keep typed values (unit). A 422 shows the shared message, not per-field placement (see Departures).
11. [x] After 201 the page re-reads, the reply shows, the form closes, one POST: unit and e2e.
12. [ ] 6104 numbered rows tagged Open, 6105 shows none: met. "Replaced" row and "Ask Tola to draft v2" button: not met (held; see above).
13. [ ] Corrections: held, button hidden because the source ids cannot be read.
14. [x] 6107 shows the document title, version, sections and the acknowledge form; 6101 shows no document; 403 reads do not break the page: unit and e2e.
15. [x] "Acknowledged by Support" appears only from a `support-receipt` row with a status: model test.
16. [x] Absent: Tola card, "Review needed", attachments, sub-nav, open-question note, with no empty headings: e2e on 6101, 6104 and 6107 at 1440 and 390. Board-by-board screenshot comparison was not done.
17. [x] 6108 reads "This record is unavailable.": unit and e2e.
18. [x] Another line's item does not draw the handover panel: the adapter registers only on the `support-replies` panel key, which only this line lists. No separate test.
19. [ ] Not run against live Django 8030 or `psl_demo5`; field-for-field comparison is open.
20. [x] No Publish or Record was run against a real audience. Evidence is the mock, labelled as mock results.
21. [x] `liveApi.POST` is not called from this feature; writes go through `useWorkCommand` and descriptors. Nothing is added under `workspace/` except the one import.
22. [x] lint, typecheck and the full unit suite pass (below).

## Validation
- `node --check` on `mock/server.mjs` and `mock/handover-live.mjs`: ok.
- `npx tsc --noEmit`: clean. `npx eslint . --max-warnings 0`: clean.
- `npx vitest run` (full): 209 files, 4787 tests passed. That includes `next-config`, `demo-mock`, `mock-contract`, `line-adapter` and `live-work-item`. New: `handover-model.test.ts` (21) and `handover-live.test.tsx` (22).
- Playwright `e2e/delivery-handover.spec.ts` on a production build, ports 4880 (app) and 4881 (mock): 12 passed (6 tests at 1440 and 6 at 390), including axe (wcag2a, 2aa, 21a, 21aa, 22aa) and no side scroll. The servers exited with the run; nothing is left listening.
- Design fidelity tool: not run. The live work item draws boards' parts through shared sections, with several parts hidden by the spec. A board-by-board run is for the coordinator or design engineer to call.
- Not run: `checks.sh` itself (its ci mode waits for GitHub on the pushed head). The steps it runs locally were all run as above.
- Shared-code note for the coordinator: `useWorkCommand`'s notice words cannot place a 422 message beside its field. Any line that wants field-level errors needs a shared change. `makeCommand` still drops an `action` placed in `fixed` when `action: null`; none of this feature's bodies depend on it.
