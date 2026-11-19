STATUS: READY
COMMIT: ee8fe64afa47a84ad9599e9f70820ec5fdacaae6
BUILDER: builder
LANE: full

## Summary
- W-4004 (and the reconciled W-4003) now draw the verified figures as the board's dark strip: six cells on desktop, a 3x2 grid on a phone. Each cell shows its label over its value. The values come from the fixture and the page does no arithmetic. A missing value reads Unknown. The VERIFIED cell is green because the fixture's tag says `verified`. The limit sentence is a muted caption under the strip with no panel. The 10 "tool limit" exceptions that hid this are removed.
- Fact tags ("ACCEPTED", "UNKNOWN", and the "NOT SET" holds) are drawn as tags in the tone the backend sends.
- Phone W-4003 now runs in the board's order: title, status, station line, banner, Delivery, Next, then the choices above the pinned "Record and continue". There is no gap, and nothing sits above the workspace.
- On desktop W-4003 the button can now be pressed before a choice, and the press says "Choose what happened to continue." After "It arrived" the button stays off until the proof is uploaded, and "Upload the proof to continue." sits beside it (`aria-describedby`).
- Gate and e2e are green. Visual on the two verified boards fell under the 70 floor: the strip now matches the board but sits lower because of the frame. One-board floor exceptions are proposed for the design engineer (see Fidelity).

## Changes
- `frontend/src/features/workspace/Sections.tsx`:
  - `FactsList` draws `item.tag` as a `Tag` in its tone, in place of the same words as plain text.
  - New `FiguresStrip` (a `dl`), used when `SectionView` gets `strip` on a `figures` section.
  - New `caption` prop: a one-item, untitled, plain `text` section is drawn as `<p class="ws-caption">`.
  - **Listed difference:** this file is shared and read-only in the spec. UI-1-1 and UI-1-2 cannot be met without changing it, and the new tests fail without the change. Other lines' tagged facts (F-33 W-2706, F-42 W-3907…W-3909 "NOT SET") now draw as a stopped-tone tag with the same words. Their tests pass unchanged.
- `frontend/src/features/workspace/Workspace.tsx`:
  - On `cash_forecast`, untitled `figures` sections get `strip` and every section gets `caption`. W-2004, the older D-62 example on the same line key, has only titled figures, so it is unchanged.
  - The reconcile panel sits at the top of `.ws-side` on desktop (`nested`, so it is a named section and not a second landmark). On a phone it is drawn after the side column.
- `frontend/src/features/work-item/WorkItemOverview.tsx`: the overview draws no reconcile panel for `cash_forecast` at either width. The exceptions list uses the shared constant.
- `frontend/src/features/workspace/labels.ts`:
  - `reconcileBeside` is replaced by `forecastLine(lineKey)`.
  - `SCHEDULE_LINES` uses `INTERNAL_RECONCILE_LINE` from `response/labels.ts`, so the `cash_forecast` key is written once (TECH-1-3).
- `frontend/src/features/response/ReconcilePanel.tsx`:
  - new `nested` prop (`section` instead of `aside`);
  - for the internal line only: the button can be pressed before a choice (desktop as well as phone), and there is a proof-first hint.
  - Other lines are unchanged: `grep -c "invoiced twice"` is still 1, and `response.test.tsx` is unchanged and passes.
- `frontend/src/features/workspace/workspace.css`: additive `.ws-figstrip*`, `.ws-section--figures.ws-section--strip` and `.ws-caption` rules, tokens only.
- Fixtures `W-4004.json` and `response/W-4003.delivered.json`: V-6 VERIFIED gets `tag: {label: "VERIFIED", tone: "verified"}`. This is backend data for the cell tone. The tag's words are not drawn twice.
- Tests: `tests/cash-forecast.test.tsx` (44 tests), `e2e/cash-forecast.spec.ts` (new verified-strip test, phone order check, the desktop press, the proof hint, and the region role).
- `delivery/features/F-43/fidelity-exceptions.json`:
  - removed the 10 tool-limit entries for the strip and caption;
  - "Unknown" is recategorised as `component` (UI-1-4);
  - waivers re-scored.
  - All entries remain "builder proposal, pending design engineer".

## Fixes
- UI-1-1 | 29a7f94c | Verified figures are the dark strip (6 across / 3x2), label over value as returned, Unknown never 0, the VERIFIED cell's tone from its tag. The limit sentence is a caption. The 10 tool-limit exceptions are removed.
- UI-1-2 | 29a7f94c | `FactsList` draws a fact's `tag` in its tone (ACCEPTED done, UNKNOWN waiting).
- UI-1-3 | 89a5caf4 | The phone reconcile panel is drawn inside the workspace after Next. The order is stations, banner, Delivery, Next, then the choices. No gap, and the overview draws no copy.
- UX-1-1 | 89a5caf4 | On desktop, a press with no choice shows "Choose what happened to continue." The off button after "It arrived" is described by "Upload the proof to continue."
- TECH-1-2 | 89a5caf4 | The desktop panel is a named `section` in `.ws-side`, with no nested `aside`.
- TECH-1-3 | 89a5caf4 | The `cash_forecast` key is written once (`INTERNAL_RECONCILE_LINE`), and used by labels, `forecastLine` and the overview.
- TECH-1-4 | 5020a86b | The phone test checks for exactly one `.resp-reconcile`.
- UI-1-4 | (factory file) | The "Unknown" exception is recategorised as `component`.

Tests for the fixes: with `src/` reverted to 59ce7dc1, 6 of the 42 tests fail (W-4001 tags, W-4003 tag and landmark, W-4004 strip, desktop no-choice press, the proof hint, phone order and count). All pass on the head.

Left on purpose:
- TECH-1-1, the shared stale-409 gap: it comes in through dlv-00 with F-35/F-39.
- TECH-1-5, the "received" wording: a product question.
- UX-1-2, the phone callout wording: Conflicts 4 approved only the desktop words; this is for the design engineer.
- UX-1-3 and UX-1-4: fixture or product wording.
- UX-1-5: the shared frame.
- UI-1-5, the landmark name on W-4001: not asked for this round.

## Acceptance criteria
1. [x] Four states from data: component tests pass, and the AC 1 grep over `src` returns nothing.
2. [x] Amounts as returned: unchanged.
3. [x] Nothing computed. The strip draws `value`/`money` as returned. The AC 3 diff grep test passes.
4. [x] Unknown is never 0. A strip cell with no value draws `<Unknown />`.
5. to 9. [x] Unchanged; tests pass. The AC 9 Sources facts now show the ACCEPTED tag in its tone.
10. and 11. [x] Pass. The panel is named "Record what happened" (region on desktop, complementary on a phone).
12. [x] W-4004 shows the six figures as a strip, the caption and Next; Verified appears only after the re-read.
13. to 17. [x] Unchanged; pass.
18. [x] "Choose what happened to continue." now shows at both widths. "It arrived" keeps the button off until the proof is uploaded, with a hint.
19. and 20. [x] Pass.
21. [x] Phone: one column in the board's order, `scrollWidth` 390, and the footnote clears the pinned bar (measured: foot bottom 651, bar top 762 after scroll).
22. [~] Coverage after exceptions is 100 on all 8 boards. Visual: 6 boards are 70.9 to 84.4 with D-83 waivers. The 2 verified boards are 55.6 and 51.9, with one-board floor exceptions proposed and pending the design engineer.
23. [x] e2e axe is clean at 1440 and 390.
24. [x] The CSS diff uses tokens only, with no component copy.
25. [x] Mock tests pass.
26. [~] As in round 1, plus the listed shared `Sections.tsx` change for UI-1-1 and UI-1-2.
27. [x] Gate green, and the listed e2e set is green (one flaky mock reset; see Validation).
28. [x] This file.

## Validation
- `bash delivery/checks.sh` at 5020a86b, run under the shared lock (lock removed afterwards): `exit 0`. Test Files 120 passed, Tests 2882 passed, build compiled.
- e2e: `E2E_PORT=4895 MOCK_PORT=4894 npx playwright test e2e/cash-forecast.spec.ts e2e/income-schedule.spec.ts e2e/workspace.spec.ts e2e/response.spec.ts e2e/finance-month-end.spec.ts` gave 142 passed and 1 failed (9.5m).
  - The failure was `response.spec.ts:177` (W-1603, client line). The mock proxy logged `read ECONNRESET` on that test's `/actions` POST, so the panel correctly stayed in its uncertain state.
  - Rerunning `e2e/response.spec.ts` gave 16 passed (1.4m).
  - `test-results` was deleted.
- Fidelity: one run, `round-2/fidelity/run.sh` with the updated exceptions file. It used a production build (`API_ORIGIN=http://127.0.0.1:4894 FRAME_FIXTURES=1`), app on 4895, mock on 4894 reset before each board, persona `finance_lead`.

| board | coverage | with exceptions | visual | waiver |
|---|---|---|---|---|
| desktop investigating 1440 | 86.1 | 100 | 84.4 | D-83 |
| desktop review 1440 | 74.6 | 100 | 75.6 | D-83 |
| desktop uncertain 1440 | 84.6 | 100 | 70.9 | D-83 |
| desktop verified 1440 | 93.8 | 100 | 55.6 | D-83 + floor exception (proposed) |
| mobile investigating 390 | 77.8 | 100 | 83.1 | D-83 |
| mobile review 390 | 56 | 100 | 78.4 | D-83 |
| mobile uncertain 390 | 57.1 | 100 | 74.5 | D-83 |
| mobile verified 390 | 82.4 | 100 | 51.9 | D-83 + floor exception (proposed) |

- Verified boards, for the design engineer:
  - Raw coverage rose from 68.8 to 93.8 (desktop) and from 29.4 to 82.4 (phone), because the strip and caption are now read without the tool-limit exceptions.
  - Visual fell from 75.8 to 55.6 and from 72.6 to 51.9. The side-by-side shows the strip drawn as the board draws it, but about 40px lower on desktop and about 70px lower on a phone. On desktop the shared StationTrack adds status lines under the station names. On a phone the frame draws the full two-line title, the status tag and History. All of these are Conflicts 11 and 9. A dark block a little lower scores worse pixel by pixel than the old white list did.
  - This is an open design-engineer decision: sign the two floor exceptions, or change the shared frame. It is not a gap in this feature.
- Demo left running: mock on 4894 (`MOCK_PORT=4894 node mock/server.mjs`) and the app on 4895 (production build, `next start -p 4895`). Disk had 5.6 GB free.

## Blocked
None.
