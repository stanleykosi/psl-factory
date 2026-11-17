# The minutes line, finished: filed internal minutes and published client minutes show the actions created and who each recipient's delivery receipt says got them (contract mock only)

> Tasks: FE-LINE-MINUTES, second part (R-WORKITEM; acceptance A-WORKSPACE frontend half, with A-WORKITEM, A-DECIDE and the F-17, F-21 and F-23 tests kept green). Architecture: package `architecture/packages/v7`; FE-LINE-MINUTES at `architecture/packages/v7/delivery.md:2046`, no unresolved gates; the `workspace` block is typed at `frontend/src/api/schema.d.ts:1693`; this feature changes no generated type. Design: approved canvas version 1794581312-b166 (client-approved 13 Nov 2026); `design.py check --project .` run for this spec on 17 Nov: `EXCEPTION`, `passes: true` (design_sha256 `2859ab21…d82`, D-89 "+ Start" frame change). Screens: SCR-28, 4 artboards: `SCR-28-desktop-internal`, `SCR-28-mobile-internal`, `SCR-28-desktop-published`, `SCR-28-mobile-published` (`design/canvas/project/`). With F-23's 8, SCR-28 is 12 of 12. Decisions consumed: D-LINE-WORKSPACE (`proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)), D-64, D-83, D-91 to D-96, D-98, D-104 to D-106. Open and held: D-ALERT-PROVIDERS (real client send), D-RETURN, and the audience-skips-review rule (no decision id). Model: `delivery/features/F-23/spec.md`, `delivery/features/F-27/spec.md` (shape).

## What is sent to the client, and what stays held (read first)
- **On the contract mock, nothing is sent to anyone.** There is no email, no WhatsApp, no real recipient, no real template, no real filing and no real action record. Every "sent", "emailed", "delivered" and "filed" word on these four boards is text a fixture returns, as a backend would return it. The PR and `build.md` must say so and must not claim a working minutes line, delivery, duplicate-send protection or filing.
- **What a real send would be (backend, not built):** when the PMO Lead approves client minutes, the backend sends only the exact approved version to the recipients it took from client contact records. The page will show those recipients and each person's own receipt. The frontend never chooses a recipient, never sends, never resends and never composes a delivery claim.
- **Held, because a product or backend decision is open:** (1) which audiences skip review (no decision id; internal skips it on the boards, the frontend decides nothing); (2) whether actions are created at the PM's confirm or at approval (G-SCR28-7); (3) where internal minutes are filed; (4) the real client send and its provider (D-ALERT-PROVIDERS); (5) what a return does to confirmed items (D-RETURN, not on these boards); (6) the real client template (the label stays "TEST TEMPLATE" until PSL supplies one); (7) the records for actions, decisions and meetings (G-SCR28-6). The frame shows whatever the reloaded work item returns and adds no rule.
- **Held on the page itself:** after an uncertain send (`effect_uncertain`) the only action is reconcile; no resend and no new key (INV-RESEND). A recipient whose receipt is `uncertain`, `failed`, `unknown`, `not_yet` or absent is never shown as Sent or Delivered.

## Conflicts with the boards (for the design engineer, before the build)
"Recommend" is what this spec builds if no answer comes. Items 1 to 6 change what a person sees or how the page is composed and need an answer. Items 7 to 12 are exceptions to sign. Every exception goes in `delivery/features/F-28/fidelity-exceptions.json` with `approved_by: "builder proposal, pending design engineer"` until signed.

### Contract conflicts (board vs data and safety)
1. **Published desktop names no recipients; the contract and safety need them.** `SCR-28-desktop-published` says only "emailed to Lagoon Health … delivery confirmed" and draws no recipient list. INV-RESEND and G-SCR25-1 need a receipt per person, and one aggregate "delivered" cannot show that one contact's delivery is uncertain.
   - **Option A (recommend):** the published fixture carries a `recipients` section titled "Sent to" (name, channel, `receipt`, time) under the "Actions created" list in the main column. Extra element, exception category `safety`.
   - **Option B:** draw nothing beyond the board; the aggregate sentence is the only delivery evidence. Not recommended: it cannot show a partial or uncertain send.
2. **The board's green sentence is one aggregate claim ("delivery confirmed", "delivered").** The frame can only show it as returned. **Recommend:** the sentence is a returned `text` item, shown verbatim; the frame composes no delivery wording and does not check the sentence against the recipients. The fixtures keep them consistent (all `received` for the board fixture) and a mixed fixture (W-2312) returns a sentence that does not say confirmed. The rule that a "received" sentence and the verified tone appear only when every recipient is `received` is the backend's (G-SCR25-1); recorded for the backend developer, not enforced here. **Option B:** the frame hides the sentence's verified styling unless every returned recipient receipt is `received`. That is a frontend rule about delivery truth; not recommended without your word.
3. **Created actions: the boards draw a title and a tag; readiness requires owner and due date.** Internal rows read "ACT-0451 · Prepare test devices list [OPEN]". Published rows read "Send test accounts for UAT · Client [OPEN]", with the owner folded into the text and no due date; the third reads "Assess the SMS reminders change · no owner [OWNER NEEDED]".
   - **Option A (recommend):** a `table` section with columns ACTION, OWNER, DUE, STATE. Owner is the returned cell text, due is a date or "Unknown", state is the returned tag (OPEN, OWNER NEEDED). Owner and DUE are extra columns (exception `no column`) at both widths. An action without an owner shows "OWNER NEEDED" in the state tag and "No owner yet" in the OWNER cell as returned text; nothing is guessed.
   - **Option B:** a `checklist` exactly as drawn (text plus tag), with owner and due only inside the backend's text. Closest to the boards, but due is then not shown separately and "Unknown" cannot be a value. Not recommended.
4. **The phone boards are almost empty; the data is the same at both widths.** `SCR-28-mobile-internal` draws only "Minutes filed" and "Internal: filed, no review. 2 actions created." `SCR-28-mobile-published` draws "Minutes published" and "Sent to Lagoon Health, delivered. 3 actions created." Neither draws the action list, "Next" or "Open actions". The desktop boards draw all three. The frame renders one dataset at every width.
   - **Option A (recommend):** the phone shows the same sections as desktop, stacked. The action list, Next sentence, "Open actions" and (published) "Sent to" are extras on the phone (exception `phone composition`). Everything the backend returns is visible; a phone user can open the actions.
   - **Option B:** hide the list, Next and Open actions on phones by CSS. Matches the phone boards but hides data the page was given, including OWNER NEEDED and receipts. Not recommended.
   - **Option C:** the design engineer draws the fuller phone boards. Then the phone half waits; the desktop half builds alone.
5. **Titles and status wording differ by width.** Desktop: crumbs "PROJECTS / LAGOON HEALTH / MINUTES · MIN-0141", heading "Weekly sync · 10 Nov", tag "FILED · INTERNAL" or "PUBLISHED · RECEIVED". Phone: heading "Minutes filed" / "Minutes published", bar tag "FILED" / "DONE", back link "← Project". The contract has one `title`, one `status` and one back link.
   - **Option A (recommend):** desktop wording at both widths, as F-23 Conflicts 10. Fixtures return `title` "Weekly sync · 10 Nov", `status` {label "Filed · Internal", tone `verified`} and {label "Published · Received", tone `verified`}. Phone title, bar tag and back link are exceptions (`phone wording`, `frame item`).
   - **Option B:** a phone `title_short` and `status_short` contract proposal. More surface for the backend to accept; not recommended.
   - Note on "PUBLISHED · RECEIVED" and "DONE": the status tone is returned. In the mixed fixture (W-2312) the status is returned as "Published · Delivery unconfirmed" with tone `uncertain`. The frame never promotes a tone.
6. **Where the "Open actions" button sits.** Desktop draws it in a "Next" panel in the right column, as a full-width outlined link under the Next sentence. The frame's Next panel is the F-17 decide/next panel and `workspace.links[]` draws in a links row. **Recommend:** the Next sentence stays in `workspace.next[]` and "Open actions" is a `workspace.links[]` entry of kind `project_tab` (proposal), drawn by the existing links row under it; any difference in placement or size is an exception (`frame layout`). It is drawn only when the data supplies it (G-SCR28-3).

### Layout and frame (exceptions to sign)
7. **The green banner.** The boards draw a full-width green band (no tag) at the top of the main column. The frame carries a returned `text` item with a `tag` (as F-21's received view, W-2211). **Recommend:** that item, in the frame's panel; the band's exact placement and the tag are exceptions (`frame layout`, `no field`). Under D-106 the frame draws warnings full-width; verified text keeps the frame's own placement.
8. **Left/right columns.** Boards put the action list in the main column and "Next" on the right. The frame's side column holds `next` and workspace-scope steps (F-17, D-62). The `table` section stays in the main column. Exception `frame layout`, as F-23 Conflicts 6.
9. **Panel headings.** "CREATED" (internal) and "ACTIONS CREATED" (published) are section titles returned by the data. The frame's own panel head styling (ink; blue means agent work, D-92b) is the frame's. No exception for the words.
10. **Row ids.** "ACT-0451" and "ACT-0452" are returned as the start of the action cell text. They link nowhere (no per-action page exists; `link.action_id` is a proposal, G-SCR28-3, recorded and not built). The only way to the actions is "Open actions".
11. **Frame items.** Top bar, "Tunde Bello · PMO", phone back link "← Project", "+ Start", project tab bar with counts (Milestones 4, Documents 6, Registers 6, Actions 9) are the shell's and F-14/F-17/F-23's. The counts are a missing field under D-83. Exceptions `frame item`, as F-23.
12. **Tokens.** Board colours the design system lacks are exceptions, not hard-coded values. OPEN reads as the amber tag the board draws (`uncertain` tone maps to `waiting`); OWNER NEEDED reads as the `person` tone tag. The frame maps tone from data only, never from the word.

## Summary
- After the PM confirms internal minutes, the same work item (`/work/{id}`, line key `minutes`) reloads as "Filed · Internal": a returned sentence, the actions created (action, owner, due, state, with "OWNER NEEDED" where there is none), and the Next sentence with "Open actions".
- After the PMO Lead approves client minutes on the F-16 page, the work item reloads as "Published": the returned sentence, the actions created, "Sent to" with each person's own receipt, Next and "Open actions".
- Receipts are per person. "Sent" or "Delivered" shows only where that person's receipt says so; an uncertain one offers only reconcile, never a resend.
- Everything is rendered by the F-17 frame; there is no minutes page, route or component. Unknown shows "Unknown", never 0 or blank.
- Contract mock only: nothing is sent or filed; the backend developer may change or refuse any field.

## Context
- Renderer: `frontend/src/features/workspace/` (`Workspace.tsx`, `Sections.tsx` with `table`, `recipients`, `text` and `StatusWord` for receipts via `RECEIPT_WORDS` in `labels.ts`; `Links.tsx` `WorkspaceLinks`; `proposals.ts` `workspaceLinks`, today only kinds `assistant` and `document`; `Steps.tsx`, `StepForm.tsx`, `useWorkspaceStep.ts` with the reconcile lock). Mounted from `frontend/src/features/work-item/WorkItemOverview.tsx`; route `frontend/src/app/work/[id]/page.tsx`.
- Project tabs exist: `frontend/src/app/projects/[caseId]/[tab]/page.tsx` and `PROJECT_TABS` in `frontend/src/features/projects/model.ts:31` (the `actions` tab is `/projects/{case_id}/actions`).
- Existing "received" rendering to copy: F-21's `frontend/mock/fixtures/work/W-2211.json` (verified `text` item plus `recipients` with `receipt` and `at`).
- F-23's seam: `frontend/mock/fixtures/work/W-2301.json` (+ `.next.json`, `.steps.json`), `W-2304.json` (+ `.approve.json`, `.return.json`), `W-2305.*` (uncertain send, `reconcile`). `frontend/mock/workspace.mjs` (E-WORK-STEP handler; `<id>.next` swapped in on a 200, lines 105 to 125). `frontend/mock/server.mjs:140-147` `taskResponse` applies `<work_id>.approve.json` / `.return.json` after a decide. Reconcile: `frontend/src/features/response/` (`ReconcilePanel`, `workAction`). Decision page: `frontend/src/features/decide/`.
- Taken fixture ids: W-1xxx, W-2001 to W-2010, W-2201 to W-2214, W-2301 to W-2308. **F-28 uses W-2309 to W-2314.**
- Records: model.json has no REC-ACTION, REC-DECISION or REC-MEETING (G-SCR28-6): a backend item.

## Contract

### E-WORK-ITEM `GET /api/v1/work/{work_id}` (read, `workspace`; unchanged, proposal)
All of F-17 Contract 1 to 11 and F-23's rules apply: hide when absent, words for enums, INV-UNKNOWN, INV-RESTRICTED, sample label, WAT dates, nothing from `/me`. The two end states set:

| Field | Internal (`view: "internal"`) | Published (`view: "published"`) |
|---|---|---|
| `line_key`, `screen` | `minutes`, `SCR-28` | same |
| `title`, `subtitle`, `context.crumbs` | "Weekly sync · 10 Nov"; "Formal minutes and action handoff · MIN-0141"; Projects / Lagoon Health / Minutes · MIN-0141 | same |
| `status` | {label "Filed · Internal", tone `verified`} | {label "Published · Received", tone `verified`} (W-2312: "Published · Delivery unconfirmed", tone `uncertain`) |
| `sections` | `text` (no title): one item, "Internal minutes are filed straight away; no review. 2 actions were created on the action list." with a `tag` Filed (tone `verified`); `table` "Created" | `text`: one item, "Minutes v1 approved by Kemi Adebayo and emailed to Lagoon Health on 10 Nov 17:30, delivery confirmed. 3 actions are on the action list." tag Delivered; `table` "Actions created"; `recipients` "Sent to" (Conflicts 1) |
| `table` columns | `action` text, `owner` text, `due` date, `state` tag | same |
| `table` rows (internal) | "ACT-0451 · Prepare test devices list" (owner and due as the fixture gives), OPEN; "ACT-0452 · Book go-live rehearsal", OPEN | "Send test accounts for UAT" owner "Client · Lagoon Health", OPEN; "Finish the Android login fix" owner "Engineering (recorded by PM)", OPEN; "Assess the SMS reminders change" owner cell "No owner yet", due `{unknown: true}`, state tag OWNER NEEDED |
| `recipients` items | n/a | one per person: `text` (name · role), `channel`, `receipt`, `at` when known; the board fixture has two, both `received` |
| `next` | ["Owners see their actions in My work."] | ["An action with no owner shows in Unassigned for leads. Actions being done is tracked separately."] |
| `links` (proposal) | "Open actions" {kind `project_tab`, tab `actions`, case_id `C-0211`} | same, plus "Open the minutes" {kind `document`, D-2304, version 1} only where the fixture offers it (the published board draws none; W-2311 omits it, W-2312 includes it) |
| `steps` | none (no actionable step; read only) | none, except `reconcile` through the existing `reconcile` path in W-2312 |
| `revision` | a number | a number |

Counts ("2 actions", "3 actions", "2 contacts") are returned text. The frame computes none and checks none against the rows. The frame draws no "Created", "Filed", "Sent", "Delivered" or "OWNER NEEDED" wording of its own: every such word is a returned string, tag label, or the existing `RECEIPT_WORDS` mapping of a returned `receipt`.

### Proposals (fixtures only, read by `features/workspace/proposals.ts`, stripped before the contract check)
| Proposal | Shape | Frame behaviour |
|---|---|---|
| G-SCR28-3 `workspace.links[]` kind `project_tab` (new kind beside `assistant`, `document`) | `{key, label, target: {kind: "project_tab", tab, case_id}}` | Drawn only when supplied, `tab` is a key in `PROJECT_TABS` and `case_id` passes `RECORD_ID`; it is a `Link` to `/projects/{case_id}{tab path}`. Otherwise it is not drawn. All other unknown kinds are still not drawn |
| G-SCR28-3 `link.action_id` in cells | recorded for the backend developer | **Not built.** Row ids are plain text (Conflicts 10) |
| G-SCR28-1 `items_default`, X-LINKS `assistant`/`document` | built by F-23 | unchanged |
| Item step `assign_owner` on an OWNER NEEDED action (W-2313 only) | an item-scope step with one `record` field `owner`, using the F-23 step form | Drawn only when the data lists it on the item. No board draws it; extra element (Conflicts, Assumptions). Skipped, with nothing else changed, if the builder finds the F-23 `edit_item` path needs more than a fixture |

Recorded in `build.md`, not built: G-SCR28-4 `work_id` on E-LINE-OPTIONS (already recorded by F-23), G-SCR28-6 records, G-SCR28-7 order of creation, the audience-skips-review rule, G-SCR25-1 meaning of "received", D-RETURN, the meeting source, the unbuilt `workspace` block and E-WORK-STEP, the unbuilt idempotency promise and the server-side refusal of a resend while delivery is uncertain (SEC-5-C1).

### Writes
No new write and no new endpoint. The reached boards are produced by existing calls:
- **Internal:** the PM presses "Confirm and create actions" on W-2301 (F-23, E-WORK-STEP `confirm_minutes`) with `inputs.audience: "internal"`. The mock's reply swaps in the internal item. 
- **Published:** the PMO Lead approves on the F-16 page (E-TASK-CLAIM, E-TASK-DECIDE), unchanged. The mock's decide sidecar swaps in the published item.
- **Reconcile** after an uncertain send: the existing E-WORK-ACTION path, one POST to `/actions`, no POST to `/steps` or `/decision`, no resend, no new key.
- **Owner assignment** (W-2313 only): the F-23 per-item step form through E-WORK-STEP with a new UUID key per attempt, `expected_revision` = `workspace.revision`, E-LINE-OPTIONS `minutes/owner` (the F-23 hook, `STEP_RECORD_FIELDS.minutes = ['owner']`). 409 reloads and keeps inputs (F-17 flow); 422 `fields[].name` lands under its input; a blank owner is left out of `inputs`. Permission and tenant: the backend decides per record and step; a wrong-tenant or wrong-user read is 403/404 and shows `NoAccessState` with no title, client or id.

### E-DOCUMENT (`GET /api/v1/documents/{document_id}/versions/{version}`)
"Open the minutes" (published W-2312 only) uses the F-23 `WorkspaceLinks` document panel unchanged: one GET, title, version, a "Test template" tag when `test_template: true`; 403/404 "You can't open this document." with no title; 5xx/network manual retry of the read only.

### Screen states
- **Loading, error, signed out, no access:** the work item page's `LoadingState`, `WorkErrorCard`, signed-out callout with `next`, and `NoAccessState`.
- **Internal, success:** as the table above. **Published, success:** all recipients `received`. **Published, mixed:** a recipient with `uncertain`, `failed`, `unknown` or `not_yet` reads Uncertain, Failed, Unknown or Not yet, never Sent or Delivered; the status tone and sentence are as returned; if `reconcile` is present the only action is `ReconcilePanel` and every other control is locked (the F-17 lock).
- **Empty:** a section with `items: []` reads "Nothing here yet." (for example no actions were created). **Unknown:** "Unknown" for a missing due; the receipt time of a received or uncertain recipient without `at` reads "Time unknown" (existing). **Restricted:** a restricted item shows only its label.
- **Nothing to act on:** no step, no form, no button except "Open actions" and, where offered, "Open the minutes" and the reconcile panel. No animation; `prefers-reduced-motion` respected.

### Fixtures (`frontend/mock/fixtures/work/`, new; existing files byte-for-byte unchanged)
After the proposals are stripped, every fixture validates against the generated E-WORK-ITEM 200 schema.

| Id | Shows |
|---|---|
| W-2310 | internal board: Conflicts 3 table with two actions, OPEN, "Open actions" link, no steps |
| W-2311 | published board: sentence, 3 actions incl. OWNER NEEDED, "Sent to" with two recipients both `received`, "Open actions"; no "Open the minutes" |
| W-2312 | published, mixed receipts: one `received`, one `uncertain` with `reconcile` and `allowed_actions: ["reconcile"]`, one `not_yet`; sentence that does not say confirmed; tone `uncertain`; "Open the minutes" (D-2304 v1) |
| W-2313 | internal where every action has an owner except one (`due` unknown), with an `assign_owner` item step on that action; `.steps.json` 200 `done`, 422 on blank owner |
| W-2314 | published with minimal data: no `links`, no `next`, one action with no due and no owner, no recipients section (the "Open actions" and "Sent to" absence case) |
| W-2309 | a review item (copy of W-2304's shape, fresh id) whose `.approve.json` sidecar is the published item (id W-2309), so approving on the F-16 page ends on the published view. W-2304 and its sidecars are not touched |
| `W-2301.next.internal.json` | new sidecar: W-2301 as internal (id W-2301) |

Mock changes (additive):
- `mock/workspace.mjs`: when the step has `inputs.audience` and a sidecar `<id>.next.<audience>` exists, serve it; else `<id>.next` as today. One small change; every existing test keeps passing (audience "client" has no sidecar).
- A new `mock/fixtures/E-DOCUMENT.json` entry is not needed (D-2304 v1 exists from F-23).

## Lanes
- **Frontend lane (builder)** owns:
  - Fixtures W-2309 to W-2314 and their sidecars (`W-2309.approve.json`, `W-2313.steps.json`), `W-2301.next.internal.json`, and the audience branch in `mock/workspace.mjs`.
  - Small, general changes in `frontend/src/features/workspace/**`, each listed in `build.md` with its reason: `proposals.ts` (kind `project_tab` in `workspaceLinks`, typed as PROPOSAL), `Links.tsx` (draw a `project_tab` link as `Link`), `labels.ts` only if a tone mapping is missing, `workspace.css` additive rules, tokens only. No minutes-specific code, route or copy in `src/`.
  - Tests: `frontend/tests/minutes-end.test.tsx`, `minutes-end-mock.test.ts`, `mock-contract.test.ts` (new fixtures and the `project_tab` proposal stripped, checked on its own first), `frontend/e2e/minutes-end.spec.ts`.
  - Factory files: `delivery/features/F-28/fidelity-exceptions.json`, `round-<N>/fidelity/**` (`drive-states.mjs` if needed, `scores.txt`, per-board folders), `round-<N>/build.md`.
- **Shared, read only:** `features/decide/**`, `features/response/**`, `features/work-item/**`, `features/start-work/**`, `features/projects/**` (import `PROJECT_TABS`), `src/components/**`, `src/shell/**`, `features/my-work/**`, `src/api/**` including `schema.d.ts`, `src/styles/**`, `package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`, F-23's fixtures W-2301 to W-2308 (except the new `W-2301.next.internal.json` sidecar), and the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Record in `build.md`: G-SCR28-3, -6, -7, -8, G-SCR25-1, the audience rule, the unbuilt endpoints and idempotency.
- **Integration owner:** the coordinator. `features/workspace/**` and `mock/workspace.mjs` are shared with F-17, F-21, F-22 and F-23; whichever merges second merges the current base and reruns `delivery/checks.sh`, the F-21 and F-23 e2e and the 390 e2e.
- **Ports:** app **4791**, mock **4792** (the 479x range is not in any other spec, `playwright.config.ts` or `delivery/config.json`; the builder greps before using it). `cd frontend && E2E_PORT=4791 MOCK_PORT=4792 npx playwright test e2e/minutes-end.spec.ts e2e/minutes.spec.ts` with `timezoneId: 'Africa/Lagos'`. Score on a production build (`next build`, `next start -p 4791`, mock on 4792). `df -h /System/Volumes/Data` first (stop under 3 GB); delete `frontend/test-results` after.
- **Review routing (D-64):** medium risk. Technical (Sonnet), security (Opus: receipts, resend lock), UI (Opus first review, fidelity gate on 4 boards), UX (Sonnet), QA (Opus). Product acceptance not required. Sonnet builder.
- **Size:** about 700 to 1,100 lines, two thirds tests and fixtures. One PR.

## Acceptance criteria
Fidelity command per board (swap `--board`, `--page`, `--width`, `--out`; cookie `psl_mock_persona=pm`):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-28-desktop-published.dc.html \
  --page "http://localhost:4791/work/W-2311" --width 1440 \
  --cookies psl_mock_persona=pm \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-28/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-28/round-<N>/fidelity/SCR-28-desktop-published-1440
```
| Board | Page | Width | How reached |
|---|---|---|---|
| `SCR-28-desktop-internal` | `/work/W-2310` | 1440 | live URL |
| `SCR-28-mobile-internal` | `/work/W-2310` | 390 | live URL |
| `SCR-28-desktop-published` | `/work/W-2311` | 1440 | live URL |
| `SCR-28-mobile-published` | `/work/W-2311` | 390 | live URL |

### Fidelity (4 boards, D-83)
1. **Desktop boards at 1440.** Both have `scores.coverageWithExceptions` = 100 and `scores.visual` >= 90. A board at >= 70 but below 90 passes only with a D-83 visual waiver signed for that board in `fidelity-exceptions.json` and the UI reviewer's side-by-side reading finding no fixable gap. — verify: the commands exit 0; `round-<N>/fidelity/scores.txt` lists board, width, coverage, visual, pass and waiver.
2. **Phone boards at 390.** The same rule at `--width 390`. The phone boards are sparse, so extras are expected (Conflicts 4). — verify: same command, rows in `scores.txt`.
3. **Exceptions limited.** Each entry has `role`, `name`, `category`, `reason`, `approved_by` and maps to a Conflicts number; none covers a value the data supplies (name, date, count, receipt, owner, state). One fidelity run per round (D-64). — verify: file content; `build.md`.

### Page behaviour
4. **Internal from data.** `/work/W-2310` shows the status "Filed · Internal", the returned sentence, the "Created" table with each action's owner, due ("Unknown" when missing) and state, the Next sentence and "Open actions". Nothing is counted or composed by the frame: a fixture whose sentence says "3 actions" over two rows shows both unchanged. — verify: `tests/minutes-end.test.tsx`; page at 1440 and 390.
5. **Published from data.** `/work/W-2311` shows the sentence, three actions with "OWNER NEEDED" on the ownerless one (owner cell "No owner yet", due "Unknown"), "Sent to" with each person's name, channel and receipt word and time, Next and "Open actions". — verify: component test; page at 1440 and 390.
6. **Receipts are per person.** On W-2312 the received recipient reads Received, the uncertain one reads Uncertain, the `not_yet` one reads Not yet, and a recipient with `unknown` or an absent `receipt` reads Unknown or "Not yet" (never blank). The strings "Sent" and "Delivered" appear only for a recipient whose `receipt` is `received`. No aggregate "Delivered" is drawn by the frame; only the returned sentence and tag are. — verify: component test over all five `receipt` values; `grep -rnE "Delivered|delivery confirmed" frontend/src/features/workspace` finds none in code (fixtures only).
7. **Uncertain send keeps the lock (INV-RESEND).** On W-2312 the only action is `ReconcilePanel`; "Open actions" and "Open the minutes" (reads only) stay usable; any step control is `aria-disabled`; one reconcile press sends one POST to `/actions` and none to `/steps`, `/claim` or `/decision`; no new idempotency key; the same after a reload. — verify: component test with a recording `fetch`; e2e at 1440 and 390.
8. **No claim beyond the data.** A published fixture with every recipient `not_yet` and a sentence "Minutes v1 approved by Kemi Adebayo." shows no "emailed" or "delivered" text from the frame; the page contains only returned strings. — verify: component test of `document.body.textContent`.
9. **OWNER NEEDED and Unknown.** An action with no owner shows "OWNER NEEDED" only because the data returns that tag; no owner is guessed from the sentence or notes text (a fixture row text "owner Tunde" changes no owner cell). A missing due shows "Unknown", never 0, blank or "-". — verify: component test on W-2311/W-2314.
10. **Links only from data.** "Open actions" appears only when `workspace.links[]` supplies a `project_tab` target whose `tab` is a known project tab and whose `case_id` is a valid id; it links to `/projects/C-0211/actions`. W-2314 shows neither "Open actions" nor "Open the minutes". A target of an unknown kind or tab draws nothing. "Open the minutes" (W-2312) sends exactly one GET `/api/v1/documents/D-2304/versions/1`. — verify: component tests; recording `fetch`.
11. **Reaching internal.** On `/work/W-2301` choosing audience Internal and pressing "Confirm and create actions" sends the F-23 request (F-23 criterion 8 unchanged) and the reloaded item renders as the internal view; choosing Client still ends on the drafted view (W-2303). — verify: component test and e2e.
12. **Reaching published.** On `/work/W-2309/decide?task=T-2309` an approve sends the F-16 requests only; back on `/work/W-2309` the item renders as the published view. The work page sends nothing to `/steps`, `/claim` or `/decision`. — verify: e2e with recorded requests.
13. **Owner assignment (W-2313 only).** The "assign owner" control exists only on the item whose data lists the step; it uses the F-23 form, sends one POST with `expected_revision` = `workspace.revision` and a UUID key, leaves a blank owner out of `inputs`, shows a 422 under the field with focus there and keeps inputs, and reloads on 409. W-2310, W-2311 and W-2314 draw no such control. — verify: component tests. (If the builder drops this per the proposal table, `build.md` says so and this criterion is removed by the approver.)
14. **Wrong user, wrong tenant, signed out.** With `X-Mock-Scenario: 404` or `403`, `/work/W-2311` shows `NoAccessState` with no title, client, project or id and none of those strings in `document.body.textContent`. A 401 shows the signed-out callout with `next`. — verify: component tests.
15. **Nothing derived from `/me`.** Personas `pm`, `ceo` and `finance_lead` see the same controls for the same fixture; `git diff` adds no `/me` read under `frontend/src/features/workspace`. — verify: component test across personas; diff.
16. **Nothing sends, nothing files.** No request is made on load or on a timer (fake timers advanced 60 s); every e2e request goes to port 4792; the views contain no button that sends, resends, files or approves. — verify: recording `fetch`; e2e request log; `grep -rniE "resend|send again" frontend/src/features/workspace` finds nothing new.

### Quality
17. **Accessibility.** For W-2310 to W-2314 at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`); no sideways scroll; visible focus; 44px phone targets (D-92c); the table has real headers and keeps its meaning on a phone; receipts and state are text, not colour only; no wrapping button labels or tags on one line; live regions for the reconcile result; `prefers-reduced-motion` respected. — verify: `e2e/minutes-end.spec.ts`.
18. **Shared components and tokens.** New UI imports from `@/components`; no new local button, tag, table or panel. `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\("` on this feature's CSS diff returns nothing. — verify: diff and grep.
19. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**` or the protected paths, and no existing fixture edited. The `project_tab` key exists only in fixtures and `proposals.ts`, is checked on its own and stripped in `mock-contract.test.ts`; the fixtures otherwise validate with no stripping. — verify: `tests/mock-contract.test.ts`; `git diff --stat`.
20. **Mock matches the contract.** `minutes-end-mock.test.ts`: W-2310 to W-2314 and the sidecars load; the audience branch serves the internal sidecar for `internal` and `W-2301.next` for `client`; the W-2309 decide sidecar applies once; a repeated step key returns the stored reply with send count 1. — verify: `cd frontend && npx vitest run tests/minutes-end*.test.* tests/mock-contract.test.ts`.
21. **No overclaim.** `build.md` and the PR state the "What is sent" section: contract mock only, nothing sent, filed or created; D-LINE-WORKSPACE limits; the template is a test template. — verify: file content.
22. **Existing behaviour not weakened.** `tests/minutes*.test.*`, `tests/workspace*.test.*`, `weekly*.test.*`, `work-item*.test.tsx`, `decide*.test.tsx`, `response*.test.tsx`, `shell.test.tsx` and the matching e2e specs pass with no assertion removed or loosened; F-23's eight scores and F-21's scores do not drop. — verify: `delivery/checks.sh`; `e2e/minutes.spec.ts`; `git diff`.
23. **build.md evidence:** commands and results, the 4 scores and waivers, every exception with its Conflicts number, every frame change with its reason, every proposal and backend item, and the held list from "What is sent". — verify: file content.

## Out of scope
- The F-23 boards and steps (do not reopen); every other line; Approve and Return in-page (F-23 Conflicts 3 Option B).
- A real send, a resend control, a "mark delivered" control, choosing or editing recipients, deciding which audiences skip review, deciding when actions are created, filing internal minutes anywhere, real action or meeting records.
- A per-action page or link (`link.action_id`); closing, reassigning or editing created actions (the Actions tab is its own feature); computing counts or sentences.
- Alerts (D-ALERT-PROVIDERS), the real client template, a phone-only title or status field, section placement hints.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, `my-work/**`, new npm dependencies, changes to F-17's region driver.

## Assumptions
- Option A for Conflicts 1, 3, 4, 5, 6, 7, 8 unless answered. Reason: they keep everything the data holds visible and use the one frame; each difference is an exception, not a hidden change.
- `received` is the only receipt that may read Sent/Delivered. Reason: G-SCR25-1 (delivered means the provider confirmed that address) and INV-RESEND; the frame uses `RECEIPT_WORDS` ("Received") and the returned tag for the word.
- The published banner is a returned `text` item with a tag, as F-21's received view. Reason: smallest reuse of an existing, approved rendering.
- "Open actions" opens the project's Actions tab (`/projects/{case_id}/actions`). Reason: the board links to the Actions screen and the tab exists; no per-action page does.
- The internal view has no step and the published view has no step except reconcile. Reason: the boards draw none; owner assignment is offered only where a fixture lists it (W-2313), as a proof of the existing step form, not a board element.
- The mixed-receipt view returns a "Published · Delivery unconfirmed" label with tone `uncertain`. Reason: the boards draw only the success case; a received label over an uncertain recipient would break INV-RESEND. The wording is a fixture, not a frontend string.
- New ids W-2309 to W-2314 and ports 4791/4792. Reason: unused by any other spec or config.
- The fixtures are served to the `pm` persona for every board. Reason: the mock has no PMO Lead persona and the frame derives nothing from role (as F-23).
- Row id "ACT-0451" is part of the returned action text. Reason: the boards draw it inline and there is no separate id field in the table cell contract.
