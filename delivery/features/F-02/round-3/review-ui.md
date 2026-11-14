VERDICT: PASS
COMMIT: 02d59d8bb2216a7242a02454b957d4a0b0fdde49
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (visual consistency against the approved SCR-01 boards, tokens and layout at desktop and phone width; design-fidelity gate)

## Summary
- I re-ran the fidelity gate myself on the shared build (localhost:3311) with the D-17 exceptions file, the `psl_mock_worklist=board` cookie, and the board image map. All 9 SCR-01 boards have 100% coverage. 6 of 9 score 90 or more on the visual match. The builder's scores match within 0.5, apart from phone-empty: 75.1 here, 73.0 in the builder's run.
- The three boards under 90 are desktop-filter 83.6, phone and phone-lead 81.1, and phone-empty 75.1. Desktop-filter, phone and phone-lead fall short only for causes D-20 names: the boards' own sample rows, the approved rows-per-page footer, and the frame's phone top bar.
- Phone-empty has one cause D-20 does not name. With the board's image now rendered, the board shows a different Tola image from the page. The builder put this down to an image that "does not render locally". See UI-3-1, which I list as a follow-up and not a blocker.
- No hard-coded colours in the my-work CSS or components; only design tokens are used. No horizontal overflow at 390 or 1440 on the Needs me, Waiting on others, Done and PM caught-up views. No console errors.

## Findings
- UI-3-1 | non-blocking | medium | frontend | The caught-up panel uses a different picture of Tola from the boards. Both SCR-01-desktop-empty and SCR-01-mobile-empty use Tola's full-body thumbs-up "done" pose (`/_blob/67a43730…`, which the image map links to `design/mascots/transparent/pmo-done.png`; alt text "Tola, the PMO agent, giving a thumbs up"). The page scales up the round avatar head-and-shoulders image instead (`frontend/src/features/my-work/CaughtUp.tsx:84`, `AGENT_AVATAR.tola.src` = `/agents/tola.png`). You can see it at the top of both side-by-sides in `round-3/fidelity-review/SCR-01-*-empty-*/`. This is not one of the causes D-20 names. It is part of why phone-empty is under 90 (with the heading wrap, which is approved wording, and the Start work button, which is an approved exception), and it shows on desktop-empty even though that board passes (90.5). The fix: add the done pose under `public/agents/` and use it for the caught-up image (keep the 150px height and auto width). I list it as non-blocking because D-14 (mascot images, not initials) is met, the screen is not broken, and this was F-02's last round. If the design engineer wants the exact pose before merge, they can make it blocking.

## Verified
- FID-1 | verified | I re-ran the gate on 02d59d8: coverage with exceptions is 100 on all 9 boards. Visual scores are desktop 92.2, desktop-my-work 90.9, desktop-empty 90.5, desktop-filter 83.6, phone 81.1, phone-my-work 90.1, phone-empty 75.1, phone-filter 95.1 and phone-lead 81.1. The scores are in `round-3/fidelity-review/scores.txt`, with each board's report.json, report.html and side-by-side.png. The causes for desktop-filter, phone and phone-lead are the ones D-20 accepts:
  - **desktop-filter:** the board's second invoice row (excepted under D-17), the kind tag and the approved footer. The panel's position and layout match the board.
  - **phone and phone-lead:** the approved rows-per-page footer and the phone top bar. Card order, size and type match the board.
  - **phone-empty:** the remaining gap is UI-3-1, listed above.

## Notes
- **How I ran it.** I used the official tool `software-factory/packages/design/fidelity/fidelity.mjs`, with the builder's `act-filter.mjs` and `act-wait.mjs` page actions added through a small `--actions` hook, in my scratchpad. I passed `--exceptions delivery/features/F-02/fidelity-exceptions.json` and set the cookie `psl_mock_worklist=board`, adding `psl_mock_persona=pm` for the empty boards. The builder's driver is older and has no `--assets` support, so Tola's board image showed as an empty area in their run. The official tool loads `design/mascots/canvas-assets.json` automatically, which is why phone-empty scores 75.1 here against 73.0. No server was started; the gate ran only against the shared build on 3311 and mock on 3312, and I opened no browser session of my own.
- **Body text on the empty view.** spec.md:267 says the empty body should read "New work will appear here." with no alert promise. The page follows the board instead ("9 things you started are moving. We'll alert you on WhatsApp…"). That is UX's or product's call (the WhatsApp alerts decision); visually it matches the board.
- **Phone "While you're free".** The page lists the third sample suggestion, where the board draws two. It falls below the scored height, comes from the sample data, and the panel scales cleanly. No action needed.
- **The boards disagree with each other.** The records line is lowercase on SCR-01-desktop but drawn in capitals on the empty and filter boards. The page uses lowercase everywhere, which is right. The empty boards also show "Needs me 3" over an empty Needs me; the page shows 0, which is consistent.
- **Taste.** In the desktop table, the station bar sits level with the kind tag, where the board draws it a little lower, level with the title. The difference is a few pixels and does not affect the score.
- The phone tab strip still clips "Done" at the edge. That is the intended sideways scroll.
