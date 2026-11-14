VERDICT: PASS
COMMIT: 0758d3e3f8568c084ed88b1c37a05f0641d62510
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
- This extra round (D-47) re-ran the fidelity gate on the six SCR-04 boards against the shared build on :4611. That build's BUILD_ID is from 16:47 and the 0758d3e commit is from 16:27. All six boards reach 100% coverage with the exceptions file.
- Desktop visual scores dropped from 92.7–94.6 to 85.2–87.2. Every pixel of that drop is in the My work page behind the drawer. The Start work drawer itself is pixel-identical to the round-3 (230edd6) capture. **D-49 is confirmed: the gap comes only from the background.** F-02 rebuilt My work to its own SCR-01 boards, and the SCR-04 boards still draw the old My work behind the drawer.
- Phone visual scores are the same as round 3 (lines 76.6, change 78.9, weekly 85.3). On the phone, the only pixel change in the built page is the "Updated 10:42" stamp behind the sheet, which is gone after the merge.
- The merge changed only `safePath` in start-work (logic and comment, no markup) and two `shell.css` rules (`.shell-phonenote` and `.shell-title` at 40px), both outside the drawer. No design-system or start-work CSS changed.
- All round-1 UI findings, UI-1-1 to UI-1-12, still hold as verified (see Verified). Nothing new.

## Findings
None.

## Verified
- UI-1-1 | verified | The primary button is still start orange at flex 2 beside a flex-1 Back/Cancel, about 48px tall. On the phone it is full width. See fidelity-review-extra/SCR-04-desktop-1440, -desktop-change-1440 and -mobile-weekly-390. No change in the drawer since round 2.
- UI-1-2 | verified | The segmented fields are unchanged since cc3e185 (round-2 check on desktop-minutes and mobile-leadership). The merge did not touch `IntakeField.tsx` or `start-work.css`.
- UI-1-3 | verified | The chooser still matches desktop-lines and mobile-lines: line cards, an ink border on the chosen card, the Tola mascot box, and the phone head reading "Lines you can start · 8". The drawer region is pixel-identical to round 3.
- UI-1-4 | verified | "What happens next" is one line under a hairline, with "a Finance Lead decides" in bold red and the journey link after it (desktop-1440 side-by-side).
- UI-1-5 | verified | The phone footer is the primary alone. The head reads title plus "Step 2 of 2 · change line" (mobile-change-390, mobile-weekly-390).
- UI-1-6 | verified | This was settled by D-02/D-16: a bottom sheet on every line, recorded in fidelity-exceptions.json. The phone sheets are unchanged.
- UI-1-7 | verified | Template sits in the bordered read-only box (mobile-weekly-390 side-by-side).
- UI-1-8 | verified | The validation state is unchanged since round 2. No start-work markup or CSS changed in the merge.
- UI-1-9 | verified | This is covered by the D-16 entries in fidelity-exceptions.json. Coverage with exceptions is 100 on all six boards.
- UI-1-10 | verified | The pickers still draw the "▾" glyph (desktop-1440, mobile-weekly-390).
- UI-1-11 | verified | The phone "+ Start" is drawn by the base's PhoneBar. The desktop top-bar control is unchanged since round 2.
- UI-1-12 | verified | `start-work.css` is unchanged by the merge.
- SEC-3-1 / TECH-3-1 | verified (UI lens only) | The `safePath` fix changes no visuals. "See the full invoice journey" still renders for the same-origin journey link (desktop-1440).

## Fidelity results (re-run at 0758d3e; a pass needs coverage 100 with exceptions and visual >= 90)
| Board | Coverage (with exceptions) | Visual (round 3 at 230edd6) | Cause of gap |
|---|---|---|---|
| SCR-04-desktop-1440 | 100 | 85.2 (92.7) | Background only: the new My work (F-02/SCR-01) vs the board's old My work. The drawer is pixel-identical. |
| SCR-04-desktop-lines-1440 | 100 | 85.4 (92.9) | Background only, as above. |
| SCR-04-desktop-change-1440 | 100 | 87.2 (94.6) | Background only, as above. |
| SCR-04-mobile-lines-390 | 100 | 76.6 (76.6) | Unchanged: the frame bar (D-08) and real lines vs the sample (UI-2-2). |
| SCR-04-mobile-change-390 | 100 | 78.9 (78.9) | Unchanged: the bottom sheet (D-02/D-16) and the frame bar (D-08). |
| SCR-04-mobile-weekly-390 | 100 | 85.3 (85.3) | Unchanged: the bottom sheet (D-02/D-16) and the frame bar (D-08). |

## Method
- I ran `round-2/fidelity/_driver/fid-driver.mjs` with `act.mjs`, unchanged, against http://localhost:4611/my-work. Settings: persona pm, `--exceptions delivery/features/F-05/fidelity-exceptions.json`, wait 800 ms. The outputs are in `round-3/fidelity-review-extra/<board>-<width>/` (report.json and side-by-side.png).
- Background-only check: I pixel-diffed the built-page half of each new side-by-side against the round-3 `fidelity-review/` side-by-side for the same board, with a per-pixel threshold of 60 on the RGB sum.
  - On all three desktop boards, the diff's bounding box is x 100–971 in the built half, and the drawer starts at about x 972. Nothing inside the drawer changed.
  - On the phone, the diff is 350 px at x 293–385, y 129–141: the "Updated 10:42" stamp behind the sheet.
- `git diff 230edd6 0758d3e -- frontend/src/features/start-work frontend/src/styles` shows only the `safePath` change and the two `shell.css` rules.
- I started and stopped no servers, built nothing and copied no frontend files.

## Notes
- The SCR-04 desktop boards now disagree with SCR-01 about what My work looks like. The design engineer may want to redraw the SCR-04 background, or add a background-region exception, so later reruns score the drawer alone.
- UI-2-2 (product, non-blocking) still stands as a wording note on D-16 for the three phone boards drawn as full pages.
