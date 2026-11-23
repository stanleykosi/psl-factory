# Emergency change line: record, refused, review, retrospective and report, live on the work item page

> Tasks: FE-EMERGENCY-ESCALATION (part 1: SCR-50 only). Architecture: v9 package (revision as pinned in the feature record at branch time); contract API 1.26.0 as in `frontend/src/api/live-schema.d.ts` on main. Design: approved canvas under `design/review.json` (SCR-50 client-approved); screens: SCR-50 (boards `SCR-50-desktop-/mobile-` record, refused, review, retro, report).

## Summary
- A work item whose `panels[]` holds the key `emergency` shows the emergency line on `/work/[id]`, drawn from `GET /work/{id}/emergency` through lane C's line adapter (F-85). No new workspace frame.
- The five SCR-50 boards come from the read's `stage` and `actions[]`: refused (a recorded `reject`), record the outcome, review the outcome, retrospective decision, report. Only what the read supplies is drawn.
- Writes: `authorize`, `capture_outcome`, `record_review`, `retrospective_decision`, `reconcile_retrospective` on `POST /work/{id}/emergency`; the report review on `POST /work/{id}/reviews` (`kind:"document"`); retrospective follow-up changes on `GET/POST /projects/{case}/emergency-outcomes/{outcome_id}/followups`.
- "Customers affected" and "side effects" show "Unknown" when null, never 0 or "None". Names and times come only from `authorization_history[]` and `outcome_history[]`. No approver, role gate or attempt count is invented: `options[]` and `actions[]` decide what is offered.
- "Return with a note" on the outcome review does not exist (D-28). The review board offers one button, "Confirm outcome". Returns happen on the retrospective and on the report review.

## Context
Verified against `e2f44656` (F-85, PR #101; present in the repository, `git cat-file -t e2f44656` is `commit`). The checkout at `/Users/Hunchoo/psl-factory` is not yet on that commit; the builder branches from it.
- Page: `frontend/src/features/work-item/live/LiveWorkItemView.tsx` renders `item.panels[]` through `PanelView`: `adapterFor(panel.key)` reads the panel and draws `Section[]` (`workspace/labels.ts` kinds `facts`, `text`, `recipients`, ...). Adapters register by a side-effect import at the top of that file (`import '@/features/workspace/weeklyReportAdapter'`).
- Adapter: `frontend/src/features/workspace/adapter.ts` (`LineAdapter`, `LineContext`, `makeCommand`, `readPanel`, `registerLineAdapter`). Reference: `workspace/weeklyReportAdapter.ts` (`NOT_RECORDED = 'Not recorded'`, nulls stay unknown). `makeCommand` puts `action` and the tokens in the body and, with no `keyField`, no idempotency key (the emergency command has none).
- Evidence picker: `workspace/EvidencePicker.tsx`, `workspace/evidence.ts` (`uploadCaseFile`). It returns an `upload_id`, which is not an evidence id. The emergency commands need an `evidence_id` (see Contract, Proof).
- Sending and the `Actions` seam: F-87 (lane C) adds `adapter.Actions` rendered by `PanelView` under the panel's sections, `useWorkCommand`, and `LineContext.state` (see `delivery/features/F-87/spec.md`, "Lanes"). F-87 is not on main yet. Prerequisite below.
- Panel key: `apps/core/factory_api/work.py:397` maps `pmo-emergency/v1` to the panel key `emergency`. The read is `apps/core/factory_api/emergency.py` (`detail`, `command`, follow-ups `followups`, `followup_command`). Stage values the server emits: `source`, `preauthorization`, `refused`, `implementation`, `retrospective`, `report`, `complete` (`apps/workflows/factory_emergency.py:139-163,446`).
- Live reads used (viewer: `python3 /Users/Hunchoo/psl-factory-main/delivery/connect/oa.py live GET /api/v1/work/{work_id}/emergency 3`):
  - `GET /work/{work_id}/emergency` 200: `expected_revision, case_revision, profile_id, change_version_id, incident_id, critical_production|null, p1|null, stage, finding, actions[] (preauthorization_decision|authorize|capture_outcome|record_review|retrospective_decision|reconcile_retrospective), options[{role, authority_role, verdicts[]}], decisions[{id, role, authority_role, verdict}], authorization_id|null, recorded_authorizations[ids], outcome_id|null, recorded_outcomes[ids], outcome_impact{customers_affected: number|null, side_effects: string|null}|null, authorization_history[{id, by, at}], outcome_history[{id, by, at}], document_version_id|null, review_verdicts[], receipt_ids[], evidence[{id, version, kind}]`.
- Not on this read: the note text of an outcome or decision, `implemented_at`, a refuser's name, time or reason, the recipient list of the report, the reason a document was returned. These are not drawn.

### Prerequisite
F-87 must be on main (it supplies `Actions`, `useWorkCommand`, `LineContext.state`). If it is not, the builder stops and reports "blocked on F-87"; the builder does not edit lane C's frame to add a private seam.

## Contract

### Read: `GET /api/v1/work/{id}/emergency` (through the adapter, key `emergency`)
Registered as `emergencyAdapter` (`key: 'emergency'`, `read: readPanel`). The page reads it when the item loads and again after every successful write and every item poll that changes `updated_at` (existing `PanelView` behaviour).

Header facts (a `facts` section):
| Shown | Source |
|---|---|
| Stage tag | `stage` words: `preauthorization` "Waiting for preauthorisation", `refused` "Preauthorisation refused", `implementation` "Ready to implement", `retrospective` "Retrospective", `report` "Report", `complete` "Report received", `source` "Not ready". An unknown value shows the raw text. |
| What is happening / next | `finding` when non-empty (server text, shown as is) |
| Critical production, P1 | `critical_production`, `p1`: "Yes" / "No"; `null` shows "Not classified" (never "No") |
| Four-step track "1 Preauthorise, 2 Implement, 3 Retrospective, 4 Report" | `preauthorization`=1, `implementation`=2, `retrospective`=3, `report` and `complete`=4; `refused` marks step 1 as refused; `source` or an unknown stage draws no track. The track is read only. |

Boards (the sections drawn follow the read, not the viewer's guess):
1. **Refused** (any `decisions[]` row with `verdict:"reject"`, or `stage:"refused"`). A text section: "{role} refused the preauthorisation." with the role as served (`role`, with `authority_role` in brackets when different). No name, time or reason is drawn (not on the read, Conflicts). Next-step line from `finding`. Steps 2 to 4 are not drawn as reachable. No other write is offered. "Raise a new emergency change" links to the existing Start work drawer for the emergency line (`frontend/src/features/start-work`, label `emergency_change`); if the drawer has no emergency entry for this person, the link is omitted. No intake call is made here.
2. **Authorisation and implement** (stage `preauthorization` or `implementation`). `decisions[]` rows as words: "Approved", "Returned", "Refused" per `verdict`, each with its `role`. "Authorised by {by} · {at}" from the newest `authorization_history[]` row (the list is newest first; take the row with the highest `id`) when it is non-empty; empty shows "Not authorised yet". Button "Authorise the change" when `actions` has `authorize`. Form "Record what happened" when `actions` has `capture_outcome` (below).
3. **Record** (an outcome exists: `outcome_id` not null). "Recorded by {by} · {at}" from the newest `outcome_history[]` row. Impact block (below). The board's "What was done" text and proof file are not on the read and are not drawn after saving.
4. **Review** (stage `retrospective` and `actions` has `record_review`). The outcome block (recorded by, time, impact) plus the reviewer form: note, proof, one button "Confirm outcome". The line "This isn't the retrospective" (from the board) is kept as static helper text.
5. **Retrospective** (`actions` has `retrospective_decision`). Decision form (below) plus the follow-up changes list.
6. **Report** (stage `report` or `complete`). "Report" section: `document_version_id` null shows "The report isn't drafted yet."; non-null shows "Report drafted (version {id})" with the verdicts as words from `review_verdicts[]` ("Approved", "Returned", "Refused"; empty shows "Not reviewed yet"). `receipt_ids` non-empty shows "{n} delivery {receipt|receipts} recorded"; empty shows "No receipt yet" and never a tick. "The emergency is closed" is drawn only when `stage === 'complete'`. A review form appears per the report-review rule below.

Impact block (`outcome_impact`, when not null):
- "Customers affected": `customers_affected` as an integer (0 shows "0"); `null` shows "Unknown".
- "Side effects": `side_effects` text; `null` shows "Unknown"; an empty string shows "Not recorded". The board's "BANK TO CONFIRM" and "NONE FOUND" words are not drawn (Conflicts).
- `outcome_impact === null` hides the whole block.

Follow-ups list (retrospective and report boards, when `outcome_id` is not null): `GET /api/v1/projects/{case_id}/emergency-outcomes/{outcome_id}/followups?page=` `{revision, outcome_id, can_manage, records[{id, version_id, supersedes_id, closure_id, note}], evidence[], next_page}`. `case_id` is the loaded item's `case_id`. Each row: "Follow-up change {version_id}", its `note`, and "Completed" when `closure_id` is not null, else "Open". `next_page` not null shows "Show more". Empty shows "No follow-up work recorded." A 403 or 404 on this read hides the list and shows "You can't see the follow-up list." The rest of the board still draws.

### Writes: `POST /api/v1/work/{id}/emergency` (201 `{work_id, state, revision, record_id}`)
All bodies carry `action`, `expected_revision`, `case_revision`, `profile_id` from the latest read (`makeCommand` tokens `expected_revision`, `case_revision`, plus `profile_id` in the body inputs). A control is drawn only when its action is in `actions[]`; none is drawn from a role guess. The emergency command has no idempotency key; the button is disabled while a request runs and a repeat press is not sent. Tokens are never defaulted to 0.
| Control | Body (`action`) | Rules |
|---|---|---|
| Authorise the change | `authorize` `{}` | Draws only when `actions` has `authorize`. Hard-to-undo: ask "Authorise this emergency change?" with Cancel first. |
| Record outcome | `capture_outcome` `{evidence_id, note, implemented_at, customers_affected?, side_effects?}` | `implemented_at` is required (a date-time input, not in the future, sent as ISO 8601 with offset). `note` required. `evidence_id` chosen from `evidence[]` of kind `change_implementation`. `customers_affected` blank sends `null`; otherwise an integer 0 to 2147483647, else field error. `side_effects` blank sends `null`; never `""` or `"none"`. |
| Confirm outcome | `record_review` `{evidence_id, note}` | Proof kind `post_implementation_review`. One button. No verdict, no return. |
| Record decision | `retrospective_decision` `{role, verdict, evidence_id, note}` | `role` one of `Product`, `Engineering Lead` (the schema's only values; the person picks, the server checks authority). `verdict`: "Accept as handled" sends `approve`; "Needs follow-up work" sends `return`. Proof kind `emergency_decision`. `reject` is not offered. |
| Reconcile the result | `reconcile_retrospective` `{}` | Draws only when `actions` has it. Words: "Check the result". |
| Report review | `POST /work/{id}/reviews` `{kind:"document", expected_revision, case_revision, version_id: document_version_id, verdict, note}` (200 `{work_id, state, revision, review_id}`) | See below. Verdict buttons "Approve report", "Return report", "Refuse report"; `note` required for return and refuse. |

Report-review rule: the read carries no "can review" flag. The form is drawn when `stage === 'report'`, `document_version_id` is not null and the viewer's work item `tasks[]` or the server allows it; the builder draws it when `document_version_id` is not null and `stage === 'report'`, and a 403 from the server replaces it with "You can't review this report." (Assumption 3). The server enforces independence from the drafter.

Proof (`evidence_id`): the person chooses from `evidence[]`, listed as "{kind words} · version {version}" for the kinds the action takes (table above). No upload is made on this line: the emergency API has no route that turns a file upload into an emergency evidence record (Conflicts, backend question below). When no evidence of the right kind exists the control is disabled with "No proof is available yet." and the reason is shown, never hidden. The F-85 `EvidencePicker` is not used here.

Errors, all writes:
- 401 signed-out state (existing); 403 `csrf_failed` refresh session then "Try again" (nothing was sent); 403 other: "You can't do this." plus the server message; 404 "This record is unavailable."
- 409 (stale revision): re-read the item and panel, keep the person's typed text, say "This changed while you were working. Check it and press again." No automatic resend.
- 422: the first `fields[].message` beside its field; unknown field shows the message under the form.
- 429, 503, network: "Try again shortly." / "We couldn't reach the server." Nothing is shown as saved. After a failure with no response (network or 5xx), the form re-reads the panel before offering a retry, so a record that landed is not sent twice.
- Success (201/200): re-read the item and the panel; the new board is drawn from the new read. "Saved" is not claimed until the re-read shows it (e.g. a non-empty `outcome_history`, a decision row, or a changed stage).
- Permission and tenant: every call is made as the signed-in person with the item's `case_id`; no path or id is typed by the person.

### Follow-up change: `POST /projects/{case_id}/emergency-outcomes/{outcome_id}/followups` (201 `{id, revision}`)
Drawn on the retrospective board only when the follow-ups read says `can_manage: true`, after "Needs follow-up work" was recorded or while `actions` has `retrospective_decision`. Body `{action:"create", revision (from the followups read), reference, category: "Normal"|"Standard", module, description, note, evidence_id}`. Evidence from the followups read's `evidence[]` (not the emergency read's). Fields `reference` and `module` max 160 characters; `description` and `note` max 4000. `link_revision` and `complete` are not built. 409 re-reads the list. After 201 the list is re-read.

### Screen states (each board)
- Loading: the existing panel loading (nothing drawn until read). Error: "We couldn't load this part of the page." with Try again (existing `PanelView`). 401/403/404 as the item page.
- Empty: `stage: "source"` with no `finding` draws only the stage tag.
- Success: the boards above. Disabled controls always show their reason.
- Mobile: the page is the existing responsive work item page; no mobile-only layout is added. The mobile boards `SCR-50-mobile-*` are checked in the fidelity review.

### Fixtures (mock serves these for numeric work ids; live ids use the real read)
- `4301` refused: `stage:"refused"`, `decisions:[{id:1, role:"CTO", authority_role:"CTO", verdict:"reject"}]`, `actions:[]`, `options:[]`.
- `4302` record: `stage:"implementation"`, `actions:["capture_outcome"]`, `authorization_history:[{id:7, by:"Segun Okoro", at:"2026-11-13T08:05:00+01:00"}]`, `evidence:[{id:51, version:1, kind:"change_implementation"}]`, `outcome_impact:null`.
- `4303` review: `stage:"retrospective"`, `actions:["record_review"]`, `outcome_id:9`, `outcome_history:[{id:9, by:"Tunde Bello", at:"2026-11-13T08:30:00+01:00"}]`, `outcome_impact:{customers_affected:null, side_effects:null}`, evidence kind `post_implementation_review`.
- `4304` retro: `actions:["retrospective_decision"]`, `outcome_impact:{customers_affected:0, side_effects:"None found"}`, a followups read with `can_manage:true`, `records:[]`.
- `4305` report: `stage:"report"`, `document_version_id:77`, `review_verdicts:[]`, `receipt_ids:[]`. `4306` complete: `stage:"complete"`, `review_verdicts:["approve"]`, `receipt_ids:[31,32]`.
- `4307` pending-authorisation: `actions:["authorize"]`. `4308`: followups read 403. `4309`: every write answers 409 once.

## Lanes
- Frontend lane (owner, all of this feature): new `frontend/src/features/emergency/**` (`emergencyAdapter.ts`, `emergencyModel.ts` words and stage mapping, `EmergencyActions.tsx` the `Actions` component, `useEmergencyFollowups.ts`, `emergency.css`), `frontend/mock/emergency-live.mjs` plus the route entries it needs in the mock server, unit tests `frontend/src/features/emergency/*.test.ts(x)`, `frontend/e2e/emergency.spec.ts`, and live types for the emergency read in `frontend/src/api/types.ts` (aliases of the schema, additive).
- Backend lane: none. Backend question (not blocking): "Which route turns a checked PDF into an emergency evidence record (kinds `emergency_decision`, `change_implementation`, `post_implementation_review`) so a person can attach proof?" Add it to `delivery/connect/backend-questions.md` as lane C's integration owner directs.
- Integration owner: lane C coordinator. Shared files and who owns them: `frontend/src/features/work-item/live/LiveWorkItemView.tsx` (lane C; this feature adds one `import '@/features/emergency/emergencyAdapter'` line and nothing else); `workspace/adapter.ts`, `workspace/useWorkCommand.ts` (lane C, from F-87; used as is); `frontend/src/api/*` (shared; additive types only); `frontend/mock/server.mjs` (shared; route entries only). No other lane C file changes.
- Protected paths in `delivery/config.json` stay unchanged.

## Acceptance criteria
1. Opening `/work/4301` in the mock shows "Preauthorisation refused", "CTO refused the preauthorisation." and the "Raise a new emergency change" link or its absence per the Start work drawer, and no authorise, record, review or retrospective control — verify: open the page; unit test on the model with a `reject` decision.
2. The refused board draws no refuser name, time or reason, and the track marks step 1 refused — verify: unit test asserts the section text has no name; page view.
3. `/work/4302` shows "Authorised by Segun Okoro · 13 Nov 08:05" from `authorization_history`, and the "Record what happened" form with proof options listing only `change_implementation` evidence — verify: page; unit test that kind `post_implementation_review` evidence is not offered.
4. Record outcome without `implemented_at`, or with a future date, or with a negative or fractional "Customers affected", is refused in the form and sends nothing — verify: unit test and e2e assert no POST; field messages shown.
5. Record outcome with both impact fields blank sends `customers_affected: null` and `side_effects: null`, not `0` or `""` — verify: unit test inspects the request body; mock `POST /work/4302/emergency` receives them.
6. `/work/4303` shows "Customers affected: Unknown" and "Side effects: Unknown"; `/work/4304` shows "0" and "None found" — verify: page; unit test for `customers_affected: 0` renders "0" not "Unknown".
7. The review board has exactly one decision button, "Confirm outcome", and no "Return with a note" or return control — verify: page; test asserts the label list.
8. "Confirm outcome" sends `action:"record_review"` with `evidence_id` of kind `post_implementation_review`, a non-empty `note`, and the tokens from the read; with no matching evidence the button is disabled and says "No proof is available yet." — verify: unit test on the body; page.
9. "Accept as handled" sends `retrospective_decision` verdict `approve`; "Needs follow-up work" sends `return`; the role field offers only `Product` and `Engineering Lead`; `reject` is never sent from this form — verify: unit tests on the body for both.
10. The follow-up form appears only when the followups read has `can_manage: true`; it sends `action:"create"` with `category` `Normal` or `Standard` and the followups read's `revision`; on `can_manage:false` or a 403 it is absent — verify: page against `4304` and `4308`; unit test on the body.
11. `/work/4305` shows the report as drafted with "Not reviewed yet" and "No receipt yet"; `/work/4306` shows "Approved", "2 delivery receipts recorded" and "The emergency is closed"; "closed" does not appear on `4305` — verify: page.
12. The report review sends `POST /work/{id}/reviews` with `kind:"document"`, `version_id` equal to `document_version_id`, the tokens and a verdict; "Return report" and "Refuse report" without a note send nothing — verify: unit test on the body; e2e.
13. A control appears only for an action in `actions[]`: a read with `actions:[]` draws no write control; `4307` draws "Authorise the change" and it asks for confirmation before sending — verify: unit test over the six actions; page.
14. A 409 on any write keeps the typed text, re-reads, shows "This changed while you were working. Check it and press again." and does not resend — verify: mock `4309`; unit test counts requests.
15. A 403 `csrf_failed` is not shown as "no access"; a 403 on the report review shows "You can't review this report." — verify: unit test with mocked client.
16. While a write is in flight its button is disabled and a second press sends nothing; after a network failure the panel is re-read before Try again is offered — verify: unit test with a deferred promise; request count.
17. A write is not reported as saved until the re-read shows it: after 201 with an unchanged read the page says it could not confirm the change and offers a re-read — verify: unit test with a mock that answers 201 but an unchanged GET.
18. `critical_production: null` shows "Not classified", never "No" — verify: unit test.
19. A work id the account cannot see answers 404 and the page shows exactly "This record is unavailable." — verify: open a live id the account cannot see and a mock 404; compare text.
20. An unknown `stage` value shows its raw text and no track; unknown `actions[]` entries draw nothing — verify: unit test.
21. The adapter is registered with `registerLineAdapter` under `emergency`, `commands()` descriptors use `POST /api/v1/work/{id}/emergency`, carry `profile_id`, and never put `0` for a null token — verify: `frontend/src/features/emergency/emergencyAdapter.test.ts`.
22. Against live Django (8020, account with an emergency work item) the page matches `oa.py live GET /api/v1/work/{id}/emergency` for stage, decisions, history names and times, and impact — verify: compare page with the viewer output.
23. No new "not available" placeholders are drawn for data the read does not carry (decision names, notes, `implemented_at`, recipients) — verify: grep the sections for those words; page.
24. The fidelity review compares the desktop and mobile boards `SCR-50-*-refused/record/review/retro/report` with the page and every difference is on the Conflicts list below or is fixed — verify: design fidelity tool output for the five states.

## Out of scope
- The CTO preauthorisation decision control (`preauthorization_decision`) stays in FE-DECIDE-VARIANTS; this line only shows its recorded rows.
- The emergency start flow and authority recovery (`/projects/{case}/emergency-intake`, `/authority-recoveries`); only a link to the existing Start work drawer.
- A file upload for emergency proof, and any use of the F-85 evidence picker or `fileToEvidence` on this line.
- A "return" on the outcome review, or any return control invented on `record_review`.
- All of SCR-51 Escalation; follow-up `link_revision` and `complete`; the Tola agent card, step list and "Ask Tola"; sending, resending or verifying the report (the server delivers; the page shows receipts only).
- Naming approvers, guessing a role gate, counting attempts, or computing an "authorisation preceded implementation" fact in the UI.
- Edits to lane C's frame, the generic step engine, or any protected path.

## Assumptions
1. Panel key is `emergency` (`apps/core/factory_api/work.py:397`), not a key I invented; the builder confirms it with `oa.py live GET /work/{id}` on a live emergency item.
2. The boards follow the read's `stage` and `actions[]`: the review and retrospective boards both sit at stage `retrospective`, and `actions[]` decides which forms show (server removes review actions until an outcome exists, `emergency.py:136`).
3. The report-review form shows when `stage==='report'` and `document_version_id` is set, because the read has no "can review" flag; the server's 403 is the gate. If the backend adds a flag, switch to it.
4. The newest history row (highest `id`) is "the authoriser" and "the recorder"; the read orders newest first.
5. Proof is chosen from `evidence[]` by the kinds the server checks (`emergency.py:23-30`); this is the only way to get an `evidence_id` on this line.
6. Retrospective roles `Product` and `Engineering Lead` are offered as a plain choice because the read does not say which applies to the viewer; the server refuses the wrong one.
7. "Needs follow-up work" maps to `return` per D-28 ("use the retrospective return action").
8. One-time confirmation before `authorize` because it records authority and cannot be undone.
9. The mock needs no new env; mock work ids 4301 to 4309 extend F-85's 4101 to 4106.

## Conflicts with the boards
1. Refused board: "Segun Okoro (CTO) refused on 13 Nov 08:20: '…reason…'". The read gives role and verdict only (`decisions[]`), though D-30 says decisions carry a named actor and time; the live schema does not. Spec draws "{role} refused the preauthorisation." without name, time or quote. Recommendation: keep it; ask the backend to add actor, time and note to `decisions[]`.
2. Record board: "What was done" text, "Proof: emg0007-deploy-log.pdf · Uploaded · 44 KB" are inputs only; after saving they are not on the read, so they are not drawn. The upload field becomes a pick from existing evidence. Recommendation: keep; backend question for an upload route.
3. Review board: "Return with a note" is removed (D-28). "Note (needed to return or refuse)" becomes "Note" (required for the one action). Recommendation: keep.
4. Review board: "UNKNOWN · BANK TO CONFIRM" becomes "Unknown"; "NONE FOUND" is never drawn for null (null means no confirmed value, D-29). Recommendation: keep.
5. Retro board: "Engineering Lead (recorded by PM)" and "the Product and Engineering Leads have no login" assume a PM records for them; the API takes `role` and the signed-in person. The role is a picker, with no "recorded by PM" line. Recommendation: keep.
6. Retro board: the follow-up field is free text on the decision; the API makes a follow-up an ordinary change (`reference`, `category`, `module`, `description`, `note`, `evidence_id`) through a second call. The board's one text box maps to the decision `note`; the structured follow-up form is added when `can_manage`. Recommendation: keep, add the form.
7. Report board: the Tola card ("Read the incident…", "Drafted the emergency report", TEST TEMPLATE, "Published to Harmattan Bank and leadership · 14 Nov 10:05", "Ask Tola") has no source on this read. Replaced by the report, review verdicts and receipts count. Recommendation: keep.
8. All boards: the station step list is drawn as the read-only four-step track from `stage`; "Tola · PMO agent · done" is not drawn.

## Questions for the design engineer
1. Refused board without the refuser's name, time and reason: draw only "CTO refused the preauthorisation." (recommended), or leave the refused board empty until the backend adds them?
2. Proof on the record, review and retrospective forms: a plain list of existing evidence ("Deploy log · version 1") (recommended), or hide the forms until an upload route exists?
3. Authorise confirmation: a small yes/no step before sending (recommended), or send on the first press?
4. Retrospective role: a two-choice radio "Engineering Lead / Product" shown on the form (recommended), or a dropdown?
5. Report review buttons: "Approve report / Return report / Refuse report" (recommended), or only Approve and Return?
6. Follow-up changes: show the list and the create form on the retrospective board only (recommended), or also on the report board?
