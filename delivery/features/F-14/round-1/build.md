STATUS: READY
COMMIT: 6eaac8c628c227f10a9aed6c64088a9c0f77902b
BUILDER: builder
LANE: frontend

## Summary
- The work item page (`/work/[id]`) and its history (`/work/[id]/history`) are rebuilt to the 26 SCR-02 boards. One per-state layout map in `WorkItemOverview.tsx` sets each board's section order for desktop and phone. The page adds the state card, the invoice preview, the agent section/banner/panel and the two phone disclosures.
- Board-only values come from one PROPOSAL `presentation` block (`presentation.ts`) plus history `lines`. Only the new fixtures W-1701 to W-1711 carry them. Without them the page renders the F-03 layout.
- Contract fields always win:
  - the started line comes from `started_by`/`started_at`/`revision`;
  - the decision rows come from `DecisionRows`;
  - Unknown always wins over a detail;
  - the contract status words stay in the accessible text.
- The phone back link uses `usePhoneBack`, and titles use the frame's `.shell-title`: 40px on desktop, and the boards' 22px (20px on history) on phones.
- **Fidelity:** coverage after exceptions is 100 on all 26 boards. Visual is ≥ 90 on 6 boards (4 desktop, 2 phone); 20 are between 71.4 and 88.6. Causes are below. The readiness split rule applies: the phone boards are the remainder for a round 2.

## Changes
- `frontend/src/features/work-item/presentation.ts` (new): the `WorkItemPresentation` and `BoardHistoryEntry` types (PROPOSAL, D-WORKITEM-VIEW). It also has `presentationOf` (safe cast) and `isAppPath`, which allows only single-`/` app paths, so absolute, `//` and `javascript:` hrefs are dropped.
- `WorkItemOverview.tsx`:
  - `LAYOUTS` holds the board order per contract state, plus `task` (the default board: a decision for you) and `issue` (a record with a preview). It sets the desktop row or list track, the tag position, and the desktop and phone main/aside order.
  - New blocks:
    - `AgentSection`: the default/verified/owner/effect boards, with numbered steps and `agent.steps[].at` times;
    - `AgentBox`: the phone note, with a "See his steps" disclosure;
    - `AgentBanner`: the waiting board;
    - `AgentPanel`: the processing board, an `<aside>` around the CMP-09 card;
    - `StatePanel`: an `<aside>` with tone, lead, body, Reason quote, rows, navigation links and note;
    - `PanelSummary` and the phone bottom bar;
    - `InvoicePreview` (TEST TEMPLATE) and `PreviewSummary`, with a "Preview the invoice" disclosure.
  - `FactsStrip` and `StationTrack` take optional details. Facts and stations are now `div role="list"/"listitem"`, because the fidelity tool cannot read text inside `<li>`. `FactsStrip` has a `paidNote` flag.
  - `TaskPanels` adds `DecisionRows` when the task has `decision`. Its export, props and the single "Open the decision" expression are unchanged.
  - `NextStep` is unchanged.
  - One marked `{/* F-09: ReconcilePanel mounts here */}` slot sits at the top of the right column, which every item renders, live ones included.
  - An agent the board does not draw still gets a card. A board layout never drops contract data.
- `WorkItemView.tsx`: the header has a crumb row ("revision N" at its end when there is no `started_by`), then the title line with tag and tabs (History shows a count when `history_counts` exists), then the started line. On phones it shows the title, then tag + "REF · revision N", with the tabs at the end of the page. History on phones shows the HISTORY eyebrow and "History · REF". It calls `usePhoneBack`: "Queue" → /my-work on the overview, also while loading and with no access; `back_label` or "Work item" → /work/{id} on history.
- `WorkItemHistory.tsx`:
  - filter count badges;
  - the detail inline after the event plus `lines` when counts are present;
  - a phone card list;
  - "+ N earlier entries" on phones with counts;
  - rows per page moved under the list next to Show more (DOM order is still filter → select → Show more);
  - the info icon on the WAT callout.
- `WorkItemStates.tsx`: the no-access card uses each board's wording. On desktop that is a bulleted list; on phones, two short paragraphs with "Back to my queue" in a bottom bar.
- `labels.ts`: `agentImage`, `formatWatDay` and `startedLine`. The FACTS receipt label shows "RECEIPT", with " RECORDED" kept for screen readers.
- New: `usePhone.ts` (DOM order follows each viewport's board) and `InfoIcon.tsx`.
- `work-item.css`: rebuilt to the boards with token variables only. `grep -nE "#[0-9a-fA-F]{3,8}\b|rgba?\(|hsl\(" …/work-item.css` returns nothing.
- Fixtures (new): `mock/fixtures/work/W-1701.json` … `W-1711.json` and `W-1705.history.json`. Existing fixtures are untouched. No `mock/server.mjs` change.
- Tests: `tests/work-item-board.test.tsx` (new, 75 tests), `tests/work-item.test.tsx` (harness only, see below), `tests/mock-contract.test.ts` (fixture strip and proposal schema, unchanged-fixture check, W-1799 fallback), `e2e/work-item-board.spec.ts` (new) and `e2e/work-item.spec.ts` (one selector).
- Factory files:
  - `delivery/features/F-14/fidelity-exceptions.json`: 57 entries, each marked `approved_by: "builder proposal, pending design engineer"`.
  - `round-1/fidelity/`: report.json and side-by-side.png per board, `scores.txt`, and `_driver/` (prod.sh, runall.sh, fid.sh, act-wait.mjs, exceptions.py, missing.py, measure.mjs).

### Changed F-03 assertions (wrappers only)
- `tests/work-item.test.tsx`:
  - Every render is wrapped in `AppShell`, because `usePhoneBack` throws outside the frame.
  - `serve()` answers `/api/v1/me` with `me.finance_lead.json`.
  - `itemUrls()` counts only `/api/v1/work/…` item calls.
  - The fake-timer helpers settle one extra tick for the frame's E-ME.
- Two call counts change from `fetchStub toHaveBeenCalledTimes(1|2)` to `itemUrls() toHaveLength(1|2)`, because the frame's `/me` is not an item read.
- The network-error stub answers `/me` and then rejects the item.
- The no-access guidance assertion now finds two `<li>` instead of one paragraph regex, because the desktop permission board draws a bulleted list.
- `e2e/work-item.spec.ts`: `li[aria-current="step"]` becomes `[role="listitem"][aria-current="step"]`, because stations are `div role="listitem"`.
- No behaviour assertion changed. The F-03 suite (46) and e2e (all F-03 cases) pass.

## Contract proposal (D-WORKITEM-VIEW, for the architecture)
The `presentation` block is optional on the E-WORK-ITEM 200 response. It is typed in `frontend/src/features/work-item/presentation.ts`:

| field | what it carries | boards that need it |
|---|---|---|
| `back_label` | phone history back link noun ("Invoice") | mobile-history |
| `facts.{name}` | visible fact detail ("v2", "Ada", "To client 06 Nov", "Never", "Held", "Not found") | every overview board except ready/processing |
| `stations[i]` | visible station detail ("Approved 10:47", "Held · no reviewer", "Waits") | all overview boards |
| `agent.role` | "Finance agent" / "PMO agent" | every board with an agent |
| `agent.summary` | phone one-liner | mobile default, ready, waiting, owner-needed, effect-uncertain |
| `agent.headline` | bold banner line | desktop-waiting |
| `agent.message[]` | agent card paragraphs | default, ready, waiting, verified, owner-needed, effect-uncertain, issue |
| `panel.{title,tone,lead,body[],quote,rows[],note,links[],summary}` | the state card; links are navigation only; `summary` is the phone callout or line | ready, processing (title, note, Ask Chidi), waiting, verified, issue, cancelled, owner-needed, setup-needed, effect-uncertain |
| `preview.{template_label,brand,bill_to,number,issue_note,lines[],tax,footer,version,basis}` | invoice preview on PSL's test template | desktop-issue, mobile-issue |
| `task_note` | small print under the decision panel | desktop default |
| `history_counts.{all,decisions,agent_work,evidence}` | tab and filter badges, "+ N earlier entries" | desktop-history, mobile-history |
| history entry `lines[]` | extra detail lines ("Note: …", "Used: …") | desktop-history (phone shows them too) |

Contract fields are used wherever one exists:
- the header from `started_by`, `started_at` and `revision`;
- the decision rows from `tasks[].decision`;
- agent step times from `steps[].at`, and "Started 10:41" from `agent.started_at`;
- the phone invoice amount from `amount`.

`tests/mock-contract.test.ts` validates the block against a JSON schema written from this type. It strips `presentation` and `lines` before the strict v4 schema check, and asserts that only W-17xx files carry them.

**Mock date note:** W-1701's `started_at` is `2025-11-10T13:05Z`, because 10 Nov is a Monday in 2025 (it is a Tuesday in 2026). The board's and AC 9's "Mon 10 Nov 14:05" is computed from the contract date, not hard-coded. The year is not shown.

## Exceptions (provisional; every entry is `"builder proposal, pending design engineer"`)
Each entry has `role`, `name`, `reason`, `approved_by` and a `category`.
- **Frame items (5):** Start work, More ways to start, "Bisi Adeyemi · Finance" (frame persona), "← Queue" and "← Invoice". The frame names the phone back link "Back to …", so the check reads a different name for the same link.
- **Contract state words, rule 6 (5):** AWAITING FINANCE DECISION, AGENT WORKING, WAITING ON CLIENT, APPROVED · READY TO SEND, READY.
- **Controls owned by F-04, F-06 or F-09 (26):**
  - F-04 (decision is taken on SCR-03): Note field and its label, Approve v2, Return, Reject, "Review and decide", and the "Your decision" landmark (the decision panel is F-03's TaskPanels, named "Current human task", a binding F-09 seam).
  - F-06: See all exceptions. The processing board's line "No person needs to act yet…", which is the item's `next_step` shown inside NextStep with its fixed "Next step." prefix.
  - F-09: Record the client's response, plus the whole ReconcilePanel (the unnamed side panel on the awaiting-reconciliation boards, CONFIRM WHAT HAPPENED, its text, the three choices as radio and as text, Record and continue, its small print, and the phone callout).
  - **Flag for the design engineer:** "₦4,250,000.00". It is on the page, in F-04's `DecisionRows`/`AmountValue`, which F-14 may not edit. The tool cannot read a lone span inside a `<dd>`. I filed it here because the owning component is F-04's; strictly it is a tool-reading limit, not a missing value.
- **Effects with no operation in scope (9):** Change the reminder, Issue and send INV-0412, Issue and send, Tell the PMO Lead, Ask for access, "This attempt is recorded in the audit history.", Download history (CSV), the Documents 2 tab, and the lagoon-uat-signoff.pdf link (shown as text).
- **Disagreements between boards (12):**
  - QUEUE crumb and the five REF · CLIENT eyebrows: one crumb is kept (D-17).
  - The `Work item` tablist: only the history board draws tabs, and the page keeps F-03's navigation links. This is a structural difference, flagged for the design engineer.
  - The default phone agent note drawn without the name.
  - The waiting phone note's bold first sentence.
  - The owner-needed phone small print, and the processing phone footer "Started 10:41", where the fixture follows the desktop board.
  - "+ 2 EARLIER ENTRIES": the desktop board lists all 7. The smallest page is 10 rows, so all 7 load.

## Fixes
None (round 1).

## Acceptance criteria
1. [ ] Desktop fidelity: coverage after exceptions is 100 on all 13. Visual is ≥ 90 on 4 (ready 90.6, verified 90.9, setup-needed 90.2, effect-uncertain 90.6). The other 9 are 76.5–88.6. Gaps are below.
2. [ ] Phone fidelity: coverage after exceptions is 100 on all 13. Visual is ≥ 90 on cancelled (90.9) and effect-uncertain (90.1); the other 11 are 71.4–85.4. Gaps are below.
3. [x] Exceptions are limited and explained: 57 entries, all provisional and mapped above. Two are flagged as edge cases: the DecisionRows amount and the tablist.
4. [x] Phone back link: e2e at 390 covers W-1701, W-1099 and loading ("← Queue" → /my-work), W-1705/history ("← Invoice" → /work/W-1705) and W-1004/history ("← Work item"). It also checks that there is no Menu, that main has no "←" link, and that the bar is hidden at 1440. A component test inside `AppShell` covers the same four cases plus loading.
5. [x] Titles: e2e reads `getComputedStyle`. Item and history titles are 40px at 1440; at 390, 22px on overviews and 20px on history; no-access is 30px/24px as drawn. There is exactly one `h1` on every board URL, and every one uses `.shell-title`.
6. [x] Facts: the F-03 W-1004 test passes unchanged. On W-1705 the visible details are v2/Ada/10:47/11:02/11:09/11:12, and each box's text contains "Earned".
7. [x] Unknown wins: crafted W-1710 with `facts.sent` "Delivered" shows Unknown, and a missing receipt fact shows Unknown. W-1710 Sent reads "SENTUnknown".
8. [x] Stations: the board details show with the contract word kept for screen readers (`04Finance reviewDone: Approved 10:47`). `aria-current="step"` and the amber uncertain class are tested. No W-17xx page scrolls sideways at 390 (e2e). The F-03 station e2e passes after the one selector change.
9. [x] Header: W-1701 shows the crumb, title and `STATE_TAGS.waiting`, and "Started by Tunde Bello (PMO) · Mon 10 Nov 14:05 · revision 2". W-1702 (no `started_by`) shows "revision 1" only.
10. [x] Decision summary: W-1701 shows the rows Amount ₦4,250,000.00 / Basis / To / Version from `DecisionRows`, both role lines, and "Open the decision" → `/work/W-1701/decide?task=T-1701`. There is no approve/return/reject button and no textbox. W-1002 has no link or button in its task panel.
11. [x] Agent card: a table test over W-1701–W-1706, W-1708, W-1710 and W-1003 checks the name, role, mascot alt "{name}, {role}", the message and "Cannot approve, send or pay.", and that no control matches /approve|send|pay/i. W-1707, W-1709 and W-1711 carry `agent.status: none` because their boards draw no agent.
12. [x] State panels: a table test checks every heading and body, including the W-1705 "Verified doesn't mean paid", the W-1706 TEST TEMPLATE label, the W-1707 Reason quote, and the W-1710 rows Sent at / Checks / If not found. Every board renders `NextStep` with `nextStepKind`. The F-03 W-1005 warning test passes unchanged.
13. [x] Links: the five board links point to their routes. A crafted panel with `https://`, `//` and `javascript:` hrefs renders none of them.
14. [x] Read only: for all 11 W-17xx items and W-1001–W-1006 at phone width, every button is clicked and every recorded fetch is a GET to `/api/v1/me`, E-WORK-ITEM or E-WORK-HISTORY. The only buttons are the disclosures (`aria-expanded`), the radios, Show more / "+ N earlier entries" and Try again. History filter, rows per page and Show more are GET-only.
15. [x] No role guesses: W-1708 and W-1709 produce identical `main` markup under finance_lead and pm, with React ids normalised.
16. [x] No access, signed out and error: the F-03 tests pass inside `AppShell` (403, 404, 401 with `next=/work/W-1001`, 500 then Try again, network error).
17. [x] Fixtures: validated with `_kind`, `presentation` and `lines` stripped; the proposal is validated against its schema; only W-17xx files carry it. `git diff --diff-filter=MDR 8930da1` lists no existing fixture. W-1799 falls back to the default fixture.
18. [x] History: W-1705 at 1440 shows "History 7", All 7 / Decisions 2 / Agent work 2 / Evidence 1, the three columns, 7 rows newest first with time, tag, actor, event + detail, lines and version, and About history. At 390 it shows the HISTORY eyebrow, "History · INV-0412" and 7 cards. The "+ 2 earlier entries" and "Show more" (no badges) variants are tested. The F-03 history tests and the 10 → 12 e2e pass.
19. [x] Updates: W-1703 re-reads at 5 s and 10 s (fake timers). The other ten W-17xx items never poll in 30 s. The F-03 polling tests pass.
20. [x] Accessibility: axe is clean at 390 and 1440 on all 11 W-17xx URLs, W-1705/history and W-1099. There is no sideways scroll. Focus rings are tested on the tabs, the panel link, the filter, rows per page and both disclosures. With `reducedMotion: 'reduce'` the W-1703 current step has no animation at both widths. `timezoneId: 'Africa/Lagos'`.
21. [x] Tokens: the grep returns nothing.
22. [x] F-09 seams:
    - `grep -n "export function TaskPanels({ id, tasks }"` matches at line 535.
    - "Open the decision" is still one `{task.you_can_act && (<Link …/>)}` expression.
    - "F-09: ReconcilePanel mounts here" matches exactly once.
    - `git diff 8930da1` shows no change inside `NextStep`.
    - The rebase note is below.
23. [x] Existing suites pass. `delivery/checks.sh` reports 403 unit tests passing (15 files). The `e2e/work-item.spec.ts` and `e2e/decide.spec.ts` suites pass. Changed assertions are listed above.
24. [x] build.md evidence: the proposal list, the scores, the side-by-side paths, and the gaps below.

### Fidelity (final, `round-1/fidelity/scores.txt`)
Settings: production build (`next build` + `next start -p 4501`), contract mock on 4502, cookie `psl_mock_persona` as in the spec's fixture table, exceptions file as above. The side-by-side for each board is `round-1/fidelity/<board>-<width>/side-by-side.png`.

| board | width | URL | coverage (raw / with exceptions) | visual | pass |
|---|---|---|---|---|---|
| SCR-02-desktop | 1440 | /work/W-1701 | 70.7 / 100 | 85.8 | no |
| SCR-02-desktop-ready | 1440 | /work/W-1702 | 86.7 / 100 | 90.6 | yes |
| SCR-02-desktop-processing | 1440 | /work/W-1703 | 83.9 / 100 | 88.6 | no |
| SCR-02-desktop-waiting | 1440 | /work/W-1704 | 81.3 / 100 | 87.4 | no |
| SCR-02-desktop-verified | 1440 | /work/W-1705 | 94.5 / 100 | 90.9 | yes |
| SCR-02-desktop-history | 1440 | /work/W-1705/history | 78.6 / 100 | 86.0 | no |
| SCR-02-desktop-issue | 1440 | /work/W-1706 | 88.2 / 100 | 84.0 | no |
| SCR-02-desktop-cancelled | 1440 | /work/W-1707 | 90.6 / 100 | 76.5 | no |
| SCR-02-desktop-owner-needed | 1440 | /work/W-1708 | 94.5 / 100 | 88.4 | no |
| SCR-02-desktop-setup-needed | 1440 | /work/W-1709 | 86.7 / 100 | 90.2 | yes |
| SCR-02-desktop-permission | 1440 | /work/W-1099 | 70.6 / 100 | 84.3 | no |
| SCR-02-desktop-effect-uncertain | 1440 | /work/W-1710 | 93.5 / 100 | 90.6 | yes |
| SCR-02-desktop-awaiting-reconciliation | 1440 | /work/W-1711 | 67.6 / 100 | 84.3 | no |
| SCR-02-mobile | 390 | /work/W-1701 | 80.0 / 100 | 81.6 | no |
| SCR-02-mobile-ready | 390 | /work/W-1702 | 88.9 / 100 | 72.7 | no |
| SCR-02-mobile-processing | 390 | /work/W-1703 | 85.0 / 100 | 85.4 | no |
| SCR-02-mobile-waiting | 390 | /work/W-1704 | 78.9 / 100 | 77.3 | no |
| SCR-02-mobile-verified | 390 | /work/W-1705 | 94.1 / 100 | 78.9 | no |
| SCR-02-mobile-history | 390 | /work/W-1705/history | 90.9 / 100 | 74.2 | no |
| SCR-02-mobile-issue | 390 | /work/W-1706 | 87.0 / 100 | 81.9 | no |
| SCR-02-mobile-cancelled | 390 | /work/W-1707 | 94.4 / 100 | 90.9 | yes |
| SCR-02-mobile-owner-needed | 390 | /work/W-1708 | 90.0 / 100 | 77.7 | no |
| SCR-02-mobile-setup-needed | 390 | /work/W-1709 | 88.9 / 100 | 71.4 | no |
| SCR-02-mobile-permission | 390 | /work/W-1099 | 71.4 / 100 | 84.2 | no |
| SCR-02-mobile-effect-uncertain | 390 | /work/W-1710 | 94.4 / 100 | 90.1 | yes |
| SCR-02-mobile-awaiting-reconciliation | 390 | /work/W-1711 | 55.6 / 100 | 71.5 | no |

Pass is false on 20 rows only because visual < 90. Coverage with exceptions is 100 everywhere.

### Boards under 90: measured gap and cause
Causes common to every board (measured with `_driver/measure.mjs`; the board and page block positions are within 2–7px after the header changes):
- **Frame:** the desktop top bar has no Start work (F-05). The phone bar shows the frame's link and no reference.
- **NextStep:** the contract `next_step` callout (required on every state, AC 12, markup owned by F-06) is an extra block, about 40px on desktop and 60px on phones.
- **Overview / History tabs:** extra on every overview board. On phones they close the page.

Per board:
- **desktop default (85.8):** The F-04 Note/Approve/Return/Reject block (about 250px tall in the right card) is excepted but counts in the visual score. Our card ends at the "Open the decision" button.
- **desktop processing (88.6), waiting (87.4), owner-needed (88.4):**
  - the mascots are the 192px avatars from `public/agents`, not the boards' full-pose images, which `public/` does not have and is outside this lane;
  - the waiting card lacks the two excepted buttons;
  - each has the NextStep block.
- **desktop history (86.0):** the approved rows-per-page footer, the "As of" line, the missing Documents tab and the CSV button (both excepted).
- **desktop issue (84.0):** the board omits the stations. The page keeps them under the preview (contract data, about 290px) and appends the agent card, because Chidi's work is on the record. The excepted "Issue and send" button is missing.
- **desktop cancelled (76.5):** the long title still wraps at 40px, where the board's 36px title fits on one line. That shifts the whole page by about 40px.
- **desktop permission (84.3):** the excepted "Ask for access" button and audit line are missing.
- **desktop awaiting-reconciliation (84.3):** the right column is F-09's ReconcilePanel slot, which is empty on the base. The gap is confined to that region, and the coordinator re-scores after F-09 (spec carve-out).
- **Phones (71.4–85.4):**
  - The phone boards end their main column early and pin an action bar at 760–844px. On the page the content flows, and NextStep and the tabs follow it.
  - The boards cut the station list at the frame edge, while the page shows every station.
  - "Milestone 2 invoice" wraps on phones where some phone boards say "M2 invoice" (a board disagreement; the fixture follows desktop).
  - The local Archivo renders narrower than the canvas font, so titles that wrap on the board fit on one line here.
  - The awaiting-reconciliation phone board is mostly F-09's panel.
  - Per the readiness split rule, the phone boards are the remainder for round 2. The likely next steps are a bottom action bar pinned on phones and the board fixtures' phone wording; both need a design-engineer call on the exceptions.

## Rebase note for F-09
- `TaskPanels({ id, tasks })` is unchanged. Wrap its single `{task.you_can_act && (<Link …>Open the decision</Link>)}` expression with `responseOf(task) ? … : …` as before. `DecisionRows` now sits just above it.
- Put `<ReconcilePanel id={id} item={asResponseItem(item)} />` at the single `{/* F-09: ReconcilePanel mounts here */}` comment. It is at the top of `.work-aside`, which every item renders, live ones included.
- Do not mount it beside the columns as before: `WorkItemOverview` now renders one column pair for both the F-03 and the board layouts.
- Re-score SCR-02 waiting and awaiting-reconciliation after the rebase.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-14 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0. The Django check is clean, and npm ci, lint, typecheck, vitest (15 files, 403 tests) and `next build` all pass.
- `cd frontend && E2E_PORT=4501 MOCK_PORT=4502 npx playwright test e2e/work-item.spec.ts e2e/work-item-board.spec.ts e2e/decide.spec.ts`: exit 0, 82 passed, on the final code.
- Fidelity: `round-1/fidelity/_driver/prod.sh` then `runall.sh <round-1/fidelity>`. I started and then stopped my own servers on 4501/4502, and nothing is listening on either port now.
- `frontend/test-results` is deleted. Disk had 6.9 GB free.

## Blocked
Not blocked. Open for the design engineer:
- the 57 provisional exceptions, including the two flagged edge cases;
- the 20 boards under 90;
- the architecture adoption of D-WORKITEM-VIEW.
