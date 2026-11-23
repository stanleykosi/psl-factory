# Hypercare lets the PM log a metric observation with proof and set the criteria

> Tasks: FE-CONNECT-1. Architecture: v9 package; contract `contracts/psl-factory.openapi.json` API 1.25.0 or later (lane-d worktree `/Users/Hunchoo/psl-factory-worktrees/lane-d`). Design: approved 13 Nov canvas with the D-173/D-181 exceptions in `design/review.json`; screens: SCR-46 (the observation and criteria forms have no board; the `-record` boards belong to F-113B, see Conflicts with the boards). Part 2 of 2; part 1 is F-115 (`delivery/features/F-115/spec.md`).

## Summary
- WAIT (build start only, not a blocker): F-115 (the hypercare adapter and reads), F-85 (shared adapter, `EvidencePicker`) and F-87 (`LineAdapter.Actions` slot and `useWorkCommand`) must be on main first. This spec is written against F-115's, F-85's and F-87's specs. High risk: the merge goes to the design engineer's merge batch.
- Two forms, in `frontend/src/features/hypercare/HypercareActions.tsx`: **Log an observation** (`POST /work/{id}/stability`, a structured reading by Engineering or Infrastructure with the approved metrics, never a free note) and **Set the criteria** (`POST /work/{id}/stability/criteria`, then the policy review). The release record is not here (coordinator decision): the release form (`observe_release` with the checked PDF on the release register) is built in F-113B. F-115B only shows the release through F-115's display and draws no release form.
- Each form appears only when the line read says the person may use it (`observation_owners[]` not empty and `criteria` set; `can_draft_criteria`; the review button only for the transition the policy-configuration read offers in `actions[]`). The front end checks no role.
- Proof is chosen from the list the read supplies (`proofs[]`), nothing preselected; the button stays off when the list is empty. No evidence id is ever invented, and `fileToEvidence` is not used.
- Every result is told from a re-read of `stability` and `stability/events` (F-115's display draws the new criteria result). A failed write is never retried by itself and never shown as success.

## Context
- Part 1 files (F-115, on main before the build): `frontend/src/features/hypercare/` (`hypercareAdapter.ts`, `hypercareLabels.ts`, `BackgroundControl.tsx`, `useHypercareIssues.ts`). This feature adds `HypercareActions.tsx` and its helpers there and assigns it to the `stability` adapter's `Actions` field. The slot, `LineActionsProps = { readback, ctx: LineContext, commands: CommandDescriptor[], reload }`, and `useWorkCommand` come from F-87 (`frontend/src/features/workspace/useWorkCommand.ts`); the example to copy is F-89's `WeeklyReportActions.tsx`. Nothing under `frontend/src/features/workspace/**` or `work-item/**` is edited.
- Backend (read only): `apps/core/factory_api/hypercare.py` (`detail`, `observe`, `draft_criteria`, `events`, F-115 reads only), `apps/core/factory_api/urls.py:175-177`, `apps/core/factory_api/delivery.py` (`release_register`, line `delivery-release/v1` only).
- Reads (F-115 already reads them; this feature reads the readback passed to `Actions`; the events read feeds no form here):
  - `GET /work/{id}/stability`: `expected_revision`, `case_revision`, `configuration_id|null`, `criteria|null`, `can_draft_criteria`, `observation_owners[]`, `proofs[{id,version,kind}]` (up to 50, filled only when `observation_owners` is not empty), `observations[]`, `criterion_results[]`.
  - `GET /setup/{case_id}/policy-configurations?component=D11.hypercare_criteria_ref` returns `{case_revision, items[{id,component,version,state_id,state,actions[]}], next_page}`; `actions` holds at most one next transition for this viewer (`validated`, `active`, `revoked`).
- Mock: `frontend/mock/server.mjs`; fixtures added by this feature use work ids 4301 to 4313 (F-115 uses 4201 to 4208).
- The release record is out: `observe_release` and any release form belong to F-113B on the release line's own work item.

## Contract

### Where the forms are drawn
`HypercareActions` renders under the panel's sections, only for the `stability` panel, in this order, each form only when its condition holds, with no heading or gap for a form that is absent:
1. Log an observation: `criteria !== null`, `configuration_id !== null` and `observation_owners.length > 0`.
2. Set the criteria: `can_draft_criteria === true`. Shown whether or not criteria exist (a new draft replaces nothing until reviewed).
3. Review the draft: after a draft exists (see below).
Setup needed with `can_draft_criteria` false draws no form (F-115's text "An admin sets the criteria in Setup." stays). No release form or release button is drawn; F-115's "The release has not been recorded." line stays text with no link.

### 1. Log an observation
- **Who**: a select of `observation_owners[]` ("Engineering", "Infrastructure"), nothing preselected; one owner is still chosen by the person.
- **Observed at** (date and time, required, ISO with offset, never defaulted).
- **Confirmed stable?** three radios: "Yes" (`true`), "No" (`false`), "Not known" (`null`); nothing preselected, required.
- **Metrics**: one row per entry of `criteria.metrics` whose `owner` equals the chosen owner, labelled "{key words}, {unit}" with the rule "at most / at least / exactly {threshold} {unit}" (same wording as F-115's `hypercareLabels.ts`). Each row has a number input and a "Not known" checkbox. A row is valid when it has a finite number, or "Not known" is ticked (sent `null`). An empty row without "Not known" is invalid; nothing defaults to 0. Only the approved keys are sent, and all of them for that owner (the server rejects a set that differs from the rule's keys).
- **Reference** (text, 1 to 240 characters, required).
- **Proof**: a select of `proofs[]` labelled "{kind}, version {version}", nothing preselected, required; with an empty list the button is off with "No proof is on this project yet." There is no upload route on this action, so no file picker is drawn here.
- A free-form note is not drawn: the stability request has no note field (D-18 allows a note only where the contract has one). `verify_sample` is not drawn (the read does not say whether the project is a sample; hidden under D-182).
- Request: `POST /api/v1/work/{id}/stability`, body `{expected_revision, case_revision, configuration_id, owner, observed_at, confirmed, reference, evidence_id, metrics}` (no `verify_sample`), tokens from the stability readback, `configuration_id` from the readback as loaded, `successStatuses [201]`, response `{work_id, state, revision, record_id}`.
- The button is "Record observation". No confirmation dialog (an observation is added, not a release); a second observation by the same owner is allowed by the server and sent as the person asks.
- After 201: re-read, then "Observation recorded for {owner}." only when `observations[]` has more rows than before or the owner's `source_id` changed; otherwise the uncertain message above. F-115's display shows the new result; this feature adds nothing to it.
- A 409 `STALE_VERSION` message ("Review the current stability rule...") is shown as given and the form re-reads: the rule changed while the form was open, the fields are cleared of metrics but the other entries are kept.

### 2. Set the criteria
No board draws this form (Conflicts 2). One plain form in the record panel:
- **Window length (hours)**: number, 0 to 87600, required (`minimum_hours`).
- **Who confirms stability**: checkboxes Engineering and Infrastructure, at least one (`confirmation_owners`).
- **Metrics**: 1 to 20 rows, each: key (`^[a-z][a-z0-9_]{0,39}$`, live validation message "Use lower-case letters, digits and underscores, starting with a letter."), unit (1 to 40), owner (Engineering or Infrastructure), rule (at most `lte` / at least `gte` / exactly `eq`), threshold (finite number). "Add a metric" and "Remove" per row. Duplicate keys for the same owner show "Each metric needs its own name for this owner."
- `clock` is fixed `elapsed_hours_since_release` and `financial_controls` fixed `independent`; shown as read-only text "Counted in hours from the release" and "Financial controls stay independent". Nothing else is prefilled: no threshold, owner, window or unit.
- `issue_clearance` is not drawn (Assumptions; Questions 2).
- **Policy decision** (the proof): a select of `proofs[]` filtered to `kind === 'policy_decision'`, nothing preselected, required; none available: "Add a policy decision to this project first." and the button off.
- **Effective from** (date and time, required, never defaulted).
- Request: `POST /api/v1/work/{id}/stability/criteria`, body `{case_revision, criteria, evidence_id, effective_from}` (no `expected_revision`, no idempotency key), `case_revision` from the stability readback, `successStatuses [201]`, response `{configuration_id}`.
- After 201: the draft is not active criteria. Show "Draft saved. It takes effect only after review." and read `GET /setup/{case_id}/policy-configurations?component=D11.hypercare_criteria_ref`, following `next_page` up to 4 pages, then find the item whose `id` equals the returned `configuration_id`.
- The form validates live; validation errors show beside the field and the button is off until all pass. Server 422 `fields[].message` are shown under the form as given.

### 3. Review the draft
- Drawn when the policy-configuration read has an item for the draft (just created, or any item for this component with `state` `draft` or `validated` and `actions` not empty) whose `actions[0]` is `validated` or `active`.
- One button named by the transition: `validated` "Mark as validated", `active` "Make these the hypercare criteria". The viewer sees only the button the read offers; never both. `revoked` is never offered here (out of scope).
- `POST /api/v1/setup/{case_id}/policy-configurations/{configuration_id}/review`, body `{case_revision, state_id, transition}`, `case_revision` from that same policy read (not the stability readback), `state_id` from the item, `successStatuses [200]`, response `{id, component, version, state_id, state, actions}`.
- `active` opens a `Dialog`: "Make these the hypercare criteria? They decide whether this project qualifies. They take effect from {effective_from}." (omit the date phrase if the read does not give it) with "Make active" and "Go back". `validated` has no dialog.
- If the item's `actions` is empty (this viewer may not review, or the independence rule blocks them) the section reads "Waiting for a reviewer" with no button. A 403 or 422 from the server is shown as given.
- After 200: re-read the policy list and `stability`; "Criteria are now active." only when the stability read shows `criteria` with the new values and `configuration_id` equal to the reviewed id; "Validated. Waiting for activation." when `state` is `validated`.
- If the criteria form's 201 succeeded but the policy read fails, show "Draft saved. We couldn't load the review step. Reload to continue." and no button.

### Errors, for every write in this feature
Through `useWorkCommand` (F-87), with these words: 409 "This changed while you were working. Showing the latest version." plus the server message, re-read, no resend; 403 `csrf_failed` refresh session once, "Press the button again", no resend; 403 "You can't do this." plus server message; 404 "This record is unavailable."; 422 server `message` and `fields[]` as given, entries kept; 413/415 not applicable (JSON); 429 and 503 "Try again shortly."; network or 5xx: uncertain, re-read `stability` and `events`, lock that form with "We couldn't confirm that this was recorded. Check the page before trying again." and unlock only when the re-read shows a different `revision` than the one sent, or the page is reloaded. A failed write is never retried by itself. Press lock: one request in flight across both forms, a double click sends one request.

### Null tokens and permission
A `null` or missing `expected_revision` or `case_revision` holds the form with "We don't have this item's current version yet. Reload and try again." (never 0). Every call uses the loaded item's `work_id` and `case_id`; no id is typed. Every list comes from the readback, never from the front end's own role knowledge.

### States
- Loading: forms absent until the readback exists (F-115's page states apply).
- Empty: no form qualifies, so `Actions` renders nothing, no heading.
- Working: pressed button "Working..." and both forms locked.
- Error: a `Callout` (role alert) above the pressed form; entered values kept.
- Success: a `Callout` (role status) with the words above, replaced by the next result; the submitted form's fields cleared.
- Poll rule: F-115's polling re-reads while a form is open; a poll result never clears typed values or an uncertain lock.

### Fixture examples (mock; ids free but shape fixed; live-shaped; added to `frontend/mock/server.mjs`)
- Release fixtures are not needed: F-115's `4202` to `4204` already carry the events read.
- `4301` observation: criteria with Engineering metric `error_rate` (`lte` 2 `percent`) and Infrastructure metric `uptime` (`gte` 99.5 `percent`), `configuration_id:88`, `observation_owners:["Engineering","Infrastructure"]`, `proofs:[{id:61,version:1,kind:"monitoring_export"}]`.
- `4302` one owner only (`["Infrastructure"]`); `4303` no proofs; `4304` `observation_owners:[]` (no form); `4305` criteria null with `can_draft_criteria:false` (no form).
- `4306` criteria setup: `criteria:null`, `can_draft_criteria:true`, `proofs:[{id:71,version:1,kind:"policy_decision"},{id:72,version:1,kind:"notes"}]`; policy list after draft returns item `{id:90,state_id:301,state:"draft",actions:["validated"]}`; after the validated review `actions:["active"]`; after active the stability read serves the new criteria.
- `4307` criteria setup where the viewer cannot review: draft item with `actions:[]`.
- `4308` criteria setup with no `policy_decision` proof.
- `4309` write failures per scenario (header or query switch, F-85's mechanism): 403 `forbidden`, 403 `csrf_failed`, 409 `stale_version`, 422 with `fields`, 429, 503, 500, dropped connection, on the observation, criteria and review POSTs.
- `4310` uncertain effect: the POST drops, the re-read shows the record (treated as recorded); `4311`: the POST drops, the re-read shows nothing (locked).
- `4312` null `expected_revision`; `4313` null `case_revision`.
- Mock POST handlers return the 201/200 bodies in the contract and update the reads only after a successful write.

## Lanes
- Frontend lane (owner): `frontend/src/features/hypercare/HypercareActions.tsx`, `ObservationForm.tsx`, `CriteriaForm.tsx`, `CriteriaReview.tsx`, `hypercareForms.ts` (validation and body builders), the `Actions` assignment in `hypercareAdapter.ts` (F-115's file, additive, rebased on F-115), `useCriteriaPolicy.ts` (the policy-configuration read), the new descriptors added to the adapter's `commands()`, tests `frontend/src/features/hypercare/*.test.ts(x)`, `frontend/mock/server.mjs` and `frontend/mock/fixtures` for the ids above, `frontend/e2e/hypercare-record.spec.ts`, and live types in `frontend/src/api/types.ts` (additive).
- Backend lane: none. No backend, contract or migration change.
- Integration owner: lane D coordinator. Shared and not edited here: `frontend/src/features/workspace/**` and `work-item/**` (lane C: F-85, F-87; a needed frame change is named as a lane C dependency), `frontend/src/features/hypercare/hypercareAdapter.ts` (F-115's, one additive change), `frontend/src/api/*` (additive types only). Any change to `frontend/mock/finance*` or the payments fixtures is named in build.md; none is expected.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. No release form: on every fixture (F-115's `4202` to `4204` and this feature's) there is no "Record release" button, no release proof select, and no POST to `stability/events` or `release-register` — verify: e2e asserts absence and request capture; grep `stability/events`, `release-register`, `observe_release`, `can_record_release` in the new non-test files returns nothing.
2. F-115's release and acceptance facts section is unchanged by this feature — verify: F-115's tests still pass; the diff to `hypercareAdapter.ts` is only the `Actions` assignment and the new descriptors.
3. On `4301`, choosing Engineering shows only the `error_rate` row; choosing Infrastructure shows only `uptime`; a different owner's metric is never drawn — verify: page.
4. Observation validation: an empty metric row without "Not known" blocks the button; "Not known" sends `null`; `0` typed is sent as `0`; nothing defaults to 0; `confirmed` has no preselected radio and "Not known" sends `null`; the button stays off with no proof selected — verify: unit test on `hypercareForms.ts`.
5. The observation POST body is exactly `{expected_revision, case_revision, configuration_id, owner, observed_at, confirmed, reference, evidence_id, metrics}`: no `verify_sample`, no note, no key not in the contract, and `metrics` has exactly that owner's approved keys — verify: request capture; unit test.
6. After an observation 201 the page re-reads and F-115's criteria list shows the new result; the success text appears only when `observations[]` changed — verify: e2e on `4305`.
7. `4302` offers only Infrastructure; `4303` (no proofs) disables the button with "No proof is on this project yet."; `4304` and `4305` draw no observation form — verify: pages.
8. A 409 `STALE_VERSION` on the observation re-reads, keeps owner, time, reference and proof, clears the metric values, and shows the server message — verify: scenario test.
9. On `4306` the criteria form draws the controls above with nothing prefilled; invalid key text, a duplicate key for the same owner, 0 confirmation owners, hours above 87600 and a missing policy decision each show their message and keep the button off — verify: unit test and page.
10. Submitting criteria sends exactly one `POST /api/v1/work/4306/stability/criteria` with `{case_revision, criteria, evidence_id, effective_from}`, `criteria.clock` `elapsed_hours_since_release`, `criteria.financial_controls` `independent`, no `issue_clearance`, no `expected_revision`; `evidence_id` is a `policy_decision` proof — verify: request capture.
11. After the draft 201 the page says the draft needs review, reads the policy configurations (following `next_page`, max 4 pages) and shows the "Mark as validated" button only because the item lists `validated`; `4307` shows "Waiting for a reviewer" and no button; `4308` shows the missing policy decision text — verify: pages.
12. Review sends `POST /api/v1/setup/{case_id}/policy-configurations/90/review` with `{case_revision (from the policy read), state_id, transition}`; "Make these the hypercare criteria" opens the confirm dialog first; `revoked` is never offered — verify: request capture; grep `revoked` in the new files finds no button.
13. The "criteria are now active" text appears only when the re-read `stability` shows the new `criteria` and `configuration_id`; with a stale re-read the page says it could not confirm — verify: e2e with a delayed mock.
14. Error mapping for the observation, criteria and review POSTs: 409, 403 `csrf_failed` (one session refresh, "Press the button again", one POST), 403, 404, 422 with `fields`, 429, 503, network; after each failure no automatic resend; entered values stay — verify: unit tests counting fetch calls per scenario (`4309`).
15. Uncertain effect: after a dropped connection the page re-reads; `4310` (record present) shows it as recorded, `4311` (absent) locks the form with the "couldn't confirm" text and unlocks only after the item `revision` changes or a reload — verify: e2e.
16. Press lock: a double click on any form's button sends one request; while one form works, the other forms' buttons are disabled — verify: e2e request count.
17. A `null` `expected_revision` (`4312`) or `case_revision` (`4313`) holds the form with the "current version" sentence and sends nothing — verify: unit test.
18. Nothing sends on page load, polling or navigation: the only POSTs are the observation, criteria and review calls, from a press — verify: e2e asserts zero POSTs on load; `grep -rn "\.POST(\|liveApi.POST" frontend/src/features/hypercare` shows only F-115's background call and call sites inside the four builders.
19. Hidden parts: no "Log an issue", no `verify_sample` control, no free-note field on the observation form, no go-live acceptance action, no file upload control, no release form or release-register call — verify: grep for `release-register`, `acceptance`, `verify_sample`, `fileToEvidence` in `frontend/src/features/hypercare` returns nothing outside tests.
20. Wrong user: a viewer whose reads return `observation_owners:[]`, `can_draft_criteria:false` and no review `actions` sees none of the forms and sends no request; a direct server 403 on a crafted POST shows "You can't do this." — verify: mock accounts; scenario.
21. Wrong tenant: a work id the account cannot see (404 from every read) shows "This record is unavailable." and no form — verify: open an unknown id in the mock; compare with F-115's wording; against live Django use a work id from another organisation.
22. Viewport 1440 and 390: forms are one column on the phone, controls 44 px high, no horizontal scroll, no axe violations; the forms use the existing design-system tokens and components — verify: screenshots; `hypercare-record.spec.ts` axe run.
23. No file under `frontend/src/features/workspace` or `frontend/src/features/work-item` is changed, and `HypercareActions` is registered only through the `Actions` field of F-115's adapter — verify: `git diff --stat origin/main -- frontend/src/features/workspace frontend/src/features/work-item` is empty; a test renders the adapter's `Actions` with the right props.
24. Against live Django (8030, the lane-d Postgres fixture, a PM account that is an observation owner on a `delivery-hypercare/v1` item): record one observation, and the `curl` of `/api/v1/work/{id}/stability` shows the new `observations[]` row and an updated `criterion_results[]`; a repeated call with a stale `expected_revision` returns 409 and the page shows the stale text — verify: curl against the same work id; page.
25. `npm run typecheck`, `npm run lint`, `npm test` pass and `api-live-schema-drift.test.ts` passes — verify: `delivery/checks.sh`.

## Out of scope
- All read states, the pause and continue control and the issues list (F-115).
- Go-live acceptance (`action:"acceptance"`) from this screen (SCR-45, F-114) and signatures.
- Recording the release in any form (`stability/events` release, `observe_release`, release proof, private log, readiness record): that is F-113B. File upload and `fileToEvidence`.
- Criteria `issue_clearance`, revoking a configuration, editing or superseding criteria beyond drafting and the one-step review, and a Setup > Rules page.
- Free-form observation notes, "Log an issue" from this screen, a day count, actual reading values drawn in the display, `verify_sample`.
- Any change to `frontend/src/features/workspace`, `work-item` (lane C), the SCR-47 archive, backend, contract and migrations.

## Assumptions
- `proofs[]` (any kind) is the evidence list for observations; criteria use only `kind === 'policy_decision'`. Reason: the backend checks `policy_decision` for criteria (`hypercare.py` `draft_criteria`); the observation action states no kind.
- `issue_clearance` is omitted from the criteria form. Reason: it needs a `reader_id` (a user id) and no read tells the form who may be named; inventing one would be a business rule. Criteria drafted here have no issue check; Setup can add one.
- Nothing from `criteria.metrics` is prefilled for the form beyond showing the approved keys of the owner chosen. Reason: rule text is stored as reviewed; thresholds are shown as rules, never as values.
- Confirm dialog only for making criteria active. Reason: it is the hard-to-undo step here.
- The release form is F-113B's (coordinator decision). Reason: the release register is served on the release line's own work item.
- The policy-configuration list is filtered to `D11.hypercare_criteria_ref` and read with `page`, up to 4 pages. Reason: it pages at 25 and the draft is the newest; no stricter rule is documented.

## Conflicts with the boards
`SCR-46-desktop-record` and `SCR-46-mobile-record` draw the release form. Under the coordinator's decision F-113B builds it, so F-115B draws no release form and does not build those two boards. No board draws the observation form or the criteria and review forms.
1. **No board for the observation form and the criteria form.** This spec draws both as plain forms in the record panel. Recommendation: the design engineer draws them (4 concepts, per the undrawn-design rule) before the build starts; the build follows the board that is chosen, and the spec text defines the fields.
2. **Kept hidden because the API does not supply it:** the setup-needed board's "Open Setup > Rules" link (F-115 left it as text). Nothing added here; hidden under D-182.

## Questions
1. Criteria `issue_clearance`. (a) Leave it out now; Setup adds it (recommended: the `reader_id` has no source on this screen). (b) Add an optional block with a reader chosen from the issues read's `owners[]`, if backend confirms that list is the allowed readers.
2. Criteria form board. (a) The design engineer draws one plain form and the review step before the build (recommended). (b) Build from this text and review in the UI round. (c) Leave criteria to Setup and show text only.
3. Observation proof when no file is on the project. (a) The person adds evidence elsewhere first, and the select stays empty with its explanation (recommended, as built). (b) A backend change gives this action an upload field (D-1 names none for it); for backend, not this feature.
