STATUS: READY
COMMIT: 1432023f985798659f2cc4342c3a745936d30324
BUILDER: builder
LANE: full

## Summary
- When E-WORK-ITEM returns a `workspace`, the work item's Overview now draws it from the data alone: the header, all nine section kinds in the order returned, words for every status, receipt and severity, Unknown for unknown money and dates, restricted sections showing only their label, and inert paging and filters (Part A, 0464551).
- Steps show only as `workspace.steps` returns them, and only when `workspace.revision` is a number. They are placed by `applies_to`. A step with fields opens a form built with IntakeField. The E-WORK-STEP write sends one key per attempt and is never retried by the page. done, queued, effect_uncertain, 409, 422, 401, 403, 404 and 5xx each get their own state, and a decision step is a link to the F-16 decision page (Part B, 92df846).
- New mock `mock/workspace.mjs` handles E-WORK-STEP with fixture scripts, an idempotency map and `GET /__mock/workspace-log`. Fixtures W-2001 to W-2010 are new; no existing fixture changed.
- Region-level design check (D-59) built and run (1432023). Coverage is 100% in all 26 region and width runs once the proposed exceptions are counted. Visual is >= 85 in 7 runs, all at 1440. Every 390 run is below 85 (see Blocked/open decisions below).
- **D-LINE-WORKSPACE limits:** contract mock only. D-LINE-WORKSPACE is `proposed` and has no recorded approval. The backend developer may change or refuse any field of `workspace` or E-WORK-STEP. Nothing is released and no real send happens. This build does not claim a real backend, does not claim the idempotency promise (same key, same result, no second send) is verified, and does not claim any line works. The "one send per key" evidence below comes from the mock only.

## Changes
- `frontend/src/features/workspace/labels.ts`: types derived from the generated schema. Enum words, tone to existing `psl-tag--*` classes, money and date text (null means Unknown), and `refPath`: a link only for a plain `work_id` or `case_id`, and any URL stays text. Frontend-owned sentences.
- `Sections.tsx`: one renderer per section kind, plus restricted, empty, as_of and coverage, inert filters, total and Show more, and a table scroll frame. It has hooks for item, items and form controls.
- `Workspace.tsx`: the header (the page keeps one h1; the workspace title becomes an h2 only when it differs from the item title), the live region, the notices, the step rows, item and items controls and the forms.
- `Steps.tsx`: step control and consequence sentence. Disabled steps use `aria-disabled` with their reason. A `task_id` step is a link to `/work/{id}/decide?task=…` with "Claim it first".
- `StepForm.tsx`: fields from the descriptor. Kinds IntakeField draws go through IntakeField. Money uses a ₦ box: blank sends `{currency, unknown: true}`, never 0. Evidence uses the existing ProofField and useEvidenceUpload. Restricted fields draw "Restricted". A field named `note` is sent as the top-level `note`. Client checks are only required, the 2000-character note and the integer shape. Escape and Cancel close the form and return focus to the step.
- `useWorkspaceStep.ts`: the write. A synchronous ref guard, one write at a time, one key per attempt, and no timers. It reads the 422 `fields[]` from the raw reply, because `call()` drops them.
- `usePageReload.ts`: re-reads the item once, quietly, after a write. The page draws whichever read is newer, so the header, the facts and the existing ReconcilePanel update while the form keeps its inputs. 401, 403 or 404 on the re-read shows the signed-out or no-access state for the whole page.
- `workspace.css`: token variables only.
- `features/work-item/WorkItemOverview.tsx` (+3 lines): mounts `<Workspace>` after the standard blocks and passes the page hook through.
- `features/work-item/WorkItemView.tsx` (+11/-4): calls `useWorkspacePage`, draws the newer item, handles access lost on a step, and shows the existing refresh-failed callout for a failed re-read. (Spec Lanes allow this file "if the reload hook must be passed".)
- `frontend/mock/workspace.mjs`, plus a 3-line hook and reset in `mock/server.mjs`.
- Fixtures: `frontend/mock/fixtures/work/W-2001…W-2010`, and `.steps.json` for W-2001, 2006, 2007 and 2008. `.next.json` for W-2007 (revision 4 to 5) and W-2008 (carries `reconcile`). `frontend/mock/fixtures/response/W-2008.{not_delivered,unknown}.json` are reconcile sidecars, so the ReconcilePanel answer gets a 200 from F-09's mock. W-2009 is W-1901 with its own ids and without the board blocks. W-2010 is W-1002 with its id changed.
- Tests: `tests/workspace.test.tsx` (29), `tests/workspace-step.test.tsx` (37), `tests/workspace-mock.test.ts` (7), new describe blocks appended to `tests/mock-contract.test.ts` (5 tests; no existing assertion touched), and `e2e/workspace.spec.ts` (31).
- Factory files (on the branch): `delivery/features/F-17/regions.json`, `fidelity-exceptions.json` (provisional) and `round-1/fidelity/` (`region-check.mjs`, `region-scores.txt`, and only `report.json` and `side-by-side.png` per region).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Unchanged without a workspace: W-2010 draws byte-identical HTML to W-1002 (ids swapped), and W-1701 and W-1901 draw no `.ws`. The existing work-item, work-item-board, decide and response tests pass unchanged.
2. [x] Header from data: shown on W-2001; W-2005 draws no header; one h1; the h2 appears only on W-2002. The e2e counts h1 = 1 on W-2001 to W-2005 at both widths.
3. [x] Nine section kinds, one test each, in returned order. Cells are drawn by column kind. Six crafted `https://x.example`, `//`, `javascript:` and backslash links produce 0 `<a>`.
4. [x] All 8 statuses, 5 receipts and 4 severities show as words. The uncertain row does not match /received/i. The unlisted `waiting_on_vendor` and `critical` render raw.
5. [x] INV-UNKNOWN on W-2004: In, Closing (no amount), Expected and Confirmed read Unknown, and the due date reads "Due Unknown". No 0, ₦0, dash or blank.
6. [x] INV-RESTRICTED: none of the 10 hidden fixture strings appears in `document.body`, the restricted cell reads "Restricted", and a section without its own label reads "Restricted".
7. [x] as_of ("As of 14 Nov 10:40 WAT") and coverage show on W-2004 and are absent on W-2001. The SAMPLE DATA label shows with `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1`, and an item with `sample: false` shows none. Note: an existing assertion requires `sample: true` on every work fixture, so "absent elsewhere" is proven with a crafted `sample: false` copy, not a fixture.
8. [x] W-2005 shows "ActionsNothing here yet."; a crafted workspace with no sections and no steps draws an empty frame and throws nothing.
9. [x] Filter, chip and Show more are disabled, and the line "More rows aren’t available yet." is tied to them by aria-describedby. Clicking every button sends no request (component test and e2e). Contract proposal: a section-page read.
10. [x] Every W-20xx item and `.next` validates against E-WORK-ITEM (existing test plus a new block). The existing byte-for-byte fixture check passes, and `git diff --stat 79f25e5 -- frontend/mock/fixtures/work/W-1*` is empty.
11. [x] e2e for W-2001 to W-2005 at 1440 and 390: axe clean (all 5 tag sets), scrollWidth no wider than the viewport, 44px buttons, table frames scroll inside themselves at 390 with a focus ring, a cite-link focus ring, and no running animations with reduced motion.
12. [x] Steps appear only as returned; none without a revision. Four personas see identical controls. The disabled step shows its reason through aria-describedby and sends nothing.
13. [x] W-2002: the item steps are on the right items; Accept selected is off with 0 checked; the request carries `item_ids: ["R-07","R-09"]` in item order; item steps send no item_ids.
14. [x] W-2006 form shows all 13 kinds, display shown and not sent, restricted drawn as "Restricted" (no value), help, depends_on ("Choose Project first"), the required check, and the confirm text above the submit. No file in `features/start-work/**` changed (no widening was needed: the step field type matches the E-LINES intake type). Deviation: IntakeField draws no money field and draws evidence as a disabled box, so money and evidence use the workspace's own box and the existing ProofField. IntakeField behaviour was not changed.
15. [x] One POST to `/api/v1/work/W-2006/steps` with X-CSRFToken, `expected_revision: 2`, inputs shaped per kind, a UUID key and the trimmed note. It validates against the generated request schema. A note over 2000 characters and a non-integer are refused with no request. The mock also checks the body (`workspace-mock.test.ts`).
16. [x] A double click sends 1; while pending the button reads "Approve and send…" with aria-disabled. StrictMode sends 1. Try again after a network or 500 failure reuses the key. A new form, done, 409 and 422 each renew it. e2e: the mock log shows `sends[key] = 1`. Mock evidence only.
17. [x] For 500, network, 409 and effect_uncertain, the POST count stays 1 after 60 s of fake timers.
18. [x] done reloads once, shows the live Done line (or the returned message), and the next press uses revision 4 with a new key. queued shows "Waiting: …", reloads once, and nothing is resent. Tested on W-2001 and W-2007, component and e2e.
19. [x] W-2008: alert with the returned message; every step aria-disabled; ReconcilePanel from the re-read item; exactly 1 POST to `/actions` and no further `/steps` (component and e2e). Without reconcile: "We are checking what happened. Nothing was sent again." with only a Reload button.
20. [x] W-2007 409: the typed input is kept, one reload, "…Showing version 5.", the next press sends `expected_revision 5` with a new key. The e2e mock log shows a 409 at 4, then a 200 at 5.
21. [x] 422: messages under answer and hours (aria-invalid, aria-describedby), focus on answer, the unnamed message at the top, inputs kept, new key. A 422 with no fields shows its message at the top.
22. [x] 401 shows the signed-out callout with `next=/work/W-2001`. 403 reloads and says "You can’t take that step." (403 on the re-read shows NoAccessState). 404 shows NoAccessState with no title, id or reference on the page. 500 on a sending step offers no Try again and stays aria-disabled; on a non-sending step Try again reuses the same key.
23. [x] W-2009: the link points to `/work/W-2009/decide?task=T-2009` with "Claim it first". The disabled decision step is not a link. The workspace sends no POST. e2e follows the link and the decision page opens (the page's own claim calls are F-16's).
24. [x] e2e for W-2006 (form open, 422), W-2007 (409), W-2008 (uncertain) and W-2009 at 1440 and 390: axe clean, no sideways scroll, 44px targets (choice segments, proof button and checkbox targets raised inside `.ws-form` and `.ws-checkwrap`), focus to the heading on open and back to the step on Escape, alert and status live regions, reduced motion.
25. [ ] Region check (D-59). `round-1/fidelity/region-scores.txt` covers 13 regions × 2 widths, coverage 100% after exceptions in all 26 runs. 11 exception categories: frame layout, no field, drawn on press, anchor, phone composition, amount format, copy split, form layout, no board; every entry reads "builder proposal, pending design engineer". The region-check method itself was approved by the design engineer, 14 Nov (D-59). Visual >= 85 in 7 of 26 runs: text-cites, recipients, timeline, checklist, checklist-gates, facts and notice-done, all at 1440. Below 85: steps 1440 (54.6), table 1440 (76.3), suggestions 1440 (44.9), findings 1440 (72), unknown-money 1440 (65.8), step-form 1440 (45.2), and every 390 run (33.8 to 82.3). See Blocked/open decisions.
26. [x] The token grep on `features/workspace/*.css` returns nothing.
27. [x] `git diff --stat 79f25e5 -- frontend/src/api apps architecture design` is empty. Contract proposals are listed below.
28. [x] The e2e checks that every page request went to localhost (proxied to the mock on 4702). This file states the D-LINE-WORKSPACE limits.
29. [x] `git diff 79f25e5` on all the listed existing tests is empty except `mock-contract.test.ts`, which has blocks appended only. The listed e2e specs pass: 129 passed.
30. [~] The four new test files exist. The three vitest files run in `delivery/checks.sh`. `e2e/workspace.spec.ts` does not run there: checks.sh (protected) runs no Playwright. It was run separately: 31 passed.

## Validation
- `bash /Users/Hunchoo/psl-factory/delivery/checks.sh` at the final tree: exit 0 (Django check OK; lint, typecheck; vitest 47 files and 1243 tests passed; next build OK). One earlier run during Part A failed 5 existing tests at a machine load average of about 300. The same files passed in isolation (211/211), and the final run passed with the machine quiet.
- `E2E_PORT=4701 MOCK_PORT=4702 npx playwright test e2e/workspace.spec.ts`: 31 passed.
- Same ports with `e2e/work-item.spec.ts work-item-board.spec.ts decide.spec.ts decide-board.spec.ts response.spec.ts start-work.spec.ts`: 129 passed.
- Region check: `node delivery/features/F-17/round-1/fidelity/region-check.mjs --tool …/software-factory/packages/design/fidelity --playwright frontend/node_modules/playwright/index.mjs --design design --base http://localhost:4701 --mock http://127.0.0.1:4702 --regions delivery/features/F-17/regions.json --exceptions delivery/features/F-17/fidelity-exceptions.json --out …`, on a production build (`API_ORIGIN=http://127.0.0.1:4702 next build`, `next start -p 4701`). The driver hides everything outside the region, lays the page region out at the board region's width, then runs the tool's own `extractInBrowser`, `compare` and `visualInBrowser`. The servers I started on 4701 and 4702 were stopped afterwards. Temporary output was deleted.

## Contract proposals (for the backend developer; the frame does not extend the contract)
- A section-page read for `next_cursor` and `filters` (Contract 9).
- A money field's currency in the step field descriptor (the frame sends NGN).
- A panel title or deciding role for the workspace step row (boards draw "Decide · PMO Lead").
- A client-preview link, a "source" cite link on suggestions, and "select all" for items steps (board copy without a field).
- Backend items not built: E-WORK-STEP and `workspace` are `unimplemented`, and the idempotency promise is unbuilt (PMO-0-2).

## Blocked
Not blocked. Open decisions for the design engineer:
1. Confirm or refuse the provisional exceptions in `delivery/features/F-17/fidelity-exceptions.json`.
2. Visual score below 85 (criterion 25). The phone boards draw a line-specific composition: no panel frame, pinned bottom buttons, a one-line summary. The frame draws the returned sections the same way at every width. On desktop, the decide panel, the suggestion card and the edit card sit in the board's side column with a coloured head. Should the frame copy these compositions now, or leave them to each line task's whole-board gate (spec: "Not checked here: whole-board fidelity")? I have not changed any layout for this.
