VERDICT: PASS
COMMIT: ab5a4f0f8046ab431cd183345b6e98f8012369ca
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- Phone SCR-13-mobile-delegation @390 passes the tool: 100% coverage after exceptions, visual 98.6. In the side-by-side, the cards, tags, the "← Setup" bar and the 50px "Add delegation" footer (12/16/18 padding, 2px ink rule) all match the board.
- Desktop SCR-13-desktop-delegation @1440: 100% coverage after exceptions, visual 84.0, so it fails the 90 gate. The table, columns, tags, title and the panel's field order match the board. I found no gap the feature's own code can close within the spec. The remaining difference comes from four things: the shared frame (Start work, persona text, the tab badges that shift every tab by 52px), the ink panel head (D-92b), the two Dates fields (Conflicts 5, about 80px), and the shared 44px field height (the board draws 48px; 4 fields × 4px = 16px). I recommend a one-board visual waiver at 84.0. D-83's floor covers line screens only, so this needs an explicit signature, as D-104 was for F-23.
- Panel head: I recommend keeping ink (details under Q2). D-93 kept D-92's colour-meaning call above the boards. The Set a rule and Templates upload panels in Setup are already ink.
- Phone add form: I recommend keeping the full-height `Drawer` (details under Q3). It is the design system's form container and is a sheet below 720px. `BottomSheet` is specified for filters, short choices and confirmations.
- This PASS is conditional on sign-off. The 10 exceptions are still "builder proposal, pending design engineer" and the desktop waiver is unsigned. Merge waits for the design engineer to sign both. Fidelity was not re-run (D-64). I read the builder's report.json and side-by-side.png in `round-1/fidelity/`, and started no server.

## Findings
- UI-1-1 | non-blocking | low | builder | SCR-13-desktop-delegation | The restyled panel head is not listed in `fidelity-exceptions.json`. The tool reports it as a style difference on the matched "ADD A DELEGATION" text: the board has a #2459D6 background, white text and a blue 2px border; the page has no fill, ink text and an ink border. build.md mentions it only inside the waiver text. A restyled board element needs an exception for the design engineer to sign. | Add an entry: role text, name "Add a delegation", category "colour meaning", reason "D-92b/D-93: blue is for buttons and agent work; Setup form panels use the standard ink panel, as F-11 Set a rule and F-20 upload (design-system-conformance/review-ui.md)". Can ride with the sign-off; no code change.
- UI-1-2 | non-blocking | low | builder | SCR-13-mobile-delegation (sheet, not drawn) | In the phone `Drawer`, "Add delegation" and "Cancel" sit at the end of the scrolling body (`DelegationView.tsx:275-279`, `DelegationForm.tsx:204-215`). The Drawer spec puts the main action in a footer that stays put ("the body scrolls and the footer stays"; README Layout: "the main action goes full width in a footer"). At 390 the five fields push the button below the fold. | Optional. Pass the submit/cancel buttons through `Drawer footer` on phones, or accept it as is (the sheet is on no board). Not a gate item.
- UI-1-3 | non-blocking | low | builder | SCR-13-mobile-delegation | `setup.css:108` hard-codes `padding-bottom: 82px` (the comment shows it is 12 + 50 + 18 + 2). `.setup-deleg__bar` (`setup.css:106`) repeats the bundle's `.psl-actionbar` padding, ground and rule. No colour literal, so spec item 20 holds, but D-92a says every size comes from a token. | `calc(var(--space-3) + var(--control-lg) + var(--space-18px) + var(--rule-strong))`, and build the bar on `psl-actionbar` with a fixed-position modifier. Fix if a round 2 happens for another reason.

## Answers for the coordinator / design engineer

### Q1. Fixable desktop gaps in code?
None that reaches 90 within the spec and the design system. What I checked:
- **Two Dates fields (about 80px).** Side by side, each DateField would be about 136px wide in the 288px panel body. That leaves about 80px for "18 Nov 2026" next to the 44px calendar button, so the text clips (builder measured 84.8). Making the aside wider breaks the board's 320px. Hiding the visible "Starts"/"Ends" labels would save about 40px but leaves two date boxes without visible labels (WCAG 3.3.2). That is not acceptable. The real fix is a range picker in the library, a design-system item, not F-27.
- **Field height.** The board draws 44px content plus a 2px border (48px). The shared `psl-input` is 44px in total. This is library-wide (the SCR-13 Rules board draws the same 48px boxes and F-11 was accepted at 44), so it is not a per-feature fix.
- **Frame.** Start work/More ways to start, "Admin · sample" against "Ada Okafor · Admin", the bell, and the tab badges "Roles 2"/"Rules 8" (no read carries them, G-SCR13A-6). These are shell and contract items, the same as F-20 (D-71).
- **Panel head.** Ink by D-92b (Q2). The builder measured blue at 86.3, still under 90.
- **Order notes from the tool** ("misplaced" side panel/main) come from the extra Dates label and the Delegations region wrapper. They are not visible differences.
Everything else in the side-by-side matches: table frame and widths, column heads, row text, "18–25 Nov 2026" date format, square neutral UPCOMING/ENDED tags, the hint under To, the 50px blue Add button and the 12px note. **Recommendation: sign a one-board visual waiver at 84.0 for SCR-13-desktop-delegation, citing the frame, D-92b and Conflicts 5. Add the range picker to the design-system backlog.**

### Q2. Panel head: ink or the board's blue?
**Recommend ink (keep as built).**
- D-93 says boards win on look, but it names D-92's colour-meaning call as still standing. The README gives `action` blue one job: buttons, links and everything agents do. Agent panels are drawn with an `action` border.
- A solid blue panel with a blue border would read as agent work on a screen where nothing is agent work. That matters here because the screen must not suggest anything happens automatically (spec AC 16).
- Setup is already consistent: the conformance work turned the Set a rule panel (SCR-13-desktop-rules) and the Templates upload panel ink. That difference is listed in `delivery/design-system-conformance/review-ui.md` with D-92b as its reason. A blue Delegation panel next to an ink Rules panel would make the two Setup tabs disagree.
- If the design engineer prefers the boards' blue, decide it Setup-wide (Rules, Templates upload, Delegation) and change the README's colour rule, not this feature. Either way, record it as UI-1-1's exception.

### Q3. Phone add form: Drawer or BottomSheet?
**Recommend the Drawer (as built).**
- The board draws no sheet, so the board decides nothing here. The design system does. The `Drawer` spec is the form container: ValidationSummary for "needs fixing", busy submit, close and toast on done, and "below 720px it is a full-height sheet". `BottomSheet` is specified for "filters, short choices and confirmations" with a grab handle and swipe-down dismiss.
- This form has From, To, two DateFields with pop-up calendars, Reason, field messages, the hint and the note. As a bottom sheet it would grow to almost full height anyway, and a stray swipe could close it and lose the entries.
- Precedent: the phone Start work form (SCR-04-mobile) is the Drawer sheet. D-104's bottom sheet for F-26 is a short read-only drill-down, which is what BottomSheet is for.
- The spec's Conflicts 1, which D-103 answered, named this Drawer, "a full-height sheet below 720px". D-103's "shared bottom sheet" reads as plain wording for that.
- Ask the design engineer to confirm this reading in one line at sign-off. If they meant `BottomSheet`, it is a small swap in `DelegationView.tsx:275`.

## Waivers and exceptions, per board
- SCR-13-desktop-delegation @1440 | coverage 83.3 raw, 100 with exceptions (8 entries pending) | visual 84.0 | waiver recommended at 84.0 (no fixable gap; frame + D-92b + Conflicts 5), pending design engineer signature; add UI-1-1's head entry.
- SCR-13-mobile-delegation @390 | coverage 80 raw, 100 with exceptions (2 frame entries pending) | visual 98.6 | passes; no waiver needed, the frame exceptions ("← Setup", "Start") to sign as F-20/D-71.

## Verified
- Round 1: no earlier UI findings.
