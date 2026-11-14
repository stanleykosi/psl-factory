VERDICT: CHANGES
COMMIT: 86aefc6d97a27dcb0f7c0801c9edce099038752d
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer, round 1 (visual review against the approved SCR-03 boards and the design system)

## Summary
- Layout, type, tokens and the phone action bar are close to the approved SCR-03 boards: no sideways scroll at 390 in any state checked, the bar sits inside the viewport with 50px targets, and all text pairs pass WCAG AA (lowest 4.76:1).
- Blocking: Approve is green (`psl-btn--confirm`) where the approved boards and the Button rules use action blue for Approve.
- Blocking: the done view has no success treatment and its "YOU APPROVED" eyebrow is in the signal (alarm) colour; the boards use a green success banner.
- Non-blocking (UI-1-3 to UI-1-5): "1 steps" copy, phone Approve height, and a fixture chain label.
- No SAMPLE DATA tag is shown on any decide view, which matches the design-owner decision of 14 Nov 2026.

## Findings
- UI-1-1 | blocking | high | frontend | Approve is filled green, not action blue. The approved boards `design/canvas/project/SCR-03-desktop.dc.html` and `SCR-03-mobile.dc.html` set "Approve v2" on `#2459D6` (action), and `design/system/project/components/Button/README.md` makes Approve a Primary (action blue) button, reserving Confirm (green) for "verified or complete". The build uses `psl-btn--confirm`, which the bundle maps to `--verified` `#22764A`. Seen on the 1440 aside and the 390 action bar. Actual: `frontend/src/features/decide/DecidePanel.tsx:121` `psl-btn psl-btn--confirm psl-btn--lg psl-btn--block`. Expected: the default `psl-btn` (action blue) with the same size and full width, matching the board. The spec names `psl-btn--confirm`, but it does not record the colour as an approved deviation from the board; if the design owner wants green, the spec must record it first.
- UI-1-2 | blocking | medium | frontend | The done view does not match the approved done boards. `SCR-03-desktop-done.dc.html` and `SCR-03-mobile-done.dc.html` show a green-tinted success banner (verified tint and border), the eyebrow "YOU APPROVED · 10:47" in verified green and the heading "Invoice v2 for Lagoon Health is approved" in verified ink. The build renders the eyebrow in `.decide-eyebrow` (`--signal-ink`, the alarm colour) on the plain steel background, with the h1 in ink and no banner. Actual: `frontend/src/features/decide/DecideStates.tsx` DoneView (lines 220-236) with `DecideHeader` and `frontend/src/features/decide/decide.css:15`. Expected: a `psl-callout--success`-style banner (`--verified-tint`, `--verified-ink`) around the done header for the approve verdict, with the eyebrow in verified ink. Re-check the return and reject done states against the design owner's intent (no board exists for them).

- UI-1-3 | non-blocking | low | frontend | The cannot-act chain reads "1 steps" (W-1203 and W-1204, desktop and phone), from `frontend/src/features/decide/DecisionContent.tsx:119` `${chain.step_count} steps`. The spec text is literal, but "1 step" reads correctly; this is copy, so route to product if the spec wording is kept.
- UI-1-4 | non-blocking | low | frontend | The phone Approve is 50px (`psl-btn--lg`, `DecidePanel.tsx`). The Button README and the phone board use `control-xl` 54px for phone footers. It meets the 44px rule, so this is a small size deviation only.
- UI-1-5 | non-blocking | low | frontend | W-1206 chain step 3 renders "CEO · Not assigned yet (you)". A step with no person and `is_you: true` reads as a contradiction. Adjust the fixture so "(you)" only follows a named person.

## Verified
- None. Round 1, so there is no previous UI review to retest.

## Notes
- Taste: on desktop the facts strip sits below the approval chain, because the spec orders the content that way. The board puts the facts strip above the decision rows. Spec-ordered, so no change needed.
- Taste: the stale comparison is two bordered cards, not the single table on `SCR-03-desktop-stale.dc.html`. The spec defines two columns, so this is recorded. The Chidi "Redrafted it" card is omitted, as the spec says.
- Taste: the cannot-act layout (W-1203) does not use the board's dark facts strip, and the own view (W-1204) uses a grey "WAITING FOR REVIEW" chip, not the finance own board's two-panel layout. Both follow the spec's read-only panel, so they are recorded.
- Taste: the not-open state (W-1001) uses the item title as the h1 and the sub-line is blank. It reads acceptably.
- Sample label: no SAMPLE DATA tag appears on any decide state, which matches the design-owner decision of 14 Nov 2026. The spec's criterion 2 text check for "SAMPLE DATA" is superseded and should not be re-added.
- Checked at 1440x900 and 390x844 (live app on the shared build, port 3401, mock 3402): default W-1201, unknown W-1202, not-yours W-1203, own W-1204, already-decided W-1205 (copy path), not-your-turn W-1206, chain W-1208, not-open W-1001, done and stale (local stubs, see below).
- Sideways scroll: `scrollWidth` equals `clientWidth` (390 and 1440) on every state measured, including done and stale.
- Phone action bar: at 390 the bar is `position: fixed` at the bottom (top 677, bottom 844), the three buttons are 50px tall, and the page reserves 220px of bottom padding so the chain is reachable.
- Contrast (WCAG ratios, token pairs): signal-ink on signal-tint 6.13; verified-ink on steel 8.24; ink-muted labels 6.87; ink-subtle hint 4.76; white on verified 5.59; unknown ink on waiting tint 7.33. All pass AA.
- Tokens: decide.css and DecidePanel use token variables and bundle classes only; no hard-coded colours in the decide feature.
- Method: the done and stale states were produced by stubbing the decide response (and the reload) in the browser with `page.route`, so no decision reached the mock and `/__mock/reset` was not called. The claim on open was the app's normal call. Screenshots were deleted after this review was written.
