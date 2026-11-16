# The weekly client report after the review: returned to the PM, or received by the client with its delivery confirmations (contract mock only)

> Tasks: FE-LINE-WEEKLY, second part (R-WORKITEM, R-DECIDE; acceptance A-WORKSPACE frontend half, with A-WORKITEM, A-DECIDE and the F-17 and F-21 tests kept green). Architecture: package `architecture/packages/v7` (the `workspace` block, `sections[].kind: recipients`, `items[].receipt`, `items[].tag`, `workspace.next` and E-WORK-STEP are typed in `frontend/src/api/schema.d.ts:1693` to `:1900`; this feature changes no generated type); FE-LINE-WEEKLY at `architecture/packages/v7/delivery.md:2014`, no unresolved gates. Design: approved canvas version 1794581312-b166 (`design.py check --project .` run for this spec: status EXCEPTION, passes; D-89 phone "+ Start" frame change). Screens: SCR-25, 4 artboards: `SCR-25-{desktop,mobile}-{returned,received}` (files in `design/canvas/project/`). Decisions consumed: D-LINE-WORKSPACE (proposal), D-64, D-83, D-91 to D-96. Model: `delivery/features/F-21/spec.md` (shape and base), `F-17/spec.md` Contract.

## Conflicts with the boards

Each item is a place where the boards, the v7 contract and the frame disagree. "Recommend" is what this spec builds if no answer comes. Items 1 to 3 change what the page looks like and need an answer; the rest are exceptions to confirm. No requirement below adds, moves or removes a board element except as listed here.

1. **The coloured banner has no field.** Returned draws an amber callout ("Kemi Adebayo returned v1 on 12 Nov: ...") above "Your update". Received draws a green callout ("Lagoon Health received v2: ... both deliveries confirmed. Verified."). The contract has no banner field with a tone: `agent_note` is an info callout headed by an agent name (wrong: it would credit Tola with the PMO Lead's words), and a section `note` is always a warning callout drawn below the rows.
   - Recommend (built now, existing fields only):
     - **Returned:** a section `returned` (kind `text`, no title, **no items**) with a `note` holding the whole backend-composed sentence. A small general frame change in `Sections.tsx` (`SectionView`): a section with no items, no title and a `note` draws only the warning Callout (no panel chrome, no "Nothing here yet."). Order is the fixture's section order, so it sits above "Your update" as the board draws it.
     - **Received:** a section `delivery` (kind `text`, no title) with one item whose `text` is the backend-composed sentence and whose `tag` is the backend's (`Verified`, tone `verified`, only in the fixture where every recipient is confirmed). The green callout is not drawn; the sentence and the green tag are. Exception, category `no field: callout tone`.
   - Contract proposal for build.md (design engineer and backend decide): additive `workspace.banner: {tone (the existing display tones), text}`. The frame cannot add it locally.
2. **"DELIVERED hh:mm" versus the receipt word.** `recipients` rows draw `RECEIPT_WORDS` (`received` reads "Received", `labels.ts`) and ignore the item's `tag`. The boards say "DELIVERED". Recommend: a small general change in the `recipients` case of `Sections.tsx`: when the item has a `tag`, draw that tag (the backend's label and tone) in place of the receipt word; with no tag, keep today's receipt word. The tag is never drawn from the receipt value. The row's time is `item.at` formatted by `formatDayTime` ("12 Nov 15:10"), the board draws only "15:10" (exception, `frame vocabulary`; D-93 date format).
3. **"What happened" is three rows of one section.** The Approved row has no receipt. Recommend: one `recipients` section "What happened"; the first item is `text` "Approved by Kemi Adebayo" with `at` and no tag, no receipt (draws its time only); the others are the emails. Contract proposal: a proper per-recipient receipt record (address, channel, receipt state, confirmation time) so a recipient row is not also the approval row.
4. **The "Next" panel.** `workspace.next: string[]` exists in the schema but the frame draws nothing from it. Recommend: a general frame change in `Workspace.tsx`. When `workspace.next` has lines, the side column draws a panel titled "Next" with the lines; any `workspace` steps go in that same panel (this is the board: "Edit your update" sits in "Next"). With no `next`, the panel stays "Decide" (`STEP_TEXT.decide`), so every F-17 and F-21 board and fixture is unchanged. On received there are no steps, so the panel shows the lines only.
5. **Returned has one button.** The board draws "Edit your update" only. The step is `send_to_tola` (the F-21 write path, which already keeps the 409/422/idempotency flow), relabelled "Edit your update", primary, `consequence` "Edit your part, then Tola reassembles v2 and it goes back for review." (the board's sentence, from data). Pressing opens the F-21 four-part form (D-69 press-to-open) with the saved words; the form's heading and submit button read "Edit your update" because the contract has no submit label. Exception `frame form`; contract proposal `steps[].submit_label`. No `save_draft` step is offered (not drawn); whether a returned item offers one is the backend's call and is listed as a proposal.
6. **Phone wording and extent.** Phone returned shows the status "RETURNED", the title "Report returned", a shorter quote, and only "Edit your update"; phone received shows "DONE", "Report received", "Delivered to 2 client contacts. Verified." and nothing else. The frame has one title and one data set for both widths. Recommend: desktop wording at both widths; the phone also shows "Your update" and "What happened"; the shorter quote, the "DONE" status word and the mobile-only titles are exceptions. The desktop and phone notes differ in length: the page shows the single note the data carries.
7. **Frame items** as F-21: the desktop boards select the "Documents" project tab and draw the project tab bar (D-81); the page keeps its own title, tabs, facts strip and station track; the phone back link ("← Project"); top bar and "+ Start". Exceptions `frame item` and `frame layout`.
8. **Status tags.** "RETURNED TO YOU" and "RECEIVED BY CLIENT" are `workspace.status` (label and tone from the fixture). They are never computed from `/me`, from `view`, or from `state`.

## D-LINE-WORKSPACE and open-decision limits (binding on the PR description and build.md)
- D-LINE-WORKSPACE is `proposed`; F-22 consumes it only under the recorded exception (`architecture/sources/decisions-2026-11-15.md` (g), (i)): **contract mock only**. The backend developer may change or refuse any field.
- **Nothing is released.** No real send, no real client template, no real recipient or delivery confirmation. Do not claim a real backend, "no duplicate send", or that the weekly line works. The template is a test template when the data says so.
- D-RETURN (open) holds the real behaviour of a return (what task the preparer gets, how v2 is numbered). D-ALERT-PROVIDERS (open) holds real delivery. Neither blocks the mock. The frame derives neither the "v2" number nor any confirmation.

## Summary
- After the PMO Lead's decision, `/work/W-2209` shows a returned report: the return note, "Your update" with its cites, and a "Next" panel whose only action is "Edit your update", which opens the F-21 editor.
- `/work/W-2211` shows a received report: who it went to and a confirmation per recipient, each with the backend's own tag and time.
- "Verified", "DELIVERED" and "both deliveries confirmed" appear only when the data says so. Partial, failed, unknown and uncertain confirmations are shown as returned; an uncertain one offers reconcile only and no resend.
- Everything is on the contract mock, on the existing route and renderer, with three small general frame changes (Conflicts 1, 2, 4).

## Context
- Renderer: `frontend/src/features/workspace/` (`Workspace.tsx`, `Sections.tsx`, `StepForm.tsx`, `Steps.tsx`, `useWorkspaceStep.ts`, `labels.ts`, `workspace.css`), mounted from `frontend/src/features/work-item/WorkItemOverview.tsx`; page `frontend/src/app/work/[id]/page.tsx`. Shared library `frontend/src/components` (D-91): use `Callout`, `Tag`, `Button`, `Panel` and the existing `formatDayTime`; add no local copy of a callout, tag or panel.
- F-21 work that stays unchanged: fixtures `frontend/mock/fixtures/work/W-2201` to `W-2208` and sidecars, `frontend/mock/workspace.mjs` (E-WORK-STEP handler, idempotency map, `/__mock/workspace-log`), `frontend/mock/start-work.mjs` (E-LINE-OPTIONS for `weekly_report` cite fields), `frontend/tests/weekly.test.tsx`, `weekly-mock.test.ts`, `frontend/e2e/weekly.spec.ts`.
- `weekly-mock.test.ts:54` asserts no served fixture contains `"returned"` or `"received"`; F-22 replaces it (Acceptance 17).
- Uncertain-send lock: `useWorkspaceStep.ts` (`awaitingReconcile`, `allLocked`), `ReconcilePanel` and `workAction` in `frontend/src/features/response/`; fixture W-2205 and `W-2205.next.json` show the shape of `reconcile` and `allowed_actions: ["reconcile"]`.
- Fidelity: F-21 `fidelity-exceptions.json` and drive script as the model (`delivery/features/F-21/`).

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (read, `workspace`; unchanged, proposal)
Every F-17 and F-21 rule applies (hide when absent, words for enums, INV-UNKNOWN, INV-RESTRICTED, sample label, WAT dates, no `/me`). `view` is a free string, so `returned` and `received` need no schema change. The two states set:

| Field | Returned | Received |
|---|---|---|
| `line_key` | `weekly_report` | `weekly_report` |
| `screen`, `view` | `SCR-25`, `returned` | `SCR-25`, `received` |
| `title` | "Weekly client report · 5–11 Nov" | same |
| `status` | label "Returned to you", tone `stopped` | label "Received by client", tone `verified`, only when every recipient is confirmed; otherwise the backend's own label and tone (for example "Delivery not confirmed", tone `uncertain`) |
| `sections` | `returned` (item-less, `note` = the whole sentence, Conflicts 1); `update` (kind `text`, title "Your update", four items with `cites` and `cite_label` as in W-2204) | `delivery` (kind `text`, the sentence as item `text`, tag only when all confirmed); `happened` (kind `recipients`, title "What happened", Conflicts 3) |
| `next` | `["Edit your part, then Tola reassembles v2 and it goes back for review."]` | `["Next week's report opens on 19 Nov, after the week ends."]` |
| `steps` | `send_to_tola` labelled "Edit your update" (Conflicts 5), eight fields as W-2201, saved words as `value`; absent when the viewer cannot edit | none |
| `allowed_actions`, `reconcile` | absent | present only on the uncertain fixture, as W-2205.next |

The recipient rows of `happened`: `{id, text: "Emailed to <name>", channel?, receipt: received | not_yet | uncertain | failed | unknown, at?, tag?: {label, tone}}`. The frame computes no count ("2 contacts"), no next-week date, no "v2", no sentence.

### Rendering rules (frame, general, not weekly-specific)
- **Item-less note section:** a section with `items: []`, no `title` and a `note` draws the note's Callout alone. A section with items or a title is drawn as today.
- **Recipients row:** main = `text` and `channel`; end = the item's `tag` when present, else the receipt word (`RECEIPT_WORDS`; `unknown` reads "Unknown", `uncertain` reads "Uncertain", never "Received" or "Delivered"); then `<time>` from `at` when present. A row with a `receipt` other than `received` never shows a time the data did not give. A missing `at` draws no time (not 0, not blank placeholder): for a `received` or `uncertain` recipient with no `at`, the end reads "Time unknown".
- **Next panel:** Conflicts 4. Lines are plain text from `next`; empty `next` or absent draws no panel title change.
- **Empty recipients:** a `recipients` section with no items draws "Nothing here yet." and no tag; nothing else on the page may say Delivered, Received or Verified unless the data's own text does.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (unchanged)
- From the returned page only (`send_to_tola`). Request, 200/409/422/401/403/404/5xx, idempotency and `expected_revision` exactly as F-21 Contract. No `note`, no `evidence_ids`; the body validates against the generated request schema. The frame does not trim, check "TBD" or require a cite.
- Mock script for W-2209: `send_to_tola` 200 `done`; `.next.json` = the assembling item (W-2203 content, `id` W-2209, revision + 1, title unchanged). Mock-only; D-RETURN decides the real v2 behaviour.
- A received item has no step and the page sends nothing to `/steps`.

### E-WORK-ACTION `POST /api/v1/work/{work_id}/actions` (reconcile; reuse)
Only on the uncertain received fixture (W-2212), from the existing `ReconcilePanel`. Locked from the item's own `reconcile` and `allowed_actions`, so a reload does not unlock it. The mock still answers 501 for it (BACKEND-HANDOFF.md "Added during F-21"); the reply and the next state are undefined and verified on the mock request only.

### Permission, tenant, errors
Backend decides per record. A 401 shows the signed-out callout with `next` = this page; 403/404 and wrong-tenant show `NoAccessState` with no client, title or id. An unknown work id is 404 with no client, title or id and nothing from another item's fixture (F-21 QA-3-2). Nothing is derived from `/me`: whether "Edit your update" appears comes only from the item's `steps`.

### Screen states
- **Loading / error / signed out / no access:** as the work item page and F-17.
- **Returned, success:** status tag, warning note, "Your update" (four parts, cites), "Next" panel with the primary button. **Edit:** the F-21 form opens under the button with the saved words and cites; focus to the form heading; Escape closes and returns focus to the button. **After a done send:** reload to the assembling state (W-2203 shape). **Cannot edit (W-2210):** same page, no button, no explanation invented.
- **Received, all confirmed (W-2211):** green "Verified" tag with the data sentence, "What happened" rows with their DELIVERED tags and times, the Next line, no button.
- **Received, partial / uncertain (W-2212):** status per data, sentence per data (no "Verified"), the confirmed row tagged, the other row "Uncertain"; `ReconcilePanel` and its single action; no resend.
- **Received, unknown / failed (W-2213):** each row shows its own tag or word; "Unknown" with no time where `receipt` is `unknown`; no "Verified".
- **Received, no recipients (W-2214):** "Nothing here yet." under "What happened"; no delivery claim.
- Reduced motion respected. State is always also in words.

### Fixtures (`frontend/mock/fixtures/work/`, new; every existing file byte-for-byte unchanged)
All validate against the generated 200 schema and are `sample: true`, `line_key: "weekly_report"`, case `C-0211`, reference `WCR-0216`, WAT times.

| Id | Shows |
|---|---|
| W-2209 | returned: banner note "Kemi Adebayo returned v1 on 12 Nov: "Say what we need from the client for the login fix: test devices by Friday."", the four parts of W-2204 with cites, `next`, step `send_to_tola` "Edit your update"; `.steps.json` `send_to_tola` 200 `done`; `.next.json` = assembling item |
| W-2210 | returned, no `steps` (viewer cannot edit): same page, no button |
| W-2211 | received, both confirmed: Approved row (12 Nov 14:58), two DELIVERED rows (15:10, 15:11, recipients "Dr Amaka Obi" and "Lagoon Health projects inbox"), sentence "Lagoon Health received v2: emailed 12 Nov 15:10 to 2 contacts, both deliveries confirmed. Verified." with the verified tag |
| W-2212 | received, one delivered and one `uncertain`; status tone `uncertain`; sentence without "Verified" ("Emailed 12 Nov 15:10 to 2 contacts; 1 delivery confirmed, 1 not confirmed yet."); `reconcile` and `allowed_actions: ["reconcile"]` |
| W-2213 | received, one recipient `receipt: unknown` with no `at` and no tag, one `failed` with the backend's tag; no Verified |
| W-2214 | received, no recipients, no delivery section |

A test builds the returned-without-note case from W-2209 in memory (note section removed) and checks that the page draws no invented text.

## Lanes
- **Frontend lane (builder)** owns:
  - Fixtures W-2209 to W-2214 and sidecars (above).
  - The three small general frame changes in `frontend/src/features/workspace/Sections.tsx`, `Workspace.tsx` and `workspace.css` (tokens only), each listed in build.md. No weekly page, route, component or new renderer.
  - Tests: `frontend/tests/weekly-returned-received.test.tsx` (new), `frontend/tests/weekly-mock.test.ts` (replace the line-54 guard; existing assertions kept), `frontend/tests/mock-contract.test.ts` (new fixtures only), `frontend/e2e/weekly-returned-received.spec.ts` (new).
  - Factory files: `delivery/features/F-22/fidelity-exceptions.json`, `round-<N>/fidelity/**`, `build.md`.
- **Shared, read only (import, do not edit):** `frontend/src/components/**` (used as is), `src/features/start-work/**`, `features/decide/**`, `features/response/**`, `features/work-item/**`, `src/shell/**`, `features/my-work/**`, `src/api/**` (including `schema.d.ts`), `src/styles/**`, `frontend/package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `frontend/mock/workspace.mjs`, `frontend/mock/start-work.mjs`, `architecture/**`, `design/**`, `apps/**`, and protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`. F-21's fixtures W-2201 to W-2208 and tests keep passing unedited, except the one guard in `weekly-mock.test.ts`.
- **Backend lane:** none. Record in build.md, not blocking: how per-recipient confirmations are carried (Conflicts 3), the banner with a tone (Conflicts 1), `steps[].submit_label` (Conflicts 5), where the return note and returner live, whether a returned item offers `save_draft`, the reconcile reply, 404 on unknown ids, and the D-RETURN / D-ALERT-PROVIDERS limits.
- **Integration owner:** the coordinator. `features/workspace/**` is shared with F-17 and F-21: whichever merges second merges the current base and reruns `delivery/checks.sh` and the 390 e2e.
- **Ports:** app 4750, mock 4751 (range 4750 to 4759; no other spec or Playwright file uses it). `cd frontend && E2E_PORT=4750 MOCK_PORT=4751 npx playwright test e2e/weekly-returned-received.spec.ts`, `timezoneId: 'Africa/Lagos'`. Score on a production build (`next build`, `next start -p 4750`, mock on 4751). Check `df` first (stop under 3 GB) and delete `frontend/test-results` after.
- **Review routing (D-64):** technical (sonnet); security (opus: client-bound send truthfulness); UI (opus, fidelity gate on 4 boards); UX (sonnet); QA (opus). Product acceptance not required. Medium risk, Sonnet builder. One fidelity run per round; only affected reviews re-run.
- **Size:** one PR, about 600 to 1,000 lines. If it exceeds that, drop the two phone boards to a follow-on.

## Acceptance criteria
Fidelity command for one board (swap `--board`, `--page`, `--width`, `--out`; cookie `psl_mock_persona=pm`):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-25-desktop-received.dc.html \
  --page "http://localhost:4750/work/W-2211" --width 1440 \
  --cookies psl_mock_persona=pm \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-22/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-22/round-<N>/fidelity/SCR-25-desktop-received-1440
```
Boards: `-returned` on `/work/W-2209`, `-received` on `/work/W-2211`; desktop at 1440, mobile at 390.

### Fidelity (D-83, line screens)
1. **Four boards.** Each of the four boards: element coverage after approved exceptions = 100% (`scores.coverageWithExceptions`), the UI reviewer's side-by-side reading finds no fixable gap, visual >= 70, with a visual waiver per board in `fidelity-exceptions.json` citing D-83 (`approved_by`: "builder proposal, pending design engineer" until signed). — verify: the command per board, `round-<N>/fidelity/scores.txt` (board, width, coverage, visual, pass), the waivers in the file.
2. **Exceptions are limited and mapped.** Each entry has `role`, `name`, `category`, `reason`, `approved_by` and maps to a Conflicts number in build.md; none covers a value the data can supply (a name, a time, a tag, a count). — verify: file content and build.md.
3. **One fidelity run per round** (D-64). — verify: build.md.

### Page behaviour
4. **Returned from data.** `/work/W-2209` shows the status "Returned to you", the warning note above "Your update", the four parts with their cite chips ("2 RECORDS", "ISS-0233", "MIN-0141", "2 ACTIONS"), the "Next" panel with its line and the primary "Edit your update". Every string comes from the fixture; none is in `src/`. — verify: component test; page at 1440 and 390; `grep -rn "returned\|received\|Kemi\|Lagoon" frontend/src/features/workspace` finds no new string literal.
5. **Edit opens the F-21 editor, no new write path.** Pressing "Edit your update" opens the four-part form with the saved words, focus on its heading, picker options only from E-LINE-OPTIONS; no control writes, suggests or generates text. Submitting sends one POST `/api/v1/work/W-2209/steps` with CSRF, `expected_revision` = `workspace.revision`, `step: "send_to_tola"`, the eight `inputs`, a UUID key, no `note`, no `evidence_ids`; `done` reloads once and shows the assembling state; a 409, 422 and 500 behave as in F-21. — verify: component test with a recording `fetch`; e2e.
6. **No edit without a step.** W-2210 (no steps) shows no "Edit your update" and no other button; role or persona changes nothing (`grep -n "/me\b" frontend/src/features/workspace` unchanged). — verify: component test with two personas.
7. **Absent is not invented.** A returned item without its note section draws no banner and no invented words; no returner, date or version appears that the data lacks. — verify: component test on a modified copy of W-2209.
8. **Received, all confirmed.** `/work/W-2211` shows the status, the data sentence with the "Verified" tag, "What happened" with the Approved row and two rows tagged "DELIVERED" each with its own time, and the Next line; no button and no POST of any kind. — verify: component test and page at both widths.
9. **Nothing is claimed without confirmation.** On W-2212, W-2213 and W-2214 the text "Verified", "both deliveries confirmed" and "DELIVERED" appears only on a row whose own tag or `receipt: received` says so. W-2212's uncertain row reads "Uncertain" and W-2213's rows read "Unknown" (no time) and the backend's failed tag. W-2214 reads "Nothing here yet." — verify: component tests asserting `document.body.textContent` for each fixture; a recipient with `receipt: unknown` never reads Received or Delivered.
10. **Reaching `received` is not proof.** A fixture whose `view` is `received` but whose recipients are not all confirmed draws no verified tag, no green, and the status tag shows the fixture's own label and tone. — verify: W-2212 and W-2213 component tests.
11. **No resend while uncertain (INV-RESEND).** On W-2212 no "Send again", "Resend" or send control exists; `ReconcilePanel` is the only action; its answer is one POST to `/actions` and none to `/steps`; a reload keeps it (locked from the item's `reconcile`); no new idempotency key exists. If the reload carries no `reconcile`, the page says "We are checking what happened. Nothing was sent again." and offers a reload only. — verify: component tests and e2e (request log); mock evidence only.
12. **Unknown id and access.** An unknown work id gives the 404 state with no client, title or id; 401 shows the signed-out callout with `next`; 403/404 on a step and wrong-tenant read show no client, title or id; nothing from another item's fixture shows. — verify: component tests.
13. **Recipients and time rules.** A recipient with `receipt: received` and no `at` reads "Time unknown"; the page computes no count and no date (the "2 contacts" and "19 Nov" appear only inside fixture strings). — verify: component test changing the fixture strings and checking the page follows the data.
14. **Frame changes do not touch other boards.** F-17, F-21 and every earlier fixture render as before: the panel is still "Decide" when `next` is absent; the recipients row still draws the receipt word when no tag; a section with items or a title is unchanged. — verify: existing `workspace*.test.tsx`, `weekly.test.tsx` and their e2e unchanged and passing; F-17's `regions.json` check still passes at its recorded scores.

### Quality
15. **Accessibility and layout.** W-2209 to W-2214 at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), one h1, no sideways scroll, 44px targets on phones, visible focus, focus to the form heading on open and back to the button on Escape, tags readable without colour, reduced motion respected. — verify: `e2e/weekly-returned-received.spec.ts`.
16. **Tokens only.** `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" frontend/src/features/workspace/*.css` returns nothing from this feature's diff; shared components used, no new local callout, tag or panel. — verify: the command on the diff.
17. **Weekly mock test updated, not weakened.** The line-54 guard in `weekly-mock.test.ts` keeps its check for W-2201 to W-2208 (none contains `"returned"` or `"received"`) and adds positive checks for W-2209 to W-2214: each is served as its own fixture, schema-valid, `sample`, `line_key: "weekly_report"`, with `view` `returned` or `received`; every step script names only a step its item offers; W-2209 `send_to_tola` is done and serves the assembling item; a repeated key returns the stored reply with no second send. No existing assertion removed or loosened. — verify: the test and `git diff`.
18. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**`, `mock/workspace.mjs`, `mock/start-work.mjs`; no existing fixture edited; wanted fields the schema lacks are proposals in build.md. — verify: `tests/mock-contract.test.ts`; `git diff --stat`.
19. **No real send, no overclaim.** Every request in the e2e run goes to the mock (4751). The PR description and build.md state the D-LINE-WORKSPACE, D-RETURN and D-ALERT-PROVIDERS limits and claim no real backend, delivery or idempotency. — verify: build.md; the e2e request check.
20. **Existing behaviour not weakened.** `delivery/checks.sh` passes; F-17, F-21, F-09, decide, response, start-work and shell tests and e2e unchanged and passing. — verify: the run output in `round-<N>/build.md`.
21. **build.md evidence.** Lists commands and results, the 4 scores, every exception with its Conflicts number, every frame change with its reason, every contract proposal and the limits. — verify: file content.

## Out of scope
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`; a real E-LINE-OPTIONS; the reconcile reply.
- Real sends, real delivery confirmation, real templates, real recipients; any claim that duplicate sends are prevented.
- The return-and-edit loop beyond F-21, a "returned" counter or history view, the PMO Lead's own view of a returned report, a "Send again" or "Resend" of any kind, and any new decision UI (Return and Reject stay on the F-21 review board).
- A client-side banner field, local contract extension, or computing the next-week date, contact count, "v2" number, tone or sentence on the client.
- Writing, suggesting or generating client text; "Ask Tola"; "Open the report as the client will see it".
- FE-LINE-MINUTES (F-23), the assistant (F-24), every other line, any weekly-specific page or route.
- Changes to `src/shell/**`, `my-work/**`, the existing work item boards, new npm dependencies.

## Assumptions
- Fixture ids W-2209 to W-2214: W-2001 to W-2010, W-2101 to W-2109 and W-2201 to W-2208 are taken and no F-23/F-24 readiness names these ids.
- Ports 4750 (app) and 4751 (mock): the first free pair in the assigned range; nothing else in `frontend/` or `delivery/` uses it.
- The returned page uses the existing `send_to_tola` step relabelled, not a new step key. Reason: it reuses the F-21 write path and handler; the real key is the backend's call.
- One step only on the returned page, no `save_draft`. Reason: the board draws one button; saving a half edit is a backend proposal.
- Banner as an item-less warning note (returned) and a data sentence with a data tag (received). Reason: the contract has no toned banner; the design engineer decides at Conflicts 1.
- The recipients section carries the Approved row. Reason: the contract has no receipt record separate from `recipients`; a proposal is recorded.
- One returned fixture serves both widths and the phone shows the same data. Reason: no per-width data; the shorter phone quote is an exception.
- The "Next" panel title is "Next" when `workspace.next` has lines, else "Decide". Reason: the only data signal the schema offers; it leaves every earlier board unchanged.
- "Time unknown" is the frame's neutral wording for a confirmed or uncertain recipient with no `at`. Reason: INV-UNKNOWN; the sources are silent on the words. The approver may escalate any wording.
- Mock-only `.next.json` for W-2209 is the assembling item. Reason: the existing assembling state is the closest; how a real return numbers v2 is D-RETURN.
