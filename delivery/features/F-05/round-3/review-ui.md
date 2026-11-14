VERDICT: PASS
COMMIT: 230edd60f366ea64a1a138dc66f2084bd447ebd1
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
- Round 3 changes only two things you can see. The chooser's Tola avatar is now the mascot image (UI-2-1), and on the change line the hint now sits under Proof (UI-2-3). Both are fixed at 1440 and 390.
- I re-ran the fidelity gate on the boards round 3 touched: desktop and phone lines, desktop and phone change. I also spot-checked desktop default and phone weekly. All six reach 100% coverage with the exceptions file, and my scores match the builder's to within 0.1.
- Desktop boards pass with visual scores of 92.7 to 94.6. Phone visual scores are 76.6 to 85.3, the same as round 2. The causes are the approved bottom sheet (D-02/D-16), the frame bar (D-08) and real data in place of board samples. None of them is an F-05 defect.
- Nothing overflows at 1440 or 390. The changed CSS uses existing classes, and no new hard-coded colours were added.
- There are no new findings. UI-2-2 is a non-blocking wording note for the design engineer about D-16 and stays open.

## Findings
None.

## Verified
- UI-2-1 | verified | The chooser's "Not sure which line?" box now draws the Tola mascot image (`/agents/tola.png` through next/image) at 28x28. It is round (border-radius 50%), uses `object-fit: cover` and has `alt=""`. The image loads (naturalWidth > 0) at both 1440 and 390. Evidence: Playwright probe on :3511, and round-3/fidelity-review/SCR-04-mobile-lines-390/side-by-side.png. D-14 is met.
- UI-2-3 | verified | On the change line, the help text reads in this order: "What the client asked for", then Proof, then "Emergency changes for an incident use "Emergency change" instead." This holds at 390 and at 1440, as both SCR-04-change boards draw it. The request box's `aria-describedby` still points to that hint. "change line" is now weight 400, as the boards draw it. Evidence: round-3/fidelity-review/SCR-04-mobile-change-390 and SCR-04-desktop-change-1440 side-by-sides.
- UI-2-2 | verified | Unchanged and correctly left as is. On the three boards drawn as sheets, the remaining gap is:
  - the app-frame phone bar (D-08);
  - the 8 real lines plus the Tola box, against the board's 5 or 6 sample lines (spec-required);
  - the kept help hint, optional note and Project field.

  None of these is an F-05 defect. The design engineer should still know that the D-16 wording ("bottom sheet") does not explain these three boards. This is a product note, not a blocker.

## Fidelity results (my re-run at 230edd6; pass needs coverage 100 with exceptions and visual >= 90)
| Board | Coverage (with exceptions) | Visual | Result / cause of gap |
|---|---|---|---|
| SCR-04-desktop-lines-1440 | 100 | 92.9 | PASS |
| SCR-04-desktop-change-1440 | 100 | 94.6 | PASS |
| SCR-04-desktop-1440 (spot check) | 100 | 92.7 | PASS |
| SCR-04-mobile-lines-390 | 100 | 76.6 | Frame bar (D-08); 8 real lines plus Tola box vs board sample (UI-2-2) |
| SCR-04-mobile-change-390 | 100 | 78.9 | Bottom sheet vs full page (D-02/D-16); frame bar (D-08); proof upload disabled (D-16) |
| SCR-04-mobile-weekly-390 (spot check) | 100 | 85.3 | Bottom sheet (D-02/D-16); frame bar (D-08) |

desktop-validation (88.3 in round 2, and 88.3 in the builder's round-3 run) was not touched by round 3. Its gap is still the kept help hint and optional note, which D-16 accepts.

## Method
- I ran `round-2/fidelity/_driver/fid-driver.mjs` with `act.mjs`, unchanged, against the shared build on http://localhost:3511/my-work. Settings: persona pm, `--exceptions delivery/features/F-05/fidelity-exceptions.json`, wait 800 ms.
- The build's BUILD_ID is dated 07:43, after the 230edd6 commit at 07:30.
- Outputs are in `round-3/fidelity-review/<board>-<width>/` (report.json and side-by-side.png), with `results.txt` as the summary.
- A headless Playwright probe opened the lines and change states at 1440x900 and 390x844. It checked:
  - the Tola image's size, load and style;
  - the order of the hint and Proof;
  - the hint's `aria-describedby`;
  - the "change line" weight;
  - `scrollWidth` (1440 and 390: no overflow).
- I started no dev server and stopped nothing. :3511 and :3512 were only viewed.

## Notes
- On desktop-lines, the board's own Tola image does not load in the board render (a broken-image icon on the left of the side-by-side). That is a board-asset matter, not the build. On the build, with 8 lines, the Tola box and the "You only see lines…" hint sit below the fold and the body scrolls, as noted in round 2.
- next/image serves a 32px source for the 28px avatar at 1x, with a 2x srcset entry, so it is sharp on retina screens.
