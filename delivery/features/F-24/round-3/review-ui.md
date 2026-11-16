VERDICT: PASS
COMMIT: 2075d4aa29aa4d09b9adc118b4955ad7e5c29af3
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- Judged from the round-3 fidelity run (SCR-05-mobile and SCR-05-mobile-draft-started rescored) and the round-3 diff (0f94b4b2..2075d4aa: assistant.css, shell.css, e2e). I did not re-run fidelity or start a server. The other six boards keep their round-2 scores and readings; nothing in this diff touches them except the underline on the phone-bar note button, which only the assistant home uses.
- UI-2-1 is fixed. On phones the "Open INV-0415" footer is now docked like the composer: sticky at the bottom, `surface` background, 2px ink top rule. The fidelity tool places it exactly on the board: boardBox and pageBox both 16,776, 358×50. Visual went from 77.3 to 82.8.
- The phone home now passes outright (coverage 100 with exceptions, visual 90.6), so its waiver is rightly removed.
- The kept "← Home" exception is accurate and acceptable. The UX-2-1 underline differs from the board, but it is a small, justified affordance; the design engineer should sign it as a listed difference.
- No blocking findings. 7 visual waivers remain, each with no fixable gap.

## Findings
- UI-3-1 | non-blocking | SCR-05-mobile (390) | UX-2-1 underline vs board. The board draws "3 earlier" as plain white mono text in the phone bar. The page now underlines it (`.shell-phonenote--action`, `text-decoration: underline; text-underline-offset: 3px`). The tool reports "underlined on the page, not on the board", and the board still passes at 90.6. The underline is the only cue that the note can be tapped, and it uses the bar's own colour, with no colour-meaning change. It is not recorded anywhere for the design engineer. | Add a line to `notes` in fidelity-exceptions.json: "'N earlier' is underlined in the phone bar so it reads as tappable (UX-2-1); the board draws plain text."
- UI-3-2 | non-blocking | fidelity-exceptions.json | Stale reason on "← Assistant". It still says '"← Home" on the phone default is a frame item and is not drawn', which is no longer true. The real cause on the thread boards is the same as for "← Home": the frame names the link "Back to Assistant", so the tool cannot match "← Assistant". | Reword the "← Assistant" reason to match the "← Home" entry ("frame vocabulary": same visible words, accessible name "Back to Assistant").

## Verified
- UI-2-1 | verified | assistant.css: below 720px `.as__open { margin-top:auto; background: var(--surface); border-top: var(--rule-strong) solid var(--ink); position: sticky; bottom:0; z-index: var(--z-bar) }`, all tokens, matching `.as__composer`. round-3 SCR-05-mobile-draft-started report: "Open INV-0415" matched at 100% similarity, pageBox 16,776 358×50, the same as boardBox. The side-by-side shows the white docked footer with the top rule at the fold, as the board draws it. The builder's e2e asserts it is within 4px of the viewport bottom.
- UI-1-4 | verified | Closed by UI-2-1: the footer is built from `draft.started` and docked.
- UI-2-2 | verified | (a) "← Home" kept with a new reason. It is accurate: the round-3 SCR-05-mobile report lists board "← Home" as missing and page "Back to Home" as extra, i.e. the frame's `aria-label` replaces the visible "← Home" as the accessible name. The visible words are the board's, and the side-by-side shows "← Home" in the bar's place, so this is a tool-vocabulary exception, not a missing element. Accepted. (b) The mobile-thread waiver now reads 78.1, matching scores.txt. (c) The "Start this invoice" reason now names the desktop-thread tool false-miss. One follow-up is UI-3-2.
- UX-2-1 | verified (UI lens) | Underline present (shell.css). Judged against the board under UI-3-1: a non-blocking listed difference. It does not affect other pages, because `shell-phonenote--action` is only rendered when a page passes `onNote` (only AssistantHome does), and plain notes ("RULES", references, "OUTCOME") stay non-underlined spans.

## Waivers (one line per board)
- SCR-05-desktop 1440 (88.1): justified, sign. Only the frame, dropped attach and shortcuts (Conflicts 3/4) and the grey Send remain.
- SCR-05-desktop-working 1440 (89.4): justified, sign. Only the frame, attach, shortcuts and the grey Send remain.
- SCR-05-desktop-thread 1440 (86.3): justified, sign. Edit draft, echo chips, attach and shortcuts (Conflicts 2/3/4/7), and the frame. The "Start this invoice" miss is a tool false-miss.
- SCR-05-desktop-draft-started 1440 (85): justified, sign. The hidden start button and Edit draft, the short started line and the side sentence (Conflicts 5/6), the list's "Started · INV-0415" (Conflicts 15), and the frame.
- SCR-05-mobile 390 (90.6): passes; no waiver needed. The underline is listed under UI-3-1.
- SCR-05-mobile-working 390 (80.4): justified, sign. The title used as the task, the full composer instead of the compact field, the desktop copy (Conflicts 8/9/11), and the frame bell.
- SCR-05-mobile-thread 390 (78.1): justified, sign. The longer copy and steps, all draft rows and the CLIENT source from data (Conflicts 11/14), attach, and the ellipsed title note.
- SCR-05-mobile-draft-started 390 (82.8): justified, sign. The footer now matches. What remains is the full thread instead of the board's collapsed card, the started line in the card below the fold, and Chidi's "will tell you" callout (Conflicts 6/14). These are product claims and data choices, not fixable gaps.

## Notes
- After a start on phones, the green started line now sits below the fold behind the docked footer, while the board shows it near the top. The docked "Open INV-0415" footer plus focus moving to the started line (with the round-2 scroll padding) carry the confirmation. If PSL wants the board's collapsed post-start view, that is a later product/design call (Conflicts 6/14), not a fix for this round.
