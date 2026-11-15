VERDICT: PASS
COMMIT: 4e8a8c7d75957adbc9de381887453e0e5e11ecf4
REVIEWER: reviewer-ui
AUTHORITY: UI reviewer (round 3 extra round D-47, design-fidelity gate)

## Summary
- UI-3-1 is fixed. Tola's panel on the project page now shows her mascot image, as the board draws it, in place of the letter "T".
- FID-1 is fixed. On phones the "← Projects" back link sits in the top bar, where the board puts it, and the page titles no longer sit a few pixels low.
- My re-run of the fidelity gate gives the same numbers as the builder: SCR-22-desktop 93.1, SCR-22-mobile 91.6 and SCR-07-desktop 91.1, all at 100% coverage with exceptions. SCR-07-mobile is at 100% coverage and 78.8 visual. The design engineer's waiver (D-50) accepts that score.
- Nothing scrolls sideways at 390 or 1440 on the list, Closed, P-0101, empty P-0105 or no-access P-0104. The CSS this feature changes has no hard-coded colours.

## Findings
- UI-3-1 | blocking | low | frontend | Fixed at 4e8a8c7, see Verified. Was: Tola's avatar on SCR-07 was the initial "T", not the mascot that D-14 requires.

## Verified
- UI-3-1 | verified | `ProjectJourney.tsx:109` renders `/agents/tola.png` with `alt=""` and `aria-hidden="true"`, 36px, on the `psl-avatar--tola` circle. On the shared build :4711 at 1440, P-0101 and P-0105 each have that one image, which loads (naturalWidth 192). `frontend/public/agents/tola.png` is byte-identical to `origin/dlv-00-delivery-setup`, so the lanes merge cleanly. In `round-3/fidelity-review-extra/SCR-07-desktop-1440/side-by-side.png` the Tola panel matches the board. No-access P-0104 has no agent image, which is correct.
- FID-1 | verified | At 390 the project pages have no in-page back link. The frame bar link "Back to Projects" sits at y=6, the same place as the board's "← Projects". Its accessible name differs from the board's only because the frame draws the arrow as an icon. The new entry in `fidelity-exceptions.json` covers it under D-33, the rule for phone back links that come from the frame. The title, eyebrow and meta line now line up with the board on SCR-07-desktop and SCR-22.
- FID gate | verified | Ran `fidelity.mjs` against the shared build :4711 (mock :4712) with `--cookies psl_mock_persona=pm` and `--exceptions delivery/features/F-07/fidelity-exceptions.json`. The tool now sets the cookie site-wide, so no shim was needed.
  - SCR-22-desktop, `/projects?status=all` at 1440: coverage 95.7% (100% with exceptions), visual 93.1. PASS.
  - SCR-22-mobile, `/projects` at 390: coverage 88.9% (100% with exceptions), visual 91.6. PASS.
  - SCR-07-desktop, `/projects/P-0101` at 1440: coverage 95.7% (100% with exceptions), visual 91.1. PASS.
  - SCR-07-mobile, `/projects/P-0101` at 390: coverage 88.9% (100% with exceptions), visual 78.8. The tool fails it on the visual score. The board carries the D-50 visual waiver, which the design engineer approved: the board's wider Archivo title wraps onto two lines, and the spec keeps the "What is next" row. I read the side-by-side and found no other difference.
  - `report.json` and `side-by-side.png` for each board are in `round-3/fidelity-review-extra/<board>-<width>/`.

## Notes
- The remaining tool differences are all approved:
  - Start work and More ways to start are missing (frame, F-05, D-08).
  - "← Home" is missing on the SCR-22 phone board (frame phone bar, D-08).
  - "Back to Projects" is the frame's back link (D-33).
  - Invoice · Milestone 2 shows WAITING (D-10).
  - "What is next" and the paging footer are additions the spec requires.
- The tool marks the breadcrumb and the "Plan a project" row on SCR-07-desktop as moved. The cause is the downward shift of about 3-6px that comes from the line-height. It is not part of the pass rule, and nobody would see it.
- The image is lazy-loaded, so at 390 it has not loaded yet (naturalWidth 0) because the Tola panel is below the visible area. The phone board does not draw the panel near the top, so this is expected.

## Method (not part of the verdict)
- I used the shared servers :4711 and :4712 only. I started and stopped no server, and I ran no copy, `npm ci` or build. I used the worktree's Playwright.
- Probes and full tool output stayed in the session scratchpad. Only report.json and side-by-side.png were copied into the feature folder.
