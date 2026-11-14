VERDICT: PASS
COMMIT: cc3e185dd1ead6fc3079f9e15ef4f969b8b97fc8
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
- I re-ran the fidelity gate myself on all 20 SCR-04 boards, against the shared build on :3511, which was built from cc3e185. My scores match the builder's to within 0.1.
- Every board reaches 100% coverage once `fidelity-exceptions.json` is counted. That file holds D-02 and the 42 D-16 entries.
- Desktop: 9 of 10 boards pass, with visual scores of 92.8 to 96.4. desktop-validation scores 88.3. The only reason is the kept help hint and optional note field, which D-16 accepts.
- Phone: visual is 75.8 to 86.4.
  - For the 7 full-page line boards, the gap comes from the bottom sheet (D-02/D-16) and the app-frame phone bar (D-08).
  - The 3 boards that are drawn as sheets (mobile, -lines, -validation) score low for other reasons, but none is an F-05 defect (see UI-2-2).
- All 12 round-1 findings are fixed. Tokens are used wherever one exists. Nothing overflows at 390, and contrast is fine.

## Findings
- UI-2-1 | non-blocking | low | frontend | The Tola avatar in the chooser's "Not sure which line?" box is still the letter "T" at 1440 and 390 (`<span class="psl-avatar psl-avatar--tola">T</span>`, `frontend/src/features/start-work/LineChooser.tsx:28`). D-14 says agent avatars use the mascot images. Those images (`frontend/public/agents/tola.png`, commit 1827260 on main) are not on this branch yet. When main is merged in, draw the mascot image.
- UI-2-2 | non-blocking | low | product | D-16 says all phone visual scores are below 90 because of the bottom sheet. That is only true for the 7 full-page line boards. SCR-04-mobile, -mobile-lines and -mobile-validation are drawn as sheets themselves, and their gap has other causes:
  - The board's phone bar shows "← My work" where the app frame shows menu, logo and "+ Start". That is a frame item (D-08/D-13), not F-05.
  - Real content differs from the board samples:
    - mobile-lines: 8 returned lines plus the Tola box, against the board's 5 lines;
    - mobile and mobile-validation: the help hint and optional note are kept, as on the desktop board.

  None of these is an F-05 defect. The design engineer should know the D-16 wording does not fit these three boards.
- UI-2-3 | non-blocking | low | frontend | On the change line, the hint "Emergency changes for an incident use "Emergency change" instead." sits under "What the client asked for", above Proof. SCR-04-mobile-change draws it below Proof as the form's last line. This is a small order difference only.

## Verified
- UI-1-1 | verified | The primary is start orange (`psl-btn--start`), flex 2:1 beside Back/Cancel, about 48px tall on every desktop board. On the phone it is alone and full width. Chooser Next matches. Side-by-sides: round-2/fidelity-review/SCR-04-desktop-1440, -minutes-1440, -weekly-1440, SCR-04-mobile-*-390.
- UI-1-2 | verified | Internal/Client and Internal Tuesday/Monthly executive fill the field width (desktop-minutes-1440, mobile-leadership-390).
- UI-1-3 | verified | The chooser matches the boards:
  - bordered line cards with an ink border on the chosen card, and no radio dots;
  - a tinted, bordered Tola box;
  - the head reads START WORK / Choose a line / Step 1 of 2;
  - on the phone the head reads "Lines you can start · 8", with titles only, no search and no Back.
  - The letter avatar is carried forward as UI-2-1.
- UI-1-4 | verified | "What happens next" is one line under a hairline, with "a Finance Lead decides" in bold red and "See the full invoice journey" after it. On the phone it reads "Next: Chidi drafts · a Finance Lead decides" (desktop-1440, mobile-390).
- UI-1-5 | verified | The phone footer is the primary alone. The phone head is the title plus "Step 2 of 2 · change line", with no eyebrow (all mobile line boards).
- UI-1-6 | verified | Resolved by the design engineer's decision D-02 (bottom sheet for every line), recorded in fidelity-exceptions.json. The sheet draws the board's content, order and styling.
- UI-1-7 | verified | Template and Audience sit in bordered read-only boxes (desktop-weekly-1440, mobile-leadership-390).
- UI-1-8 | verified | The eyebrow stays START WORK and "2 things to fix" is the subline. Inline errors have no icon. Billing contact is its own red-bordered box. The phone callout reads only "2 things to fix" (desktop-validation-1440, mobile-validation-390).
- UI-1-9 | verified | Board titles, Cancel vs Back and the one-box week field are in. Proof is drawn disabled. What remains is covered by D-16 entries in fidelity-exceptions.json.
- UI-1-10 | verified | Pickers draw the "▾" glyph.
- UI-1-11 | verified | "Start work" in the top bar has a single space (desktop side-by-sides).
- UI-1-12 | verified | `start-work.css` uses `--space-*`/`--control-*` wherever a token exists. The literals left over (14px, 10px, 6px, 2px, 70px, and the 13/14/18/22px type sizes) have no token in `frontend/src/styles/tokens.css`, which defines no type-size tokens. Each one is commented with its board source.

## Fidelity results (my re-run; pass needs coverage 100 with exceptions and visual >= 90)
| Board | 1440 coverage / visual | 390 coverage / visual | Cause of any visual gap below 90 |
|---|---|---|---|
| default | 100 / 92.8 PASS | 100 / 86.3 | Phone: frame bar (D-08); kept help hint and note. Not the sheet. |
| lines | 100 / 92.9 PASS | 100 / 76.8 | Phone: frame bar; 8 real lines plus the Tola box vs the board's 5. Not the sheet. |
| validation | 100 / 88.3 | 100 / 75.8 | Desktop: kept help hint and note (D-16). Phone: frame bar; kept help, note and project field. Not the sheet. |
| weekly | 100 / 96.2 PASS | 100 / 85.2 | Bottom sheet vs full page (D-02/D-16) and frame bar only. |
| minutes | 100 / 94.7 PASS | 100 / 77.8 | Bottom sheet (D-02/D-16) and frame bar only. |
| issue | 100 / 96.4 PASS | 100 / 86.4 | Bottom sheet (D-02/D-16) and frame bar only. |
| change | 100 / 95.0 PASS | 100 / 79.1 | Bottom sheet (D-02/D-16) and frame bar; hint order (UI-2-3). |
| incident | 100 / 95.5 PASS | 100 / 77.2 | Bottom sheet (D-02/D-16) and frame bar only. |
| escalation | 100 / 94.5 PASS | 100 / 78.5 | Bottom sheet (D-02/D-16) and frame bar only. |
| leadership | 100 / 95.1 PASS | 100 / 76.2 | Bottom sheet (D-02/D-16) and frame bar only. |

Without exceptions, coverage is 50 to 72.7%. Every missing item maps to a D-02 or D-16 entry.

## Method
- I ran `round-2/fidelity/_driver/runall.sh` unchanged, with `OUT=round-2/fidelity-review` and `PAGE=http://localhost:3511/my-work`. Settings: persona pm, `--exceptions delivery/features/F-05/fidelity-exceptions.json`.
- Outputs are `round-2/fidelity-review/<board>-<width>/report.json` and `side-by-side.png`, with `results.txt` as the summary.
- The :3511 server runs from the f-05 worktree. Its BUILD_ID is dated 06:58, after the cc3e185 commit at 06:35.
- I compared the side-by-sides by eye for default, lines, validation, weekly and minutes at 1440, and for default, lines, validation, weekly, change and leadership at 390.
- A Playwright check in the scratchpad confirmed:
  - scrollWidth is 1440 and 390, so nothing overflows;
  - the Proof box is rgb(74,83,87) on rgb(238,240,237), about 7:1;
  - the Tola avatar is the letter "T".
- I started no dev server, used no named browser session beyond headless Playwright, and stopped nothing (shared :3511/:3512 only viewed).

## Notes
- The native date inputs show the browser's locale format: 11/12/2026 in headless en-US, where the boards show "12–18 Nov 2026". This is covered by D-16. On en-GB browsers it reads day first.
- The drawer title still uses the bundle's wider `psl-drawer__title` against the boards' plain Archivo bold (round-1 note). It is a design-system choice.
- On desktop-lines the Tola box and the "You only see lines…" hint fall below the fold with 8 lines. The body scrolls, which is fine.
