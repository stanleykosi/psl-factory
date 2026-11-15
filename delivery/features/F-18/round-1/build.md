STATUS: READY
COMMIT: 352893425c8d197b3de15ab04eac6c68d1d05782
BUILDER: builder
LANE: full

## Summary
- Slice A (48afcfb): desktop pages sit inside an RFP frame built only from `rfp`. Team input is recordable on `/work/[id]/respond`, and a new `/work/[id]/outcome` route records won, lost, pending or unknown with proof. The mock now covers team input and E-RFP-OUTCOME, with fixtures W-2101 to W-2110.
- Slice B (3528934): the recorded states (rows, reminder, lessons, engagement, Next) and the follow-up card. Only a person's click sends the follow-up. It uses an idempotency key per version and text, is never resent, and an `effect_uncertain` send stays blocked. The mock covers E-RFP-FOLLOWUP, with fixtures W-2108.sent and W-2111 to W-2114.
- All of this runs on the contract mock (D-RFP-OUTCOME r2, still proposed). There is no backend change. Nothing goes to a real person or provider.
- All 18 boards reach 100% coverage after exceptions. The visual score is at least 90 on 4 boards; the other 14 fall short, mostly because of approved exceptions (see Fidelity: gap and cause per board).
- `delivery/checks.sh` passes at head. So do the e2e tests (`rfp`, `response`, `work-item`: 69 passed).

## Changes
- `frontend/src/features/rfp/` (new)
  - `RfpFrame.tsx`: eyebrow `line · reference`, the h1 `client · title`, a status tag toned by kind, the PM tag, and `<nav aria-label="RFP">`. The current tab gets `aria-current`, Team input and Outcome are links, and the unbuilt tabs are plain text.
  - `OutcomeView.tsx`, `OutcomeForm.tsx`, `useOutcome.ts`: the outcome page, its form and the write. Guards: 409 keeps entries and proof and reloads; 422 shows the server's message; 403 reloads and removes the form; network or 5xx reloads once and never resends; a failed reload keeps Record off and "Try again" only reads.
  - `RecordedView.tsx`, `FollowupCard.tsx`, `useFollowup.ts`: the recorded states and the person-sent follow-up.
  - `RfpOutcomeLink.tsx`, `api.ts`, `contract.ts` (types derived from `src/api/schema.d.ts` only), `labels.ts`, `rfp.css`, `index.ts`.
- `frontend/src/app/work/[id]/outcome/page.tsx` (new): the page title is "Record the outcome · PSL Factory".
- `frontend/src/features/response/`
  - New: `TeamInputForm.tsx`, and `Segmented.tsx` (a role="radio" psl-seg group with one tab stop and arrow keys, as `start-work/IntakeField`).
  - `labels.ts`: `team_input` added to `RECORDABLE`, `entry` and `record`.
  - `useResponse.ts`: team, estimate and what entries; `teamAction`, `estimateShown` and `teamInputOpen`; the team fields in the body.
  - `contract.ts`: `teams`, `blocking` and the three team body fields, all already in v7.
  - `ResponseView.tsx`: team input variant, RFP frame and the "← RFP" phone back link.
  - `ResponseForm.tsx`: exports `Select`, `WhenField`, `Note` and `RecordRow`.
  - `ProofField.tsx`: an optional `choose` label.
- `frontend/src/features/work-item/WorkItemOverview.tsx`: one import and one rendered line, `<RfpOutcomeLink id item />`.
- `frontend/mock/response.mjs`
  - Team-input rules on E-RESPONSE.
  - E-EVIDENCE-UPLOAD accepts `rfp_outcome.evidence_kind`.
  - E-RFP-OUTCOME swaps in W-2105 to W-2108 under the item's own id, case and next revision.
  - E-RFP-FOLLOWUP keeps the repeated-key store, the W-2111 uncertain reply and W-2112's one-time 409, and serves `.sent`.
  - `server.mjs` is not edited.
- Fixtures: `mock/fixtures/response/work/W-2101…W-2114.json`, `W-2108.sent.json`, `W-2112.next.json`, plus `mock/fixtures/response/W-2101.recorded.json`.
- Tests: `tests/rfp.test.tsx` (50), `tests/rfp-mock.test.ts` (38) and `e2e/rfp.spec.ts` (all new), plus one changed assertion in `tests/response-mock.test.ts` (below).
- Factory: `delivery/features/F-18/fidelity-exceptions.json` (45 entries) and `round-1/fidelity/**` (driver, frozen server, 10 frozen pages, 18 `report.json` and `side-by-side.png`, `scores.txt`).

### Deviations from the spec (for the reviewers)
- **Task ids are T-2101 and T-2102, not T-2001 and T-2002.** T-2001 already exists in the default `E-WORK-ITEM.json` and in `work/W-1002.json`. `server.mjs`'s claim lookup finds the default first, so the claim answered 409. `server.mjs` is read-only, so I renamed the tasks. The fidelity URL is `/work/W-2101/respond?task=T-2101`.
- **`W-2101.recorded.json` is in `fixtures/response/`, not `fixtures/response/work/`.** `respond()` reads its `.recorded` sidecars from there (the F-09 convention). `W-2108.sent` and `W-2112.next` are in `response/work/` as the spec says.
- **W-2105 to W-2108 went in slice A,** because the slice A outcome mock swaps them in. Slice B added W-2108's follow-up.
- **The team-input board is scored on a frozen, filled page,** like the outcome forms, not on the live URL. The board draws the form filled in, so the live empty form would need an exception for every value.
- **Board copy kept where the spec is silent:**
  - "For the RFP response and the costing sheet." under the team panel head.
  - "A role PSL allows to record outcomes" under "You are recording as".
  - "What the client told us. Use Unknown if they didn't say." under the expected date.
  - The outcome footnote, as the spec allows.
- **Data the frame and card read that the spec didn't list:**
  - The frame eyebrow leads with `item.line` ("PRE-SALE / RFP · …"). On W-2110 it shows line, reference and status only.
  - "· done" and a DONE tag on the follow-up agent card come from every `checks[]` item being `done`. Nothing else derives them.
- **Layout choices that keep the board's rows in place:**
  - The team attestation sits beside the proof and the note beside Received on desktop, as F-09's SOW form does.
  - "Amount not known" shares the amount hint's line.
  - `.rfp-frame .rfp-tabs` has a -8px top margin to absorb the 40px title (Conflicts 2).
- **Phone targets and title:** segmented options are 44px on the phone (AC20), and the phone h1s use `shell-title` at 26px (AC5).

## Fixes
None. This is round 1.

## Acceptance criteria
1. [ ] **Desktop fidelity:** coverage after exceptions is 100 on all 9. Visual is at least 90 on team-input (93.4), rfp-outcome (90.3), -lost (94.6) and -pending (92.9). Under 90: rfp-outcome-unknown 88.6, rfp-won 73.5, rfp-lost 88.2, rfp-pending 74.6, rfp-unknown 86.7. Causes are under "Fidelity: gap and cause per board".
2. [ ] **Phone fidelity:** coverage after exceptions is 100 on all 9. Visual is 77.3 to 89 on all 9 (scores.txt). Causes are under Fidelity.
3. [x] **Form variants:** `round-1/fidelity/drive-states.mjs` resets the mock, opens the page with the pm cookie and uses the real controls. It types the board's values and uploads the board's file name and size (unknown gets `tamarind-submission-email.pdf`, 42 KB, because proof is required, Conflicts 7). It copies values into attributes, strips scripts, adds `<base href="http://localhost:4623/">` and writes `frozen/<variant>-<width>.html`. Frozen pages: `team-input`, `rfp-outcome`, `rfp-outcome-lost`, `rfp-outcome-pending` and `rfp-outcome-unknown`, each at 1440 and 390. `serve-frozen.mjs` serves them on 4623. No product or mock code is changed for this.
4. [x] **Exceptions:** 45 entries, each with role, name, category, reason and approved_by. The map is below.
5. [x] **Titles and phone bar:** e2e "axe, title and bar" runs on 11 states at both widths. Each has one h1 with `.shell-title`, computed 40px at 1440 and 26px at 390. The phone bar link is "← RFP" (named "Back to RFP"), it goes to `/work/{id}`, and the note is OUTCOME, WON, LOST, PENDING or UNKNOWN (none on team input). There is no frame on the phone and no "← " link inside main. On 403/404 there is one h1 and no id in main or the bars.
6. [x] **Frame:** component tests on W-2101 (reference, h1, status, "PM Tunde Bello", badges exactly ["64","2/4"], plain-text tabs with no tabindex, team input `aria-current`), W-2103 (Team input links to /work/W-2103; the outcome link appears only with `rfp_outcome`, checked against W-2109) and W-2110 (no nav, PM or badges), plus status tones. e2e: the first Tab from the frame lands on "Team input", and Requirements, Pricing and Submission are never focused.
7. [x] **Team input options and request:** tests cover the returned teams only, Security showing the Estimate field and QA hiding it, the hint then alert lines, and the exact POST body (team, `estimate_person_days: 18` as a number, what, action `estimate`, who, attested, `responded_at` with +01:00, case_revision). The claim comes first with `expected_revision: 4`. A non-estimate team sends `input` and no estimate.
8. [x] **Team input guards:** tests cover W-2102, no block, no input action and empty teams (all not open, no write). They also cover a double press (one claim, one response); 409 keeping entries; 422 showing the message; 403 leading to the not-open state; 401 showing sign-in; and network errors (one reload, then a failed reload keeps Record off, "Try again" only reads). The mock's `record-then-fail` is covered in `rfp-mock.test.ts`.
9. [x] **Entry links:** the `WorkItemOverview` test on W-2101, W-2102, W-2103 and W-2109. The `work-item*` tests pass unchanged.
10. [x] **Outcome options and gating:** tests on W-2103 (four results with none chosen, both roles, Record off until everything required is in), W-2104 (Won and Lost only, single role with no select), and W-2109 / no record_as / empty results (not open). Mock: persona none gets 403.
11. [x] **Outcome request:** tests assert the exact body for won, lost, pending and unknown. Fields typed under another result are not sent. A note over 2000 characters makes no request.
12. [x] **Unknown stays unknown:** a blank amount sends no `awarded_amount`. "Amount not known" sends `{currency:'NGN', unknown:true}`. "40,951,000" sends "40951000.00". "abc" and "1.234" show a message and make no request. `grep -rn "0\.00" frontend/src/features/rfp` finds nothing. Recorded won shows no amount.
13. [x] **Outcome guards:** tests cover 409 (entries and proof kept, next press carries revision 9 and case_revision 12), 422, 403, network and 502 (one reload, no resend), a failed reload (Record off, Try again reads), a double press (one request), 200 (one reload, then the recorded heading), a failed reload after 200 ("Outcome recorded. Won" with no rows), 401, and 403/404 (no secrets shown).
14. [x] **Recorded states:** tests on W-2105, W-2106, W-2107 and W-2108, and on W-2110 with `recorded: {result}` (heading only). Board-only copy is absent from the DOM. An unknown result string reads "Outcome recorded".
15. [x] **Follow-up display:** tests on W-2108 (agent, marks, `To procurement@tamarindloans.example`, draft, note, Send and Edit), W-2113 (neither button), W-2114 (callout and Check again, which only reads) and W-2108.sent ("Sent 03 Dec 10:30", no buttons). With no note the card says "It goes only if you send it."
16. [x] **A person's action:** with fake timers advanced 10 minutes plus focus events there are 0 follow-up POSTs; one click makes 1. A double click makes 1 request. The body keys are exactly expected_revision, version and idempotency_key; `body` is sent only when edited, different and not blank. The only caller of `sendFollowup` is `useFollowup.send` (grep). Mock test: a repeated key returns the stored reply with no second effect.
17. [x] **Uncertain and stale:** W-2111 shows the callout and no Send after one reload and one POST. Network and 502 reload once, and a later press reuses the same key. A failed reload turns every control off. On W-2112, 409 keeps "My own words", shows "Current draft (v3)", and the next press sends version 3 with a new key. 403 removes Send; 422 keeps the text.
18. [x] **Tenant and permission:** 403/404 component tests check for no reference, title or client. The mock gives persona none 403, no CSRF header gives `csrf_failed`, and W-2109 (no block) gives 403 on E-RFP-OUTCOME; the follow-up gives 403 on W-2113 and W-2114.
19. [x] **The mock matches v7:** `npx vitest run tests/rfp-mock.test.ts tests/response-mock.test.ts` gives 88 passed. Every W-21xx fixture and sidecar validates. W-2110 carries only `reference`/`status`, `submission{id,label}`, `results` and `record_as`. Every reply is validated by `post()`.
20. [x] **Accessibility:** `E2E_PORT=4621 MOCK_PORT=4622 npx playwright test e2e/rfp.spec.ts e2e/response.spec.ts e2e/work-item.spec.ts` gives 69 passed, with timezone Africa/Lagos. It covers no axe violations on 11 states at 390 and 1440 and no sideways scroll; focus rings and Tab order (Team, Estimate, What, Choose a file, confirmation, Received, Note); and on the phone a 50px pinned Record and segment targets of at least 44px. Follow-up Send and Edit are reached by keyboard and Enter sends once, and nothing animates under reduced motion.
21. [x] **Tokens only:** the colour grep over `rfp.css` and `response.css` returns nothing.
22. [x] **Existing behaviour:** `delivery/checks.sh` passes (46 files, 1269 tests). `response.test.tsx:689-694` still passes unchanged: team_input on W-1601 has no teams and no input/estimate action, so it stays not open. The one changed assertion is listed below. `git diff --stat 79f25e5 -- frontend/src/shell frontend/src/api architecture frontend/package.json frontend/package-lock.json frontend/mock/server.mjs` is empty.
23. [x] **No new dependency or hard-coded options:** `package.json` and the lock file are unchanged. `grep -rn "Relationship owner\|Scope fit\|Engineering" frontend/src` finds only a pre-existing comment in `features/exceptions/types.ts:10`.
24. [x] **build.md evidence:** this file.

### Changed assertion
- `tests/response-mock.test.ts:113`: `expect(RESPONSE_OPERATIONS).toEqual([...])` now lists 'E-RFP-OUTCOME' and 'E-RFP-FOLLOWUP' as well. The spec adds both to `RESPONSE_OPERATIONS`. The match is still exact, not loosened.

## Fidelity
`round-1/fidelity/scores.txt` (cookie `psl_mock_persona=pm`, production build, app 4621, mock 4622, frozen pages 4623):

```
board                              width  coverage  with-exceptions  visual  pass   page
SCR-16-desktop-team-input          1440   76.9      100              93.4    true   /frozen/team-input-1440.html
SCR-16-desktop-rfp-outcome         1440   72.5      100              90.3    true   /frozen/rfp-outcome-1440.html
SCR-16-desktop-rfp-outcome-lost    1440   75        100              94.6    true   /frozen/rfp-outcome-lost-1440.html
SCR-16-desktop-rfp-outcome-pending 1440   73.8      100              92.9    true   /frozen/rfp-outcome-pending-1440.html
SCR-16-desktop-rfp-outcome-unknown 1440   71.1      100              88.6    false  /frozen/rfp-outcome-unknown-1440.html
SCR-16-desktop-rfp-won             1440   56.7      100              73.5    false  /work/W-2105/outcome
SCR-16-desktop-rfp-lost            1440   74.1      100              88.2    false  /work/W-2106/outcome
SCR-16-desktop-rfp-pending         1440   76.9      100              74.6    false  /work/W-2107/outcome
SCR-16-desktop-rfp-unknown         1440   82.4      100              86.7    false  /work/W-2108/outcome
SCR-16-mobile-team-input           390    73.7      100              85.1    false  /frozen/team-input-390.html
SCR-16-mobile-rfp-outcome          390    60        100              88.5    false  /frozen/rfp-outcome-390.html
SCR-16-mobile-rfp-outcome-lost     390    66.7      100              82.4    false  /frozen/rfp-outcome-lost-390.html
SCR-16-mobile-rfp-outcome-pending  390    64.7      100              87.1    false  /frozen/rfp-outcome-pending-390.html
SCR-16-mobile-rfp-outcome-unknown  390    53.8      100              89      false  /frozen/rfp-outcome-unknown-390.html
SCR-16-mobile-rfp-won              390    37.5      100              74.4    false  /work/W-2105/outcome
SCR-16-mobile-rfp-lost             390    40        100              78.5    false  /work/W-2106/outcome
SCR-16-mobile-rfp-pending          390    60        100              77.3    false  /work/W-2107/outcome
SCR-16-mobile-rfp-unknown          390    85.7      100              86      false  /work/W-2108/outcome
```

Side-by-side images: `delivery/features/F-18/round-1/fidelity/SCR-16-{desktop,mobile}-<board>-{1440,390}/side-by-side.png` (18 folders, each with `report.json`).

### Gap and cause per board under 90
These causes apply to several boards:
- **(T) Conflicts 2.** The frame title is 40px against the board's 32px, and the phone h1 is 26px against 20–22px. On desktop the tabs absorb the 8px; on the phone every row below moves down 4–6px.
- **(R) Conflicts 5, 10, 11 and AC20.** Fields the request needs but the boards don't draw: the note, the attestation, "Amount not known", "You are recording as" on the phone when there are 2 roles, and the "To …" line. Segments are 44px on the phone against 40px on the board.
- **(D) The browser's date input.** Native datetime-local text ("12/04/2026, 11:00 am") sits where the board draws "04 Dec 2026, 11:00". The values are exceptions (Conflicts 8); the drawn text differs.
- **(C) Approved omitted copy.** Board blocks with no field behind them leave an empty band, so the rest of the page shifts up: Conflicts 12/13 and D-60 (c).

| Board | Visual | Cause |
|---|---|---|
| desktop rfp-outcome-unknown | 88.6 | (C) the "What happens next" box and "No proof needed" are gone, while the proof card is kept (Conflicts 7 / D-60 b); (R) the note |
| desktop rfp-won | 73.5 | (C) the intro sentence and the planning-packet agent card (about 300px tall, D-60 c); the heading is the result word (Conflicts 15) |
| desktop rfp-lost | 88.2 | (C) the "Nothing is deleted…" half of the archive callout; the lost tag is red by spec (the board is grey) |
| desktop rfp-pending | 74.6 | (C) the intro callout ("…delayed to 12 Dec…", Conflicts 12); the rows panel moves up 50px |
| desktop rfp-unknown | 86.7 | (R) the "To procurement@… · draft v1" line (spec Contract 6); (C) "Ask Tola"; the unknown tag is neutral by spec (the board is amber) |
| mobile team-input | 85.1 | (T); (R) the note, the attestation and 44px segments; (D); "Engineering" against "Eng." (Conflicts 6) |
| mobile rfp-outcome | 88.5 | (T); (R) the roles select, the note and "Amount not known"; (D) |
| mobile rfp-outcome-lost | 82.4 | (T); (R) the roles select and the note; (C) the "What happens next" box |
| mobile rfp-outcome-pending | 87.1 | (T); (R); (D) |
| mobile rfp-outcome-unknown | 89 | (T); (R); the proof card is kept (Conflicts 7) |
| mobile rfp-won | 74.4 | (T); (C) the intro and the planning-packet card; plus the Next panel and engagement row, which the phone board draws differently |
| mobile rfp-lost | 78.5 | (T); the debrief link, archive callout and Next panel ("No engagement…" and "Back to projects") come from data but the phone board doesn't draw them |
| mobile rfp-pending | 77.3 | (T); (C) the intro; the Next panel and the "Record the outcome" button sit in the page, where the board pins the button |
| mobile rfp-unknown | 86 | (T); the agent checks card and the "To" line are shown (spec Contract 6, AC15); the phone board draws only the draft |

### Exception-to-Conflicts map (`fidelity-exceptions.json`)

| Exceptions | Conflicts item | approved_by |
|---|---|---|
| tablist "RFP"; tab "Requirements 64", "Team input 2/4", "Team input 4/4", "Pricing", "Submission", "Outcome" | 3, 4 | coordinator, provisional (D-60) |
| link "← RFP" | 1, 19 | coordinator, provisional (D-60) |
| radio "Eng., given" | 6 | coordinator, provisional (D-60) |
| "No proof needed. Nothing has been heard yet." | 7 / D-60 (b) | design engineer, 14 Nov (D-60) |
| "26 Nov · submission email" | 8 | coordinator, provisional (D-60) |
| 11 typed or chosen values drawn as fixed text ("18", "Security estimate…", the dates, "₦40,951,000.00", the lessons text, "Relationship owner ▾") | 8, same cause generalised | builder proposal, pending design engineer |
| "As stated in the award letter. If it differs…"; "What happens next:" and its 4 variants | 12 / D-60 (c) | design engineer, 14 Nov (D-60) |
| "Archived as ARC-0117. Nothing is deleted…" (desktop and phone wordings) | 12 / D-60 (c) | design engineer, 14 Nov (D-60) |
| "Building the planning packet", "Tola · PMO agent · step 3 of 5", "WORKING", "Started 14:02…", link "Ask Tola" | 13 / D-60 (c) | design engineer, 14 Nov (D-60) |
| headings "Won · handed off to engagement", "Lost · archived with lessons", "Lost · archived" | 15 | coordinator, provisional (D-60) |
| the recorded intros "Won. The response…", "Handed off to engagement EN-0042.", "Tamarind Loans told us…", "Delayed to 12 Dec…"; "Lessons · recorded by … from the client's debrief" | 12 | coordinator, provisional (D-60) |
| "HANDOFF" | 13 (the won board's rows heading around the packet card) | coordinator, provisional (D-60) |
| "Lessons" (phone panel name) | 12 (the two boards disagree) | builder proposal, pending design engineer |

### Contract questions for the backend developer (D-RFP-OUTCOME r3)
1. Should `evidence_id` be optional on `result: unknown`? The board says "No proof needed" (D-60 b).
2. Is there a field for consequence copy, such as `rfp_outcome.consequences[]` or `recorded.intro`? It would carry "What happens next…", the recorded intros, "flag for the PM if it differs from costing v2" and "Nothing is deleted / Tola uses accepted answers" (D-60 c).
3. Is there a field for the planning-packet agent on a won outcome (steps, status, `started_at`)? Is there an assistant endpoint behind "Ask Tola"?
4. `followup` has no agent status. The page shows "· done" only when every `checks[]` item is `done`. Should there be `followup.agent_status`?
5. Can rows and lessons carry a tone? The board shows "NOTHING YET" as an amber tag and lesson categories in amber or green; the page draws neutral.
6. Should `teams[]` carry a short label? The phone board draws "Eng.".
7. Is there a currency list for `awarded_amount`? NGN is fixed today.
8. Fixture note for whoever owns `server.mjs`: task ids T-2001 and T-2002 collide with the default `E-WORK-ITEM.json` and W-1002, so F-18 uses T-2101 and T-2102.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-18 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0 at 48afcfb (slice A, 1235 tests) and at 3528934 (slice B: Django check OK, lint, typecheck, 46 files and 1269 tests passed, next build OK). In one earlier run on this head, `work-item-board.test.tsx` ("keeps the link visible…") timed out on Loading while the machine was loaded. It passed in isolation, on the base without these changes, and in the full re-run.
- `npx vitest run tests/rfp.test.tsx`: 50 passed. `npx vitest run tests/rfp-mock.test.ts tests/response-mock.test.ts`: 88 passed.
- `E2E_PORT=4621 MOCK_PORT=4622 npx playwright test e2e/rfp.spec.ts e2e/response.spec.ts e2e/work-item.spec.ts`: 69 passed (1.2m). `frontend/test-results` was deleted afterwards.
- Fidelity: the command from the spec for each of the 18 boards (with `--exceptions …/fidelity-exceptions.json --wait-ms 500`), on a production build. Only `report.json` and `side-by-side.png` are kept, plus the frozen pages and the two helper scripts. The servers on 4621, 4622 and 4623 are stopped.

## Blocked
Not blocked.
