VERDICT: CHANGES
COMMIT: 1a7e4c9de8d61230a4b5b667982212ba18008918
REVIEWER: ui-design-reviewer
AUTHORITY: UI design review (design-fidelity gate)

## Summary
- I re-ran the fidelity tool on 11 boards against a production build of the head (FRAME_FIXTURES=1, app on 4811, mock on 4812). To tell this branch's effect apart from changes that reached main since each feature's recorded run, I also rebuilt the branch's base (68fa141) in the same worktree and ran the same boards the same way. The worktree is now back on the head; it is clean and rebuilt.
- These fixes match the boards and raise the scores: phone decision-done (UI-2-1, Paid now reads once), Tola's thumbs-up pose on My work empty (phone 75.1 to 80.0), and the primary action now comes first on owner-needed desktop (89.5 to 92.7).
- Blocking: SCR-02-desktop-setup-needed drops from 91.9 (base) to 89.8, below the 90 pass line it met before (92.8 at F-14 round 4). The new button order still leaves the "This is a business decision…" small print below "Open Setup". The board puts that line above the buttons.
- SCR-01-desktop-empty drops 0.5 (89.2 to 88.7). The new pose matches the board exactly, and the panel is now the board's 190px height. The board already fails on the base because of shell changes that came later, so I have listed this as non-blocking.
- SCR-22 phone (89.3) and SCR-15 settings phone (92.7) are the same on the base and the head. They are lower than the scores the features recorded because of later changes to the phone top bar (bell, Start), not because of this branch.

## Findings
- UI-1-1 | blocking | medium | frontend | SCR-02-desktop-setup-needed at 1440 now fails the gate. Visual is 89.8 (base 68fa141, same run setup: 91.9; F-14 round 4 recorded 92.8), and coverage after exceptions is 100. The reorder for F-14 UI-4-1 puts "Open Setup" first, which is right. But UI-4-1 also asked for "the panel's text order as the board draws it". The setup-needed board draws: body, then the small print "This is a business decision for PSL, not something the factory guesses.", then "Open Setup", then the secondary button. The page draws: body, "Open Setup", "See all exceptions", then the small print. The filled orange button is now about 40px higher than on the board, and the small print is about 90px lower. Owner-needed is right as it is, because its board draws the note after the action. So the note's position depends on the board and can't be moved for every panel. Expected: on setup-needed, the note renders before the panel links, for example through a `note_before_links` presentation flag on W-1709 or by putting the sentence in the body as small print. Keep owner-needed and effect-uncertain as they are. Path: frontend/src/features/work-item/WorkItemOverview.tsx:443-445 (links, children, note order); mock/fixtures/work/W-1709.json `presentation.panel.note`. Evidence: delivery/followups-01/fidelity/SCR-02-desktop-setup-needed-1440/side-by-side.png.
- UI-1-2 | non-blocking | low | frontend | SCR-01-desktop-empty at 1440 drops 0.5 (base 89.2, head 88.7, the same on a second run). It fails on both, and F-02 round 3 recorded 90.5. The change itself is faithful: the image is `/agents/tola-done.png` at 120x170, aligned to the bottom, with the board's alt text, and the panel is 190px tall like the board's (measured: board panel 878x190 at y 215, page 882x190 at y 224). The remaining gap is from before this branch. The tabs are 48px tall at y 152 on the page and 44px at y 149 on the board, and the header now has the bell and the Start work order from later features. Together these push the page's panel 9px lower, so a taller panel moves everything under it further from the board. Expected follow-up (not for this branch): line up the My work tab height and the top offset with SCR-01, or record the shell drift as an approved exception, so desktop-empty is back at 90 or above.
- UI-1-3 | non-blocking | low | frontend | Not caused by this branch, recorded so the gate stays honest: SCR-22-mobile at 390 scores 89.3 on both the base and the head (F-07 recorded 91.6), and SCR-15-mobile-settings scores 92.7 on both (F-12 recorded 95.8). Both drops come from the phone top bar that merged later (bell and Start button where the boards draw none). A frame-level exception or a frame fix should cover them. SCR-22's only change here, the "1 PROJECT" singular, does not show on the default list.

## Verified
- F-16 UI-2-1 | verified | On the frozen phone done page (W-1901, Approve v2, finance_lead) the next-step card ends at "…comes back." and "Paid is tracked separately by Finance…" appears once, as the line under it, which matches SCR-03-mobile-done. Score 95.1 (base 94.5, recorded 94.9), coverage 100 with exceptions, PASS.
- F-02 UI-3-1 / D-21 | verified | Both empty boards now show Tola's full-body thumbs-up pose, the same image as the boards: 170px high on desktop, 150px on phone, centred above the text on phone. Alt text "Tola, the PMO agent, giving a thumbs up". Phone-empty goes from 75.1 to 80.0. What remains is the approved heading wording, the approved Start work exception and the phone top bar (D-20). Desktop-empty: see UI-1-2.
- F-14 UI-4-1 | partly verified | Owner-needed desktop: "Fix it in Setup", then "See all exceptions", then the note, the order the board draws. 92.7 (base 89.5), PASS. Effect-uncertain desktop unchanged at 92.6 PASS. Phone owner-needed 96.0 and phone setup-needed 93.9, both the same as the base, PASS. Setup-needed desktop: reopened as UI-1-1.

## Boards checked (head 1a7e4c9 / base 68fa141 / previously recorded)
- SCR-03-mobile-done @390: cov 100 (89.5 raw), visual 95.1 / 94.5 / 94.9: PASS
- SCR-01-desktop-empty @1440: cov 100 (95.7 raw), visual 88.7 / 89.2 / 90.5: FAIL (UI-1-2, drift before this branch)
- SCR-01-mobile-empty @390: cov 100 (90.9 raw), visual 80.0 / 75.1 / 75.1: FAIL as before, improved (D-20 causes)
- SCR-02-desktop-owner-needed @1440: cov 100 (98.2 raw), visual 92.7 / 89.5 / 90.4: PASS
- SCR-02-desktop-setup-needed @1440: cov 100 (96.7 raw), visual 89.8 / 91.9 / 92.8: FAIL (UI-1-1)
- SCR-02-desktop-effect-uncertain @1440: cov 100 (98.4 raw), visual 92.6 / 92.6 / 94.0: PASS
- SCR-02-mobile-owner-needed @390: cov 100, visual 96.0 / 96.0 / 97.5: PASS
- SCR-02-mobile-setup-needed @390: cov 100, visual 93.9 / 93.9 / 95.5: PASS
- SCR-15-mobile-settings @390: cov 100 (75 raw), visual 92.7 / 92.7 / 95.8: PASS
- SCR-22-desktop @1440: cov 100, visual 92.3 / 92.3 / 92.1–93.1: PASS
- SCR-22-mobile @390: cov 100 (88.9 raw), visual 89.3 / 89.3 / 91.6: FAIL on base and head alike (UI-1-3)
- Reports and side-by-sides: /Users/Hunchoo/psl-factory/delivery/followups-01/fidelity/<board>-<width>/

## Notes
- Method: fidelity.mjs with the worktree's Playwright, `--wait-ms 500` and each source feature's fidelity-exceptions.json. Cookies: `psl_mock_worklist=board,psl_mock_persona=pm` (SCR-01 empty), `psl_mock_persona=pm` (PMO desktop SCR-02, SCR-22), `psl_mock_alerts=stale` (SCR-15). The decision-done view only exists after a decision, so I drove it with Approve v2 and saved a self-contained snapshot with stylesheets and fonts inlined, then scored it as a file:// URL. That way I needed only ports 4811 and 4812. I reset the mock before and after. For the base run, the mock process was the head's mock; the only mock differences are W-1711 response sidecars and the projects contract stripping, and none of the boards above use them.
- Code check: the changed CSS uses tokens (`--space-*`, `--mascot-tola-tint`). The new `--alerts-footer: 86px` custom property and the `.setup-sr` visually hidden class are fine. There are no new hard-coded colours. Nothing overflows sideways at 390 on My work empty: the panel is 358px wide inside a 390 viewport.
- Item 7 (F-09 "Add another file") and the wordmark below 380px were not changed. I agree that both are design-engineer calls. Not changing them is consistent with the boards.
