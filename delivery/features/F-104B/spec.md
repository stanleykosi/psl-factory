# A Finance person resolves a duplicate ledger source, an independent reviewer confirms, returns or withdraws it, and a verified source can be re-checked, live

> Tasks: FE-CONNECT-1. Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.25.0 or later (read from `/Users/Hunchoo/psl-factory-worktrees/lane-d/contracts/`). Design: approved 13 Nov canvas under the recorded exceptions in `design/review.json`; screens: SCR-58 part 2 (states duplicate, rejected, verified, and the review of a resolution; the other states are F-104).

## Summary
- On `/work/{id}` for a ledger source, when the live read says another capture conflicts (`conflict_id` set), the page draws the duplicate board (refused, nothing posted) and a form to resolve it: choose the capture to keep, the ones to retire, say whether it is a reference correction or a duplicate alias, write what was checked and a short reason. It sends `POST /projects/{case_id}/incumbent-resolutions` `propose`.
- A reviewer sees each resolution packet that includes this source and records Confirm, Return or Withdraw with a written note (made as `ledger_resolution_review` evidence). The server enforces who may.
- A verified source shows the board's "a re-check reopens it" sentence with a Re-check button; a cancelled one shows Restart. Both send `recheck` or `restart` with a typed reason to `POST /work/{work_id}/incumbent-reference`.
- The lineage row ("New · no predecessor", "Continues an earlier capture") and the rejected board's "correction continues the same lineage" sentence are drawn only from `lineage_id`, `predecessor_id` and `latest_decision`.
- Hidden, not faked (D-182): amounts, "LED-nnnn" labels, capture dates and "Open LED-0049" (the API supplies none). No amount anywhere; nothing is posted or sent to QuickBooks. Build waits for F-104 (part 1), F-85 and F-87 on main.

## Context
Part 1 is `delivery/features/F-104/spec.md`: the panel `ledgerSourceAdapter` (key `incumbent-reference`, `frontend/src/features/ledger-source/`), the read, observe and review writes, the hold line, `captureLedgerSource` and `startLedgerWork`. It is not yet in the lane D worktree (`frontend/src/features/ledger-source` does not exist at b8542c79); the builder reads it from main once F-104 is merged. Do not duplicate or edit part 1's files except through its exported functions (mapper, `labels.ts`, `ledgerSourceApi.ts` read and error helpers).

- Seam (F-87, lane C): `LineAdapter.Actions?: ComponentType<LineActionsProps>`, `LineActionsProps = { readback, ctx: LineContext, commands: CommandDescriptor[], reload }`, rendered by `PanelView` in `frontend/src/features/work-item/live/LiveWorkItemView.tsx` under the panel's sections, inside its error boundary. `LineContext = { workId, caseId, revision, caseRevision }` (`frontend/src/features/workspace/adapter.ts`). Sends go through `useWorkCommand` (`workspace/useWorkCommand.ts`, F-87) and `makeCommand`. Reference example: F-89's `WeeklyReportActions.tsx`.
- Shared UI by name: `FileUpload` is not needed here; use `Button`, `Callout`, `Select`, `Tag`, `Sections.tsx` kinds from `workspace/labels.ts`; errors from `src/api/errors.ts` (`ApiError`); reads through `liveApi` in `src/api/client.ts`.
- Backend (read only): `apps/core/factory_api/ledger.py` (`detail`, `command`, `collisions`, `resolve_collision`, `evidence`), `apps/finance/ledger_resolution.py` (`propose`, `review`, `visible_packets`, `visible_claims`), `apps/workflows/factory_ledger.py` (`recheck`, `restart`, `conflicting_source`).
- Live operations (live viewer: `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live <METHOD> <path> 3` from the main checkout needs `contracts/`; read the JSON in the lane D worktree instead):
  - `GET /api/v1/projects/{case_id}/incumbent-resolutions` (`ledger_collisions`).
  - `POST /api/v1/projects/{case_id}/incumbent-resolutions` (`ledger_resolve_collision`): `propose` or `review`.
  - `POST /api/v1/projects/{case_id}/incumbent-evidence` (`ledger_evidence`), kinds `ledger_resolution` and `ledger_resolution_review` (value is a text string, 1 to 4000 characters).
  - `POST /api/v1/work/{work_id}/incumbent-reference` (`ledger_command`), actions `recheck` and `restart`.
  - The incumbent-reference read is part 1's; this feature takes `lineage_id`, `predecessor_id`, `conflict_id`, `stage`, `latest_decision`, `can_observe`, `verified`, `expected_revision`, `case_revision`, `source` from it (through part 1's exported read, never a second read of the same route).

## Contract

### Read: `GET /api/v1/projects/{case_id}/incumbent-resolutions` -> 200
`case_id` is the loaded work item's `case_id`. Response (all required, no extra keys): `case_revision` int; `claims[]` (max 100) `{id int, case_id uuid, source_reference string, target_reference string|null}`; `resolutions[]` (max 40) `{id, reference, mode "reference_correction"|"duplicate_alias", version, selected_id, current_reviewed bool, members[{lineage_id, disposition string}], last_review_id|null, last_verdict "confirm"|"return"|"withdraw"|null}`; `resolution_evidence[]` (max 40) `{id, version, kind}` (not used by this feature; see Assumptions).
- A claim `id` and a member `lineage_id` and `selected_id` are lineage ids, the same kind as the incumbent-reference read's `lineage_id`, `predecessor_id` and `conflict_id`. A resolution `id` is a resolution id.
- The server returns only claims and packets the person may see (`ledger.private.read`, readable workspaces). A claim that is missing is simply not drawn; the page never fills it in.
- Errors: as part 1's read (401, 403 `forbidden` no-access, 403 `csrf_failed` refresh, 404 "This record is unavailable.", 409 and 422 server message, 429/503 "Try again shortly.", network "We couldn't reach the server."). This read runs once on mount and after every write. A failed read here shows one small Callout with Try again inside this feature's block and does not blank part 1's panel.

### What is drawn (the `Actions` component `LedgerResolutionActions`)
Everything below is drawn under part 1's sections. Part 1's mapper is untouched.

| Block | Shown when | Content |
|---|---|---|
| Lineage row | `lineage_id` not null | `predecessor_id` null: "New · no predecessor". Not null: "Continues an earlier capture" plus its `source_reference` when a claim with that id is in `claims[]`. No id numbers drawn. |
| Duplicate card | `conflict_id` not null (stage `duplicate`) | Board text: "Another capture of this source already exists. It isn't clear which is right, so this capture is refused. Nothing was posted." Then "Compare": two rows, "This capture" (the read's `source.source_reference`, `target_reference`) and "The other capture" (the claim whose `id === conflict_id`: `source_reference`, `target_reference`; if no such claim is served the row says "You can't see the other capture."). No amount, no capture date, no "LED-nnnn", no "Open LED-0049" link (not served). |
| Resolve form | `conflict_id` not null | below |
| Resolution packets | any `resolutions[]` entry whose `members[].lineage_id` includes this read's `lineage_id` or `conflict_id` | one card per packet, newest version first: "{Reference correction | Duplicate alias} · version {version}", `members[]` as rows "{claim reference or 'Capture'} · {disposition as given}", state line from `current_reviewed` and `last_verdict` ("Confirmed", "Returned", "Withdrawn", "Waiting for review"; `current_reviewed:false` after a confirm reads "Confirmed earlier; needs review again"), then the review form if it applies |
| Rejected sentence | `latest_decision.verdict === "reject"` and `can_observe` | "Correct it with the right evidence; the correction continues the same lineage." No Correct button (part 1's observe form is already open below; Question 2). |
| Re-check | part 1 readback `verified !== null` | "A reference only. If the source changes later, a re-check reopens it." and a "Re-check" button opening the reason field |
| Restart | `ctx.state === "cancelled"` (see Lanes, dependency on lane C) | "Restart" button opening the reason field. Without `ctx.state` it is not drawn. |

Unknown values read "Not recorded", never 0, never blank.

### Write 1: propose a resolution (`conflict_id` not null)
Fields, nothing chosen when it opens:
- "Which captures are involved": a checklist of `claims[]` (label `source_reference` and, when not null, "target {target_reference}"; the row whose id equals this read's `lineage_id` is tagged "This capture", the one equal to `conflict_id` "The other capture"). Ticking sets the member list.
- "Keep": a radio over the ticked captures (the anchor, `selected_id`). Every other ticked capture is retired. At least two ticked and one kept; the button stays off otherwise.
- "What kind": two choices, "Correct a reference" (`reference_correction`) and "Same record, two references" (`duplicate_alias`). Nothing chosen at first (words: Question 3).
- "Reference": a `Select` of the distinct non-null `source_reference` and `target_reference` values of the ticked captures, "Choose..." first. The person picks, never types, an identifier.
- "What you checked": text, 1 to 4000 characters. It becomes the `ledger_resolution` evidence.
- "Reason": text, 1 to 400 characters (`propose.reason` limit). Counter shown.
Button "Propose resolution", off until all are set. Words under it: "A second person has to review this. Nothing is posted."

One press runs two calls in order (the first result is kept if the second fails):
1. `POST /api/v1/projects/{case_id}/incumbent-evidence` `{kind:"ledger_resolution", case_revision, value:<What you checked>}` -> 201 `{id, version, kind}`. `case_revision` is the resolutions read's.
2. Re-read the resolutions to get the current `case_revision` (and the latest packet for the chosen reference), then `POST /api/v1/projects/{case_id}/incumbent-resolutions` `{action:"propose", case_revision, selected_id, retired_ids:[...], member_ids:[... all ticked incl. selected], mode, reference, predecessor_id, evidence_id:<step 1 id>, reason}` -> 201 `{id, case_revision}`.
- `predecessor_id` is the `id` of the highest-`version` entry of `resolutions[]` with the same `reference`, else `null`. It is derived from the read, never typed. (The server requires it to be the exact latest packet for that reference.)
- `retired_ids` is a proper, non-empty subset of `member_ids` and excludes `selected_id`; ids are distinct integers; `member_ids` has 2 to 40 entries. The page does not decide whether the population is complete: the server refuses an incomplete or changed population with its 422 message, shown as given.
- After 201: re-read the resolutions and the incumbent-reference (and the work item through `reload`). "Proposed" is told from the re-read (a packet with `id` equal to the 201's id is present), not from the 201 alone.
- Retry: after a definite failure on step 2 (400, 403, 409, 413, 415, 422, 429) the same evidence id is reused; if the failure was 409 or the re-read shows a changed claim list, the evidence is made again from a fresh read. After a dropped connection or 5xx on step 2: uncertain. Re-read; if a packet with the chosen reference and a higher version (or a new `id`) is present, show it proposed; otherwise show "We couldn't confirm that this was recorded. Check the page before trying again." and lock the button until the re-read shows a different `case_revision` or the person reloads. Nothing is sent by itself.

### Write 2: review a resolution (confirm, return, withdraw)
Shown on a packet card when `last_verdict` is `null` (Confirm, Return, Withdraw) or `"confirm"` (Withdraw only). Not shown on a returned or withdrawn packet. Whether the person may review is the server's call (the independent-reviewer rule); no client role check (Question 4 asks the backend for a flag).
- Field "Note": text, required for all three, 1 to 4000 characters. It becomes `ledger_resolution_review` evidence. Buttons "Confirm", "Return", "Withdraw", off until the note is set. There is no reason field (the review body has none). Words on the card: "Confirming records that this resolution was checked. Nothing is posted."
- One press, two calls: (1) `POST /projects/{case_id}/incumbent-evidence` `{kind:"ledger_resolution_review", case_revision, value:<note>}` -> `{id,...}`; (2) re-read for the current `case_revision`, then `POST /projects/{case_id}/incumbent-resolutions` `{action:"review", case_revision, resolution_id, evidence_id, verdict:"confirm"|"return"|"withdraw"}` -> 201 `{id, case_revision}`. The same retry, uncertain and re-read rules as Write 1; "Reviewed" is told from the re-read (`last_review_id` changed or equals the 201's `id`).
- One verdict per press; all three buttons of that card lock while one runs. Another card is independent.
- Errors: 403 non-csrf "You can't do this." plus the server message (this is where the server's "Independent resolution reviewer required" appears), then re-read; the rest as part 1.

### Write 3: re-check or restart (`POST /api/v1/work/{work_id}/incumbent-reference`)
- Re-check: shown when `verified !== null`. Restart: shown when `ctx.state === "cancelled"`. Field "Reason" (1 to 2000 characters, required). Buttons "Re-check" / "Restart", off until a reason is set. A confirm line under the field before sending is not added; the button is the confirmation.
- Body (built by `makeCommand`): `{action:"recheck"|"restart", expected_revision, case_revision, reason}`; the action values come from the generated type in `live-schema.d.ts` (the viewer shows them as an enum `recheck`, `restart`). `expected_revision` and `case_revision` are the incumbent-reference read's, never 0, never null, never defaulted. Neither token nor any key goes inside `inputs` to `makeCommand`. 201 `{work_id, state, revision, record_id}`.
- After 201: `reload()` re-reads the panel and the work item; the result is shown from the re-read (the verified block gone and the state tag changed). The 201 alone changes nothing on screen.
- Errors as in Write 2; 409 (including "Refresh active incumbent work", "Refresh settled cancelled work") re-reads and says "This changed while you were working. Showing the latest version."; 5xx or drop is uncertain: re-read, lock both buttons until `expected_revision` differs or the person reloads.

### Idempotency and versioning
No body here has an idempotency key. Duplicates are prevented by the press lock, the uncertain lock and the revision tokens. Tokens: the resolutions read's `case_revision` for the project endpoints (re-read between the evidence call and the write); the incumbent-reference read's `expected_revision` and `case_revision` for Write 3. A fresh read follows every write and every 409.

### Screen states
- Loading: skeleton lines in this feature's block while the resolutions read runs; part 1's panel shows as part 1 draws it.
- Empty: no `conflict_id`, no packets, not verified, not cancelled: this feature draws only the lineage row (when `lineage_id` is set) and nothing else; no empty heading.
- Error: the read error Callout with Try again; or the write's mapped message in a Callout in the block that wrote.
- Success: after a write, the re-read result (packet appears, verdict shown, verified block gone).

### Fixture examples (mock, port 4991; ids 4221 onward so as not to collide with part 1's 4201 to 4210)
- `4221` duplicate: incumbent-reference `lineage_id:11, conflict_id:12, can_observe:false, stage:"duplicate"`; resolutions `claims:[{id:11,case_id,source_reference:"JE-7741",target_reference:"JE-7741-A"},{id:12,case_id,source_reference:"JE-7741",target_reference:null}]`, `resolutions:[]`, `case_revision:9`.
- `4222` duplicate where the other claim is not served (`claims` has only id 11).
- `4223` pending packet: `resolutions:[{id:5,reference:"JE-7741",mode:"duplicate_alias",version:1,selected_id:11,current_reviewed:false,members:[{lineage_id:11,disposition:"selected"},{lineage_id:12,disposition:"retired"}],last_review_id:null,last_verdict:null}]`.
- `4224` confirmed (`last_verdict:"confirm", current_reviewed:true`, Withdraw only); `4225` returned and `4226` withdrawn (no review form).
- `4227` verified (`verified` set) with Re-check; `4228` cancelled with `state:"cancelled"` (Restart); `4229` rejected with `can_observe:true` (the sentence).
- `4230` 409 on first write then success after re-read; `4231` resolutions read 404.
- Mock routes: `GET`/`POST incumbent-resolutions`, `POST incumbent-evidence` for the two kinds returning `{id, version:1, kind}`, `POST incumbent-reference` for `recheck` and `restart`, each checking field names, `additionalProperties`, limits (reason 400 and 2000, note 4000) and that `retired_ids` is a proper subset of `member_ids` without `selected_id`. Scenarios (the F-85/F-87 mechanism): 403 `forbidden` (message "Independent resolution reviewer required"), 403 `csrf_failed`, 409, 422 with `fields`, 429, 503, 500, and a dropped connection in applied and not-applied variants for propose, review and recheck.

## Lanes
- Frontend lane (all of this feature): `frontend/src/features/ledger-source-resolution/**` (`LedgerResolutionActions.tsx`, `ProposeForm.tsx`, `ResolutionCard.tsx`, `ReasonForm.tsx`, `resolutionApi.ts`, `resolutionModel.ts`, `labels.ts`, tests), `frontend/mock/ledger-resolution.mjs` and `frontend/mock/fixtures/ledger-resolution/**`, `frontend/e2e/ledger-resolution.spec.ts`, live types in `frontend/src/api/types.ts` from `live-schema.d.ts` for the four operations. The combined adapter is registered in one place: `{...ledgerSourceAdapter, Actions: LedgerResolutionActions}` under key `incumbent-reference`. If the registry refuses a second registration of a key, the one registration line in F-104's adapter file is the only part 1 edit allowed; name it in build.md.
- Backend lane: none. No backend, migration or contract change.
- Integration owner: lane D coordinator.
- Shared files: `src/features/workspace/**` and `LiveWorkItemView.tsx` (lane C owns; used as is). `mock/server.mjs` (one import line to mount `ledger-resolution.mjs`). `src/api/*` (additions limited to live types). Part 1's `src/features/ledger-source/**` (F-104 owns; used through exports).
- Dependency on lane C (additive, to be named before the build starts): `LineContext.state` (the work item's `state`) so Restart can be drawn. Without it Restart is not drawn and Question 1 stands. No change to the frame beyond that.
- Dependency on F-104: it exports `ledgerSourceAdapter`, its read helper and `labels.ts`, and it does not itself call the resolutions or recheck operations.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
Ports: Next 4990, mock 4991, Django 8030.
1. `/work/4221` (mock) shows the duplicate card with "Nothing was posted.", the rows "This capture" and "The other capture" with the references of claims 11 and 12, the resolve form, and no amount, no capture date, no "LED-" label and no "Open" link — verify: page; DOM text search; e2e.
2. `/work/4222` shows "You can't see the other capture." and the form with only the served claim; no id numbers in the text — verify: page; unit test on the model.
3. The resolve form opens with nothing ticked, kept, chosen or typed; "Propose resolution" is off until at least two captures are ticked, one is kept, a kind and a reference are chosen, and both texts are within limits (4000 and 400) — verify: component test stepping through each requirement.
4. "Reference" offers only the distinct non-null references of the ticked captures and no free text — verify: component test; the input type is a `Select`.
5. One press sends exactly two requests in order: `POST /api/v1/projects/{case_id}/incumbent-evidence` with `{kind:"ledger_resolution", case_revision, value}`, then (after a resolutions re-read) `POST .../incumbent-resolutions` with `{action:"propose", case_revision, selected_id, retired_ids, member_ids, mode, reference, predecessor_id, evidence_id, reason}` where `evidence_id` is the first response's id; `retired_ids` is a proper subset of `member_ids` without `selected_id` — verify: e2e request capture; unit test on the builders.
6. `predecessor_id` is `null` when no packet has the chosen reference and the highest-`version` packet's `id` when one does (two packets with one reference: the later version wins) — verify: unit test.
7. After the propose 201 the page re-reads and shows the packet only if the re-read has it; with a mock that returns 201 and an unchanged re-read it does not say "Proposed" — verify: e2e with both scenarios.
8. A 422 on propose (for example an incomplete population) shows the server message and first `fields[].message` as given and sends nothing more; a retry after a 422 sends only the propose call with the same `evidence_id` — verify: unit test counts evidence and propose POSTs (one and two).
9. A 409 on propose re-reads, says "This changed while you were working. Showing the latest version.", keeps the typed texts, and the next press makes new evidence from the fresh read — verify: e2e on `/work/4230` counting requests.
10. After a dropped connection on propose the page re-reads; with no new packet it says "We couldn't confirm that this was recorded. Check the page before trying again.", disables the button and sends nothing over 60 s of fake time; with the new packet present it shows it proposed — verify: unit test with fake timers; e2e applied and not-applied variants.
11. `/work/4223` draws the packet card with its mode, version, members and "Waiting for review" and the Confirm, Return and Withdraw buttons, off until the note is set (1 to 4000) — verify: page; component test.
12. Pressing Confirm sends the evidence call `{kind:"ledger_resolution_review", case_revision, value}` then `POST .../incumbent-resolutions` `{action:"review", case_revision, resolution_id, evidence_id, verdict:"confirm"}`; Return and Withdraw send their verdicts; the body has no reason, no null and no 0 — verify: e2e request capture for each verdict.
13. `/work/4224` offers only Withdraw; `/work/4225` and `/work/4226` offer no review control and show "Returned" and "Withdrawn" — verify: e2e asserts absence.
14. A double click on a verdict sends one evidence call and one review; while it runs all three buttons of that card are disabled and a poll or re-read result mid-write does not clear the lock — verify: unit test with a deferred POST; e2e counts requests.
15. A 403 `forbidden` on a review shows "You can't do this." plus the server message "Independent resolution reviewer required", re-reads, and sends nothing more — verify: mock scenario; e2e.
16. A 403 `csrf_failed` on any write of this feature refreshes the session once, says "Press the button again", is not shown as no-access, and sends no second request — verify: unit test counts POSTs (one) and session reads (one).
17. After a review 201 the card shows the verdict from the re-read; with an unchanged re-read it does not — verify: e2e with both scenarios.
18. `/work/4227` shows "A reference only. If the source changes later, a re-check reopens it." and a Re-check button; `/work/4201` (part 1 verified-free item) shows neither — verify: page; e2e asserts absence.
19. Re-check sends one `POST /api/v1/work/4227/incumbent-reference` with exactly `{action:"recheck", expected_revision, case_revision, reason}` (tokens from the incumbent-reference read, `action` equal to the generated type's value, no key, no 0 or null); an empty reason sends nothing — verify: e2e request capture; unit test on the descriptor `body()`.
20. `makeCommand` for these commands is called with `inputs` holding only `reason`; no revision token and no key appear in `inputs` — verify: unit test; grep.
21. After a re-check 201 the page re-reads and the verified block and sentence follow the re-read, not the 201; after a dropped connection both buttons stay locked until `expected_revision` changes or the page is reloaded — verify: e2e applied and not-applied variants.
22. `/work/4228` (`ctx.state` cancelled) shows Restart and its reason field; with `ctx.state` absent from the context, Restart is not drawn and nothing breaks — verify: e2e; unit test with a context lacking `state`.
23. `/work/4229` shows "Correct it with the right evidence; the correction continues the same lineage." and no Correct button; a rejected item with `can_observe:false` shows no such sentence — verify: page; unit test.
24. The lineage row reads "New · no predecessor" for `predecessor_id:null` and "Continues an earlier capture" otherwise, with the claim's `source_reference` only when that claim is served, and never an id number — verify: unit test on the model.
25. `/work/4231` (resolutions read 404) shows "This record is unavailable." in this feature's block and part 1's panel still draws; a 429 or 503 shows "Try again shortly." with Try again — verify: e2e; mock scenarios.
26. No client code reads `/me` or a role to decide a control; the forms are drawn from `conflict_id`, `claims`, `resolutions`, `verified` and `ctx.state` only — verify: grep `useMe`, `/me`, `role` in `features/ledger-source-resolution`.
27. On load, poll and navigation the page sends no `POST`; every write is from a press — verify: e2e asserts zero POSTs after load and after a 12 s poll window; grep `liveApi.POST` shows calls only in `resolutionApi.ts` and `useWorkCommand`.
28. No amount, currency symbol or "posted" claim appears in any state of this feature; "Nothing was posted" appears only on the duplicate card — verify: DOM text search across the fixtures.
29. Part 1's files are unchanged apart from the named registration line (if needed) — verify: `git diff --stat origin/main -- frontend/src/features/ledger-source` shows nothing, or that one line.
30. Against live Django 8030 with a Finance account that may read the case: the claims and packets the page draws equal `GET /api/v1/projects/{case_id}/incumbent-resolutions` for that case (use the session with `curl`); proposing, then reviewing as a second Finance user, changes the packet's `last_verdict` in that read. Also record whether the evidence call changes `case_revision`. If no accounts or data reach this state, say so and mark it not run — verify: page against the live read; output pasted in build.md.
31. Against live Django, the same person who proposed tries to confirm: the page shows the server's refusal unchanged and nothing changes in the read — verify: live read before and after; if not reachable, mark not run.
32. Viewport check at 1440 and 390: the duplicate, rejected and verified states match the SCR-58 duplicate, rejected and verified boards for the parts that remain; hidden parts leave no gap or heading; the forms and cards (not drawn) follow the design system tokens — verify: screenshots at both widths against `design/screens.md` SCR-58 artboards.
33. New tests: unit tests for the model (lineage row, packet filtering by `lineage_id`/`conflict_id`, predecessor, retired subset), the request builders and the lock rules, component tests for the three forms, and `frontend/e2e/ledger-resolution.spec.ts`; `delivery/checks.sh` passes — verify: the check run output.

## Out of scope
- Everything part 1 owns: the incumbent-reference read, observe and review writes, the hold line, the reviewer name and date, `captureLedgerSource`, `startLedgerWork`.
- Payroll (SCR-59), SCR-53, SCR-57, month-end, and the "refused, nothing was posted" state as a stand-alone state; any amount; any posting or call to QuickBooks.
- "Open LED-0049" and any link to the other capture's work item (the API serves no work id), capture dates, "Amount in file" columns, "LED-nnnn" labels.
- A "Correct" button that opens another record. A resolution on cases the person cannot read. Editing or deleting a packet.
- Choosing or pre-selecting claims, evidence, mode, reference or a reason for the person; typing identifiers. Using `resolution_evidence[]` or `verification_evidence[]` as pickers.
- Backend, migrations, contract edits, changes to F-85's frame beyond the one additive field named under Lanes.

## Assumptions
- Evidence for propose and review is made by this page through `incumbent-evidence` kinds `ledger_resolution` and `ledger_resolution_review` with the person's own text. Reason: that is the action's own evidence route (the propose and review bodies require `evidence_id` of exactly that kind); `resolution_evidence[]` carries no kind filter and is not used.
- The review "Note" is the evidence text; there is no separate reason. Reason: the review body has no reason field.
- The case revision for the second call is taken from a fresh resolutions read after the evidence call. Reason: the evidence response carries no revision and it is unknown whether adding evidence moves `case_revision`; acceptance 30 records the answer.
- `predecessor_id` is derived from the highest-version packet with the same reference. Reason: the server demands the exact latest packet and the read lists packets with `reference` and `version`.
- Packets are shown when their members include this item's `lineage_id` or `conflict_id`. Reason: the read serves packets across the tenant's readable cases; these are the ones about this source.
- Review controls: all three on a never-reviewed packet, Withdraw only after a confirm, none after return or withdraw. Reason: the contract allows any verdict at any time; the page offers only the ones that still mean something and the server decides the rest.
- Forms for propose and review show to everyone who can read the case and the server refuses the rest. Reason: the read gives no `can_propose` or `can_review` flag (Question 4); this is the best reading of the contract.
- Re-check is drawn when `verified !== null`; Restart when `ctx.state === "cancelled"`. Reason: the work read supplies no recheck or restart flag, and the board ties re-check to a verified source; the server (`factory.manage`, settled work) refuses the rest and its message is shown.
- Ids are never drawn as text. Reason: they are technical identifiers and the boards use "LED-nnnn" labels the API does not serve.
- Two-call writes keep the first result on failure, like part 1. Reason: avoids a second evidence record for the same intent.
- Mock fixture ids 4221 to 4231. Reason: free in the mock and clear of part 1's 4201 to 4210.

## Conflicts with the boards
Each place the spec adds, moves or removes something a board draws. Recommendation first; the design engineer decides once before the build starts.
1. Duplicate board: removed "Amount in file", "Captured" dates, "LED-0049" and "LED-0052" labels and "Open LED-0049" (not served). Replaced by two reference rows. Recommend accept; revisit when the backend serves amounts, dates and a link.
2. Duplicate board: added a resolve form (claims checklist, keep, kind, reference, what you checked, reason) and the packet cards with review forms. None is drawn. Recommend a board by the design engineer (4 concepts per the design-fidelity rule) before the build; the spec's layout is a plain stack on the existing form styles.
3. Rejected board: "Correct" button removed; the sentence kept. Recommend accept (the observe form from part 1 is already open).
4. Verified board: sentence kept and a Re-check button added (not drawn); Restart added on cancelled (no board). Recommend accept after a quick board.
5. Review board: the "Note" label now also covers Confirm, Return, Withdraw on a resolution card, and the evidence is the note. Recommend accept.
6. The lineage row is drawn only as "New · no predecessor" or "Continues an earlier capture"; the board's "Captured by", "Observed by" and the board's other lineage detail stay hidden as in part 1.

## Questions
1. Restart needs the work item's `state` and the page's `LineContext` does not carry it. Options: (a) lane C adds `state` to `LineContext` (additive) before the build, Restart drawn when it is `cancelled` (recommended: the server still decides); (b) Restart is not drawn in this feature and is listed as held; (c) Restart is drawn on every cancelled-looking readback by a client guess (rejected). Context: the incumbent-reference read has no cancelled flag and `actions[]` on the work item lists only `background`, `reconcile`, `release_invoice`.
2. The rejected board's "Correct" button. Options: (a) draw the sentence and no button, because part 1's observe form is already open for a rejected source (recommended); (b) draw a "Correct" button that moves focus to part 1's observe form (needs an element hook from F-104); (c) hide the sentence too. Context: a button that only scrolls adds a part 1 edit.
3. Plain-words labels for the two modes, which no board draws: "Correct a reference" (`reference_correction`) and "Same record, two references" (`duplicate_alias`). Options: (a) these words (recommended); (b) show the raw mode names; (c) hold the mode choice until the design engineer supplies the words. Context: the API gives only the two codes.
4. Backend: the resolutions read has no flag for who may propose or review, so the forms show to everyone who can read the case and the server refuses the rest. Options: (a) build as drawn here and ask the backend for `can_propose` and `can_review` on the read, switching the forms on them when served (recommended); (b) hold the forms until the flags exist; (c) hide the forms unless the incumbent-reference read is `can_observe`-capable (rejected: wrong signal). Context: the independent-reviewer rule makes a wrongly shown Confirm refuse with a message, not a wrong write.
5. Who types the "Reference" value. Options: (a) pick from the ticked captures' own references (recommended: no typed identifier; the server accepts any identifier shape); (b) type it with the identifier pattern; (c) fix it to the kept capture's target reference. Context: the server groups packets by this string and demands the latest packet's id as `predecessor_id`; which reference is the right one is a Finance call.
6. The ticked list is every claim the person can see (up to 100), not only related ones. Options: (a) show all in served order with this capture and the other one tagged, and let the server refuse an incomplete population (recommended: no client rule about what is related); (b) filter to claims sharing a source or target reference with this one (a client rule that could hide a member the server requires); (c) pre-tick the two tagged captures (rejected: pre-selected answers). Context: the server computes the full related population and refuses a mismatch.
