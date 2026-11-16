VERDICT: PASS
COMMIT: 59799cb8aada3c594a7b223cf462bbacb72ed038
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- UI-2-1 is fixed. The Start work line cards now have one even gap: 14px seven times on desktop (65.1px cards) and 10px seven times on the phone (44px cards).
- UI-2-2 is fixed. On W-1702 at 390, the reference "PLN-0160" sits to the left of the bell and "+ Start", and nothing overlaps.
- On phones, each filter chip's remove button is now a 44px target, and neighbouring targets don't overlap. The drawn chip is 34px tall, the same as the board, and the × sits where the board draws it. On SCR-36, "HR only" is plain 13px muted text with no lock, as the board draws it. UI-2-3's note and README text are updated.
- The QA-round alert wrappers change nothing visible. The decide notice keeps its size and spacing in the page, and the alerts sheet footer links are 44px, side by side. One older layout slip in the decide warning notices is now recorded as non-blocking (UI-3-1).

## Findings
- UI-3-1 | non-blocking | low | frontend | Decide warning notices with a Try again button (`frontend/src/features/decide/DecideView.tsx` uncertain notice, `DecidePanel.tsx` "We couldn't get this decision ready"), with `.decide-retry { flex-wrap: wrap }` (`frontend/src/features/decide/decide.css:96`) | Before the integration (040b5e73), the icon, the text and the button were three flex items, and the icon sat beside the text. Since the Callout migration (601806aa, an earlier round, not this one), Callout puts the text and the button in one span. With `flex-wrap: wrap`, that span drops below the icon, so at 1440 the warning icon sits alone on its own line above the text. Every other callout has its icon beside the text. No board draws this state, so this is not a fidelity break. | Drop `flex-wrap: wrap` from `.decide-retry` (or use Callout `plain` with the icon in the row), so the icon sits beside the text as on base.

## Verified
- UI-1-1 | verified | Still holds at head. On W-1702 at 1440 and 390, READY TO CONTINUE is `psl-tag--person`, rgb(251,227,217) with rgb(154,47,16) text.
- UI-1-2 | verified | Still holds. On month-end at 1440, both WAITING ON HR tags are `psl-tag--waiting`, rgb(255,241,214).
- UI-1-3 | verified | Superseded by the lock removal. "HR only" is `<span class="monthend-restricted">`: 13px, rgb(74,83,87), nowrap, 17px tall and 45px wide, with no svg in the cell. The SCR-36-desktop board draws exactly `font-size: 13px; color: #4A5357; white-space: nowrap`.
- UI-1-4 | verified | Unchanged since round 2. The filter count is still the ink badge (the phone screenshot shows "2" in ink).
- UI-1-5 | verified | Fixed through UI-2-1 (below).
- UI-1-6 | verified | Unchanged since round 2. The one new token, `chip-height` 32px, has a usage line in tokens.json, and tokens.css is regenerated.
- UI-1-7 | verified | Unchanged since round 2.
- UI-1-8 | accepted | D-94. `/projects?status=closed` shows "—" for Sabi Market. `?status=all` still shows Unknown, which waits on the backend open/closed field (QA-4).
- UI-1-9 | accepted | No change.
- UI-2-1 | verified | My work, "More ways to start" drawer. At 1440 the cards are 65.1px with gaps of 14,14,14,14,14,14,14. At 390 the cards are 44px with gaps of 10,10,10,10,10,10,10. In the phone screenshot, the gaps after "Formal minutes" and after "Escalate" now match the others. The fix is `.sw-lines .sw-group > legend { margin: 0; }` (start-work.css:40).
- UI-2-2 | verified | On W-1702 at 390, the reference "PLN-0160" sits between "← Queue" and the bell, and it no longer prints through Start. Below 380px, `.work-barref` right = 8 + 134 + 8 = 150px, which still clears "← Queue" at 320. The board has no bell, so the reference sits a little further left than drawn. This is a design-system difference (see the table).
- UI-2-3 | verified | integration-build-note.md "Round 3 UI fixes" now lists the 10/17/33px font sizes, the pinned-bar clearances, the control and row heights, the nudges, the line heights and the widths. The README Spacing line now names the scale steps and the in-between tokens with D-92a/D-93.
- Chip remove targets (round 2 note) | verified | `/my-work` at 390, filters on. The "Remove Line filter" and "Remove State filter" buttons are 44.0 x 44.0px. They reach 5px past the 34px chip on the top, bottom and right, and a hit test 21px from the centre in each direction lands on the button. The rows are 12px apart (row-gap), so the 5px overhangs leave 2px between the targets of neighbouring rows. The State chip's target ends 5px before "Clear all". The chip draws as the board does: 34px tall (board 34px), white, ink border, × about 17px in from the right edge as on the board. At 1440 the buttons stay 28px as drawn.
- QA-round alert wrappers | verified, no visible change | I triggered the decide "couldn't confirm whether your decision was recorded" state (decide aborted, W-1201 read 503). The `role="alert"` div is exactly the Callout's box (1264x110 at 1440, 358x177 at 390). The main column's spacing is unchanged (24/12px gap rule), and the screenshots match the round 2 layout. In the workspace, `.ws-notices` is `display: contents` and the empty `.ws-live` is `display: none`, so the alert div takes the place the status div had, with the same box count. The SetRulePanel wrapper is a plain block around the warning box. The alerts sheet at 390 has a 48px footer with "See all alerts" (x16) and "Alert settings" (x290) on one row, each 44px tall, scrollWidth 390.
- How I checked | I rebuilt the head with `FRAME_FIXTURES=1` and API_ORIGIN 4945, ran the mock on 4945 (pid 14026) and `next start` on 4946 (pids 14029/14066). The next processes on port 3000 were running from the main checkout, not from the worktree. I screenshotted ready, month-end, the filter panel and sheet, the line drawer and sheet, projects all/closed/phone, decide not-yours, exceptions, alert settings, the chips, the decide uncertain state and the alerts sheet at 1440 and 390, and scrollWidth equals the viewport at 390 on every page. I did not re-run fidelity scoring, because the round only changed the measured items and the builder's re-scores are in the note (SCR-04-mobile-lines 72.3, SCR-04-desktop-lines 83.1, SCR-36-desktop 91.5, SCR-02-mobile 95.8). I stopped the servers by PID. There was no test-results folder, and the worktree is clean.

## Notes
- The filter chips on the phone wrap into two rows. The SCR-01-mobile-filter board draws one row that scrolls sideways (`overflow-x: auto`, gap 8px). The wrapping is older than this round. On the board that row sits under the open sheet. Taste for now; the design engineer can say if the scrolling row is wanted.
- `/my-work?line=invoice_preparation_and_delivery` shows the raw key in the chip, because I typed that URL by hand. The filter sheet sends a known line key, so this only shows for a hand-typed key.

## Pages that differ from their board because of the design system
| board | difference | reason |
|---|---|---|
| SCR-01-mobile, -lead, SCR-02 work item, SCR-10 | Effect uncertain tag and mini-bar segment amber (board orange) | D-92b |
| SCR-07-desktop, SCR-22 | Waiting dots on the project journey amber (board white) | D-92b |
| SCR-36-desktop | Count strip neutral boxes, colour only on the numbers (board fills DONE green, WAITING and CASH amber) | D-92b |
| SCR-35-desktop, -mobile | Set tag grey (board READY green); amounts in mono with two decimals; Unknown shown as the amber tag | D-92b; D-92 content rule (README) |
| SCR-13-desktop-rules | Set a rule panel head not solid blue (board blue head and border) | D-92b (blue is for buttons and agents) |
| SCR-02-mobile-issue | TEST TEMPLATE as the dashed amber sample label | D-92b |
| SCR-01-mobile-filter | Sheet head taller (Clear is a 44px target); "All 6 lines" and the line rows are 44px (board 36px), so the sheet grows and covers the chips row | D-92c, D-94 |
| SCR-01-mobile (filters on) | Chip remove buttons are 44px targets reaching 5px past the drawn chip; chip rows 12px apart | D-92c |
| SCR-02-mobile-* | Overview/History tabs are a 44px block beside the tag line (board has no tabs there) | D-92c (UX-01) |
| SCR-02-mobile-* | The bar has a bell before "+ Start", so the reference sits further left than drawn (board has no bell) | other: shared shell bell (F-15) |
| SCR-15-mobile-settings | Alert switch is a 44px target around the 26px drawn track | D-92c (UX-02) |
| SCR-04-mobile and its sheet states | 44px change-line and close targets in the sheet head | D-92c |
| SCR-04-mobile-lines | Line cards 44px (board 40px), so eight cards push the Tola card down (72.3) | D-92c |
| SCR-04-mobile-weekly | Week range as two DateFields with a 44px calendar button (board one text box) | D-92c / library gap |
| SCR-04-desktop, -lines | Drawer 500px (board 480px) | D-92d |
| SCR-10-desktop | "Effect uncertain" and "Stopped: invoice follow-up needed" (board SEND UNCERTAIN, FOLLOW-UP NEEDED); wider tag column | D-92 README state words (CMP-05) |
| SCR-10 (blocked rows) | Blocked exceptions read "Action needed" in orange | D-92 README state words (UX-07) |
| SCR-22-desktop | On "All I can see", the closed project's next milestone shows the amber Unknown tag (board "—"); the Closed tab shows "—" | D-94 (needs an open/closed field on E-PROJECTS rows; backend handoff, QA-4) |
| SCR-13 rule cards (phone) | Inline "Finance"/"Delivery" links keep the text's line height (not 44px) | D-95 |
| All boards | Board page-title sizes (now tokens); tags in capitals; dates as the boards write them; link disclosures; one-line breadcrumb; RECEIPT and "—" in the facts strip; SCR-01 filter panel (380px, ink count badge); ▾ select arrow; one-line note; README spacing describes the in-between tokens | D-93 (design system changed to match the boards) |
| SCR-03-desktop/mobile-not-yours, SCR-03-mobile-own | Text wraps differently (mock wording against board copy) | other: mock data, accepted |
