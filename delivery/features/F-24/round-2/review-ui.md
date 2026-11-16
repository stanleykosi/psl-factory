VERDICT: CHANGES
COMMIT: 0f94b4b21e40889bb0300b3cf6891bab76829677
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- Judged from the builder's round-2 fidelity run: scores.txt, report.json and side-by-side.png for all 8 boards. I did not re-run fidelity or start a server. I read the round-2 diff (10c7accc..0f94b4b2).
- Desktop is fixed. Columns are 240/1fr/260, step references are mixed case, and the amount is in sans. The 4 desktop boards are at 85 to 89.4, and what remains is justified (frame, dropped attach, shortcuts and Edit draft, held mic, grey Send). The desktop waivers can be signed.
- On phones, the phone bar now holds "← Home" with "5 earlier", or "← Assistant" with a one-line ellipsed note. The home composer is docked, and the duplicate byline is gone.
- One fixable gap is left. The phone "Open INV-0415" footer is now built, but it sits in the page flow at the end of the thread (y 971, below the 844 fold), with no footer surface or top rule. The board docks it at the bottom of the screen (y 776). Until it is docked, the mobile draft-started waiver cannot be signed.
- The shared shell.css change cannot move other pages' boards (reasoning below). The "Start this invoice" miss on desktop-thread is a tool limitation, not a page defect.

## Findings
- UI-2-1 | blocking | SCR-05-mobile-draft-started (390) | The footer action is not docked. After a start, the phone page swaps the composer for `<div class="as__open">` (ThreadPage.tsx, assistant.css last line, `.as__open { padding … }` only). That wrapper has no `position: sticky; bottom: 0`, no `surface` background and no `rule-strong` ink top border, unlike `.as__composer` at <720px. The board draws "Open INV-0415" in a white footer with a 2px ink top rule, docked at the bottom of the screen: report.json boardBox y 776, pageBox y 971. On the page it only appears after scrolling past the whole draft card. Owner frontend. | At <720px give `.as__open` the same footer treatment as `.as__composer`: `background: var(--surface); border-top: var(--rule-strong) solid var(--ink); position: sticky; bottom: 0; z-index: var(--z-bar); margin-top: auto`. Extend the e2e Open-footer check to assert its bottom is within a few px of the viewport bottom, as for the home composer.
- UI-2-2 | non-blocking | fidelity-exceptions.json | Exception file housekeeping. (a) The "← Home" link exception (Conflicts 9) is now stale, because the page draws "← Home" in the phone bar; remove it. (b) The mobile-thread visual waiver says 78.4, but scores.txt says 78.1; use the measured score. (c) The "Start this invoice" entry reads "Applies to the draft-started boards only", yet it also silently covers the desktop-thread board, where the button is present (see "Open question" below). Add a sentence to that reason naming the tool false-miss on SCR-05-desktop-thread, so the design engineer signs it knowingly. Owner frontend. | Edit the file as described.

## Verified
- UI-1-1 | verified | assistant.css:4 is now `minmax(0,240px) minmax(0,1fr) minmax(0,260px)` (and 240 at <1080). Desktop-thread report: the list and panel match the board's 240 and 260, the composer form is 880 wide at x 268 (board 883 at 268), and DRAFTED tag x 783 (board 789). The side-by-sides at 1440 line up column for column.
- UI-1-2 | verified | shell.css: the note is now `min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap`, and the back link is `white-space:nowrap; flex:none`. The 390 side-by-sides show "← Assistant  Planning packet …" and "← Assistant  Invoice · Harmat…" on one line, with no collision.
- UI-1-3 | verified | Below 720px, `.as__center` has a viewport min-height, the composer has `margin-top:auto`, and `.as__home` has flex-grow. In the SCR-05-mobile side-by-side the composer sits at the bottom with a top rule, matching the board. Visual is 89.9.
- UI-1-4 | reopen | The "Open {reference}" footer is built from `draft.started` (matched "Open INV-0415", 358×50, 100% similarity) and its exception is removed. It is not docked as the board draws it: see UI-2-1.
- UI-1-5 | verified | `.cmp-agent--inline .psl-step__ref { text-transform:none }`, with uppercase restored below 720px. Desktop side-by-sides read "SIGNED SOW v2 · stage 2", "CLIENT · Harmattan Bank", "RESPONSE v3 · COSTING v2". Phones keep capitals, as their boards draw.
- UI-1-6 | verified | ChatMessage `hideWho`: the phone working side-by-side shows the agent once, in the card head. The compact "Message Tola" composer stays a listed difference (exception "Message Tola", Conflicts 11).
- UI-1-7 | verified | "5 earlier" is a 44px button in the phone bar (`shell-phonenote--action`), drawn as the plain mono note in the board's place. Its 44px size follows D-92c.
- UI-1-8 | verified | The draft amount is `formatAmount` in the row's sans (D-93), and the phone draft title is in sans at body size. Both match the boards.
- UI-1-9 | verified | `html:has(.as) { scroll-padding-bottom: calc(var(--space-7) * 4) }` below 720px. The builder's e2e checks that the focused draft button sits above the composer.

## Open question: "Start this invoice" missing on SCR-05-desktop-thread
- Cause: the tool cannot match this button. On the board its text is entirely a data binding (`<button onClick="{{start}}">{{thread.startLabel}}</button>`, startLabel 'Start this invoice'). dc-template marks bound text as sample data, so extract.mjs turns the board element's pattern into "…" and keyOf gives `button: …`. A pattern that is only "…" has no fixed text to compare, so the board button cannot match the page's "Start this invoice". The tool then lists it as missing and the page button as extra, even though they sit in the same place (board 336,714, page 336,743). `exceptionFor` then matches the Conflicts 5 entry by name, so coverage reads 100 for the wrong reason.
- The page is correct. Not a page defect, so not a finding against F-24. Note it in the exception reason (UI-2-2c). For the factory: the tool should match an all-data board label by role, container and position, or exceptions should be scopable per board. This is a software-factory backlog item, not F-24 work.

## Shared shell.css phone-bar change: impact on other pages
- The note is right-aligned by `margin-left:auto`. The added `padding-left` is inside that auto margin, so a short note does not move. `nowrap` and ellipsis only change a note that used to wrap.
- Other pages' notes are all short single tokens: Setup "RULES" (FinanceRulesView, DeliveryRulesView), DecideView's queue position or reference (for example "INV-0412"), and OutcomeView "OUTCOME" or the result word (`resultNote` uppercases a RESULT_LABELS key). None comes near the width where truncation starts, so nothing on those boards moves.
- The back-link rule `.psl-phonebar a[aria-label^="Back to"] { white-space:nowrap; flex:none }` only stops wrapping. All existing back labels are single words ("Setup", "Clients", "Projects", "Queue", "RFP", "Work item", or BACK[layout]), so they render the same.
- `onNote` is optional, and pages that do not pass it keep the span. No re-run of other boards is needed.

## Waivers (one line per board)
- SCR-05-desktop 1440 (88.1): justified, sign. What remains is the frame (bell, Start work/name order), the dropped attach and shortcuts (Conflicts 3/4), the hero sitting lower because the shortcut row is gone, and the grey Send.
- SCR-05-desktop-working 1440 (89.4): justified, sign. Only the frame, attach, shortcuts and grey Send remain.
- SCR-05-desktop-thread 1440 (86.3): justified, sign. Edit draft, echo chips, attach and shortcuts (Conflicts 2/3/4/7), and the frame. The tool's "Start this invoice" miss is a false miss (see above).
- SCR-05-desktop-draft-started 1440 (85): justified, sign. The hidden start button and Edit draft, the short started line and the side sentence (Conflicts 5/6), "Started · INV-0415" in the list (Conflicts 15), and the dropped controls.
- SCR-05-mobile 390 (89.9): justified, sign. Shortcuts, attach, frame bell and the one-text-per-agent copy (Conflicts 4/3/11/16).
- SCR-05-mobile-working 390 (80.4): justified, sign. The title used as the task (wraps to 2 lines), the full composer instead of the compact "Message Tola" field, the desktop copy (Conflicts 8/9/11), and the frame bell.
- SCR-05-mobile-thread 390 (78.1): justified, sign. The longer desktop copy and steps, all draft rows and the extra CLIENT source from data (Conflicts 11/14), attach, and the ellipsed title note.
- SCR-05-mobile-draft-started 390 (77.3): not yet. The undocked "Open INV-0415" footer (UI-2-1) is fixable. The full thread instead of the board's collapsed card, and Chidi's callout (Conflicts 6/14), are justified listed differences.

## Notes
- The ellipsed phone note ("Invoice · Harmat…") is a fair stand-in for the board's "Harmattan Bank". A note built from `context.project` or the client would read better; product copy, not a finding.
- The phone draft card's "DRAFTED · NOT REVIEWED" wraps under the longer data title on phones. This is acceptable; it is the same rows-from-data choice (Conflicts 14).
