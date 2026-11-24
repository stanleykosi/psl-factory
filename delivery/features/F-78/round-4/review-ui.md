VERDICT: PASS
COMMIT: 86e1a6cfc20e7f6d999d4472374f7a8298fcd29a
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer

## Summary
- Round 4 changes no CSS, no layout and no markup on the F-78 screens. The F-78 commit (d9f900c2..122c9d29) touches only `milestonesModel.ts`, `useMilestones.ts` (data handling), two tests and the e2e spec. Round-3 styling and fidelity stand.
- The only CSS and TSX changes between d9f900c2 and 86e1a6cf come from the origin/main merge (alerts, decide, rfp, start-work, work-item, AppShell). Every changed selector is prefixed for those features; none touches `mscomplete*`, `ptabs*`, `psl-panel` or `psl-empty`. No fidelity re-run is needed; the round-3 scores are carried.
- UI-1-4 verified: the three cited cases (`name_in_use`, `norole`, `baseline_required`) plus the `proof_required` PDF-only case pass in `milestone-complete.test.tsx`. No radios, no file input and no "Evidence" text under a hold or with no authority.
- QA-3-2 empty state is a plain hint line, not the tab's `.psl-empty` card that its other empty lists use. Non-blocking (UI-4-1); no spec or board draws it.
- No finding blocks. Server not started and no browser run this round; PIDs none.

## Findings
- UI-4-1 | non-blocking | low | frontend | The empty "Recorded completions" list (QA-3-2) shows `<p className="ptabs__line">No completions recorded yet.</p>` (`frontend/src/features/projects/MilestonesTab.tsx:217`), a muted hint line under a bold subhead. The tab's other empty lists use the shared empty card: `TabEmpty` (`.psl-empty`, `frontend/src/features/projects/TabParts.tsx:26-32`) for "No milestones on this project yet." (`MilestonesTab.tsx:202`), "No actions…", "No documents…" and "No … on this project yet." for registers. Expected: the tab's empty-state look, or a recorded reason for the sub-list line. Actual: a different empty look on the same tab. The line uses existing tokens and the tab's own hint class, and no board or spec draws this sub-list, so it is not blocking. The text predates round 4 (F-71 code, unreachable until `isCompletions` accepted `sections: []`), so its look has not been reviewed before. Not rendered in a browser this round; judged from markup and `project-tabs.css:26,90-91`. Decide with the design engineer: keep the hint line, or switch to `TabEmpty` (one-line change).

## Verified
- UI-1-4 | verified | `cd frontend && npx vitest run tests/milestone-complete.test.tsx -t "UI-1-4"` on 86e1a6cf: 3 passed (name_in_use, norole, baseline_required: no `input[type=radio]`, no file input, no "Evidence" text). `-t "proof_required"`: 2 passed (no radios, PDF zone present when `can_attach_pdf`, no Mark complete button). Code: `MilestoneComplete.tsx:140-141` (`showProofs` needs `can_complete`; `showPdf` needs `can_attach_pdf` and (`can_complete` or `proof_required`)). Round-4 did not touch this path (`useMilestoneComplete`, `milestoneCompleteModel`); the round-2 browser check at 1440 and 390 (`inuse`, `norole`, `baseline`, `proofreq`) still stands.
- UI-2-1 | carried | verified in round 3 (heading rgb(255,255,255) on rgb(36,89,214), 6.04:1). `milestone-complete.css` and `components.css` are unchanged since d9f900c2 (not in the d9f900c2..86e1a6cf CSS diff), so the rule is unchanged.
- UI-1-5 | carried | non-blocking, unchanged (no-access card size). Not re-checked visually this round; no change in round 4.
- UI-1-6 | carried | fidelity exceptions list, unchanged.

## Notes
- Fidelity: not re-run. The round-4 change has no layout effect on SCR-19. The round-3 scores stand: desktop 1440 coverage 100% after exceptions (raw 53.6%), visual 80.9; phone 390 coverage 100% after exceptions (raw 41.7%), visual 81.9. Visual is under 90 under the signed waiver B36 (3), approved under D-207 (round-3/review-ui.md). Copies stay in round-3/fidelity/.
- The fidelity tool scores SCR-19 only. The Milestones tab's completions list (where UI-4-1 sits) is not on the SCR-19 boards and is not in the tool's score.
- Round-3 briefing said `git diff ... -- 'src/**/*.tsx'`. That pathspec matches nothing in this repo because the files live under `frontend/src`. Corrected check (`-- '*.css' '*.tsx'`) lists 32 changed source files since d9f900c2, all from the main merge or the F-78 round-4 data files, none of them a F-78 layout file.
- Live: "Mark complete" is hidden for every staff role until backend LB-2 is fixed. Recorded as an open backend item, not a frontend failure, and not a UI finding.
