VERDICT: CHANGES
COMMIT: 9ee65d4d689c0101591a3f94a5146c72db9545bc
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
- All 20 SCR-04 boards in scope fail the fidelity gate. Desktop (1440): coverage 52.6–69.2%, visual 80.0–90.2. Phone (390): coverage 37.5–72.7%, visual 42.4–62.1. There is no `fidelity-exceptions.json`, so nothing is excused.
- The top-bar "+ Start work" split button and the phone "+ Start" match SCR-01. The drawer does not match its boards.
- The main gaps: the primary button is action-blue and auto width instead of the full-width start-orange button; choice fields do not fill the width; the chooser is a radio list where the board has bordered line cards and a Tola callout; "What happens next" is a grey stacked box instead of one inline line; the phone sheet adds Back and a different head; the phone line drawers are a sheet where the boards show full screens.
- Several differences come from the spec itself (line title as the drawer title, the From/To date range, group headings, no Proof field, billing contact in the summary, "Back" rather than "Cancel" when opened from the chooser). Only the design engineer can approve these, in `fidelity-exceptions.json`. Until then they stay blocking.
- Tokens and bundle classes are mostly used correctly. No overflow at 390 (scrollWidth 390). Contrast is fine.

## Findings
- UI-1-1 | blocking | high | frontend | Primary start button is the wrong colour and size on every line drawer. Expected (all 10 desktop and 10 phone boards): start orange `#C8401C` (`--signal`, i.e. `psl-btn--start`), `flex: 2` beside a `flex: 1` Back/Cancel, 48px tall. Actual: plain `psl-btn` in action blue rgb(36,89,214), auto width (142px at 1440), right-aligned, 44px tall. At 1440 Back is 68px wide where the board has about 140px. `frontend/src/features/start-work/LineForm.tsx:181-201` (`className="psl-btn sw-primary"`), `start-work.css:27` (`.sw-primary{margin-left:auto}`). The chooser's disabled Next has the same width problem (`LineChooser.tsx:163-170`). See fidelity/SCR-04-desktop-1440/side-by-side.png.
- UI-1-2 | blocking | medium | frontend | Choice (segmented) fields don't fill the row. Expected (desktop-minutes, desktop-escalation, desktop-leadership and the phone boards): two equal options across the whole field width (`flex: 1 0 auto`). Actual: `psl-seg` hugs its content (181px of 458px at 1440, 181 of 358 at 390). `IntakeField.tsx:236`, `start-work.css:47` (`.sw-seg{align-self:flex-start}`).
- UI-1-3 | blocking | high | frontend | The chooser doesn't match SCR-04-desktop-lines or SCR-04-mobile-lines:
  - Lines are `psl-radio` rows with visible radio circles. The board has full-width bordered cards (2px border; the chosen one has an ink border) with no radio dots.
  - "Not sure which line? Describe it to Tola" is a bare underlined link. The board shows a tinted, bordered info box with the Tola avatar. The page avatar renders as a "T" letter.
  - Head: the eyebrow "START WORK · Step 1 of 2" sits above the title. The board puts "START WORK" above and "Step 1 of 2" below the title. The tool reports "START WORK" missing and "Step 1 of 2" moved. The spec text says "START WORK · Step 1 of 2"; this needs reconciling.
  - Phone board: the subline reads "Lines you can start · 6", there is no search, no subtitles and no Back. The page has all three plus the mono count.
  - `LineChooser.tsx:22-33, 114-151`.
- UI-1-4 | blocking | medium | frontend | "What happens next" is restyled. Expected (desktop, desktop-validation; CMP-23 says "a one-line what happens next"): a 13px paragraph below a hairline rule, no fill, reading "**7 stations.** Chidi drafts the invoice from the signed SOW · **a Finance Lead decides** · issue, delivery and verification are automatic." with "a Finance Lead decides" in `#9A2F10` bold, then the link "See the full invoice journey". Phone board: one line, "Next: Chidi drafts · a Finance Lead decides". Actual: a grey `--surface-subtle` box with 5 stacked lines (stations / avatar + "Chidi" / summary / "Decided by Finance Lead." / "See the full journey"). The phone shows the whole box, which pushes the form down. `LineForm.tsx:101-122`, `start-work.css:68-70`. The spec records only a different order; the fill, the stacking and the lost emphasis are not recorded.
- UI-1-5 | blocking | high | frontend | The phone footer and head don't match the phone boards.
  - Footer: every SCR-04-mobile-* board shows only the full-width primary (or disabled Next). The page stacks a full-width blue primary over a full-width Back, so the footer is 128px tall and eats the 524px sheet.
  - Head: the board drawer shows the title with "Step 2 of 2 · change line" (or "2 things to fix") and no eyebrow. The page shows the mono eyebrow, a 2-line title, and "Line chosen from the Start work menu · change line".
  - `start-work.css:25-28` (`.sw-layer--sheet .sw-primary{order:-1}`), `LineForm.tsx:150-163`.
- UI-1-6 | blocking | high | product | The phone line boards SCR-04-mobile-weekly, -minutes, -issue, -change, -incident, -escalation and -leadership draw the line as a full-screen page: "← My work" / "START" bar, large Archivo page title, cream background, form, start-orange footer. The page opens a bottom sheet over My work. Visual scores are 48–62. The spec (Layout, below 720px: `psl-sheet`) follows SCR-04-mobile and -validation, which are sheets. The boards disagree with each other and with the spec. The design engineer must pick one and record an exception for the other; the frontend then follows that choice.
- UI-1-7 | blocking | medium | frontend | The display field is unboxed. Expected (desktop-weekly "Template", desktop-leadership "Audience", phone weekly): the value sits in a 2px-bordered, 48px read-only box like an input. Actual: plain text under the label. `IntakeField.tsx:170` (`.sw-display`).
- UI-1-8 | blocking | medium | frontend | Validation state (desktop-validation, mobile-validation):
  - The eyebrow is replaced by "2 things to fix", and the subline still reads "Line chosen from the Start work menu · change line". The board keeps "START WORK" as the eyebrow and puts "2 things to fix" as the subline. The tool reports "START WORK" missing and "2 things to fix" moved.
  - Inline errors carry a warning icon; the board has plain red text.
  - "Billing contact" is a separate red-bordered field on the board; the page lists it in the callout. That part is a spec assumption and needs an exception.
  - The phone callout reads only "2 things to fix" on the board.
  - `LineForm.tsx:146-147`, `IntakeField.tsx:202`.
- UI-1-9 | blocking | medium | product | Spec-driven departures from the boards that need the design engineer's approval in `delivery/features/F-05/fidelity-exceptions.json`. Without it they fail the gate:
  - Drawer titles are the line titles where the boards show "Minutes after a meeting", "Chase an open issue", "Scope or timeline change", "Weekly client report" and "Invoice preparation" (phone). Reported as dialog/text missing.
  - The Proof field and its upload row are missing on minutes and change.
  - The week is shown as From/To native date inputs, not one "12–18 Nov 2026" field.
  - Chooser group headings ("Client delivery", etc.) are added.
  - The footer says "Back" where the boards show "Cancel" next to "change line" (weekly through leadership).
  - Billing contact appears in the summary callout.
  - The phone chooser has a search box.
  - Background-page items (the My work table, AGE column and ages, the "Unassigned 1" tab) are missing. They belong to the My work screen under the scrim, not to F-05, and need listing too or the gate can never reach 100%.
- UI-1-10 | non-blocking | low | frontend | Record pickers draw a 12px stroked chevron SVG where every board uses a small "▾" glyph. The tool counts each chosen value ("Lagoon Health · patient app ▾") as missing because of it. Prefer the bundle's own select chevron if `psl-select` has one; otherwise list the glyph in the exceptions file. `RecordPicker.tsx:150-152`.
- UI-1-11 | non-blocking | low | frontend | The top-bar main part reads "Start  work" with a doubled gap: the flex `gap` of `psl-btn` applies between the "Start " text node and `.sw-word`. SCR-01-desktop-my-work shows "Start work" with a single space. `StartWorkButton.tsx:44-47`.
- UI-1-12 | non-blocking | low | frontend | Hard-coded spacing where `--space-*` tokens exist, contrary to the spec's "tokens and existing psl-* classes only": `start-work.css:9` (`padding-right:112px`), `:10` (`height:56px`), `:13` (`padding:0 10px`), `:35` (`gap:4px`), `:42` (`gap:10px`), `:47`, `:51` (`padding:8px 0`), `:68` (`gap:6px; padding:12px 14px`).

## Verified
None (round 1).

## Fidelity results (tool scores; pass needs coverage 100 and visual >= 90)
| Board | Width | Coverage | Visual | Missing / moved / extra |
|---|---|---|---|---|
| SCR-04-desktop | 1440 | 67.5 | 83.6 | 13 / 2 / 12 |
| SCR-04-desktop-lines | 1440 | 69.2 | 80.0 | 12 / 2 / 25 |
| SCR-04-desktop-validation | 1440 | 58.5 | 81.0 | 17 / 2 / 17 |
| SCR-04-desktop-weekly | 1440 | 67.6 | 87.1 | 12 / 2 / 7 |
| SCR-04-desktop-minutes | 1440 | 55.3 | 86.7 | 17 / 1 / 7 |
| SCR-04-desktop-issue | 1440 | 60.0 | 87.2 | 14 / 1 / 9 |
| SCR-04-desktop-change | 1440 | 52.6 | 86.0 | 18 / 0 / 9 |
| SCR-04-desktop-incident | 1440 | 61.1 | 89.9 | 14 / 1 / 7 |
| SCR-04-desktop-escalation | 1440 | 65.7 | 87.7 | 12 / 2 / 6 |
| SCR-04-desktop-leadership | 1440 | 63.9 | 90.2 | 13 / 1 / 7 |
| SCR-04-mobile | 390 | 46.7 | 42.4 | 8 / 1 / 22 |
| SCR-04-mobile-lines | 390 | 71.4 | 52.3 | 4 / 1 / 33 |
| SCR-04-mobile-validation | 390 | 37.5 | 47.2 | 10 / 1 / 25 |
| SCR-04-mobile-weekly | 390 | 72.7 | 62.1 | 3 / 7 / 14 |
| SCR-04-mobile-minutes | 390 | 50.0 | 49.3 | 6 / 5 / 13 |
| SCR-04-mobile-issue | 390 | 66.7 | 48.0 | 3 / 5 / 15 |
| SCR-04-mobile-change | 390 | 41.7 | 49.7 | 7 / 4 / 15 |
| SCR-04-mobile-incident | 390 | 50.0 | 54.2 | 5 / 4 / 14 |
| SCR-04-mobile-escalation | 390 | 66.7 | 48.3 | 3 / 5 / 13 |
| SCR-04-mobile-leadership | 390 | 66.7 | 49.2 | 3 / 5 / 14 |
| SCR-01-desktop-my-work (top bar only) | 1440 | n/a | n/a | Start work split button matches |
| SCR-01-mobile-my-work (phone bar only) | 390 | n/a | n/a | "+ Start" matches |

Missing items per board, grouped:
- Background My work page: tablist, table, WORK/STATE/AGE columns, ages, "Unassigned 1". These are not F-05's (see UI-1-9).
- Picker values with "▾" (UI-1-10).
- "Anything Chidi should know (optional)": the "(optional)" is split into a separate span.
- Placeholder text.
- "START WORK" (UI-1-3, UI-1-8).
- The Tola-callout line card and "Planning and delivery handoff" (out of scope per the spec).
- Proof rows (UI-1-9).
- Board titles (UI-1-9).
- "Cancel" (UI-1-9).
- The validation alert text and billing contact (UI-1-8).
- "12–18 Nov 2026" and "17 Nov 2026" (native date inputs).
- Phone: "← My work", "×" (the page uses an SVG with aria-label Close) and "Next: Chidi drafts · a Finance Lead decides" (UI-1-4).

Full lists are in each report.json.

## Method
- Boards: design/canvas/project/SCR-04-{desktop,mobile}{,-lines,-validation,-weekly,-minutes,-issue,-change,-incident,-escalation,-leadership}.dc.html. Finance boards (accounts, bu, forecast, ledger, payroll, ppe, schedules) are out of scope.
- Page: the shared build at http://localhost:3511/my-work with cookie `psl_mock_persona=pm`, view only.
- `fidelity.mjs` can't open a drawer, so I ran the same tool code through a driver copy. It imports the tool's own dc-template, extract, compare, visual and report modules unchanged, and adds one `--actions` hook that opens the state before the page screenshot. The hook does this:
  - desktop: the chevron, the line, Next;
  - phone: "+ Start", the line, Next;
  - then it fills the values the board shows;
  - for validation: Harmattan with no milestone, then Start, giving a 2-item 422.
- The driver, the actions and the run script are in round-1/fidelity/_driver/.
- report.json and side-by-side.png for every board and width are in round-1/fidelity/<board>-<width>/.
- I compared every side-by-side by eye as well, and read computed styles of the escalation drawer at both widths.
- I started no dev server (coordinator DISK RULE) and stopped nothing.

## Notes
- The drawer title uses the bundle's `psl-drawer__title` (Archivo 800, 112% width). The boards draw it at plain Archivo bold, so the page title runs about 15% wider. This is the design-system class, so I'm not blocking on it, but the design engineer may want the boards or the bundle aligned.
- At 390 the open sheet's scrim dims the phone bar's "+ Start". That looks right.
- The long-text area is taller than the boards' 48px note field (about 76px). That is reasonable for typing.
