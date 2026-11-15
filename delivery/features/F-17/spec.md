# The work item page renders a line workspace from the data alone and takes a step safely (contract mock only)

> Tasks: FE-WORKSPACE-FRAME (R-WORKITEM; acceptance A-WORKSPACE frontend half, with A-WORKITEM, A-DECIDE and the response tests kept green). Architecture: package `architecture/packages/v7` (the `workspace` block and E-WORK-STEP are already typed in `frontend/src/api/schema.d.ts:1693` and `:5217`; this feature changes no generated type). Design: approved canvas version 1794581312-b166 (`design.py check --project .` run by the coordinator on 14 Nov 2026: `APPROVED`, design_sha256 `9fad8d2d…`); Finance and Payroll canvas 1794579902-95a3 for the Finance anchors. Screens: none of its own (delivery/screen-coverage.md lists no SCR for the frame); anchor regions of SCR-25, 26, 28, 44, 45, 46, 49, 52 and Finance SCR-53 to 58 (see Conflicts 1). Decision consumed: D-LINE-WORKSPACE (proposal).

## Conflicts with the boards (for the design engineer, before the build)

1. **Region-level fidelity check (needs your sign-off; the frame has no board).** `fidelity.mjs` scores one whole board against one URL and has no region option, so it cannot gate a frame that is only a part of many boards. Proposal:
   - **What is checked.** Ten named anchor regions, listed in `delivery/features/F-17/regions.json` (builder writes it, you confirm). One per section kind and one for the step form:

     | Region | Board (starting anchor; builder fixes the exact heading text) |
     |---|---|
     | text with cites, and the step button row with its consequence sentence ("Approving sends this exact version") | SCR-25 `review` |
     | recipients with receipts, and timeline ("What happened") | SCR-25 `received` |
     | table and suggestions (REQUIREMENT / SUGGESTED ANSWER / STATUS, "Suggested by Tola") | SCR-26 `review` |
     | checklist with owner and due, agent working list | SCR-28 `suggesting`; SCR-44 `readiness` |
     | findings | SCR-49 `blocked` |
     | facts | SCR-46 `evaluating` (or the facts strip of the SCR-45 `signatures` board if that is the clearer one) |
     | figures with Unknown | Finance SCR-53 `quarantined` and the closest of SCR-54 to 58 |
     | step form (fields, help, error under the field) | SCR-26 `edit` |
     | restricted section | the board region that draws a restricted label, builder to name it (if no board draws one, it takes an exception to be listed) |
     | saved, queued, uncertain and stale notices | the matching `received`, `returned` or `invalid` region on SCR-25 |
   - **How.** A small driver `delivery/features/F-17/round-<N>/fidelity/region-check.mjs`. For each region it opens the board render and the frame fixture page, finds the region root by its heading text on both sides, then reuses the tool's own `extractInBrowser`, `compare` and `visualInBrowser` (all exported from `/Users/Hunchoo/software-factory/packages/design/fidelity/`) on that subtree only. Widths 1440 and 390, board file chosen by width (`-desktop-` or `-mobile-`).
   - **Pass mark per region and width.** Structure and text coverage 100% after approved exceptions, and visual >= 85. (Lower than the 90 on whole boards because only the region is compared and the surrounding page differs; if you want 90, say so.) Regions are not required to match the board's page chrome, title or copy; only the section's own elements.
   - **Fixtures carry the board copy** so text can match (`W-20xx` anchors copy the board wording as the backend would return it). This proves the renderer, not any line's content.
   - **If the driver cannot isolate a subtree** with those exports, the builder says so in build.md and the fallback is a reviewer-signed side-by-side crop per region (`side-by-side.png`) with the same 100% structure list done by hand. You decide whether that is acceptable.
   - **Not checked here:** whole-board fidelity of any line page. That gate applies at each line task.
2. **One `h1`.** Boards draw the line page with its own title as the page title. The frame keeps the work item's `h1` (`.shell-title`, F-14) and shows `workspace.title` as an `h2` only when it differs from the item title. Recommend: keep, since the page shell is F-14's and one `h1` per page is a rule; the line task can change it with its own board.
3. **Standard overview blocks stay.** On a work item that returns `workspace`, the existing header, tabs, facts strip, station track and task panels stay; the workspace sits in the Overview tab after them. Some line boards draw a page without those blocks. Recommend: keep; each line task decides what to hide with its own board, using data, not a frame flag.
4. **Decision steps leave the page.** A step carrying `task_id` is a link to the existing decision page, not an inline approve. Boards for SCR-25 `review` draw Approve in the page. Recommend: link; claim and decide stay in F-16's code. A line task may propose inline later.
5. **Tone to colour.** Boards use colours the spec cannot reproduce from names; tags use the existing `psl-tag--<tone>` classes, tokens only. Any visible colour difference is an exception candidate, not a hard-coded value.
6. **Frame items** (top bar, signed-in name, phone back link name, Start work) are exceptions, as in F-14 and F-16.

## D-LINE-WORKSPACE limits (binding on the PR description and build.md)
- D-LINE-WORKSPACE is `proposed` and has no recorded approval. F-17 consumes it only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g), (i)): **contract mock only**.
- **The backend developer may change or refuse any field** of `workspace` or E-WORK-STEP. Anything the frame cannot render from the schema is a contract proposal in build.md; the frame never extends the contract locally.
- **Nothing is released.** No real send happens. The PR and build.md must not claim a real backend, "no duplicate send" as verified, or that any line works.

## Summary
- When E-WORK-ITEM returns a `workspace`, the work item Overview renders it from the data alone: header, nine section kinds, per-item status, and the steps exactly as returned. A work item without `workspace` is unchanged.
- Restricted sections show only their label, unknown money and dates read "Unknown", and `as_of`, `coverage` and the sample label show when returned (INV-RESTRICTED, INV-UNKNOWN, INV-SAMPLE).
- Steps render from descriptors: form fields reuse the Start work field components; the step write (E-WORK-STEP) carries CSRF, `expected_revision`, one idempotency key per attempt, and is never retried by the client.
- `done` reloads, `queued` shows waiting and reloads, `effect_uncertain` shows the uncertain state and offers reconcile only, 409 follows the existing stale flow, 422 lands on the named field.
- Decision steps (`task_id`) go to the F-16 decision page; responses stay on E-RESPONSE and reconcile on E-WORK-ACTION. All on the contract mock.

## Context
- Page: `frontend/src/features/work-item/WorkItemView.tsx:134` (`WorkItemView`, tab overview renders `WorkItemOverview` at `:172`); `useWorkItem.ts` loads and reloads the item. `app/work/[id]/page.tsx` is the route. No `workspace` is read anywhere in `frontend/src` except the generated `schema.d.ts`.
- Field components: `frontend/src/features/start-work/IntakeField.tsx` (`IntakeField`, props `lineKey, field, value, onChange, parent, parentLabel, readOnly, error, note`), value shapes and checks in `intake.ts` (`buildIntake`, `parentValue`, `dependentsOf`, `newIdempotencyKey`), `RecordPicker.tsx`, types in `types.ts`. The workspace step `fields[]` carries the same descriptor kinds (D-START-INTAKE) plus `value`, `multiple` and `restricted`, so a thin adapter type is expected.
- Decide: `frontend/src/features/decide/` (`useDecision.ts` claim and decide, route `/work/[id]/decide?task=<id>`). Response and reconcile: `frontend/src/features/response/` (`ReconcilePanel`, `workAction` in `api.ts`, `asResponseItem`).
- Shared client: `frontend/src/api/client.ts` (`api`, `call`, CSRF), `errors.ts` (`ApiError` kinds `unauthenticated, forbidden, not_found, stale, invalid, server, network`).
- Mock: `frontend/mock/server.mjs` serves `fixtures/work/<id>.json`; F-09 added `mock/response.mjs` with its own operations and reset. Free fixture ids: `W-20xx` (W-17xx F-14, W-19xx F-16).
- Page chrome precedent: `frontend/src/app/frame-fixtures/phone-back/` (a test route). This spec does not add one; e2e uses the real `/work/W-20xx` route on the mock.

## Contract

### Read: E-WORK-ITEM `workspace` (unchanged, proposal)
The renderer reads only `workspace` and the existing item fields. Rules:
1. **Hide when absent.** Every optional field not returned is not drawn. No default text, no "N/A".
2. **Header.** `subtitle`, `status` (tag by `tone`), `byline`, `version.label`, `context.crumbs` (a trail, last item current; `crumb.value` is never turned into a link), `agent_note` (agent name and `lines`). `title` as in Conflicts 2.
3. **Sections in returned order**, by `kind`, with `title`, `note`, `agent`, `as_of`, `coverage`, `total`:
   | kind | Draws |
   |---|---|
   | `facts` | label/value pairs from items (`label`, `value`, `money`) |
   | `table` | `columns[]` header; each item's `cells[]` by `column` and the column's `kind`: `text`, `money`, `date`, `tag`, `reference`, `integer`. A cell `link` renders only as an app path built from `work_id`, `document_id`, `case_id` or `evidence_id` through `isAppPath`, else as plain text |
   | `checklist` | `text`, `detail`, `status` word and mark, `owner`, `due`, `held_by` (with "You" when `is_you`) |
   | `findings` | `text`, `detail`, `severity`, `cites` with `cite_label` |
   | `suggestions` | `text`, `detail`, `agent`, `cites`, `tag`, per-item `steps` |
   | `recipients` | name `text`, `channel`, `receipt` word, `at` as WAT time |
   | `figures` | `label`, `money`/`value`, `detail` |
   | `text` | `text` paragraphs, `cites` with `cite_label` |
   | `timeline` | `at` (WAT), `text`, `agent` or owner, `detail` |
4. **Words for enums** (frontend-owned, in one file `labels.ts`): item `status` done, now, next, not_yet, held, blocked, unknown, not_applicable; `receipt` received, not_yet, uncertain, failed, unknown; `severity` high, medium, low, info. Status and receipt are always words as well as colour. An enum value outside the list renders as the raw value, never hidden.
5. **INV-UNKNOWN.** `money.unknown` or `due.unknown` or `date.unknown` or a missing amount reads "Unknown". Never 0, never blank, never a dash. An unknown `receipt` reads "Unknown", and `uncertain` reads as uncertain, never as received.
6. **INV-RESTRICTED.** A section or item with `restricted: true` draws `restricted_label` (else "Restricted") and no rows, `cites`, `detail` or `money`, even if the response carries them. A `restricted` cell draws "Restricted".
7. **INV-SAMPLE.** The existing `SampleLabel` shows when the item is `sample: true`.
8. **as_of and coverage.** Drawn under the section title when returned ("As of 14 Nov, 10:40 WAT", the `coverage` text verbatim). Dates use the existing `formatWat`.
9. **Paging and filters.** `next_cursor` draws a "Show more" control, `total` and `filters` a filter group, only when returned. Neither can be actioned with a documented endpoint today (no section-page endpoint exists in the contract); they render as disabled controls with the line "More rows aren’t available yet." and send nothing. Recorded in build.md as a contract proposal (a section-page read).
10. **Empty.** A section with `items: []` draws its title and "Nothing here yet." (frontend-owned sentence). A workspace with no sections and no steps draws only its header.
11. **Eligibility is never derived from `/me`.** Nothing in the renderer calls `/me` for roles.

### Steps: what is offered
- Step controls render **only for steps in `workspace.steps`**, and only when `workspace.revision` is a number (without it, no write control: the revision is never guessed).
- Placement by `applies_to`:
  - `workspace` (or absent): button row under the header, order as returned. `emphasis` maps to primary, secondary, danger button classes.
  - `item`: a control on each item whose `steps[]` contains the step key.
  - `items`: a checkbox on each item whose `steps[]` contains the key, and one button acting on the checked items, disabled with zero checked. `item_ids` = the checked ids in item order.
- A step with `disabled_reason` is drawn as an unavailable button (`aria-disabled`, not focus-trapping) with the reason as visible text tied by `aria-describedby`. Activating it sends nothing.
- `consequence` is shown as a sentence next to the button and again in the form. `sends: true` adds the words "This sends to the client." only when `consequence` does not already say so (the sentence is the frontend's; the fact `sends` is the backend's). `claim_required` is shown as "Claim it first" text and is only meaningful for `task_id` steps.
- **A step with `task_id` is a decision.** It renders as a link to `/work/{id}/decide?task=<task_id>` (the F-16 page). The workspace never sends E-WORK-STEP, E-TASK-CLAIM or E-TASK-DECIDE for it. If `disabled_reason` is present it is drawn as above and the link is not active.
- A step with no `fields` and no `confirm` submits on press. A step with `fields` or `confirm` opens an inline form panel under the control (focus moves to its heading; Escape or Cancel closes it with no request).

### Step form
- Built with `IntakeField` per `steps[].fields[]`, kinds exactly as D-START-INTAKE: `text, long_text, date, date_range, period, datetime, integer, money, choice, record, records, evidence, display`. `required`, `help`, `placeholder`, `options`, `depends_on`, `multiple` are honoured as the Start work drawer honours them. `display` is shown and never sent. `restricted` fields draw no value. Record fields read E-LINE-OPTIONS as Start work does; evidence fields upload through the existing evidence upload, giving `evidence_ids`.
- Client-side checks are only those the descriptor states (`required`, `maxLength` 2000 on `note`, integer shape). Nothing else is invented.
- A step has an optional `note` field only if its descriptor list contains a field named `note`; the form does not add one of its own. If the descriptor has no `note` field, `note` is not sent.
- `confirm` is the text of a checkbox-free confirmation line above the submit button; the submit button label is the step `label`.
- Values are shaped by `buildIntake`-compatible helpers. If an exported helper needs widening for the step field type, that is the only allowed edit in `features/start-work/**`: type-only, no behaviour change, listed in build.md, Start work tests unchanged.

### E-WORK-STEP `POST /api/v1/work/{work_id}/steps` (frontend consumer; mock handler new)
| | |
|---|---|
| Request | `{expected_revision: workspace.revision, step: key, item_ids?: string[], inputs?: {name: value}, evidence_ids?: string[], note?: string (<= 2000), idempotency_key}`; CSRF header from the shared client. `case_revision` is sent only if a step input of kind `record` names a case and the Start work helper supplies it; otherwise omitted. |
| 200 | `{work_id, state, revision, outcome: done | queued | effect_uncertain, message?}` |
| Errors | 401 signed-out callout with `next` = this page; 403 and 404 `NoAccessState` (nothing about the item shown); 409 stale; 422 `{code, message, fields?[{name,message}]}`; 5xx and network. |
| Permission, tenant | Backend decides per record and per step. The mock cannot enforce; it returns what the fixture script says. The frame never decides who may act. |
| Idempotency | Backend promise (same key, same result, no second send) is **not built**. The frame sends the key and trusts none of it. The mock keeps an in-memory map `key -> result` and a send count so tests can prove one send on the mock only. |
| Versioning | `expected_revision` is the `workspace.revision` of the item last shown. |

**One attempt, one key.**
- A key is made (`newIdempotencyKey()`) when the form opens, or on first press for a step with no form, and kept in a ref for that attempt.
- Repeat of the same attempt (a double click, a manual "Try again" after a network failure on a step that does not send) reuses the same key. A double click sends one request: the button is disabled and a ref guard blocks a second call before React re-renders. While in flight the button reads "<label>…" and is `aria-disabled`.
- A **new** key only for a new attempt: after `done`, after a definitive 409 or 422 (nothing was written; as Start work does), or when the form is closed and reopened.
- Another step is not callable while one is in flight (one write at a time per page).
- **No automatic retry** of any write, ever, including StrictMode double effects.

**Outcomes.**
| Response | Page does |
|---|---|
| `done` | Closes the form; reloads E-WORK-ITEM once; shows a polite live line "Done: <step label>." (the returned `message` if present). The new `workspace.revision` replaces the old. |
| `queued` | Shows "Waiting: <message or 'This step is queued.'>" in a live region, reloads once. No resend. The step stays unavailable only if the reloaded workspace stops offering it. |
| `effect_uncertain` | Shows the uncertain state (warning callout) with the returned `message`. Submit for **every** step on this page is off, no resend, no new key. The page reloads once and mounts the existing `ReconcilePanel` (E-WORK-ACTION) if the reloaded item carries `reconcile` and `allowed_actions` lists `reconcile`; otherwise it says "We are checking what happened. Nothing was sent again." and offers only a reload. INV-RESEND. |
| 409 | Keeps what is shown (inputs kept in the form), reloads once, shows "This changed while you were working. Showing version <revision>." with the form re-based on the new `workspace.revision`. Never repeats the write automatically. A fresh key for the next deliberate press. |
| 422 | Maps each `fields[].name` to its input (error under the control, `aria-invalid`, `aria-describedby`, focus to the first). An unnamed field message or no `fields` shows the server `message` at the top of the form. Inputs and note kept. New key. |
| 401 | Signed-out callout with `next` = this page. |
| 403 | Reload; the page shows what the reloaded item allows (usually the step gone) with "You can’t take that step." If the reload also gives 403 or 404, `NoAccessState`. |
| 404 | `NoAccessState`. |
| 5xx or network | Reload once to show what happened. Message "We couldn’t confirm this step. Check the page before trying again." For a step with `sends: true`: no resubmit control (INV-RESEND), the reload only. For a step without `sends`: the form stays with the same key and a manual "Try again" is allowed. |

### Screen states (page with a workspace)
- **Loading:** existing `LoadingState`. **Error / no access / signed out:** as the work item page today.
- **Success:** header, sections in order, step controls. **Empty:** per Contract 10. **Restricted, unknown, sample:** per Contract 5 to 7.
- **Refresh failed after a write:** the existing "We couldn’t refresh this item. Showing what we had at <time>." callout, step controls off until a reload works.

### Fixtures (`frontend/mock/fixtures/work/`, new; existing files byte-for-byte unchanged)
All validate against the generated 200 schema for E-WORK-ITEM. They copy board wording for the anchor regions. Scripted step outcomes live in a sidecar `W-20xx.steps.json` (`{"<step key>": {"status": 200|409|422|500, "body": {...}}}`, default is `done`; a successful `done` bumps the revision and swaps in `W-20xx.next.json` if present, in memory, cleared by `POST /__mock/reset`).

| Id | Shows |
|---|---|
| W-2001 | Weekly update, board copy: facts, text with cites, recipients with receipts (`received`, `not_yet`, `uncertain`, `failed`, `unknown`), timeline, steps (workspace scope with `sends` and consequence "Approving sends this exact version"; one with `disabled_reason`) |
| W-2002 | Table (all six column kinds), suggestions with per-item `steps`, items-scope step with `item_ids`, filters and `next_cursor` |
| W-2003 | Checklist (all `status` values, owner, due, held_by incl. `is_you`), findings (all severities) |
| W-2004 | Figures with `money.unknown` and `due.unknown`, a `restricted` section, a `restricted` item, `as_of`, `coverage`, and the item `sample: true` |
| W-2005 | Empty: a section with `items: []`, and a workspace with no sections and no steps |
| W-2006 | Step form, every field kind, `required`, `depends_on`, `display`; step script 422 with `fields[]`; step with `confirm` |
| W-2007 | Step scripts: `queued` outcome; 409 with `W-2007.next.json` (revision 4 to 5); 500 on a `sends` step and on a non-`sends` step |
| W-2008 | `effect_uncertain` outcome; the reloaded item (`.next.json`) carries `reconcile` and `allowed_actions: ["reconcile"]` |
| W-2009 | A step with `task_id` (links to `/work/W-2009/decide?task=T-2009`, with `W-2009` also a valid decision fixture copied from W-1901 so the link works) |
| W-2010 | An item with no `workspace` that is a copy of an existing fixture, proving unchanged output |

Mock: new `frontend/mock/workspace.mjs` (handler, idempotency map, log at `GET /__mock/workspace-log`, reset) with a minimal hook in `mock/server.mjs`, as F-09 did for `response.mjs`. The handler validates the request body against the generated schema (422 on a bad body, 409 if `expected_revision` differs from the current revision, 404 for an unknown step key).

## Lanes
- **Frontend lane (builder)** owns:
  - New `frontend/src/features/workspace/**` (renderer, section components, `labels.ts`, step form, `useWorkspaceStep.ts`, `workspace.css` with token variables only).
  - Mount only: a minimal edit to `frontend/src/features/work-item/WorkItemOverview.tsx` (and `WorkItemView.tsx` if the reload hook must be passed). No other `work-item/**` edit; `work-item.css` is not touched.
  - `frontend/mock/workspace.mjs`, the one-line-class hook in `frontend/mock/server.mjs`, `frontend/mock/fixtures/work/W-2001` to `W-2010` and their sidecars.
  - Tests: `frontend/tests/workspace.test.tsx`, `workspace-step.test.tsx`, `workspace-mock.test.ts`, `mock-contract.test.ts` (new fixtures only), `frontend/e2e/workspace.spec.ts`.
  - Factory files: `delivery/features/F-17/regions.json`, `fidelity-exceptions.json` (provisional until the design engineer signs), `round-<N>/fidelity/**`.
- **Shared, read only (import, do not edit):** `frontend/src/features/start-work/**` (type-only widening allowed as described), `frontend/src/features/decide/**`, `frontend/src/features/response/**`, `frontend/src/shell/**`, `frontend/src/features/my-work/**`, `frontend/src/api/**` (incl. `schema.d.ts`), `frontend/src/styles/**`, `frontend/package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, `architecture/**`, `design/**`, `apps/**`, and protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. Backend items to record in build.md, not blocking: E-WORK-STEP and `workspace` are `unimplemented`; the idempotency promise is unbuilt (COORDINATOR-HANDOFF.md, PMO-0-2); a section-page read is missing (Contract 9).
- **Integration owner:** the coordinator. F-14, F-16 and F-09 share `features/work-item/**`, `decide` and `response`; whichever merges second merges the current base and reruns `delivery/checks.sh` and the 390 e2e.
- **Ports:** app 4701, mock 4702. E2E: `cd frontend && E2E_PORT=4701 MOCK_PORT=4702 npx playwright test e2e/workspace.spec.ts` with `timezoneId: 'Africa/Lagos'`. Score on a production build (`next build`, `next start -p 4701`, mock on 4702). Delete `frontend/test-results` after, and check `df` first.
- **Review routing:** technical (sonnet); security (opus; a write that can send); UI (opus, using the region-level check in Conflicts 1); UX (sonnet); QA (opus). Product acceptance is not required. Medium risk.
- **Size and split.** Estimated 2,500 to 3,500 lines of code and tests: close to the one-PR limit. Build as one PR with the criteria in two parts. If the coordinator splits (recommended if round 1 does not finish both parts), the order is fixed: **Part A (read-only)** = criteria 1 to 11 plus fixtures W-2001 to W-2005 and W-2010, no step controls rendered; **Part B (step form and write)** = criteria 12 to 24 plus fixtures W-2006 to W-2009, the mock handler and the step e2e. Part A merges first. Do not split by line.

## Acceptance criteria

### Part A: render
1. **Unchanged without a workspace.** W-2010 (and W-1701, W-1901) render exactly as before. — verify: `tests/work-item.test.tsx`, `work-item-board.test.tsx`, `decide.test.tsx`, `response.test.tsx` pass unchanged; a new test asserts no workspace element on W-2010.
2. **Header from data.** On W-2001 the page shows the returned `subtitle`, status tag word, `byline`, `version.label`, crumbs and `agent_note` lines; each absent field on W-2005 draws nothing. There is exactly one `h1` (the work item title); `workspace.title` is an `h2` only when different. — verify: component test on W-2001 and W-2005; e2e counts `h1`.
3. **Nine section kinds.** W-2001 to W-2004 draw each of facts, table, checklist, findings, suggestions, recipients, figures, text, timeline with the elements in the Contract table, in returned order. Table cells render by column kind; a cell `link` becomes an anchor only for an app path. — verify: `tests/workspace.test.tsx`, one test per kind; `<a>` count for a crafted `link` of `https://x.example` is zero.
4. **Item vocab as words.** Every item `status`, `receipt` and `severity` value on W-2003 and W-2001 appears as a word in text (not colour alone); `receipt: uncertain` never reads "Received". An unknown enum value renders raw. — verify: component tests; axe in criterion 11.
5. **INV-UNKNOWN.** On W-2004 an unknown amount, `due.unknown`, and an unknown date read "Unknown"; the page contains no "0", "₦0", "-" or empty cell in their place. — verify: component test over the DOM text of those cells.
6. **INV-RESTRICTED.** On W-2004 a `restricted` section shows only `restricted_label` and no row text, no `cites`, no `money`, even though the fixture also carries data for those rows (the fixture includes it deliberately, to prove it is not drawn). A restricted cell reads "Restricted". — verify: component test that none of the fixture's hidden strings appears in `document.body.textContent`.
7. **as_of, coverage, sample.** As_of (WAT), `coverage` text and the sample label show on W-2004; absent elsewhere. — verify: component test.
8. **Empty.** W-2005 shows "Nothing here yet." for an empty section and nothing else for a workspace with no sections or steps; no exception is thrown. — verify: component test.
9. **Paging and filters inert.** W-2002 shows filters, total and "Show more" disabled with "More rows aren’t available yet."; activating them sends no request. — verify: component test with a recording `fetch` (only the GET E-WORK-ITEM calls).
10. **Fixtures valid, old untouched.** Every `W-20xx` fixture validates against the generated schema; `git diff --stat` shows no edit to any existing fixture. — verify: `tests/mock-contract.test.ts`; `git diff --stat`.
11. **Accessibility and layout (Part A).** For W-2001 to W-2005 at 1440 and 390: no axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`), no sideways scroll (`scrollWidth <= viewport`), visible focus rings, 44px targets, tables scroll inside their own container at 390, no animation under `reducedMotion: 'reduce'`. — verify: `e2e/workspace.spec.ts`.

### Part B: steps and write
12. **Steps only as returned.** Controls appear only for steps in `workspace.steps`; none when `workspace.revision` is absent; none are derived from `/me` (a persona with any role sees the same controls for the same fixture). `disabled_reason` shows as text, the control is `aria-disabled`, and activating it sends nothing. — verify: component tests with a recording `fetch`.
13. **Scopes.** `workspace` steps in the row; `item` steps on the right items only (`steps[]` contains the key); an `items` step is disabled with zero checked, and sends `item_ids` = the checked ids in item order. — verify: component test reading the recorded body (W-2002).
14. **Form from descriptors.** On W-2006 every field kind renders through `IntakeField`, `display` is shown and never sent, `required`, `help`, `depends_on` behave as in Start work, and only descriptor checks run client-side. A step with `confirm` shows its text above the submit. `restricted` field draws no value. — verify: component test; `git diff --stat` shows no behavioural edit in `features/start-work/**`.
15. **Write request shape.** Submitting a W-2006 step sends exactly one POST `/api/v1/work/W-2006/steps` with the CSRF header, `expected_revision` equal to `workspace.revision`, `step`, `inputs` shaped per kind, `idempotency_key` (a UUID), `evidence_ids` only if an evidence field was filled, `note` only if a `note` field exists and is non-blank; a `note` over 2000 characters is refused before any request. The body validates against the generated request schema. — verify: `tests/workspace-step.test.tsx` and `workspace-mock.test.ts`.
16. **One key per attempt; no double send.** A double click sends one request; while pending the button is disabled and reads "<label>…". Opening the form twice gives two different keys; a manual "Try again" after a network failure on a non-`sends` step reuses the first key; a key is renewed after `done`, 409 and 422. Under React StrictMode no request is sent twice. — verify: component tests; e2e reads `GET /__mock/workspace-log` (the mock's send count for that key is 1). This is mock evidence only, not proof of backend idempotency.
17. **No automatic retry.** For 500, network failure, 409 and `effect_uncertain` the count of POSTs to the steps URL stays 1 until the person presses again, after waiting beyond any plausible timer (fake timers advanced by 60s). — verify: component tests.
18. **done and queued.** `done` reloads once and shows the live "Done" line with the new revision; `queued` shows "Waiting: …" and reloads once; neither resends. — verify: tests on W-2001 and W-2007.
19. **effect_uncertain (INV-RESEND).** On W-2008 `effect_uncertain` shows the uncertain callout with the returned `message`; every step control on the page is off; after the reload `ReconcilePanel` is shown and its answer goes to E-WORK-ACTION (one POST to `/actions`, none to `/steps`); no new key or resend is possible. When the reloaded item has no `reconcile`, the page says "We are checking what happened. Nothing was sent again." and offers a reload only. — verify: component test and e2e with the recorded requests.
20. **409.** On W-2007 a 409 keeps the typed inputs, reloads once, shows "This changed while you were working. Showing version 5.", re-bases `expected_revision` to 5, and sends nothing until the next deliberate press, with a new key. — verify: component test and e2e.
21. **422.** On W-2006 a 422 with `fields[]` puts each message under its input (`aria-invalid`, `aria-describedby`), focuses the first, keeps all inputs, shows an unnamed message at the top, and renews the key. — verify: component test.
22. **Other errors.** 401 shows the signed-out callout with `next` = this page. 403 reloads and shows "You can’t take that step.". 404 shows `NoAccessState` with no id or title. A 500 on a `sends` step offers no resubmit; on a non-`sends` step a manual Try again with the same key. — verify: component tests.
23. **Decision steps.** The `task_id` step on W-2009 is a link to `/work/W-2009/decide?task=T-2009`; following it opens the F-16 page; the workspace itself sends no request to `/steps`, `/claim` or `/decision`. — verify: component test with a recording `fetch`; e2e navigates and sees the decision page.
24. **Part B accessibility.** For W-2006 to W-2009 at 1440 and 390: axe clean, no sideways scroll, focus moves to the form heading on open and back to the step control on close or Escape, errors are announced (`role="alert"` or an associated live region), live regions for done, waiting and uncertain, 44px targets, reduced motion respected. — verify: `e2e/workspace.spec.ts`.

### Both parts
25. **Region-level design check.** After the design engineer signs Conflicts 1: every region in `regions.json` passes at 1440 and 390 with structure and text coverage 100% after exceptions and visual >= 85, via `region-check.mjs`. `fidelity-exceptions.json` entries each carry `role`, `name`, `category`, `reason`, `approved_by` (`"builder proposal, pending design engineer"` until confirmed), and none covers a value the data can supply. — verify: `round-<N>/fidelity/region-scores.txt` and per-region reports; build.md maps exceptions to categories.
26. **Tokens only.** `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" frontend/src/features/workspace/*.css` returns nothing. — verify: the command.
27. **Contract is not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**` or `design/**`; every field the renderer wanted but the schema lacks is listed in build.md as a contract proposal. — verify: `git diff --stat` and build.md.
28. **No real send, no overclaim.** Every request in the e2e run goes to the mock (4702); the PR description and build.md state D-LINE-WORKSPACE limits and do not claim idempotency or a real backend. — verify: build.md content and the recorded requests.
29. **Existing tests not weakened.** `tests/work-item*.test.tsx`, `decide*.test.tsx`, `response*.test.tsx`, `start-work*.test.*`, `shell.test.tsx`, `e2e/work-item*.spec.ts`, `e2e/decide*.spec.ts`, `e2e/response.spec.ts`, `e2e/start-work.spec.ts` pass; no assertion removed or loosened. — verify: `delivery/checks.sh`; `git diff` on those test files shows none.
30. **New tests exist and run in checks.** `workspace.test.tsx`, `workspace-step.test.tsx`, `workspace-mock.test.ts` and `e2e/workspace.spec.ts` exist and run in `delivery/checks.sh`. — verify: file presence and the run output in build.md.

## Out of scope
- Any line-specific page, route, copy or screen state, and any rule about which sections or steps exist (backend-composed). FE-LINE-WEEKLY, FE-RFP-RESPONSE, FE-COSTING, FE-LINE-MINUTES, FE-ISSUE, FE-CHANGE, FE-DELIVERY-*, FE-EMERGENCY-ESCALATION, FE-LEADERSHIP-REPORT, FE-PAYMENTS, FE-FIN-* and FE-DECIDE-VARIANTS are later tasks.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`. No local extension of the contract.
- Inline approve, claim or decide in the workspace; a decision step is a link.
- A real section-page read for `next_cursor` and `filters`; real uploads beyond the existing evidence component; client-side sorting, searching or recalculation of any figure.
- `src/shell/**`, `my-work/**`, the decide page layout, `work-item.css`.
- Real sends, real providers, and any claim that duplicate sends are prevented by the backend.
- Whole-board fidelity scores for any line board.
- A new route or test page; no new npm dependency.

## Assumptions
- Renderer lives in a new `features/workspace/` and only the mount is edited in `features/work-item/**`. Reason: keeps the shared F-14 files small; readiness says "mounted on features/work-item".
- Fixtures use `W-2001` to `W-2010` and the real `/work/W-20xx` route rather than a separate frame test page. Reason: a second route would duplicate the page chrome; the mock already serves fixtures by id.
- Workspace renders in the Overview tab after the standard blocks, with one `h1` (Conflicts 2, 3). Reason: the least change to F-14's page; the line tasks can adjust with their own boards.
- A decision step is a link to the F-16 page. Reason: readiness says reuse the F-16 claim/decide code and not reimplement; the page already owns it.
- A step with no fields and no `confirm` submits on press. Reason: the descriptor offers nothing to ask; `confirm` and `consequence` already carry the warning.
- After a network or 5xx failure on a step with `sends: true`, no resubmit control is offered. Reason: INV-RESEND is stricter than the idempotency promise, which is unbuilt; non-`sends` steps may be retried manually with the same key.
- Region check pass mark visual >= 85 and structure 100% after exceptions. Reason: a region is compared without its page; the design engineer may raise it (Conflicts 1).
- Paging and filters are inert and labelled. Reason: no section-page endpoint exists; inventing one is a contract change.
- "Nothing here yet.", "More rows aren’t available yet.", "Done:", "Waiting:" and the uncertain/stale sentences are frontend-owned neutral status text, not business rules. Reason: sources are silent; the approver may escalate any wording to the design engineer.
- Ports 4701 and 4702 are free. Reason: F-16 uses 4601 to 4603; no other spec names 47xx.
- Approver should confirm: whether the build goes as one PR or as the A/B split (Lanes, Size and split).
