STATUS: READY
COMMIT: cc3e185dd1ead6fc3079f9e15ef4f969b8b97fc8
BUILDER: builder
LANE: full

## Summary
- The Start work drawer now follows the SCR-04 boards (the boards are the spec). Changes:
  - the start-orange primary button, about twice as wide as Back/Cancel and 48px tall;
  - bordered line cards and a tinted "Describe it to Tola" box;
  - "What happens next" on one line, with the deciding role in bold red and the "See the full invoice journey" link;
  - bordered read-only value boxes and full-width two-option choices;
  - "▾" pickers;
  - the validation subline and the billing-contact box;
  - the phone sheet's own head and footer.
- Board titles, Cancel vs Back, the week field and the billing contact follow the boards, as the coordinator directed (UI-1-9). The Proof field is drawn as on the minutes and change boards, but it is disabled and reads "Proof upload comes next".
- On phones every form stays a bottom sheet (the design engineer's answer on UI-1-6). The sheet's top sits 70px below the phone bar, as SCR-04-mobile draws it, and long forms scroll inside it.
- Fidelity at 1440:
  - 9 of the 10 desktop boards pass, with 100% coverage once the approved exception and my requests below are counted. Visual scores are 91.4 to 96.4.
  - desktop-validation scores 100% coverage but 88.3 visual.
- Fidelity at 390: all 10 phone boards reach 100% coverage with the exceptions counted, but visual is 75.8 to 86.4. Most of that gap is the bottom-sheet decision and board-only differences, so a visual-bar exception is requested below.
- Merged origin/dlv-00-delivery-setup (760ba3c, no conflicts). `delivery/checks.sh` exits 0, and the full browser suite passes 93/93.

## Changes
All in commit cc3e185, on top of merge 760ba3c.

`frontend/src/features/start-work/`:
- `LineForm.tsx`:
  - From 720px the head is the "START WORK" eyebrow, the board title, and "Line chosen from the Start work menu · change line" (always). On the phone it is the title and "Step 2 of 2 · change line".
  - After a 422, the subline becomes "<n> thing(s) to fix" and the eyebrow stays.
  - The footer is Back (invoice, which goes to the chooser) or Cancel (every other line, which closes) at flex 1, beside a `psl-btn--start` primary at flex 2. On the phone the primary is alone.
  - The 422 callout has no list. A problem for a field the drawer doesn't render is drawn as its own box: a label from the key, "—" in a red-bordered box, and the message in red.
  - "What happens next" is one line under a hairline: "**7 stations.** Chidi drafts … · <red>a Finance Lead decides</red> · issue, …", then `journeyLabel`. On the phone it reads "**Next:** Chidi drafts · a Finance Lead decides".
  - `journey_url` is linked only when it is a same-origin path (security note).
  - After a 422 the start button stays greyed until something is changed, as on the validation boards (UX-1-3).
- `LineChooser.tsx`:
  - Each line is a bordered card. The radio is the card's whole surface, and the chosen card gets an ink border. Groups are kept as named `role=group` with no visible headings, since the board has none.
  - The head is "START WORK" / "Choose a line" / "Step 1 of 2".
  - The Tola link is a tinted `psl-callout--info` box.
  - On the phone the subline is "Lines you can start · N" and also names the radiogroup. The phone shows titles only, with no search, no hint and no Back; the footer is Next alone.
  - Next is start orange.
- `IntakeField.tsx`:
  - "(optional)" is part of the label text.
  - `date_range` is one bordered field holding two date inputs, labelled From and To.
  - `display` is a `psl-input` read-only box.
  - An optional `evidence` field is a dashed, disabled box reading "Proof upload comes next". It has no control and is never sent.
  - Inline errors have no icon.
- `DrawerFrame.tsx`:
  - The eyebrow shows only from 720px.
  - Close is a "×" glyph, still a button named Close.
  - It exports `useWide`.
  - A `narrow` option makes the drawer 480px for the chooser and invoice (SCR-04-desktop/-lines); the other line boards use the bundle's 500px.
- `labels.ts`: presentational maps keyed by line, following the boards:
  - the drawer titles: Weekly client report, Minutes after a meeting, Chase an open issue, Scope or timeline change;
  - the phone invoice title, "Invoice preparation";
  - Back vs Cancel;
  - the 480px drawer;
  - the journey noun.
- `intake.ts`: `shownFields` keeps an optional evidence field. `buildIntake` still drops it.
- `useStartWork.ts`:
  - the 422 notice now carries `unmatched: FieldProblem[]` and `general?`;
  - a new `awaitingChange` flag.
- `RecordPicker.tsx`: the chevron is a "▾" glyph (UI-1-10).
- `StartWorkButton.tsx`: the label is one inline span, so "Start work" has a single space (UI-1-11).
- `start-work.css`:
  - the button sizes and flex for UI-1-1;
  - cards, the Tola box, the full-width `.sw-seg`, `.sw-proof`, the one-line `.sw-next` and `.sw-decides`;
  - the sheet height `calc(100% - var(--sw-sheet-top))`;
  - the 44px phone "change line" kept on an 18px line with negative block margins;
  - `--space-*`/`--control-*` tokens wherever a token exists (UI-1-12). Board-only values (14px, 10px, 70px) remain literal and commented.

`frontend/mock/fixtures/start-work/lines.{pm,ceo,finance_lead}.json`:
- The invoice `next.summary` parts are joined by " · ".
- minutes and change_request each gain an optional `proof` field (type `evidence`) in the board's position.

Tests:
- `tests/start-work.test.tsx`:
  - updated for board titles, Back vs Cancel, "change line" always shown, "1 thing to fix", the billing-contact box, the disabled Proof and the "▾" pickers;
  - new tests for the one-line "What happens next", non-same-origin `journey_url` (3 cases), the phone chooser sheet and the phone invoice sheet (matchMedia stubbed).
- `tests/start-work-intake.test.ts`: `shownFields` keeps the optional evidence field.
- `tests/start-work-mock.test.ts`: the only evidence fields are the two optional Proof fields.
- `e2e/start-work.spec.ts`:
  - the board drawer titles;
  - Proof drawn but disabled on minutes and change;
  - Cancel only on non-invoice lines at 1440;
  - seg width equals field width;
  - the start button is rgb(200,64,28), at least 48px tall and more than 1.7× Back's width;
  - the phone chooser count is in the head, with no search;
  - "1 thing to fix".

## Fixes
- UI-1-1 | cc3e185 | The primary is `psl-btn psl-btn--start` with flex 2 : 1 beside Back/Cancel and a 48px minimum height (50px on the phone, as those boards draw it). Next in the chooser does the same.
- UX-1-1 | cc3e185 | The enabled start button is start orange at 1440 and 390 (e2e checks rgb(200, 64, 28)).
- UI-1-2 | cc3e185 | `.sw-seg` is `display:flex; width:100%`, so the two options fill the field (e2e checks seg width = field width on all 8 lines at both widths).
- UI-1-3 | cc3e185 | Line cards and the Tola callout box are in. The head is "START WORK" / title / "Step 1 of 2". On the phone: "Lines you can start · N", titles only, no search, no Back.
- UI-1-4 | cc3e185 | "What happens next" is one line under a hairline, with the red bold decision and "See the full invoice journey". On the phone it is "Next: Chidi drafts · a Finance Lead decides".
- UI-1-5 | cc3e185 | The phone footer is the primary alone. The phone head is the title plus "Step 2 of 2 · change line" (or "<n> things to fix"), with no eyebrow.
- UI-1-6 | cc3e185 | Kept the bottom sheet, per the design engineer (14 Nov). Board content, order and styling are drawn inside it. The sheet's top is 70px below the bar, and forms scroll inside the sheet.
- UI-1-7 | cc3e185 | Display values sit in a bordered 44px read-only box.
- UI-1-8 | cc3e185 | The eyebrow stays "START WORK" and "<n> things to fix" is the subline. Inline errors have no icon. Billing contact is its own red box. The phone callout reads only the count.
- UI-1-9 | cc3e185 | Board titles, Back/Cancel per board, the week as one field, the billing contact as drawn, and Proof drawn but disabled. What is left is listed for exceptions below.
- UI-1-10 | cc3e185 | The "▾" glyph replaces the SVG chevron.
- UI-1-11 | cc3e185 | Single space in "Start work".
- UI-1-12 | cc3e185 | Spacing uses `--space-*`/`--control-*` tokens where one exists.
- UX-1-2 | cc3e185 | "1 thing to fix" (singular).
- UX-1-3 | cc3e185 | The start button stays greyed after a 422 until a value changes, as the validation boards draw it.
- UX-1-5 | cc3e185 | Same fix as UI-1-5.

## Exception requests (for the design engineer)
Already approved and written to `delivery/features/F-05/fidelity-exceptions.json`:
- `link "← My work"`: "phone form is a bottom sheet for every line (design engineer, 14 Nov 2026)", covering the page chrome of the 7 full-screen phone line boards.

Requested but not approved: 42 entries in `round-2/fidelity/exception-requests.json`. The reports were scored with `_with-requests.json`, which combines the approved entry with these requests.
1. The My work page under the scrim, which is not F-05's (coordinator: ignore): the tablist "My work", the unnamed table, WORK/STATE/AGE, "2h", "40m", "1d", "3d", "Unassigned 1", and the phone cards "Lagoon Health · Milestone 2 invoice" and "Harmattan Bank · go-live report".
2. Text inside form controls. The tool names a control by its label, so it cannot match the value the control shows:
   - every picker value with "▾" (Lagoon Health · patient app, Milestone 3…, Harmattan…, INC-0031…, ISS-0233…, ISS-0241…, Weekly sync · 17 Nov, and the phone's shortened "Lagoon Health" and "Milestone 3 · UAT signed");
   - typed text ("Add WhatsApp reminders as well as SMS", "Disable the new card router…");
   - the placeholders "e.g. client wants the PO number on it" and "Find a line…";
   - the dates "12–18 Nov 2026" and "17 Nov 2026" (native date inputs show the browser's own format).
3. Labels of native inputs. `<label for>` is skipped by the tool: "Anything Chidi should know (optional)", "What the client asked for", "Plan", "Period".
4. Proof file rows (FE-M2A-PROOF): "weekly-sync-notes-17nov.docx", "client-request-17nov.pdf", "Uploaded · 38 KB", "Uploaded · 20 KB". The Proof field is drawn disabled with "Proof upload comes next".
5. Validation-board sample text:
   - "Milestone 4 · hypercare ▾", "Milestone 4 ▾", "Milestone 4 isn't marked complete yet…" and "Not marked complete yet.": Milestone 4 is unselectable per the spec's `disabled_reason`, so "Completed milestone is required." shows instead.
   - "No billing contact for this client.": the mock's Harmattan billing-contact message shows instead.
6. The "Planning and delivery handoff" card, which is out of scope (FE-M4) and not returned by E-LINES.
7. The phone "×" drawn as plain text. The build draws it inside the Close button.

Visual bar (the tool cannot record exceptions for it):
- desktop-validation, 88.3: the board leaves out the help hint and the optional note field. The build keeps them.
- the three phone sheet boards (mobile 86.2, lines 76.8, validation 75.8): the build shows 8 lines plus the Tola box, which the board doesn't draw, along with the note field and help on the invoice and the real My work page behind the sheet.
- the seven phone line boards (76.2 to 86.4): they are full-screen pages, and the build draws the same content in the bottom sheet, which starts about 126px lower (the design engineer's decision).

Spec departures the boards drove (coordinator: follow the boards):
- Drawer titles.
- "change line" is always shown, so it is also on pm's direct invoice drawer (the board is the main button's target).
- Back (invoice) vs Cancel (other lines).
- The one-box week field.
- Billing contact as its own box.
- The optional Proof field drawn but disabled (the spec said no Proof field).
- No visible group headings: groups stay named for assistive technology.
- No search on the phone chooser.

## Acceptance criteria
1. [x] The contract is v6: unchanged since round 1. `tests/api-schema-drift.test.ts` and `tests/mock-contract.test.ts` pass in the gate.
2. [x] The button shows only when `startable_lines` is not empty: `tests/shell.test.tsx` passes.
3. [x] pm's main button opens the invoice drawer directly: "pm: the main button opens the invoice drawer directly…" passes. It now also expects "change line" and Back, which goes to the chooser.
4. [x] The CEO's main button opens the chooser. Component test and e2e "ceo at /my-work…" pass.
5. [x] The chooser groups (named `role=group`), searches, and offers only returned lines: the "chooser groups lines…" and finance_lead tests pass.
6. [x] Chooser states: "chooser states" passes.
7. [x] Fields render by kind, in order: "renders each kind…" passes. The display field is now the `psl-input sw-display` box.
8. [x] Record options are narrowed by parent: the milestone test passes.
9. [x] Search and paging: the ceo paging test passes.
10. [x] The case comes from the chosen project or the fixed line: unchanged; the tests pass.
11. [x] A valid start goes to the work item: e2e "pm starts an invoice on Lagoon and lands on W-1401…" passes.
12. [x] A missing field shows the 422 inline: component tests and e2e pass at both widths ("1 thing to fix…" desktop, "1 thing to fix" phone). Billing contact is its own box.
13. [x] A double press or an uncertain result never starts twice: tests unchanged and passing.
14. [x] A 409 keeps what was typed and reloads the revision: passes.
15. [x] Wrong user, record or permission: the mock tests pass.
16. [x] Out-of-scope kinds:
    - an optional money field is not rendered;
    - an optional evidence field is drawn disabled, as the board shows it;
    - neither is sent (test asserts `intake` is `{note: 'hi'}`);
    - a required evidence field, `finance_import` or no `case_scope` still shows "can't start here".
17. [x] All 8 drawers against their boards: e2e "each of the 8 drawers shows its board title, fields and start label; Proof is drawn but disabled" passes at 1440 and 390. The fidelity results are below.
18. [x] Accessibility:
    - `e2e/start-work.spec.ts` passes 10/10, with axe at 0 violations on the chooser, invoice, validation and ceo chooser at both widths;
    - Esc closes and focus returns to the opener;
    - Tab stays inside the dialog;
    - the jsdom axe tests pass;
    - phone targets are still at least 44px, "change line" included.
19. [x] Mock fixtures match v6: `tests/start-work-mock.test.ts` validates every E-LINES and options page, including the new Proof fields.
20. [x] Nothing protected changes. `git diff --name-only 9ee65d4 cc3e185` lists only `frontend/src/features/start-work/*`, the 3 line fixtures, and 4 start-work test files.

## Validation
- `df -h /System/Volumes/Data` showed 12 GB free before the builds.
- `cd /Users/Hunchoo/psl-factory-worktrees/f-05 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh`: exit 0. That covers the django check, npm ci, lint with 0 warnings, typecheck, vitest (16 files, 425 tests) and next build.
- `cd frontend && E2E_PORT=3501 MOCK_PORT=3502 npm run test:e2e`: 93 passed, exit 0.
- Fidelity: the round-1 driver, reused in `round-2/fidelity/_driver/`. The only change is in `act.mjs`: it waits for the first radio instead of "LINES YOU CAN START", picks the line with `.check()`, and waits for `role=alert` after a 422. It ran against `next start` on 3501 with the mock on 3502, persona pm, for all 20 boards. The reports and side-by-side images are in `round-2/fidelity/<board>-<width>/`, with `results.txt` as the summary:

  | Board | 1440 coverage* / visual | 390 coverage* / visual |
  |---|---|---|
  | default | 100 / 92.7 PASS | 100 / 86.2 |
  | lines | 100 / 92.9 PASS | 100 / 76.8 |
  | validation | 100 / 88.3 | 100 / 75.8 |
  | weekly | 100 / 96.2 PASS | 100 / 85.2 |
  | minutes | 100 / 94.7 PASS | 100 / 77.8 |
  | issue | 100 / 96.4 PASS | 100 / 86.4 |
  | change | 100 / 95.0 PASS | 100 / 79.1 |
  | incident | 100 / 95.5 PASS | 100 / 77.2 |
  | escalation | 100 / 94.5 PASS | 100 / 78.5 |
  | leadership | 100 / 95.1 PASS | 100 / 76.2 |

  \*Coverage counts the approved exception and the requests. Without any exceptions it is 63 to 72%.
  The round-1 visual scores were 80.0 to 90.2 at 1440 and 42.4 to 62.1 at 390.
- Everything ran on the contract mock: mock results only.
- I deleted `frontend/test-results` and stopped my own servers on 3501 and 3502. `git status --porcelain` is empty.

## Blocked
None.
