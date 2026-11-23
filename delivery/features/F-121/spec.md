# The escalation line workspace shows the live escalation and lets the PMO Lead decide, review and recover it

> Tasks: FE-EMERGENCY-ESCALATION (part 2, SCR-51 only). Architecture: v9 package (revision as pinned in the feature record at branch time); contract `contracts/psl-factory.openapi.json` 1.24.0. Design: approved 13 Nov canvas, version 1794581312-b166 (`design/review.json` approvals[0], approved_by basedhunch@gmail.com, "PSL client approver", 13 Nov 2026 15:33Z; SCR-51 is in its `screens` list; the 12 SCR-51 artboards are in `design/canvas/project/`); screens: SCR-51 (investigating, decide, not-escalated, draft, review, received).

## Summary
- On a live work item whose `panels[]` carries the escalation panel, the page draws the escalation from `GET /work/{id}/escalation`: what is asked for (direction and target), the decision history with its reason, the exact message preview and recipients, the delivery receipts and the next action. Nothing is drawn that the read does not carry.
- The PMO Lead (whoever `client_decisions[]` lists) decides: Escalate to the client = `approve`, Don't escalate = `reject` (declined), and a rework return = `return` (D-31). A note is required to return or refuse.
- "Send for review" sends the drafted message version for review. The reviewer then approves or returns it through `POST /work/{id}/reviews` (`kind:"document"`). Review and send stay two steps; the page never says "sent" until a receipt exists.
- Receipts show only from `receipts[]`. A job state or an approval is never drawn as delivered.
- An uncertain delivery can be checked (`check_original_delivery`) and a stuck job can be cancelled or retried with a reason (`recover_delivery`), through F-87's command sender.

## Context
Where this lives today (main checkout `/Users/Hunchoo/psl-factory/frontend`, at `e2f44656`, F-85 merged):
- Live page: `src/features/work-item/live/LiveWorkItemView.tsx`. Its `PanelView` reads each `item.panels[]` entry through `adapterFor(panel.key)` and draws `Section[]` with `SectionView`; it passes `LineContext {workId, caseId, revision, caseRevision}` and re-reads when `item.updated_at` changes. `Overview` already draws title, state tag, blocker, next step, activity, decisions-waiting links and the output link.
- Adapter: `src/features/workspace/adapter.ts` (`LineAdapter`, `makeCommand`, `readPanel`, `registerLineAdapter`, `adapterFor`, `CommandDescriptor`). The reference is `src/features/workspace/weeklyReportAdapter.ts` (read only; registered by a side-effect import in `LiveWorkItemView.tsx`).
- Section kinds and words: `src/features/workspace/Sections.tsx`, `labels.ts` (`Section`, `Item`, `asOfLine`, `NOT_RECORDED` in the weekly adapter), `formatDayTime` from `@/components`.
- Types: `src/api/live-schema.d.ts` `escalations_detail` / `escalations_command`; `src/api/types.ts` holds the live aliases (add `LiveEscalation`).
- Not on main yet: F-87 (`delivery/features/F-87/spec.md`, IMPLEMENTING) adds `src/features/workspace/useWorkCommand.ts` (press lock, uncertain lock, reload, error words). F-121 sends every write through it. Mock: `frontend/mock/work-live.mjs`.
- Old v7 escalation workspace (`W-36xx` fixtures, `Workspace.tsx`, `InlineDecide.tsx`) stays as is for `W-xxxx` ids and is not touched.
- Live read `GET /api/v1/work/{work_id}/escalation` (checked in `contracts/psl-factory.openapi.json` 1.24.0): `{expected_revision, case_revision, id, direction (string), target (string), stage (string, no enum), document_version_id|null, can_request_communication_review, review_verdicts[approve|return|reject], client_decisions[{role: "PMO Lead"|"Head of PMO", verdicts[]}], history[≤30 {id, request_id, role, verdict, created_at, note|null}], communication|null {title, version, sections[{heading, text}], recipients[]|null}, receipts[≤30 {id, publication_id, recorded_at}], jobs[≤30 {id, state, operations[cancel|retry]}], next_action}`. All fields required, none extra.
- Backend answers: D-31 (reject = declined, return = rework, the eligible reviewer sees the reason and exact time), D-32 (the escalation read gives an authorised exact preview and permitted recipients; sending and receipts are separate operations). A-16: use each panel's `key`, `url` and `contract_path`.

## Contract

### Panel and adapter
- Adapter `escalationAdapter` in `src/features/workspace/escalationAdapter.ts`, `key: 'escalation'` (the panel key; see Assumptions), reading `ref.url` (`GET /api/v1/work/{id}/escalation`) with `readPanel`. It is registered by a side-effect import beside the weekly one.
- Shared piece with F-69 (SCR-50, specced in parallel): `LineAdapter` gets one optional additive member so a line can draw controls, not only sections:
  ```ts
  // additive in adapter.ts; whichever of F-69 and F-121 merges second rebases onto the first
  export type PanelRenderProps<R> = { readback: R; ctx: LineContext; reload: () => void };
  // on LineAdapter<R>:  Panel?: (props: PanelRenderProps<R>) => ReactNode;   // drawn in place of `sections` when present
  ```
  `PanelView` in `LiveWorkItemView.tsx` draws `adapter.Panel` when present (passing `reload` = re-read the panel and the item) and falls back to `sections` otherwise. `weeklyReportAdapter` is unchanged. Agree the exact names with F-69's spec; the first to merge owns them.
- The adapter still exposes `sections(readback, ctx)` (pure, tested) and `commands(readback, ctx)` (pure, tested); `Panel` composes them.

### What the panel draws (board to field)
No station track, agent card, "Tola found" facts, "raised by", issue reference or investigation steps are drawn: the read has no source for them (readiness Scope). The state tag, "Next step", blocker and current activity come from the existing page header and `Overview`.

| Board | Drawn when (from the read) | Content |
|---|---|---|
| Investigating | `communication` is null, `history` is empty, `client_decisions` is empty, no receipts | "Asked for": direction and target ("Escalate to the client" for `escalate`/`Client`, otherwise `Escalate to {target}` or `De-escalate to {target}`; unknown values shown raw); `next_action` as the Next line. Working state is shown by the page's activity line, not invented steps |
| Decide | `client_decisions` has at least one entry | "Decide · {role}" card per entry. Escalating means a formal message to the client's sponsor, reviewed before it is sent (board sentence, shown for direction `escalate` and target `Client` only). Note field labelled "(needed to return or refuse)". Buttons only for the verdicts listed for that role: `approve` "Escalate to the client", `reject` "Don't escalate", `return` "Return for rework" |
| Not escalated | newest `history` row (by `created_at`) has `verdict:"reject"` and no `communication` | "{role} decided not to escalate on {date}" plus the row's `note` in quotes when not null (null note: no quote, no placeholder); `next_action` as Next |
| Rework | newest `history` row has `verdict:"return"` | "{role} returned this for rework on {date}" plus the note when present; `next_action` |
| Draft | `communication` not null and `can_request_communication_review` true | "Message v{communication.version}": each `sections[]` as a heading and its text exactly as given; recipients as given ("Recipients: …"); null `recipients` reads "Recipients not available to you." Button "Send for review" |
| Review | `communication` not null and `review_verdicts` has `approve` or `return` | The same message and recipients under "Message v{n} · to {recipients}", a note field "(needed to return or refuse)", buttons "Approve and send" (`approve`) and "Return with a note" (`return`). A `reject` in `review_verdicts` draws no button (not on the board; Question 3) |
| Received | `receipts` not empty | One row per receipt: "Delivery recorded {recorded_at}" with the receipt id secondary. The word "verified" appears only when the page's state tag is Verified. The board sentence "This records that the message was received; it doesn't resolve the issue" is shown beside it. No "both recipients" claim (no per-recipient receipt is served) |

Always, when present: the message preview stays visible after review and after receipt (read-only); `history` is listed newest first with role, verdict word (Escalate / Don't escalate / Return for rework), time and note, as the read serves it; `next_action` under "Next".
- Recovery (not drawn on SCR-51; reuses the look of the SCR-02 awaiting-reconciliation board): when `jobs[]` is not empty, a "Delivery" block lists each job (`state` raw, plain words for known ones are not invented) with one button per entry in its `operations` ("Retry", "Cancel") and a required reason field. A "Check original delivery" button is drawn when the page state (`item.state`) is `awaiting_reconciliation` or `effect_uncertain`. Cancel asks yes/no first.

### Commands (all `POST /api/v1/work/{id}/escalation` unless stated; none has an idempotency key field, so `idempotency.field` is null)
Tokens come from the escalation read: `expected_revision`, `case_revision`. A `null` token is not possible on this read (both required integers); if the read is missing either the controls stay disabled with "This can't be changed right now."
| Id | Body | Success |
|---|---|---|
| `escalation.decide_client_action` | `{action:"decide_client_action", expected_revision, case_revision, request_id: read.id, role: <the client_decisions entry's role>, verdict, note, delegated:false}`; `note` trimmed, required (non-empty) for `return` and `reject`, `""` allowed for `approve`; the verdict must be one listed for that role | 200 `{work_id, state, revision, record_id}` |
| `escalation.request_communication_review` | `{action:"request_communication_review", expected_revision, case_revision, version_id: read.document_version_id}`; held when `document_version_id` is null | 200 |
| `escalation.check_original_delivery` | `{action:"check_original_delivery", expected_revision, case_revision}` | 200 |
| `escalation.recover_delivery` | `{action:"recover_delivery", expected_revision, case_revision, job_id, operation:"cancel"\|"retry", reason}`; reason trimmed, required, only an operation listed on that job | 200 |
| `review.document` (`POST /api/v1/work/{id}/reviews`) | `{kind:"document", expected_revision, case_revision, version_id: read.document_version_id, verdict:"approve"\|"return", note}`; `note` required for `return`, `""` allowed for `approve`; max 4000 | 200 `{work_id, state, revision, review_id}` |
The role is taken from the listed `client_decisions` entry only; the UI never names an approver or chooses a role for the person. `delegated` is always `false` (no board draws a delegation; Assumptions).

### Sending, locking and errors
- Every write goes through F-87's `useWorkCommand` (one write at a time, press lock, uncertain lock after a network or 5xx failure, re-read after success). After a success the page re-reads the work item and this panel and shows what comes back; "Done." plus the state tag, never "Sent". On 409 the panel re-reads and says "This changed while you were working. Showing the latest version." and does not repeat the press. 403 shows "You can't do this." with the server message as given and the controls re-read; 422 shows the server `message` and first `fields[].message`; 429/503 "Try again shortly."; 403 `csrf_failed` refreshes the session and says "Press the button again".
- The note and reason fields keep what the person typed after any failed or stale write.
- Uncertain failure on `decide_client_action`, `request_communication_review` or `review.document`: re-read, lock that command until `revision` differs from the one sent or the page is reloaded, and say "We couldn't confirm that this happened. Check the page before trying again." `check_original_delivery` is not locked (it is a lookup).
- Permission and tenant: the read and writes are made as the signed-in person; 404 for missing and not-yours is the same "This record is unavailable." as the page. Which verdicts and recoveries are offered is only what the read lists; the UI does no role check of its own, and a server 403 on a press is shown, not hidden.

### Screen states (panel)
- Loading: nothing drawn (as `PanelView` today).
- Error: the existing warning callout "We couldn't load this part of the page." with Try again; a 401/403/404 on the panel read replaces the page via the existing error mapping.
- Empty: a read with no history, no message, no receipts and no decisions draws only "Asked for" and the Next line; no empty headings.
- Success: the table above. Phone (390): single column, buttons full width, same order; the note field sits above its buttons.

### Fixtures (mock serves these for numeric work ids; builder creates them in `frontend/mock/`)
`4121` investigating; `4122` decide (`client_decisions:[{role:"PMO Lead",verdicts:["approve","reject","return"]}]`); `4123` declined (`history` newest `reject`, note "Their new lead starts Monday. Ask them directly first."); `4124` rework (newest `return`); `4125` drafted (`communication` set, `can_request_communication_review:true`); `4126` review (`review_verdicts:["approve","return"]`, `document_version_id` set); `4127` received (`receipts:[{id,publication_id,recorded_at}]`, item state verified); `4128` uncertain (`jobs:[{id, state:"unknown", operations:["retry","cancel"]}]`, item state `effect_uncertain`); `4129` no decision rights (`client_decisions:[]`); `4130` null `communication.recipients`; `4131` 409 `stale_version` on every write; `4132` 403 on every write.

## Lanes
- Frontend lane (owner, all of this feature): `frontend/src/features/workspace/escalationAdapter.ts`, `workspace/EscalationPanel.tsx` (the `Panel`), `workspace/adapter.ts` (additive `Panel` member only), `frontend/src/features/work-item/live/LiveWorkItemView.tsx` (`PanelView` uses `Panel` and the side-effect import; no other change), `frontend/src/api/types.ts` (`LiveEscalation` alias), `frontend/mock/work-live.mjs` and mock server routes for `GET/POST /work/{id}/escalation` and `POST /work/{id}/reviews`, tests under `frontend/src/**` and `frontend/e2e/work-item-escalation.spec.ts`.
- Backend lane: none. No backend, contract or migration change.
- Integration owner: lane C coordinator. Shared files: `workspace/adapter.ts`, `LiveWorkItemView.tsx` and `mock/work-live.mjs` are also touched by F-69 (SCR-50) and F-87; each change is additive and small, merged in the order F-87, then F-69 and F-121 (rebase via `git merge origin/main`). `useWorkCommand` is F-87's; F-121 does not copy or fork it. If F-87 is not on main when the build starts, the builder stops and says so.
- Protected paths in `delivery/config.json` (`delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`) stay unchanged.

## Acceptance criteria
1. `/work/4122` (mock) shows "Decide · PMO Lead", a note field and exactly the buttons "Escalate to the client", "Don't escalate" and "Return for rework"; `/work/4129` (`client_decisions:[]`) shows none of them — verify: `frontend/e2e/work-item-escalation.spec.ts` asserts the buttons by name on both.
2. Pressing "Escalate to the client" sends one `POST /api/v1/work/4122/escalation` with `{action:"decide_client_action", expected_revision, case_revision, request_id (= read id), role:"PMO Lead", verdict:"approve", note:"", delegated:false}`; "Don't escalate" sends `verdict:"reject"` and "Return for rework" sends `verdict:"return"` — verify: unit test on the descriptor bodies and e2e request assertion; no `approve` is ever sent by "Don't escalate".
3. "Don't escalate" and "Return for rework" with an empty or blank note send nothing and show "Add a note to return or refuse" next to the field — verify: e2e asserts zero POSTs; unit test on the validator.
4. A verdict not listed for the role (for example a read with only `["approve"]`) draws no button for the others — verify: unit test on `sections`/`Panel` with that read.
5. `/work/4123` shows "PMO Lead decided not to escalate on {date}" and the note in quotes, and no "Escalate"/"Don't escalate" buttons; with `note:null` no quote or placeholder is drawn; `/work/4124` reads "returned this for rework" and never "not to escalate" — verify: e2e on both and unit test on null note.
6. The verdict words come only from the verdict: `reject` is never shown as "returned" and `return` is never shown as "declined" — verify: unit test over all three verdicts in `history`.
7. `/work/4125` shows "Message v1" with each section's heading and text exactly as in the read, the recipients as given, and a "Send for review" button; pressing it sends `{action:"request_communication_review", expected_revision, case_revision, version_id}` with `version_id` equal to `document_version_id`; with `document_version_id:null` the button is disabled and nothing is sent — verify: e2e and unit test.
8. `/work/4130` (`recipients:null`) shows "Recipients not available to you." and no invented recipient — verify: e2e.
9. `/work/4126` shows the same message under "Approve and send" and "Return with a note"; "Approve and send" posts `/work/4126/reviews` `{kind:"document", expected_revision, case_revision, version_id, verdict:"approve", note:""}`; "Return with a note" with a blank note sends nothing, with a note posts `verdict:"return"` — verify: e2e request assertions; the page does not say "sent" after the approve, only the re-read state and receipts.
10. A `review_verdicts` of `["reject"]` draws no review button and the message stays readable — verify: unit test.
11. `/work/4127` shows "Delivery recorded {time}" once per `receipts[]` row and the board sentence that it doesn't resolve the issue; an item with `receipts:[]` shows no "Delivery recorded", "Delivered" or "verified" text anywhere in the panel, whatever `jobs[]` or `state` say — verify: e2e on 4127 and 4126; unit test with jobs present and no receipts.
12. "Verified" appears in the panel only when the work item's state is `verified`; it is not derived from `receipts[]` alone — verify: unit test with receipts and state `processing`.
13. `/work/4128` shows the job with "Retry" and "Cancel" and a required reason; "Check original delivery" is drawn because the state is `effect_uncertain`; Retry with a blank reason sends nothing; Cancel asks yes/no first; each posts `{action:"recover_delivery", expected_revision, case_revision, job_id, operation, reason}` — verify: e2e request assertions. A job whose `operations` is `[]` shows no button.
14. "Check original delivery" posts `{action:"check_original_delivery", expected_revision, case_revision}`, is not locked after an uncertain failure, and is not drawn when the state is not `awaiting_reconciliation` or `effect_uncertain` — verify: e2e and unit tests.
15. After any 200 the page re-reads the item and this panel and shows the re-read state; a double click makes one request — verify: e2e counts requests; `useWorkCommand` is imported, not copied (`grep -n "liveApi.POST" frontend/src/features/work-item frontend/src/features/workspace` shows no new POST outside `useWorkCommand`).
16. `/work/4131` (409 on writes) re-reads, shows "This changed while you were working. Showing the latest version." with the server message, keeps the typed note, and does not resend; `/work/4132` (403) shows "You can't do this." with the server message and the other controls follow the re-read — verify: e2e on both.
17. A network failure or 5xx on a decision or review press shows "We couldn't confirm that this happened. Check the page before trying again.", locks that button until the re-read shows a new revision, and sends nothing by itself — verify: unit test with fake timers (no timer sends) and e2e.
18. A 404 on the panel read gives "This record is unavailable." (same as the page); a 500 shows "We couldn't load this part of the page." with Try again and the rest of the page loads — verify: mock scenarios and e2e.
19. A read with a `direction`, `target` or `stage` value the page has no words for shows it raw and does not break; "Asked for" reads "Escalate to the client" for `escalate`/`Client` and no PMO/CTO/de-escalate wording is shown when the read says otherwise (the read's values are shown) — verify: unit test.
20. Nothing is drawn for Tola's findings (days late, milestone, times asked), investigation steps, "raised by" or an issue reference, and no placeholder stands in for them — verify: e2e asserts those strings are absent on 4121 to 4127.
21. No approver, role or authority is named by the UI except the `role` strings and history roles the read serves; no client-side role check hides or shows a control apart from the read's lists — verify: grep `escalationAdapter.ts` and `EscalationPanel.tsx` for the literals "PMO Lead", "Head of PMO", "CEO", "CTO" (none outside tests and the verdict-to-role type) and review the diff.
22. A page load, a poll and navigation make no POST; the only POSTs come from presses — verify: e2e asserts zero POSTs on load of each fixture.
23. Against live Django (8020, Postgres 55433), for a real escalation work item the panel shows the same direction, target, history, message and receipts as `GET /api/v1/work/{id}/escalation`, and the panel is found under the key the live `panels[]` gives — verify: compare the page with `oa.py live GET /api/v1/work/{id}/escalation` output; if the key differs from `escalation`, register the live key and record it in the PR.
24. Unit tests cover: `sections` for each board row above, `commands` bodies, the note and reason validators, the verdict-to-word mapping and the "no receipt, no delivered" rule — verify: `npm test` lists them.
25. Viewport check at 1440 and 390: each of the six boards matches its SCR-51 desktop and mobile artboard for the parts drawn, and no part leaves an empty heading or gap — verify: screenshots at both widths reviewed against `design/screens.md` SCR-51 artboards.
26. `npm run lint`, `npm run typecheck` and `npm test` pass; `weeklyReportAdapter` tests still pass unchanged — verify: `delivery/checks.sh`.

## Out of scope
- Raising an escalation (register `classify` then `request`, then `POST /work`, proof ids): belongs with the Start work drawer.
- Tola's findings facts, investigation steps, the agent card, "raised by", the issue reference and title: no live source (readiness).
- Delegation of the decision (`delegated:true`), choosing a role other than the one the read lists, naming approvers, or any new authority.
- A separate "send" command: none exists on this read; sending follows approval on the server and is shown only through `receipts[]`.
- De-escalation and PMO/CTO targets beyond showing the read's own values; no new wording for them.
- The escalation register screens (`/projects/{case}/escalation-register`), `POST /work/{id}/actions`, `corrections`, history page changes, the Start work drawer.
- Backend, contract or migration changes; the v7 `W-36xx` escalation workspace.
- Recording a client's reply to the message (not in the boards or the read).

## Assumptions
- Panel key is `escalation` (the line key, and the pattern of `weekly-report`); the live key is not listed in the answers. Reason: A-16 says the server owns the list; criterion 23 confirms it live.
- `request_id` in `decide_client_action` is the read's `id`. Reason: `history[].request_id` names the request and `id` is the only request identifier on the read; the server rejects a wrong one.
- `delegated` is sent as `false`. Reason: no board or answer draws delegation, and sending `true` would claim authority nobody gave.
- Approve may send an empty note, return and reject require one. Reason: the boards label the note "(needed to return or refuse)".
- Escalate verdict `approve` on the decide board and `approve` on the review board are different commands (client action vs document review). Reason: D-31 and the two endpoints.
- "Check original delivery" is drawn when the item state is `awaiting_reconciliation` or `effect_uncertain`. Reason: the read carries no flag for it; the server still refuses when it is not allowed.
- The verdict words "Escalate", "Don't escalate" and "Return for rework" for history rows. Reason: D-31 maps approve, reject and return to these actions; the board words are the same.
- The panel does not use `stage`; boards are chosen from the other fields. Reason: `stage` is a free string with no list of values.

## Conflicts with the boards
1. Decide board draws two buttons; the read can also offer `return` (rework). Recommendation: draw a third, secondary "Return for rework" only when listed for the role (the board's own note label already mentions returning).
2. Not-escalated board names the person ("Kemi Adebayo decided…"); the read gives the role only. Recommendation: show the role ("PMO Lead decided…").
3. Investigating board draws "Raised by you", "From issue ISS-0241", the agent card with four steps, and the decide board draws "What Tola found" (15 days late, milestone 3, asked 3 times); none has a live source. Recommendation: omit all of them; the page's existing activity line and Next step stand in. No placeholder.
4. Not-escalated and received boards draw fixed sentences ("The issue stays open with its owner. You can raise the escalation again later.", "The issue stays open until the data arrives…") and a "Back to the issue" link. Recommendation: draw the server's `next_action` instead; keep only the received sentence "doesn't resolve the issue" (a statement of what a receipt means, not a business rule). No "Back to the issue" link (no issue URL on the read).
5. Received board says "Delivered to both recipients … verified". Recommendation: "Delivery recorded {time}" per receipt, "verified" only from the item's Verified state, no recipient count.
6. Review board's "Approve and send" and the line's rule that send is separate from review. Recommendation: keep the label as drawn (approval is what releases the message) but never claim it was sent until a receipt exists.
7. Added with no board: the Delivery block (job list, Retry, Cancel, reason, "Check original delivery") for uncertain sends, from readiness scope and the SCR-02 awaiting-reconciliation board. Recommendation: keep, and the design engineer draws it on SCR-51 later.
8. Status tags on the boards (INVESTIGATING, YOUR DECISION, NOT ESCALATED, MESSAGE DRAFTED, YOUR REVIEW, RECEIVED) are replaced by the page's existing state tag, because the read's `stage` is a free string. Recommendation: see Question 1.

## Questions for the design engineer
1. Board status tags: (recommended) keep the page's state tag only, and put a small panel heading that names what is waiting on this person ("Your decision", "Your review") only when a decision or review control is drawn; or derive the six tags from `stage` once the backend lists its values. Reason: `stage` has no enum.
2. Direction and target wording: (recommended) "Escalate to the client" exactly as the board for `escalate`/`Client`, and "Escalate to PMO", "Escalate to CTO", "De-escalate to {target}" for the rest; or show the raw values with a label. These three phrases are new copy; the client may want to confirm them.
3. A `reject` offered in `review_verdicts` (the board has Approve and Return only): (recommended) draw nothing for it; or add a third "Refuse" button with the same required note.
4. Delivery block placement: (recommended) below the message and receipts, collapsed to one line until a job exists; or in the right column on desktop beside Next.
5. History list: (recommended) draw it as a compact list under the message on every board, as the read serves it (up to 30); or only the newest decision, as the boards show.
6. "Return for rework" label: (recommended) that wording; or "Send back to the issue owner" (not recommended: it names a person the read does not).
