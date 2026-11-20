STATUS: READY
COMMIT: 1457df1c1d4ad44327640da4efcce7d5d85dc9cd
BUILDER: builder
LANE: full

## Summary
- Round 2 fixes the blocking UI and UX findings from round 1. Contract mock only: nothing is sent to Support (unchanged from round 1; the "What is sent, and what stays held" section there stands).
- State chips take their tone from the data (amber for ready and published, red for gaps, green for acknowledged). Handover rows follow the board. The reply form's "Support replied" is one field. The phone screens carry the board's headings. Phone Back goes to the Delivery tab.
- The mock now refuses the W-37xx items to a persona who cannot see P-0101 (ceo, none).

## Changes
- Fixtures `mock/fixtures/work/W-37*.json`, `response/W-37*.json`: ready, published and not-delivered status tones are `uncertain`; the DRAFT tag is `agent`; each state carries `workspace.title` (the board's phone heading: "Support handover", "Support's reply", "Support found gaps", "Handover acknowledged").
- `workspace.css`: handover rows (label left, value right, neutral tags as plain mono caps, other tones stay chips), scoped on `data-line="delivery_handover"`; `.resp-replied` field; phone: the reply panel has no card, its head is screen-reader only, the attest row is 48px.
- `SupportHandoverForm.tsx`, `ResponseForm.tsx`, `ProofField.tsx`: one "Support replied" group holding name and role plus the date-time (the date-time and Proof keep screen-reader labels via `hideLabel`); the gaps hint is screen-reader only; the confirm tick stays.
- `Workspace.tsx` (shared, line-scoped): `screenHeading()` returns the workspace title only for `delivery_handover`; the h2 title and the h3 level step are not used for it. `WorkItemView.tsx` (shared, line-scoped): on a phone the h1 is that heading; the phone Back for `delivery_handover` is "Delivery" to `/projects/<id>/delivery`.
- `mock/server.mjs`: 404 on `/work/W-37xx` (and history) when `caseVisible('P-0101', persona)` is false.
- Tests: `tests/support-handover.test.tsx` (+6), `tests/support-handover-mock.test.ts` (+1), `e2e/support-handover.spec.ts` (+2 tests, attest row in the 44px list). `open()` waits for any h1.

## Fixes
- UI-1-1 | state chips take their tone from the fixture status (`uncertain` = amber), checked per state in a component test and an e2e colour check | 1457df1c
- UI-1-2 | Handover rows laid out like the board by CSS on the line key; DRAFT is the agent chip, other values plain mono caps at the row end | 1457df1c
- UI-1-3 | one "Support replied" field with name, role and date-time; Proof label and gaps hint visually hidden but still labelled; the confirm tick stays as an exception (Conflicts 5) | 1457df1c
- UI-1-4 | 390 headings come from `workspace.title`; the card and caption are gone on the phone record screen | 1457df1c
- UI-1-5 | waivers rewritten to name what remains | 1457df1c
- UX-1-1 | phone Back reads "← Delivery" and returns to the project's Delivery tab (component and e2e tests) | 1457df1c
- UX-1-2 | attestation row is 48px at 390 (e2e measures it) | 1457df1c
- UX-1-3 | mock returns 404 for the handover items to ceo and none; the backend must do the same | 1457df1c

Left: the History link in the shared line header is 24px tall at 390. It belongs to the shared F-22 header (all lines), so it is not changed here; recorded for the coordinator.

## Acceptance criteria
1. [~] Fidelity: coverage 100% after exceptions on all 8 boards; visual 73.8 to 88.2, all below 90, so each has a proposed D-83 waiver (builder proposal, pending design engineer).
2. [x] Exceptions: 21 entries, one added (confirm tick, Conflicts 5), the "← Delivery" one re-worded to the accessible-name difference. None covers data.
3 to 23. [x] Unchanged from round 1 and still green (checks.sh, 59 e2e).

## Fidelity
One run, app 4975 on a production build, mock 4974, persona pm. The three phone boards were re-run once after I restored one exception I had removed (the shared phone bar names the link "Back to Delivery"); the page was unchanged between those runs.

| Board | Visual | Coverage | With exceptions |
|---|---|---|---|
| SCR-48-desktop 1440 | 79.4 | 59.5 | 100 |
| SCR-48-desktop-gaps 1440 | 83.4 | 64.9 | 100 |
| SCR-48-desktop-received 1440 | 77.8 | 63.9 | 100 |
| SCR-48-desktop-record 1440 | 73.8 | 63.6 | 100 |
| SCR-48-mobile 390 | 86.8 | 55.6 | 100 |
| SCR-48-mobile-gaps 390 | 88.2 | 80 | 100 |
| SCR-48-mobile-received 390 | 75.3 | 40 | 100 |
| SCR-48-mobile-record 390 | 82.5 | 75 | 100 |

Reports in `round-2/fidelity/`. The desktop record score fell 0.4 against round 1 (the field now sits in one box, the board's text is drawn as a static line); not iterated.

## Validation
- New tests fail on the round-1 code (5 component tests, 1 mock test), pass now.
- `bash delivery/checks.sh` under the shared lock: EXIT 0.
- `npx playwright test e2e/support-handover.spec.ts e2e/delivery-release.spec.ts`: 59 passed.
- Demo left running: mock 4974, app 4975 (production build, `API_ORIGIN` set to the mock).
- Open for the design engineer: sign or refuse the exceptions and 8 waivers; Conflicts 1 to 5.
