VERDICT: PASS
COMMIT: c26c9f34deee37f0078dbc4f852fec363bf35f6c
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design fidelity gate, D-41 board-is-spec, D-45 tab strip, D-48 round-4 calls)

## Summary
- I re-ran the fidelity gate on all 26 SCR-02 boards (1440 and 390) against the shared build on 4511 (mock 4512) with `fidelity-exceptions.json`. All 26 pass, with coverage 100 after exceptions and visual 90 or more. Every score matches build.md to one decimal, so the desktop scores the builder took before its last edit still hold. Evidence: `round-4/fidelity-review/<board>-<width>/{report.json,side-by-side.png}` and `scores.txt`.
- One condition applies to the run. The five PMO desktop boards (ready, processing, setup-needed, waiting, owner-needed) draw "Tunde Bello · PMO" in the top bar, so they have to be run with the `psl_mock_persona=pm` cookie. With the mock's default finance_lead persona they show "Ada Okafor · Finance Lead" and fail at 96.7–98.2 coverage. That is the test setup, not the code. With the pm cookie they score exactly as build.md reports.
- UI-3-1 is fixed. The file has 32 entries, and each one is used on at least one of the 26 boards at this head.
- UI-3-2 and UX-3-1 are fixed. "See all exceptions" is now a secondary button: inside the item's panel on desktop owner-needed, setup-needed and effect-uncertain, and below the content on the phone and under F-09's panel. I measured the phone button in the browser at 358×44px on W-1708, W-1709, W-1710 and W-1711.
- TECH-3-1 also holds visually. On W-1002 at 1440, "revision 1" sits at x 1131–1187 and the tabs at x 1199–1352. They do not overlap and the row height is unchanged.

## Findings
- UI-4-1 | non-blocking | low | frontend | On desktop owner-needed (W-1708) and setup-needed (W-1709), the new secondary "See all exceptions" button sits above the panel's primary action ("Fix it in Setup" / "Open Setup"). On setup-needed it also pushes the "This is a business decision…" small print below the primary button. The boards put the primary action first and secondary actions under it: setup-needed draws "Open Setup" and then "Tell the PMO Lead". The effect-uncertain board, which D-48 cites, has no primary action, so its placement does not carry over directly. Expected: the secondary button after the primary action, with the panel's text order as the board draws it. Actual: the button is rendered as StatePanel children ahead of the panel's own action. Fidelity still passes because the board does not draw this button. Path: frontend/src/features/work-item/WorkItemOverview.tsx:701-707.

## Verified
- UI-3-1 | verified | `fidelity-exceptions.json` has 32 entries. I matched each entry's reason against the `exception` fields across all 26 reports, and every entry is used on at least one board: #19 "Record the client's response" on 2 boards, Start work / More ways to start on 13 each, "← Queue" on 12, and so on. #21 from round 3 was kept as asked. No entry is unused.
- UI-3-2 | verified | Desktop owner-needed, setup-needed and effect-uncertain show `psl-btn psl-btn--secondary psl-btn--lg` (288×50) in the side panel at x 1046. Effect-uncertain still matches the board with no look differences. Desktop awaiting-reconciliation (W-1711) shows a full-width secondary button under the columns, below F-09's panel. On the phone, all four exception items show a full-width secondary button below the content and above the pinned action bar, not covered by it at 844px height (side-by-side SCR-02-mobile-owner-needed-390 and SCR-02-mobile-awaiting-reconciliation-390). The order inside the panel is in UI-4-1.
- UX-3-1 | verified | Measured with Playwright at 390×844, finance_lead and pm personas: W-1708 is 358×44 at y 405, W-1709 358×44 at y 562, W-1710 358×44 at y 639, and W-1711 358×44 at y 715. There is no sideways scroll (scrollWidth 390).

## Notes
- Desktop W-1711: the "See all exceptions" button runs the full content width (1264px) under both columns, so it carries more weight than the confirm panel's own action. A button the width of the right column, under F-09's panel, would sit more quietly. This is a matter of taste, not a finding.
- All 32 exceptions are still marked "builder proposal, pending design engineer". The fidelity gate counts them as approved. Sign-off on the file by the design engineer is still outstanding from earlier rounds.
- Code tidiness: `after = (` in WorkItemOverview.tsx (around line 742) is left with a stray 8-space indent after the removed `exceptionsButton` line. No visual effect.
- The new CSS uses tokens only (`var(--space-3)`) plus fixed pixel sizes that fit the crumb row (15px, -8px/-9px). No hard-coded colours.
- Carried forward from round 3 with no change in this round: the "My work" current-page marker (shell), F-09's grey disabled "Record and continue" before a choice, and the phone "WAITING" state word (exception #6, D-17, D-46).
- Method: fidelity.mjs with the worktree's Playwright against 4511/4512 at head c26c9f3, plus a Playwright measuring script, using the pm cookie for the five PMO desktop boards. I did not copy frontend/, install packages, build, or start or stop servers.
