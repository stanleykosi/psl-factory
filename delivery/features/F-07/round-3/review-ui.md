VERDICT: CHANGES
COMMIT: 2892f009b88a0dfb1a2ec1df5f33b966f7ba0a7c
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (round 3, design-fidelity gate)

## Summary
- UI-2-1 is fixed. On phones the Filter button now has a single 2px ring, the same weight as the search box beside it.
- My re-run of the fidelity gate matches the builder's numbers. SCR-22-desktop scores 92.1, SCR-22-mobile 91.6 and SCR-07-desktop 91.0, all at 100% coverage with exceptions. SCR-07-mobile scores 68 at 100% coverage, which D-08 accepts.
- One blocking difference: Tola's panel on the project page shows the letter "T" in a tinted circle. The board draws Tola's mascot, and D-14 (approved) says agent avatars use the mascot images everywhere, not initials.
- Nothing scrolls sideways at 390 or 1440 on the list, Closed, P-0101, empty P-0105 and no-access P-0104. Projects CSS still uses only colour tokens.

## Findings
- UI-3-1 | blocking | low | frontend | Tola's avatar on the SCR-07 project page is an initial letter, not her mascot. Expected: the Tola mascot image, as drawn on SCR-07-desktop and as D-14 requires ("Agent avatars use your mascot images everywhere, not initials"). Actual: `ProjectJourney.tsx:108` renders `<span className={avatarClass(agent) + ' projects__avatar'}>` with the letter "T" on `--mascot-tola-tint`, and there is no `<img>` on the page. F-02, F-08 and F-10 already use `frontend/public/agents/{tola,chidi,zainab}.png`, the 96px exports of `design/mascots/transparent/{pmo,finance,hr}-avatar.png` (see F-10 spec.md:43). Copy them byte-identical so the lanes merge cleanly, and keep `aria-hidden` / `alt=""` because the name "Tola" is printed beside the avatar. Evidence: `round-3/fidelity-review/SCR-07-desktop-1440/side-by-side.png`, Tola panel.

## Verified
- UI-2-1 | verified | Probed the shared build on :3711 at head at 390 wide on /projects and /projects?status=closed. `.projects__iconbtn` has computed border `0px none`, box-shadow `rgb(31,36,39) 0 0 0 2px inset`, and is 44x44. In `round-3/fidelity-review/SCR-22-mobile-390/side-by-side.png` the button frame matches the board and the search box.
- FID-3 | verified | Ran `fidelity.mjs` on the shared build :3711 with mock :3712, `--cookies psl_mock_persona=pm` rewritten to path `/` by a scratchpad Playwright shim (the tool itself was not changed), and `--exceptions delivery/features/F-07/fidelity-exceptions.json`:
  - SCR-22-desktop, `/projects?status=all` at 1440: coverage 95.7% (100% with exceptions), visual 92.1. PASS.
  - SCR-22-mobile, `/projects` at 390: coverage 88.9% (100% with exceptions), visual 91.6. PASS.
  - SCR-07-desktop, `/projects/P-0101` at 1440: coverage 95.7% (100% with exceptions), visual 91.0. PASS.
  - SCR-07-mobile, `/projects/P-0101` at 390: coverage 100%, visual 68. FAIL, but D-08 accepts it: the in-page "← Projects" link pushes the page down about 56px.
  - Reports are in `round-3/fidelity-review/<board>-<width>/`.
- Head check: the shared build serves the round-3 code. Active requests `?limit=20` with no status, and searching "lagoon" reads "1 PROJECTS".

## Notes
- Approved differences seen in the side-by-sides, and not findings:
  - Start work and its split button are missing from the bar (frame, F-05).
  - The phone back links are in-page rather than in the bar (D-08).
  - Active shows 4 rows (D-09).
  - Invoice · Milestone 2 shows WAITING with a white square, and the phone journey has no visible tags (D-10).
  - The paging footer and the "What is next" row are additions the spec requires.
- UI-2-2 (title 36px against the board's 40px) stays a frame follow-up under D-13.
- Taste: the "PM Tunde Bello · Route A…" meta line and the facts strip sit about 4px lower than on the board. The difference is too small to notice.

## Method (not part of the verdict)
- I viewed the shared servers :3711 and :3712 only. I started and stopped no server, ran no dev server or build, and used the worktree's Playwright.
- Scratch probes and screenshots are in the session scratchpad only.
