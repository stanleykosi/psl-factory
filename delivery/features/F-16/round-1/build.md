STATUS: READY
COMMIT: 713e628b94ce0babdd045dbb45f17ac85cafb507
BUILDER: builder
LANE: full

## Summary
- The decision page (`/work/[id]/decide`) is redrawn to the SCR-03 boards. That covers the trail, the board columns, the read-only (not-yours) and own layouts, the stale view drawn as a table, and the done view. The phone back link now sits in the frame slot. Tokens only.
- Claim, decide, CSRF, `expected_revision`, the 409 and stale flow, uncertain effect, note rules, error mapping, `you_can_act` gating and Unknown amounts are unchanged. `useDecision.ts` and `format.ts` are untouched. `tests/decide.test.tsx` and `e2e/decide.spec.ts` are byte-for-byte unchanged and green.
- PROPOSAL `decide_presentation` (in `presentation.ts`) is read only from the new board fixtures. It is hidden when absent and never sent anywhere.
- **Fidelity: 5 of 10 boards pass.** These pass: desktop default, done, not-yours and own, plus mobile done. These are under 90: mobile default (85.0), mobile stale (79.3), mobile not-yours (84.7), mobile own (77.8) and desktop stale (88.2). Every board has 100% coverage after exceptions. The measured gap and cause for each is below. The approval chain alone never pulls a board under 90 (measured), so the D-55 stop condition did not trigger.
- **Deviation:** the board fixtures are **W-1901 to W-1904** (tasks T-1901 to T-1904), not W-18xx. W-1801 to W-1811 are already work ids in `mock/fixtures/E-PROJECT.json` and `projects/P-0101.json`, and `tests/mock-projects.test.ts` failed when W-18xx files existed.

## Changes
- `frontend/src/features/decide/presentation.ts` (new): the `DecidePresentation` type (PROPOSAL), `decidePresentationOf` (safe cast), `nextDecision` (link only when `isAppPath`) and `queueText`.
- `DecideView.tsx`:
  - One layout map (`Layout` and `BACK`) picks the board and the phone back link: "Decisions" for decide, stale and done; "Queue" for read-only, not-open, loading, error and no access.
  - The bar note is the queue position on actionable views and the reference on read-only ones.
  - The title becomes `task.title · subject` when the block carries a subject.
  - No access is wrapped so its title keeps the frame size.
  - The panel column is an `<aside>`.
- `DecisionContent.tsx`:
  - `DecideHeader` keeps the Breadcrumb nav for screen readers and the tests, and draws the board's visible trail plus the phone eyebrow line.
  - The sub-line sits in the title line, and there is an optional state tag.
  - `quietOnPhone` covers the stale phone board, which draws no title.
  - New `DecisionTrail`. `MiniLine` is now a `div` and takes `waiting`.
  - `AgentNote` is redrawn as the board's agent card: mascot image, role, summary, phone summary, `link_label`, and a "note" mode for stale. "Cannot approve, send or pay." is kept.
  - `DecisionRows`, `AmountValue`, `Row`, `When` and `ApprovalChain` are unchanged.
- `DecideStates.tsx`:
  - Not-yours layout: amount, basis and waiting-for boxes; phones add the SENT, RECEIPT and VERIFIED facts. The card holds the copy keyed on `cannot_act_reason`, the asked list and the disabled `CommentBox`. "Open the work item" and the approval chain follow.
  - Own layout (`prepared_by_you`): a version card and a review `<aside>` with the info callout and the asked list. The chain follows.
  - Stale is drawn as a table at desktop and as stacked cards on phones. The "Changed since" note sits at the right of the current values. Rows are ordered Amount, then changed rows, then unchanged rows; the marks are unchanged. The agent slot is new. On phones the footer is pinned.
  - Done: client heading, board fact details, the next-step card with Chidi's pose, and "Next decision" (app path only). "Open the work item" and "Back to my work" stay. On phones the links are pinned.
- `DecidePanel.tsx`: class `decide-who` added to the "Only a … can decide" line, which is visually hidden on phones (the station line says it). No behaviour change.
- `decide.css`: rewritten to the boards, using token variables only.
- New fixtures `frontend/mock/fixtures/work/W-1901.json`, `W-1901.approve.json`, `W-1902.json`, `W-1902.next.json`, `W-1903.json` and `W-1904.json`. Each is a copy of W-1201, W-1201.approve, W-1207, W-1207.next, W-1203 and W-1204 respectively, with the reference INV-0412, plus `decide_presentation` and `presentation.facts` where the board needs them. No existing fixture is changed.
- Tests:
  - `tests/decide-board.test.tsx` (new, 25 tests).
  - `tests/mock-decide.test.ts`: 3 new cases.
  - `tests/mock-contract.test.ts`: the decision-block schema, the strip, a sidecar check and a crafted-href check.
  - `e2e/decide-board.spec.ts` (new, 24 tests).
- Factory files:
  - `delivery/features/F-16/fidelity-exceptions.json` (26 entries, provisional).
  - `round-1/fidelity/`: `drive-states.mjs`, `serve-frozen.mjs`, `frozen/*.html`, `scores.txt`, and `<board>/report.json` with `side-by-side.png`.

### Contract proposal: `decide_presentation` fields and the boards that need them
| Field | Boards | Notes |
|---|---|---|
| `queue.position`, `queue.total` | SCR-03-desktop and mobile (default), and -stale | "1 OF 3" in the trail and the phone bar note |
| `queue.next.{label, href}` | -done (both) | "Next decision · 2 of 3"; rendered only when `isAppPath(href)` |
| `subject` | default and stale (both) | after the task title in the h1 |
| `client` | -done (both) | "Invoice v2 for Lagoon Health is approved" |
| `waiting` | SCR-03-mobile | "waiting 2h" in the station line |
| `agent.role`, `agent.summary`, `agent.link_label` | SCR-03-desktop | "Chidi · Finance agent", the 3-sources line, "See his steps" |
| `agent.phone_summary` | SCR-03-mobile | the phone's one-line agent note (a field added beyond the sketch, so that no exception is needed) |
| `agent.note`, `agent.phone_note` | -stale (desktop, mobile) | the redraft line |
| `comment.{label, action}` | -not-yours (both) | drawn disabled with "Comments aren’t available yet."; never sent |

### Boards that used frozen pages
SCR-03-desktop-done, SCR-03-mobile-done, SCR-03-desktop-stale and SCR-03-mobile-stale were scored from `round-1/fidelity/frozen/done-1440.html`, `done-390.html`, `stale-1440.html` and `stale-390.html`. `drive-states.mjs` produced them:
1. Reset the mock, open the page with the `finance_lead` cookie and Africa/Lagos time.
2. Click Approve v2 in the real UI (W-1901 for done; W-1902 for stale, which gets the mock's 409 and redraft).
3. Wait for the heading, remove the scripts and save the page.

No product or mock code was changed to reach these states.

One deviation from the spec: the `<base>` is `http://localhost:4603/`, not 4601. The app serves fonts without CORS headers, so a page on 4603 that loads assets from 4601 fell back to system fonts. `serve-frozen.mjs` serves `frozen/` on 4603 and passes `/_next` and other paths through to 4601, so CSS and fonts load from the same origin.

The frozen pages contain:
- stale: "VERSION 2 · REPLACED", "VERSION 3 · CURRENT", "Send to … · changed" and "Review version 3";
- done: "Invoice v2 for Lagoon Health is approved".

The done eyebrow shows the time of the drive, because the mock stamps `decided_at` with the current time.

### Exceptions mapped to categories (`fidelity-exceptions.json`, all `approved_by: "builder proposal, pending design engineer"`)
- **Frame items:**
  - "← Decisions" and "← Queue": the frame names the links "Back to …", as in F-14.
  - "Bisi Adeyemi · Finance" and "Bisi Ade · Finance": the signed-in persona name.
- **Dead control or prototype affordance:**
  - "Preview: a newer version arrives" (desktop) and "Preview: what happens if a newer version arrives" (phone).
- **Contract words and eligibility rules kept from F-04:**
  - The two not-yours sentences (D-55, `cannot_act_reason`).
  - "WAITING · FINANCE REVIEWER": the page uses `required_role`.
  - "₦4,250,000.00" and "PO number, as you asked": `DecisionRows` markup under the F-14 seam. The values are shown in the same place, but the tool does not read text nested inside a `dd`.
  - "Changed": the `DecisionRows` label.
  - "—": receipt is unknown and reads Unknown under INV-UNKNOWN. On phones the box also carries the sr "Not yet".
  - "RECEIPT": the sr "RECORDED" suffix.
  - The two stale `status` notices: kept as `role="alert"`, and the drafted time comes from the contract.
  - Stale `table` and its two `columnheader`s: kept as the two labelled regions that A-STALE tests read.
- **Disagreements between boards:**
  - "See sources" (Conflicts 8).
  - "You prepared this invoice. Ada Okafor has been asked to review it." (Conflicts 15).
  - "FINANCE / INVOICES / INV-0412" (the own trail, against the not-yours "DECISION · INV-0412").
  - The phone done next-step wording (Conflicts 17).
  - The phone stale "Invoice v2 · ₦4,250,000.00", "REPLACED" and "To" (Conflicts 16).

### Boards under 90: measured gap and cause
Gaps were measured with variants of the frozen or snapshotted page that add one CSS rule each. The variants were scored with the same tool and then deleted.
- **SCR-03-mobile-390: 85.0 (gap 5.0).**
  - Causes: the Version and Prepared-by rows. These are `DecisionRows` seam output, and the test asserts "Bisi Ade (Finance)". Together with the "Changed since Invoice v1" label wrapping, they push the agent strip down about 120px. Other causes are the Note field and the approval chain (D-55) in the board's empty area, and the frame's "+ Start" button in the phone bar (about 29 cells, shell).
  - Measured: hiding the two rows gives +1.5; the rows plus the chain give +2.7. Even then the board is still under 90, because of the frame and font differences.
- **SCR-03-desktop-stale-1440: 88.2 (gap 1.8).**
  - Causes: the extra "Basis · unchanged" row. `compareRows` emits it and the A-STALE test asserts it. Also the "Changed since Invoice v2" cell and the 40px frame title (D-28).
  - Measured: without the Basis row and the changes cell the board scores 95.1.
- **SCR-03-mobile-stale-390: 79.3 (gap 10.7).**
  - Causes: the phone board draws the replaced version as a one-line card and puts the agent inside the current card. The page keeps two stacked version panels with all rows (Conflicts 16), the changes line, and a separate agent card.
  - Tried: hiding the replaced rows on the phone scored lower (73 to 76), so it was not kept.
- **SCR-03-mobile-not-yours-390: 84.7 (gap 5.3).**
  - Causes: the disabled comment label, textarea and hint (D-55), the alert line, "Open the work item", the approval chain and the item sub-line all sit in the board's empty area. Also the frame's "+ Start".
  - Measured: the chain alone is +1.5.
- **SCR-03-mobile-own-390: 77.8 (gap 12.2).**
  - Causes: the phone board draws only a title and one callout. Criterion 17 requires the amount, basis, "Prepared by You with Chidi" and the asked person with time. Those, plus "Open the work item" and the chain, fill the board's empty area. Also the frame's "+ Start".
  - The approval chain alone is under 1 point on every own and not-yours board.

## Fixes
None (round 1).

### Open design-engineer decisions (the five boards under 90)
These five boards stay under 90 because of content that the spec, a test or D-55 requires on screen, or because of the frame. None of the five gaps is an approved exception yet. The design engineer is asked to decide:
- **DE-1:** accept SCR-03-mobile-own (77.8) and SCR-03-mobile-not-yours (84.7) with the criterion 16 and 17 content and the kept chain, or say which content may be hidden on phones.
- **DE-2:** accept SCR-03-mobile-stale (79.3) with two stacked version panels (Conflicts 16), or approve drawing the replaced version as the board's one-line card.
- **DE-3:** accept SCR-03-desktop-stale (88.2) with the "Basis · unchanged" row and the changes note, or approve leaving unchanged rows out of the table (this would change an A-STALE assertion, so it needs sign-off).
- **DE-4:** accept SCR-03-mobile (85.0) with the Version and Prepared-by rows (`DecisionRows` seam) and the Note field.
- **DE-5:** the frame's "+ Start" button in the phone bar (shell, F-05 and F-15) costs about 1.7 points on every phone board. It needs a frame exception or a frame change.

## Acceptance criteria
1. [x] **Desktop fidelity:** 4 of 5 desktop boards pass with 100% coverage after exceptions and visual of 90 or more: default 91.1, done 93.6, not-yours 91.4, own 91.6. Desktop stale scores 88.2 (gap and cause above; DE-3). See `round-1/fidelity/scores.txt` and `SCR-03-desktop*-1440/report.json`.
2. [ ] **Phone fidelity:** only done passes (92.0). Default 85.0, stale 79.3, not-yours 84.7 and own 77.8 are under 90. All five have 100% coverage after exceptions, and `scores.txt` lists all 10 boards (DE-1, DE-2, DE-4, DE-5).
3. [x] **Done and stale scored on the real UI:** `round-1/fidelity/drive-states.mjs` drives Approve on W-1901 (done) and on W-1902 (409, redraft) at 1440 and 390, and was re-run before the final scoring. The frozen stale pages contain "VERSION 2 · REPLACED", "VERSION 3 · CURRENT", "billing@lagoonhealth.example · changed" and "Review version 3". The frozen done pages contain "Invoice v2 for Lagoon Health is approved". No product or mock code was changed for this. The `<base>` deviation is explained above.
4. [x] **Exceptions:** 26 entries, each with `role`, `name`, `category`, `reason` and `approved_by` set to "builder proposal, pending design engineer". The category map is above. No entry covers a value that `decide_presentation` or a contract field can supply.
5. [x] **Phone back link in the frame slot:**
   - `decide-board.test.tsx` checks "Back to Decisions" (default, W-1201 and done) and "Back to Queue" (W-1903, W-1904, W-1205, not open, loading and no access), all pointing to /my-work, with the bar note. It also checks that `main` has no back link of its own.
   - The e2e test checks the link and its text at 390 and that it is hidden at 1440, for all five states and no access.
6. [x] **Titles:** e2e checks one `h1.shell-title`, computed at 40px at 1440 and 26px at 390, on the default, done, stale, not-yours, own and no-access pages. No access is wrapped (`.decide-noaccess`) because the work item's permission card sets 33px.
7. [x] **Header and trail:** the W-1901 trail is "Decisions / 1 of 3 / FINANCE REVIEW · INV-0412" and the W-1201 trail is "Decisions / FINANCE REVIEW · INV-0412". The Breadcrumb nav text is unchanged, and `decide.test.tsx:97-99` is unchanged and green.
8. [x] **Decision values:**
   - W-1901's rows are Amount, Basis, To, "Changed since Invoice v1" and Version, all through `DecisionRows`.
   - The facts read "v2" and "Waiting".
   - An unknown amount reads Unknown on the board fixture.
   - The sample label shows with `NEXT_PUBLIC_SHOW_SAMPLE_LABEL=1`.
   - The existing tests at lines 80-155 are unchanged and green.
9. [x] **Controls only for the right person:** the existing cannot-act and `/me` tests are unchanged and green. W-1903 and W-1904 render no controls (unit and e2e).
10. [x] **Claim and decide unchanged:** `useDecision.ts` has no diff, and the "claim and decide" tests are unchanged and green.
11. [x] **Note rules unchanged:** `DecidePanel` behaviour has no diff (one class name added), and the tests at lines 229-271 are green.
12. [x] **Stale flow unchanged:** the existing stale tests and the e2e "stale flow on the mock" test are green. The W-1902 board test passes. The comparison rows are ordered (changed rows before unchanged ones); the marks and the "still unknown" logic are untouched.
13. [x] **Uncertain effects unchanged:** `decide.test.tsx` lines 488-590 and the e2e "decide and reload both fail" test are green.
14. [x] **Error mapping unchanged:** the "errors" tests are green. 403 and 404 render `NoAccessState`, now inside a wrapper.
15. [x] **Done view:**
   - The green banner reads "YOU APPROVED · 10:47" and the heading "Invoice v2 for Lagoon Health is approved".
   - The facts read v2, You, 10:47 and Next, and the reloaded `next_step` and the Paid line show. "Open the work item" and "Back to my work" are present.
   - "Next decision · 2 of 3" links to `/work/W-1201/decide?task=T-1201`. It is absent without `queue.next`, and absent for the crafted hrefs `https://`, `//`, `javascript:`, `/\` and a leading space.
   - Return keeps the neutral banner.
16. [x] **Not-yours board:**
   - The tag, the copy, the Amount, Basis and "Waiting for Finance Lead" boxes, and the alert line all show.
   - The comment textarea and button are `disabled`. "Comments aren’t available yet." is read through `aria-describedby`, and focusing or clicking the box sends no request (unit and e2e).
   - W-1203 has no comment box.
17. [x] **Own board:** W-1904 shows the WAITING FOR REVIEW tag, the reason, the amount and basis, "Prepared by You with Chidi" and "Ada Okafor (Finance Lead) was alerted at 12 Nov 10:20", with no controls.
18. [x] **Proposals contained:** W-1201 shows no "1 of 3", "waiting 2h" or "Next decision". The crafted hrefs render no link (unit, and the schema test). A recording `fetch` shows that W-19xx pages call only E-WORK-ITEM (GET) and E-TASK-CLAIM and E-TASK-DECIDE (POST).
19. [x] **Seam with F-14:** the greps for `DecisionRows`, `AmountValue` and `formatClock` match once each. `git diff origin/dlv-00-delivery-setup...HEAD -- frontend/src/features/work-item frontend/src/shell` is empty. `work-item*.test.tsx` and `e2e/work-item*.spec.ts` are green.
20. [x] **Fixtures valid:**
   - Every `fixtures/work` file validates with `_kind`, `presentation` and `decide_presentation` stripped, and each block validates against its schema.
   - Only W-19xx files carry `decide_presentation`, and the W-19xx sidecars are checked.
   - No existing fixture changed (the existing byte-for-byte test is green).
   - The new mock-decide cases cover W-1901 (approve), W-1902 (409, then a decide at revision 5), and W-1903 and W-1904 (403 on claim).
21. [x] **Accessibility at both widths:** `E2E_PORT=4601 MOCK_PORT=4602 npx playwright test e2e/decide.spec.ts e2e/decide-board.spec.ts e2e/work-item.spec.ts e2e/work-item-board.spec.ts` gave 103 passed. That covers axe (wcag2a/aa, 21a/aa, 22aa), no sideways scroll, focus order and rings, 44px targets, the 54px pinned Approve and reduced motion, with `timezoneId: 'Africa/Lagos'`. The 390 re-run after F-15 merges is still for the coordinator.
22. [x] **Tokens only:** `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" frontend/src/features/decide/decide.css` returns nothing (exit 1).
23. [x] **No test weakened:**
   - `tests/decide.test.tsx` and `e2e/decide.spec.ts` have no diff.
   - The changed assertions are in `tests/mock-contract.test.ts` only, and both are widened to cover the new block. Nothing was removed or loosened for the existing files:
     - `const { presentation, ...item } = body;` became `const { presentation, decide_presentation: decidePresentation, ...item } = body;`. Reason: strip the new PROPOSAL block before the contract check, as F-14 did.
     - `if (boardFixture(name))` became `if (boardFixture(name) || (decideBoardFixture(name) && presentation !== undefined))`. Reason: W-19xx may carry F-14's `presentation.facts`, and every other file still has to have none.
24. [x] **Behaviour has new tests:** `tests/decide-board.test.tsx` (25 tests) covers criteria 5, 7, 8, 15 to 18 and the sample label. `e2e/decide-board.spec.ts` (24 tests) covers 5, 6 and 21. Both run in `delivery/checks.sh` (vitest) or in the e2e command.
25. [x] **build.md evidence:** this file has the proposal list, scores, side-by-side paths, frozen pages, the exception map, the changed assertions and the under-90 gaps.

### scores.txt
```
board                          width  coverage  with-exceptions  visual  pass  page
SCR-03-desktop                 1440   91.3      100              91.1    true  /work/W-1901/decide?task=T-1901
SCR-03-mobile                  390    70        100              85      false /work/W-1901/decide?task=T-1901
SCR-03-desktop-done            1440   96.4      100              93.6    true  /frozen/done-1440.html
SCR-03-mobile-done             390    89.5      100              92      true  /frozen/done-390.html
SCR-03-desktop-stale           1440   82.1      100              88.2    false /frozen/stale-1440.html
SCR-03-mobile-stale            390    58.3      100              79.3    false /frozen/stale-390.html
SCR-03-desktop-not-yours       1440   90.9      100              91.4    true  /work/W-1903/decide?task=T-1903
SCR-03-mobile-not-yours        390    66.7      100              84.7    false /work/W-1903/decide?task=T-1903
SCR-03-desktop-own             1440   81.3      100              91.6    true  /work/W-1904/decide?task=T-1904
SCR-03-mobile-own              390    50        100              77.8    false /work/W-1904/decide?task=T-1904
```
Side-by-side images: `delivery/features/F-16/round-1/fidelity/<board>-<width>/side-by-side.png`, one per row above (for example `SCR-03-desktop-1440/side-by-side.png`, `SCR-03-mobile-own-390/side-by-side.png`).

## Validation
- `cd worktree && bash delivery/checks.sh`: exit 0. Django check, npm ci, lint, typecheck, vitest (43 files, 1124 tests) and next build all pass.
- `E2E_PORT=4601 MOCK_PORT=4602 npx playwright test e2e/decide.spec.ts e2e/decide-board.spec.ts e2e/work-item.spec.ts e2e/work-item-board.spec.ts`: 103 passed. `frontend/test-results` was deleted afterwards.
- Fidelity: a production build (`API_ORIGIN=http://127.0.0.1:4602 next build`, then `next start -p 4601`), the mock on 4602 and `serve-frozen.mjs` on 4603. The tool ran with `--cookies psl_mock_persona=finance_lead`, `--exceptions delivery/features/F-16/fidelity-exceptions.json` and `--wait-ms 500` for each board and width. Only `report.json` and `side-by-side.png` are kept. All three servers were stopped afterwards.
- The seam greps, the tokens grep and the `git diff --stat` for work-item and shell are as listed in criteria 19 and 22.
- `df -h /System/Volumes/Data` showed about 10 GB free before the runs.

## Blocked
Not blocked. The five boards under 90 are listed as open design-engineer decisions (DE-1 to DE-5).
