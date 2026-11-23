VERDICT: PASS
COMMIT: 7d7d6cc313cb158e9d765a2593d154f06e430d16
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (lighter panel, D-180)

## Summary
- Fidelity tool NOT run: it cannot open a drawer (AC17), so no board coverage or visual score exists. I compared the drawer by eye at 1440 and 390 against SCR-04-desktop/mobile-lines and -weekly instead.
- Chooser, weekly form, project picker and the empty-press errors use the existing drawer, card, field and error-summary components and tokens. No horizontal scroll at either width. Spacing and type match the neighbouring drawers.
- The unavailable row matches no board. It uses the same card border as a startable line, so it reads as a choice until you see the note (non-blocking, see Notes).
- Source picker and the upload picker are not rendered by the weekly form, so I did not review them (build.md says so). The fidelity gate is open for the design engineer: this PASS covers the drawer reading only.

## Findings
None.

## Notes
- Board differences are D-182/D-183 decisions (LC-Q3, LC-Q10, LC-Q11), not findings: no group headings, no "Next:" line, an added Reference field, no Template line. The unavailable card is new.
- Unavailable card: same soft border as a radio card, plain text, no dimming, and "Open in the full form" repeats in every card. Taste: a muted title or a different border would separate it from a choice. Phone shows the note but, as the board does, no description.
- Phone sheet head reads "Step 2 of 2 · change line" and desktop reads "Line chosen from the Start work menu · change line". The desktop wording matches SCR-04-desktop-weekly.
- Targets: every button, link and combobox in the drawer is 24px or taller at both widths, except the desktop "change line" button (67x16, a plain link inside a sentence, as the board draws it; the inline-text exemption applies, and the e2e axe check passes per build.md). The two date inputs measure 21px tall inside a 44px composite control; not an issue.
- The 24px errors-summary links render at normal size with no clipping. Each field shows its own error under the box with the warning icon. Contrast looked readable (red 3-line summary on pink, dark text on white).
- Screenshots of this look are in the reviewer scratchpad, not copied to a fidelity folder, because no tool run exists.
- I started the dev server on 4982/4983 (PID 28614, wrapper `scripts/dev.mjs`) and left it running because the UX reviewer has not written its file yet. Stop it by that PID when the UX reviewer is done.

## Verified
None (round 1).
