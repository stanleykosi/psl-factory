VERDICT: CHANGES
COMMIT: 28c13dbcca5af9b6db6f276e2878c43a487a8958
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
- UI-1-1 to UI-1-6 are fixed. UI-1-1 holds on both `next dev` and the production build: the team form and the outcome form have no border and no padding at 1440 and at 390.
- My re-run on a production build matches the builder's scores to within 0.1 on all 18 boards. Only 4 boards pass: desktop team-input 93.4, rfp-outcome 90.3, -lost 94.7 and -pending 92.9.
- For each board under 90 I tested the cause directly. I put back the omitted or forced items on a frozen copy of the page and re-scored it (method under Fidelity). On 12 of the 14 boards the whole gap is forced. Restoring the forced items lifts desktop pending 74.6 -> 89.6, desktop lost 88.2 -> 90.3, desktop unknown 86.7 -> 94.3, phone pending 87.3 -> 94.0 and phone unknown 86.1 -> 96.3. Desktop won's gap is the D-60 planning-packet card.
- One blocking fix remains. On the phone, the lost page's spacing and panel heading are off the board, and that alone takes phone rfp-lost from 77.7 down to 70.2. A CSS-only fix takes it to 83.1 (UI-2-1). The phone unknown follow-up heading also has a small restyle, which is part of the same finding.
- UI-1-7 (product) stays open: 14 boards cannot reach 90 without the design engineer's decision.

## Findings
- UI-2-1 | blocking | medium | frontend | Phone recorded states: spacing and heading restyle on top of the forced gap (SCR-16-mobile-rfp-lost 70.2, -unknown 86.1). I compared board and page geometry at 390 (`W-2106`, `W-2108`).
  - **(a) Lessons panel head.** The board has "Lessons" at 14px/700, 14px under the panel top, with the first row 38px under the panel top. The page uses 15px/600 with `padding: 12px 14px 0` and body padding 14px, so the first row sits 47px under the panel top and the rows are inset to x=32, where the board has x=30.
  - **(b) Archive line.** The board leaves 12px between the panel and "Archived as ARC-0117". The page leaves 27px, because the new `psl-hint` keeps its default margin. The round-1 callout had `margin: 0` from `.rfp-recorded .psl-callout`.
  - **(c) Gap before the Next lines.** The phone `.resp-board` gap of 22px plus the main column's 14px leaves 35px before "No engagement is created…" on lost and 34px before "As soon as you hear anything…" on unknown. The board's rhythm is 12px everywhere (`.rfp-recorded { gap: 12px }`).
  - **(d) Follow-up heading.** The unknown board's "Follow-up drafted by Tola" is 15px/**700** with no top padding (19px tall). The page uses 15px/600 with 12px top padding (31px tall). My round-1 note said 600; the board says 700.
  - **Fix.** In `frontend/src/features/rfp/rfp.css`, inside `@media (max-width: 719.98px)`:
    - `.rfp-recorded .rfp-panel:not(.rfp-panel--rows) > .psl-panel__head { padding: 12px 12px 0; font-size: 14px; font-weight: 700; }`
    - `.rfp-recorded .rfp-panel:not(.rfp-panel--rows) > .psl-panel__body { padding: 6px 12px 14px; gap: 8px; }`
    - `.rfp-recorded__main > .psl-hint { margin: 0; }`
    - `.rfp-recorded .resp-board, .rfp-recorded__main { gap: 12px; }`
    - `.rfp-recorded .rfp-followup > .psl-panel__head { padding-top: 0; font-weight: 700; }`
  - **Measured on frozen copies with these rules injected:** phone rfp-lost 70.2 -> **83.1**, phone rfp-unknown 86.1 -> 86.9. The rows panels are left alone: a 12px body padding there scored 85.7 -> 85.6 on won and 87.3 -> 87.0 on pending, so it is not worth changing.
  - **After the fix, phone lost is still under 90 for forced reasons.** The 26px title takes it to 84.5. The spec-required debrief proof link, `next[]` line and "Back to projects" (Contract 5, AC14) take it to 89.5. The rest is the "Lost · archived" / "Lessons" wording exceptions, the lesson tag tones (UI-1-8) and the shell's bell and Start.
- UI-1-7 | blocking | medium | product | Carried forward with this round's evidence. The 14 boards under 90 cannot pass on frontend work alone; per-board split below. The design engineer must rule on:
  - whether these boards pass at their measured scores, or the boards or the contract change;
  - the 23 exceptions still marked "coordinator, provisional (D-60)" or "builder proposal, pending design engineer". The recorded intros are among them, and they are the largest lever: restoring the pending intro alone takes desktop rfp-pending from 74.6 to 89.6.
- UI-1-8 | non-blocking | low | backend | Carried forward: tag tones for "NOTHING YET" and the lesson categories need a contract field. These tones alone hold desktop rfp-lost and rfp-unknown under 90: desktop lost passes at 90.3 once the tones and the archive sentence are restored, and desktop unknown passes at 94.3 once the "NOTHING YET" tone is restored and the "To" line is removed.
- UI-1-9 | non-blocking | low | backend | Carried forward unchanged (engagement date and planning-packet row on won).

## Verified
- UI-1-1 | verified | Production `next start` and `next dev` on 4651 (mock 4652, FRAME_FIXTURES=1), `/work/W-2101/respond?task=T-2101`: `.resp-form.resp-form--team` computes border 0 and padding 0 on both at 1440 and 390, and `.resp-aside--team` keeps its 2px ink frame and 14px padding. `/work/W-2103/outcome`: `.resp-form.rfp-form` is border 0 and padding 0 on both servers, at both widths. The selectors are now (0,2,0) against `response.css`'s (0,1,0), so load order no longer matters. The re-frozen pages from head are DOM-identical to the builder's; team-input 1440 scores 93.4.
- UI-1-2 | verified | Desktop won has no NEXT panel: the `next[]` sentence, then "Open engagement EN-0042" as `psl-btn--secondary` (white, ink outline), in the right column at the board's x and width. The tool no longer reports the background or outline difference.
- UI-1-3 | verified | At 390, won and pending pin a single 50px button in a white bar with a 2px ink top rule, and the page has 110px bottom padding. Unknown shows "Record the outcome" in the flow as `psl-btn--secondary`, below the draft and above the pinned Send/Edit (screenshot at scroll end). Lost shows a quiet "Back to projects" link. No phone state draws a Next panel. Nothing scrolls sideways on W-2105, W-2106, W-2107, W-2108, W-2111 or W-2114 (scrollWidth 390).
- UI-1-4 | verified | Phone lost shows a muted `psl-hint` "Archived as ARC-0117.", not a callout. Its spacing is UI-2-1(b).
- UI-1-5 | verified | The phone follow-up heading is IBM Plex Sans, sentence case, with no rule, and the tool no longer reports the font, case or bar. The remaining weight and padding difference is UI-2-1(d).
- UI-1-6 | verified | "LOST · 04 DEC" is neutral grey and "OUTCOME UNKNOWN" is amber (`labels.ts` `statusTone`); the tool reports no tag colour difference on either board. The builder records that this departs from the spec's colour table; the coordinator should update spec Contract 1 to match the boards.

## Fidelity (reviewer re-run at head)
**Setup.**
- Production build at head, built with `API_ORIGIN=http://127.0.0.1:4652`, served by `next start` on 4651, with the mock on 4652 (FRAME_FIXTURES=1).
- Run options: cookie `psl_mock_persona=pm`, `--exceptions`, `--wait-ms 500`.
- Form boards: I re-ran `drive-states.mjs` (ports changed in a scratch copy) and served the result on 4653. The `<main>` DOM of all 10 frozen pages is identical to the builder's.
- Recorded boards: scored live on `/work/W-2105..W-2108/outcome`.
- My `report.json` and `side-by-side.png` replace the builder's in `round-2/fidelity/<board>-<width>/`. Scores are identical to the builder's except outcome-lost 1440 (94.7 vs 94.6) and rfp-unknown 390 (86.2 vs 86.1).

**What-if method.** I froze the live page, injected the change, and scored the frozen copy against the same board with the same exceptions. These copies are evidence only; no product code changed.
- Restore an omitted item: insert the board's intro or archive sentence, or give the tags their board tone.
- Remove a forced item: hide the "To" line, the agent card, the note, the Next lines, or set the title to the board's size.
- Apply a proposed fix: inject the CSS rules from UI-2-1.

The baseline frozen copies reproduce the live scores exactly (lost 390: 70.2; pending 1440: 74.6).

| Board | Width | Coverage / after exc. | Visual | Forced gap (cause, measured) | Fixable gap |
|---|---|---|---|---|---|
| team-input | 1440 | 76.9 / 100 | 93.4 | pass | none |
| rfp-outcome | 1440 | 72.5 / 100 | 90.3 | pass | none |
| rfp-outcome-lost | 1440 | 75 / 100 | 94.7 | pass | none |
| rfp-outcome-pending | 1440 | 73.8 / 100 | 92.9 | pass | none |
| rfp-outcome-unknown | 1440 | 71.1 / 100 | 88.6 | R (note), C (proof card kept, D-60 b; "What happens next" omitted, D-60 c) | none (DOM unchanged since round 1) |
| rfp-won | 1440 | 56.7 / 100 | 76.6 | C: intro, third row "Tola building…", 354px planning-packet card (D-60 c). With the intro, the row and an empty 354px card box added: 83.0. The rest is the card's content and T. Every element the page does draw sits within 2px of the board | none |
| rfp-lost | 1440 | 74.1 / 100 | 88.2 | C (archive sentence, D-60 c), UI-1-8 lesson tones; with both: 90.3 | none |
| rfp-pending | 1440 | 76.9 / 100 | 74.6 | C: intro callout (Conflicts 12, provisional) moves the rows panel up 53px; with the intro: 89.6. The rest is T and the shell bar | none (rows 40 vs 41px, Next line 21 vs 18px: under 1 point) |
| rfp-unknown | 1440 | 82.4 / 100 | 86.7 | R ("To … · draft v1", +28px), UI-1-8 NOTHING YET; with both resolved: 94.3 | none (draft tint: see Notes) |
| team-input | 390 | 73.7 / 100 | 85.1 | T, R (44px segments, note, attestation), D | none (DOM identical) |
| rfp-outcome | 390 | 60 / 100 | 88.5 | T, R (select, note, "Amount not known", 44px segments), D | none |
| rfp-outcome-lost | 390 | 66.7 / 100 | 82.4 | T (+6px), R (+4px per segment row, record_as select and note +138px), C ("What happens next"); every field label sits where the board has it after these shifts | none |
| rfp-outcome-pending | 390 | 64.7 / 100 | 87.1 | T, R, D | none |
| rfp-outcome-unknown | 390 | 53.8 / 100 | 89.0 | T, R (proof card, select, note), C | none |
| rfp-won | 390 | 37.5 / 100 | 85.7 | T, C (intro, packet card), R (`next[]` line, Contract 5) | none (panel padding test: 85.6) |
| rfp-pending | 390 | 60 / 100 | 87.3 | T alone 88.3; with T, C (intro) and R (`next[]` line) resolved: 94.0 | none |
| rfp-lost | 390 | 60 / 100 | 70.2 | After the fix: T 84.5; R (debrief link, `next[]`, Back to projects) 89.5; the rest is the heading wording exceptions, UI-1-8 and the shell | **UI-2-1: 70.2 -> 83.1** |
| rfp-unknown | 390 | 85.7 / 100 | 86.2 | T, R (agent card, checks, note, "To", `next[]` and Record): 96.3 with these removed | UI-2-1(d): 86.1 -> 86.9 |

Causes: T = approved 40px/26px titles (Conflicts 2); R = contract- or spec-required fields; D = native date text; C = D-60 / Conflicts 12-13 omitted copy; UI-1-8 = tones with no field.

**Answer to the coordinator's question.**
- Desktop rfp-won, rfp-pending, rfp-lost, rfp-unknown and rfp-outcome-unknown, and phone team-input, the four phone outcome forms, rfp-won and rfp-pending are forced-only. They can go to the design engineer as they are.
- Phone rfp-lost and phone rfp-unknown need UI-2-1 first. Even after it they stay under 90 (about 83 and 87) for forced reasons.

Frame items as in round 1 (Conflicts 19), on every board: the shell's bell, "Tunde Bello · PM" and the order of Start work, "Projects" not marked current on a work route, and the nav "RFP" reported as extra.

## Notes
- The draft body uses `--action-tint` (#E9EEFB), where the boards draw #F3F6FD. That colour is not a token, so using the token is right. If the design engineer wants the lighter tint, it should be added to the design system, not hard-coded.
- I rebuilt `frontend/.next` in the worktree with `API_ORIGIN=http://127.0.0.1:4652` to serve the production build against my mock. The next `checks.sh` run rebuilds it, but anyone using `next start` from this worktree before then should rebuild first. The worktree's git status is clean.
- I stopped my servers on 4651, 4652 and 4653 by PID or port; none are left listening.
