# BU totals are published to the CEO and BU heads, each confirms receipt, and Finance sees "Verified" only when the server says so

> Tasks: FE-FIN-BU. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0. Design: approved 13 Nov canvas under the recorded D-173/D-181 exceptions in `design/review.json`; screens: SCR-57 part 2 (`SCR-57-{desktop,mobile}-{publish,receipts,verified}`). Decisions: D-187 (LD-Q1 "Build on the API"), D-185, D-182 rule. Part 1 is `delivery/features/F-107/spec.md`.

## Summary
- Adds the publish, receipts and verified states to the BU totals panel that F-107 builds (`finance-bu/v1`). A Finance person whose read says `can_publish` presses Publish; the server sends the approved totals to the CEO and BU heads.
- Each recipient (`recipient_only`) sees only their own approved view and presses "Confirm I received it" once (`POST /work/{id}/aggregate-receipt`). Finance sees receipt progress from the served `receipt_ids[]`.
- "Verified" is drawn only when `verified_at` is non-null. A job or agent claim never draws it.
- D-187 disclosure: the page shows exactly what the API served this person and hides every board figure it did not serve (recipient names, "6 BU heads", "7 recipients", "7 OF 7", staff count "58", the BU publisher rule). A BU head never sees another BU's figures, staff names or pay. Proof is against live Django.
- Waits (not blockers): F-107 (part 1: panel, model, review code), F-85 and F-87 (adapter, `Actions` slot, `useWorkCommand`) must be on main before the build starts. High risk; the merge goes to the design engineer's merge batch.

## Context
Code is the lane D worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d/frontend` (API 1.25.0). Nothing exists yet under `src/features/finance/business-units/`; F-107 creates it, and this feature extends it.
- Frame (lane C's, read only): `src/features/workspace/adapter.ts` (`LineAdapter`, `CommandDescriptor`, `makeCommand`; a descriptor with `idempotency.field === null` carries no key), `useWorkCommand.ts` (F-87: press lock, uncertain lock, error words), `src/features/work-item/` (`PanelView` renders `adapter.Actions`).
- F-107 files this builds on (names from F-107's spec; the builder reads the merged code): `businessUnitsAdapter.ts`, `model.ts` (read-to-view allowlist mapper), `BusinessUnitsPanel` sections, `BusinessUnitActions.tsx`, `commands.ts`, `frontend/mock/work-bu.mjs`, `frontend/e2e/finance-bu.spec.ts`.
- Client: `src/api/client.ts` (`liveApi`, `call()`), `src/api/errors.ts` (`ApiError` kinds), `src/api/live-schema.d.ts` (1.25.0).
- Boards: `design/canvas/finance/project/SCR-57-{desktop,mobile}-{publish,receipts,verified}.dc.html`.
  - publish: "READY TO PUBLISH"; "Publish to CEO · Adaeze Nwosu (DISCLOSURE RULE) and BU heads · 6 (OWN BU ONLY)"; "What happens next: each recipient confirms receipt in the app. Only totals are sent; never names or pay."; button "Publish totals"; the line "Publishing is a recorded action by the BU publisher; it isn't a review, so the preparer may publish."
  - receipts (drawn as a recipient, "Femi Ade · Delivery head"): "Your copy · Delivery", "Staff 58", "Staff cost · October ₦61,400,000.00", "Confirm I received it"; "Receipts: CEO RECEIVED, Delivery head (you) NEEDS YOU, 4 other BU heads WAITING"; "Verified once all 7 recipients confirm."
  - verified: "Receipts 7 OF 7", "Coverage SUPPLIED POPULATION ONLY", "Private data in the result NONE", "Posted to the ledger NO", "Cancelling now would need follow-up: the totals were already published."
  - Mobile: same content in phone layout; header "Start" button (SCR-04, not drawn here); receipts shows "₦61.4M" (abbreviated money is not drawn; see Conflicts).
- Live operations (1.25.0):
  - `GET /api/v1/work/{work_id}/business-units`: the same read as F-107. This feature uses `publication_id` (int|null), `receipt_id` (int|null), `receipt_ids` (int[]), `verified_at` (date-time|null), `can_publish`, `recipient_only`, `result`, `totals`, `period`, `currency`, `review_subjects[]`, `finding`, `stage`, `expected_revision`, `case_revision`.
  - `POST /api/v1/work/{work_id}/business-units` body `{action:'publish', expected_revision, case_revision}`; 201 `{work_id, state, revision, record_id}`. No idempotency key in the contract.
  - `POST /api/v1/work/{work_id}/aggregate-receipt` body `{publication_id}`; 200 `{receipt_id, publication_id}`. No revision tokens and no key. "Record your own receipt for the exact current aggregate publication."
  - Errors on both: 400, 401, 403 (incl. `csrf_failed`), 404, 409, 413/415, 422, 429, 500, 503 with `{code, message, fields?}`.
  - There is no cancel, withdraw or retract-publication action in 1.25.0 (`business-units` accepts `prepare_rule`, `publish`, `restart`; E-28). The `restart` action is for settled work and is out of scope.
- Backend answers: E-26 and E-30 (recipient views are approved projections, disclosed only after the recipient acknowledges the exact current report), E-27 (a too-small group holds the publication; a recipient gets no private staff counts), E-28.

## Contract

### Which board shows (extends F-107's table; pure function of the served read, no role inference)
Evaluate top to bottom; first match wins.
| Served | Viewer | Drawn |
|---|---|---|
| `recipient_only === true`, `verified_at !== null` | recipient | Reduced view (F-107) plus "Verified" line (below). No confirm control. |
| `recipient_only === true`, `publication_id !== null`, `receipt_id !== null` | recipient | Reduced view plus "You confirmed receipt." No control. |
| `recipient_only === true`, `publication_id !== null`, `receipt_id === null` | recipient | Reduced view plus the receipt control (`receipts` board). |
| `recipient_only === true`, `publication_id === null` | recipient | Reduced view as F-107 ("Nothing has been published to you yet." when `totals` is null). No control. |
| `verified_at !== null` | not recipient | `verified` board. |
| `publication_id !== null` | not recipient | `receipts` board, Finance side (waiting for receipts). |
| `result.status === 'complete'`, `can_publish === true`, `publication_id === null`, `review_subjects[]` empty | not recipient | `publish` board. |
| anything else | any | F-107's states unchanged (source-review, investigating, held, result-review). A held result never shows Publish. |
`stage` and `finding` stay as F-107 shows them. The seven-station track is hidden (F-107 rule). F-107's "Sent. This is shown on the next screen." note is removed; the rows above replace it.

### Publish board (`SCR-57-*-publish`)
- Tag "Ready to publish" (board word) only in this state.
- "Publish to" block: one sentence, "The CEO and the business unit heads." No names, no "6", no "7", no disclosure-rule tag, no "OWN BU ONLY" chip unless the read serves it (it serves nothing like it, so none of these is drawn).
- "What happens next" sentence kept as drawn: "Each recipient confirms receipt in the app. Only totals are sent; never names or pay."
- Totals table: the same served `totals` table as F-107's result-review (period and currency from the read), so the publisher sees exactly what is sent. No sum, share or count computed.
- Button "Publish totals". Enabled only when both `expected_revision` and `case_revision` are non-null; otherwise disabled with "We don't have this item's current version yet. Reload and try again." The line about "the BU publisher ... the preparer may publish" is hidden (a business rule the API does not serve).
- Pressing sends one write and then re-reads (see Writes). Success wording comes only from the re-read: when the re-read has `publication_id` non-null the page shows the receipts board; otherwise "Recorded. The page will update when the publication is applied." (never "Published" from the 201 alone).
- Mobile: same content, button full width, bottom of the card as the board draws.

### Receipts board, Finance side (`SCR-57-*-receipts`, viewer is not `recipient_only`)
- Tag "Waiting for receipts". Title and sub-line from `period`/`currency`.
- "Receipts" card: "Receipts recorded: {receipt_ids.length}" is drawn as the length of the served array and nothing else (Questions 1). No row per recipient, no "RECEIVED/NEEDS YOU/WAITING" list, no "4 other BU heads", no denominator ("of 7"), no "Verified once all 7 recipients confirm" sentence: the read serves no recipient list and no recipient count.
- Finance sees the same totals table the publisher saw (the served `totals`), and no recipient-specific figure.
- No Publish button (a second publish is not offered while `publication_id` is non-null) and no cancel control (none served; Questions 2).

### Receipts board, recipient side (`recipient_only === true`, `publication_id !== null`)
- Reduced view from F-107 (title, period, currency, `finding`, `totals` rows as served for this person), headed "Your copy of the BU totals". It carries only the totals the API served this person. The board's "Staff 58" is drawn only if the served `totals` carries a staff-count entry for this person (it normally does not; the column rule from F-107 applies); the board's "Your copy · Delivery" label is drawn only if a served totals key names the unit.
- Receipt control: one button "Confirm I received it" and under it "This records that you received these totals." Enabled when `publication_id` is non-null and `receipt_id` is null and `verified_at` is null.
- After success: re-read; the page shows "You confirmed receipt." only when the re-read has `receipt_id` non-null; otherwise "Recorded. The page will update when the receipt is applied." The button is gone or disabled in both.
- No other write control, no Inputs list, no evidence list, no hold detail, no request to `business-unit-intake`.
- The page never shows other recipients' receipts or other units' figures.

### Verified board (`SCR-57-*-verified`, viewer is not `recipient_only`)
- Tag "Verified" and a line "Verified {verified_at}" in the viewer's local format, drawn only because `verified_at` is non-null.
- "Receipts: {receipt_ids.length} recorded" as in the Finance receipts card, without "OF 7".
- Hidden because not served: "Coverage: Supplied population only", "Private data in the result: None", "Posted to the ledger: No", "Cancelling now would need follow-up". No cancel control.
- The totals table remains as served. Recipient viewers see the "Verified" line under their reduced view only when `verified_at` is non-null.

### Writes
Both go through `makeCommand` and F-87's `useWorkCommand` (one write at a time, press lock, uncertain lock after timeout/5xx, a fresh descriptor per attempt). They are registered in `src/features/finance/business-units/commands.ts`, shape-tested, and sent from `BusinessUnitActions.tsx` (F-87's `Actions` slot; nothing added in `src/features/workspace`). Revision tokens and any key never go inside `inputs`.
| id | url | body | key | success |
|---|---|---|---|---|
| `business-units.publish` | `POST /api/v1/work/{id}/business-units` | `{action:'publish', expected_revision, case_revision}` | none (`idempotency.field: null`); the revision pair is the only guard | 201 |
| `business-units.aggregate-receipt` | `POST /api/v1/work/{id}/aggregate-receipt` | `{publication_id}` | none; no tokens | 200 |
- `publish` tokens come from the business-units read (as F-107). `aggregate-receipt` takes `publication_id` from the same read; a null `publication_id` hides the control.
- Errors (as F-107 and F-87): 400/422 server message and `fields[]` as given; 403 "You can't do this." plus the server message, `csrf_failed` refreshes the session once and says "Press again"; 404 "This record is unavailable."; 409 re-reads and shows the server message as given (a stale revision, an already-recorded receipt for the exact publication, or an independence hold); 429 and 503 "Try again shortly."
- Uncertain (timeout, dropped connection, 5xx): the control locks, the page re-reads, and says "We couldn't confirm that this happened. Check the page before trying again." For publish it unlocks only when the re-read shows a different `expected_revision` or a non-null `publication_id`. For the receipt it unlocks only when `receipt_id` is non-null (then the control is gone) or after the person reloads the page and the read still shows `receipt_id` null. The page never resends a publish or a receipt on its own.
- Tests run page load, polling and navigation with zero POSTs.

### Read states
Loading, error, 401, 403/404 (both exactly "This record is unavailable."), 429/503 as F-107. A 200 with a served field null draws nothing for that field.

### Fixture examples (mock, port 4991; shapes are the contract, ids the builder's)
Add to `frontend/mock/work-bu.mjs` (the file F-107 creates). Work ids 4710 to 4719 (F-107 uses 4701 to 4709; mock-only; named in build.md; no change to `mock/finance*` expected, and any change is named for lane B).
- `4710` publish-ready, Finance publisher: `result:{id:7,kind:'staff',status:'complete',codes:[],scope:{entity:'PSL',period:'2026-10',currency:'NGN'},totals:{...}}`, `totals` as in F-107 4704, `can_publish:true`, `review_subjects:[]`, `publication_id:null`, `receipt_id:null`, `receipt_ids:[]`, `verified_at:null`, `recipient_only:false`.
- `4711` same but `review_subjects:[{id:7,kind:'staff',version:1,purposes:['staff']}]` (still in review: no Publish button, F-107 result-review).
- `4712` same as 4710 but `can_publish:false` (no Publish button).
- `4713` waiting for receipts, Finance: `publication_id:31`, `receipt_ids:[91]`, `receipt_id:null`, `verified_at:null`, `can_publish:true` (still no Publish button).
- `4714` recipient, not yet confirmed: `recipient_only:true`, `publication_id:31`, `receipt_id:null`, `receipt_ids:[]`, `totals` for this unit only.
- `4715` recipient, confirmed: as 4714 with `receipt_id:92`.
- `4716` recipient, nothing published: `recipient_only:true`, `publication_id:null`, `totals:null`.
- `4717` verified, Finance: `publication_id:31`, `receipt_ids:[91,92]`, `verified_at:'2026-11-23T10:15:00Z'`.
- `4718` recipient, verified: `recipient_only:true`, `receipt_id:92`, `verified_at` set.
- `4719` held and `can_publish:true` (a held result never shows Publish).
- Scenarios per fixture (query or header switch as F-107 uses): `stale` (409), `drop` (connection dropped after the write is accepted), `invalid` (422), `forbidden` (403), `csrf` (403 `csrf_failed`), `rate` (429), `already` (409 on a second receipt).
- Canary rule: fixtures 4710 to 4719 carry in the mock's raw response, and only there, keys the real API would never send to that person: `staff_count`, `employee_id`, `names`, `legal_staff`, `recipient_count`, `recipient_names`, `receipts_expected`, `other_bu_totals`, `min_group_size`, `bu_publisher`. The tests assert none of their values reach the DOM, attributes or serialized page state. The recipient fixtures (4714 to 4716, 4718) also carry a second unit's row and a name under a canary key to prove they are never shown.

## Lanes
- Frontend lane (owner of all of this feature): `frontend/src/features/finance/business-units/**` (additions: publish, receipt and verified sections of the panel, `BusinessUnitActions.tsx` additions, `commands.ts` additions, `model.ts` additions, css, unit tests), `frontend/mock/work-bu.mjs` (added fixtures 4710 to 4719), `frontend/src/api/types.ts` (BU receipt/publish read types only, from `live-schema.d.ts`), `frontend/e2e/finance-bu.spec.ts` (additions) or a new `frontend/e2e/finance-bu-publish.spec.ts`.
- Backend lane: none. No backend, migrations or contract edits. Open backend questions go to `delivery/connect/backend-questions.md` via the coordinator.
- Integration owner: lane D coordinator. Shared files and owners: `frontend/src/features/workspace/*` and `frontend/src/features/work-item/*` (lane C; read only), `frontend/mock/server.mjs` (shared; F-107 already registered the file, no new line expected), `frontend/mock/finance*` (lane B; not changed, any change named in build.md), `src/api/*` (shared; types only).
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
Ports: Next 4990, mock 4991, Django 8030. The builder records the accounts used.
1. `/work/4710` shows the publish board: tag "Ready to publish", the sentence "The CEO and the business unit heads.", the "What happens next" sentence, the totals table, and a "Publish totals" button; it shows no recipient name, no "6", no "7", no disclosure-rule tag and not the "BU publisher" line — verify: open at 1440 and 390 wide against the two publish boards; the e2e asserts text and absences.
2. Pressing "Publish totals" sends exactly one `POST /api/v1/work/4710/business-units` with body exactly `{"action":"publish","expected_revision":<n>,"case_revision":<n>}` (no key, no `inputs`), and after the re-read the page shows the Finance receipts board; with a mock whose re-read still has `publication_id:null` it shows "Recorded. The page will update when the publication is applied." and never "Published" — verify: e2e request capture; unit test of the `business-units.publish` body.
3. A double click on Publish sends one request — verify: e2e counts POSTs.
4. `/work/4711` (still in review) and `/work/4712` (`can_publish:false`) and `/work/4719` (held) show no Publish button — verify: e2e by role and name.
5. `/work/4713` (published, waiting) shows "Waiting for receipts", "Receipts recorded: 1" (the length of `receipt_ids`), the totals table, and no Publish button, no per-recipient list, no "of 7" and no cancel control even with `can_publish:true` — verify: e2e; grep the DOM for `of 7`, `OF`, `WAITING`, `NEEDS YOU`, `Cancel` returns nothing.
6. `/work/4714` (recipient, not confirmed) shows the reduced view with only this person's totals and one "Confirm I received it" button; no Inputs list, no evidence list, no Publish, no request to `business-unit-intake` — verify: e2e asserts DOM and request list.
7. Pressing "Confirm I received it" on 4714 sends exactly one `POST /api/v1/work/4714/aggregate-receipt` with body exactly `{"publication_id":31}`; after the re-read with `receipt_id` non-null the page shows "You confirmed receipt." and no button; with a re-read that still has `receipt_id:null` it shows "Recorded. The page will update when the receipt is applied." — verify: e2e request capture, both mock outcomes; unit test of the body.
8. `/work/4715` (already confirmed) shows "You confirmed receipt." and no button; `/work/4716` (nothing published) shows no button and "Nothing has been published to you yet." — verify: e2e.
9. `/work/4717` (verified) shows "Verified" with the served `verified_at` and "Receipts recorded: 2", and shows none of "Coverage", "Private data", "Posted to the ledger", "Cancelling now", "7 OF 7" — verify: e2e; the verified word is absent on 4713 and 4710 (no `verified_at`) even when the mock sets `stage:'verified'` text — verify: e2e with that variant.
10. A job or agent claim is not "verified": a fixture with `verified_at:null`, `stage:'Verified'` and `receipt_ids:[91,92]` shows no Verified tag — verify: e2e and unit test of the state function.
11. The page computes nothing: the cells of every table equal served strings; the only number drawn that the page did not receive as a string is the array length of `receipt_ids`; no total row, share, recipient count or denominator — verify: property test (every cell string appears in the input) and e2e DOM comparison against the fixture.
12. A null value in `totals` shows "Unknown", never 0, `0.00` or a dash; a null `period` or `currency` hides that part with no gap — verify: unit test and e2e on a variant.
13. Authority comes from the server only: `/work/4712` (`can_publish:false`) shows no Publish for any job title in the mock session, and no code path reads a role or job title — verify: grep `frontend/src/features/finance/business-units` for role and job-title strings returns nothing.
14. Wrong person: a 403 on Publish or on the receipt shows "You can't do this." plus the server message and re-reads, no retry; a `csrf_failed` 403 refreshes the session once, says "Press again" and sends no second request — verify: e2e scenarios `forbidden` and `csrf`; unit test counts fetches.
15. Wrong tenant or unknown record: a 404 on the read or on either write shows exactly "This record is unavailable."; a 403 on the read looks the same; nothing distinguishes them — verify: e2e compares text and DOM structure.
16. Invalid input: a 422 shows the server message and `fields[]` as given and re-reads — verify: scenario `invalid`.
17. Stale publish: a 409 re-reads, shows the server message, does not repeat the press; the next press carries the new `expected_revision` — verify: e2e scenario `stale` with capture of both bodies.
18. Second receipt: a 409 `already` re-reads, shows the server message and the page shows "You confirmed receipt." when the re-read has `receipt_id`; no repeat send — verify: e2e scenario `already`.
19. Uncertain publish: a dropped connection after Publish locks the button, says "We couldn't confirm that this happened. Check the page before trying again.", sends nothing by itself for 60 s of fake time, and unlocks only when the re-read has a changed `expected_revision` or a non-null `publication_id` — verify: unit test with fake timers; e2e scenario `drop` counts POSTs.
20. Uncertain receipt: same for the receipt; unlocks only after the re-read shows `receipt_id` non-null (control gone) or after a reload; never auto-resends — verify: unit test and e2e scenario `drop`.
21. A 429 or 503 says "Try again shortly." and sends nothing more by itself — verify: unit test over 30 s of fake time.
22. A null `expected_revision` or `case_revision` disables Publish with "We don't have this item's current version yet. Reload and try again." and sends nothing; a null `publication_id` hides the receipt control — verify: unit test on both descriptors.
23. Publish and receipt are external messaging, and this page composes none: no message text, alert, email, WhatsApp copy or amount is built or sent by the page, and the only POSTs are `business-units.publish` and `business-units.aggregate-receipt` through `useWorkCommand` — verify: grep for `liveApi.POST` in `src/features/finance/business-units` shows no direct use; e2e asserts zero POSTs on load of every fixture.
24. Disclosure proof, mock: for fixtures 4710 to 4719 the canary keys and their values appear nowhere in the DOM text, attributes or serialized state; the recipient fixtures never show another unit's figures or any name — verify: e2e reads `document.body.innerHTML` per fixture; unit test that `model.ts` is an allowlist mapper that drops unknown keys.
25. Disclosure proof, live (D-187): against Django on 8030 with a seeded published BU work item, for three people (a Finance publisher, a BU head recipient, and a person with no access), compare the page with `GET /api/v1/work/{id}/business-units` fetched with the same session: every figure and word on the page is in that JSON; the BU head's JSON and page contain only their own unit's figures and no staff names, staff ids or pay; the Finance page shows no recipient figures beyond what its JSON serves; the no-access person sees exactly "This record is unavailable." — verify: `curl` with each session cookie next to the page text; record the three comparisons in build.md, plus the exact live shape of `totals` and of `receipt_ids`.
26. Live round trip: against Django 8030, the Finance publisher presses Publish on a work item whose read has `can_publish:true` and the 201 and the re-read agree; then a recipient presses "Confirm I received it" and the 200 body `{receipt_id, publication_id}` matches the re-read; the Finance re-read lists the new `receipt_id` in `receipt_ids[]`; `verified_at` appears only when the server sets it — verify: record the JSON of both responses and both re-reads in build.md. If the seeded data cannot reach `can_publish:true`, record that and keep the mock proof (Assumptions 6).
27. Viewport check at 1440 and 390: each of the six boards matches for the parts that remain; every hidden part leaves no empty heading, no gap and no "not available" text — verify: screenshots of 4710, 4713, 4714, 4717 at both widths against `design/screens.md` SCR-57 artboards; the Conflicts list is the allowed difference.
28. Typecheck, lint and tests pass, and `api-live-schema-drift.test.ts` still passes — verify: `delivery/checks.sh`. New unit tests cover: the state function for every row of the Contract table, both command bodies and their null-token holds, the allowlist model, and the lock behaviour of criteria 19 and 20.
29. build.md and the PR description state in plain words what is hidden under D-182/D-187 (recipient names and counts, receipts list, "7 OF 7", Coverage, Private data, Posted to the ledger, cancel-after-publish, the BU publisher line, abbreviated money), name every change under `frontend/mock/finance*` (expected none), and say that no cancel-after-publish is drawn because 1.25.0 serves none — verify: read build.md.

## Out of scope
- The first 8 boards (F-107): source review, investigating, held, result review, the Approve/Return/Withdraw reviews.
- Event mode (no board); starting a BU totals run (SCR-04); capturing an event source (`POST business-unit-intake`).
- Payroll import and run (F-108/F-110), payroll corrections, working rows and any link to them; the payroll aggregate (SCR-59) has its own publish and receipts.
- `prepare_rule` and `restart` forms; Setup editing of disclosure rules, the minimum group size or the BU publisher rule.
- Cancel, withdraw or correct-after-publish: no served action exists. Not drawn and not invented.
- Any message, alert, email, WhatsApp text or amount in an alert composed by this page; delivery channels and recipient lists are the server's.
- A role or job-title check in the client; computing any sum, share, count of recipients, receipt denominator or group size.
- Abbreviated money ("₦61.4M"): money shows as served with the served `currency` only.
- Backend, OpenAPI, migrations, `frontend/src/features/workspace` and `work-item` (lane C).

## Assumptions
1. The Publish board shows when `result.status === 'complete'`, `can_publish === true`, `publication_id === null` and `review_subjects[]` is empty. Reason: no read field says "approved"; the server's `can_publish` plus no pending review subject is the nearest served proof, and the server still refuses with 409/422 if not approved.
2. Only `recipient_only === true` readers see the receipt control. Reason: readiness defines the recipient as the `recipient_only` view; a Finance reader with `receipt_id` would be a role guess.
3. `receipt_id` is the viewer's own receipt and `receipt_ids[]` is all receipts for the current publication, drawn as a length only. Reason: field names and the aggregate-receipt description "your own receipt"; no answer states it, so nothing beyond the length is drawn.
4. The in-app sentence "Each recipient confirms receipt in the app. Only totals are sent; never names or pay." is kept from the board. Reason: it states how the feature works (E-26, E-30, I-ALERTS) and carries no figure; the design engineer can drop it.
5. "Verified {verified_at}" is the only verified detail drawn. Reason: it is the only served verified datum.
6. Where seeded live data cannot reach `can_publish:true`, the live round trip is recorded as not run and the mock proof stands. Reason: a live publish sends to real recipients and cannot be undone; the builder must not fabricate state in a shared database.
7. The `publish` and `aggregate-receipt` writes have no idempotency key, so uncertain-write safety comes from the re-read and the lock, never from a resend. Reason: neither request body in the contract has a key.
8. Mock work ids 4710 to 4719 are free after F-107's 4701 to 4709. Reason: no other feature claims them in this range.
9. The panel `key` and the live `totals` key shape are whatever F-107 recorded in its build.md. Reason: untyped in the contract.

## Conflicts with the boards
The spec removes or hides the following parts that a board draws; the recommendation is to hide each (D-182/D-187), so the design engineer decides once.
1. Publish board: "CEO · Adaeze Nwosu" name, "BU heads · 6", the "DISCLOSURE RULE" and "OWN BU ONLY" tags, and the "BU publisher; the preparer may publish" line are hidden (not served). A one-sentence "The CEO and the business unit heads." replaces the block. Recommendation: hide, as specified.
2. Receipts board: "Staff 58", the per-recipient list ("CEO RECEIVED / Delivery head (you) NEEDS YOU / 4 other BU heads WAITING") and "Verified once all 7 recipients confirm" are hidden; the Finance side shows "Receipts recorded: N" (array length) instead, and the recipient side shows only the confirm control and then "You confirmed receipt." Recommendation: hide; the design engineer may draw the recipient-side "You confirmed receipt." line and the Finance "Receipts recorded" card, which no board draws.
3. Verified board: "7 OF 7", "Coverage: Supplied population only", "Private data in the result: None", "Posted to the ledger: No" and "Cancelling now would need follow-up" are hidden. Recommendation: hide; replace with "Verified {verified_at}".
4. All six boards: the seven-station track and the mobile header "Start" button are not drawn (F-107 rule; start is SCR-04). Mobile receipts "₦61.4M" is drawn as the served full amount, not abbreviated.
5. Added without a board: the Finance "Waiting for receipts" card, the recipient "You confirmed receipt." line, and the "Recorded. The page will update ..." lines. Recommendation: draw them before build if the design engineer wants an exact look; otherwise reuse the card and note styles of the neighbouring states.

## Questions
1. Receipt progress for Finance. The page may show "Receipts recorded: N" from the length of `receipt_ids[]`, though the UI otherwise counts nothing. Options: (a) show the length, no denominator (recommended; it is the served list, not a derived business figure); (b) show no count and only "Waiting for receipts" until `verified_at`; (c) ask the backend to serve a received/expected pair and hold the card until then.
2. Cancel-after-publish. The verified board says cancelling would need follow-up; 1.25.0 has no cancel, withdraw or correct-after-publish action for BU totals. Options: (a) draw nothing and say so in build.md (recommended); (b) ask the backend whether a retract action is planned; (c) draw a note "Contact Finance Lead" (invented, not recommended).
3. A Finance reader who is also a recipient. If a person can both publish and be a recipient, the read may show `recipient_only:false` with a non-null `receipt_id`. Options: (a) draw the receipt control only for `recipient_only:true` and show nothing else for such a person (recommended, no guessing); (b) also draw the control when `receipt_id` is null and `publication_id` is set for a non-recipient (risk: a person with no recipient entitlement sees a button that will 403); (c) ask the backend for a served `can_confirm_receipt` flag.
4. Live proof of the publish. A real publish messages the CEO and BU heads and cannot be undone. Options: (a) run the live round trip only on a seeded test project whose recipients are test accounts, otherwise record "not run" (recommended); (b) skip it and rely on the mock plus the live read comparison of criterion 25; (c) use the production-like demo project.
