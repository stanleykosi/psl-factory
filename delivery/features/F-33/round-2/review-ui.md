VERDICT: CHANGES
REVIEWER: reviewer-ui
COMMIT: 9ebc7cbc98a2cedb7345180e50c1489ca0930d19
AUTHORITY: delivery UI review

## Summary
- I read the round-1 fidelity run for all 8 SCR-54 boards (coverage 100% after exceptions on every board, visual 72.9 to 87.8) side by side. I also took fresh screenshots of the head build on :4883 at 1440 and 390. They match the run, so the run still describes this head.
- Most of the gap is the shared F-17/F-22 frame and the D-113 decisions: top bar, crumbs, History, the joined station strip with status lines, the AgentCard head, Export and Withdraw held to part 2, the full amount on phone, and desktop content on phone. All of that can be waived under D-83.
- Three gaps can be fixed, so D-83 cannot be applied to those boards yet:
  - The returned quote uses the warning callout; the board draws the problem callout (UI-2-1).
  - The agent card's footer, "Started 11:20" and "Ask Chidi", is drawn outside the card (UI-2-2).
  - In the Decide panel, the note label's weight and the consequence's colour and size differ from the board (UI-2-3).
- Code checks:
  - Tokens and shared components only: no hex, rgb or inline style in the diff.
  - Every phone target the feature adds is at least 44 px. The only small one is the frame's History link (42x24), which predates this feature.
  - No horizontal scroll at 390.
  - None of the 18 exceptions covers an amount.
- The Sections.tsx figure-tag change and the two WorkItemOverview.tsx edits do not affect `/work/W-2901` or `/work/W-2411`. Both edits only apply when `line_key === 'income_schedules'`, and no other fixture has a tag on a `figures` item. Screenshots of both pages at 1440 and 390 look as before.

## Findings
1. UI-2-1 | blocking | medium | frontend | SCR-54-desktop-returned, SCR-54-mobile-returned | The returned quote "Ada Okafor returned it on 13 Nov: …" has the wrong tone.
   - Expected: both boards draw it as the problem callout: tint `#FBE3D9` (`--signal-tint`), ink `#9A2F10` (`--signal-ink`). That is `psl-callout--problem` in the shared `Callout`.
   - Actual: the page draws the amber warning callout (`--waiting-tint`/`--waiting-ink`). The cause is `bannerTone` (`frontend/src/features/workspace/Workspace.tsx:135-137`), which gives every non-issue line only `warning` or `success` (used at `Sections.tsx:453-458`).
   - This is the main message of the returned state, and the right component variant already exists. The waiver line "the quote banner is the shared warning Callout" describes the defect; it is not a frame item.
   - Fix: draw `problem` from data, never from the words. Either let `bannerTone` read the income line's status or stopped station the way F-30 does for the issue line, or use a mock-only section tone proposal listed in build.md. Then remove that sentence from both returned waivers.
2. UI-2-2 | blocking | low | frontend | SCR-54-desktop-investigating, SCR-54-mobile-investigating | The agent card's footer is not in the card.
   - Expected: both boards draw "Started 11:20" and "Ask Chidi" as the card's own footer row. This is CMP-09's `psl-agent__foot`, which the shared `AgentChecklist` already draws (`frontend/src/components/AgentChecklist.tsx:91-100`).
   - Actual: `LineAgent` (`Workspace.tsx:126-132`) puts "Started 11:20" in a loose `.ws-detail` paragraph under the card. "Ask Chidi" is the workspace link drawn under the main column (`Workspace.tsx:536`):
     - At 1440 it sits at (88,528) instead of inside the card at (1279,463).
     - At 390 it sits between the figures and the agent card, far from the card it belongs to.
   - Conflicts 15 approves the AgentCard head (no title, name and limits on their own lines), not moving its footer.
   - Fix: draw the started time and the `assistant` link in a `psl-agent__foot` row inside the card for the income line, for example through an optional foot on `AgentCard`. Keep the link's href and its 44 px phone target.
3. UI-2-3 | blocking | low | frontend | SCR-54-desktop-review | Type styling in the Decide panel differs from the board in two places:
   - **Note label.** The board draws "Note" bold and "(needed to …)" in regular weight, ink-muted. The page's whole label is bold, because `InlineDecide.tsx:26,182` passes one plain string. F-16 already draws this pattern: `Note <span className="psl-opt">(needed to return or reject)</span>` (`frontend/src/features/decide/DecidePanel.tsx:74`). The approved wording (Conflicts 7) stays.
   - **Approve consequence under the buttons.** The board draws it at 13px in `#4A5357` (`--ink-muted`). The page draws it at body size in ink `#1F2427` (shared `.ws-consequence` via `Consequence`, `InlineDecide.tsx:299,341`). The tool flags it as "text colour #4A5357 on the board, #1F2427 on the page".
   - Fix: reuse `psl-opt`, and add a token-only modifier for the trailing consequence (`--ink-muted`, nearest size token).
4. UI-2-4 | non-blocking | low | frontend | SCR-54-desktop-returned, SCR-54-mobile-returned | Some differences on the returned boards come from the shared frame. They are waivable but missing from the waivers, so the design engineer would sign without seeing them. Name each in the two returned waivers:
   - "Correct and resubmit" is green (`--verified`) where the boards draw signal orange (`#C8401C`). The cause is the F-22 rule that a primary button in the Decide panel is green (`workspace.css:35`), applied because Conflicts 12 puts the step in that panel.
   - At 1440 the stopped Review station is plain white with red words inside the joined frame strip (`work-item.css:370-377`). The board draws a dashed `--signal-ink` box with gaps between boxes.
   - At 390 the stopped segment of the mini bar is outlined (shared `MiniStationBar` `i.s`, as the design system defines it). The board draws it filled `#9A2F10`.
5. UI-2-5 | non-blocking | low | frontend | all 8 boards | The "SAMPLE DATA" exception cites the wrong authority.
   - It cites Conflicts 11, but spec item 11 covers the phone bar, the station line and the top bar, not the sample tag.
   - The tag is off in team builds by the 14 Nov decision (c), restated in D-92. Cite that instead.
   - Every other exception maps to the right D-113 item (1 to 8) or spec layout/exception item (9 to 16), and none covers an amount.
6. UI-2-6 | non-blocking | low | frontend | SCR-54-mobile-* | The four phone waivers share one closing sentence ("the full returned amount and sentences, and the desktop step labels"), but it does not fit every board:
   - mobile-investigating has no amount and no steps.
   - mobile-verified has no step labels.
   - mobile-review also claims a note label "shorter", but the phone draws no note label until the Drawer opens.
   - Make each waiver list what is actually different on that board (see Waiver judgements).
7. UI-2-7 | non-blocking | low | frontend | all phone boards (frame) | The frame's phone History link measures 42x24, under D-92c's 44 px.
   - It is the same on `/work/W-2901` and `/work/W-2411`, so it is not introduced here; it is already listed open in build.md.
   - Route it to a frame follow-up. Every control this feature adds measured at least 44x44 at 390.

## Waiver judgements (D-83, per board)
- **SCR-54-desktop-investigating (87.8): waive after UI-2-2.** The rest is frame:
  - top bar (Overview, Setup, alerts, name position), crumbs as a list, History;
  - the joined station strip with status lines and Archivo 15px names;
  - the AgentCard head without a title (Conflicts 15);
  - "2" plus a separate "CHIDI CHECKING" tag, as the spec's fixture defines it.
- **SCR-54-desktop-review (76.6): waive after UI-2-3.** The rest is frame:
  - shared facts list with bold `dt`, taller rows, station strip;
  - basis drawn whole without bold (Conflicts 7);
  - the note field 88 px high instead of 66 px (shared `TextArea`).
- **SCR-54-desktop-returned (72.9): waive only after UI-2-1, with UI-2-4 named.** The rest is the correction form opening on press in the Decide panel (Conflicts 12, D-98 (2)) and the D-RETURN note not drawn (Conflicts 6).
- **SCR-54-desktop-verified (75.9): waivable as written.**
  - Export and Withdraw are held (Conflicts 5), so the Next panel is shorter.
  - The "VERIFIED" section heading moves 39 px down because of the taller station strip.
  - No fixable gap found.
- **SCR-54-mobile-investigating (84.7): waive after UI-2-2.** The rest is:
  - the frame's phone bar and "← Queue";
  - the work item title instead of "Chidi investigating" (Conflicts 9);
  - the extra "Income detail · 38 rows" figures (Conflicts 10);
  - the AgentCard head (Conflicts 15).
- **SCR-54-mobile-review (80.5): waivable as written, once the UI-2-6 wording is corrected.** The rest is:
  - "₦12,400,000.00" in place of "₦12.4M" (Conflicts 3, correct: no rounding in the browser);
  - the extra fact rows, basis and consequence (Conflicts 10);
  - "Return with a note" (Conflicts 10);
  - the title (Conflicts 9).
- **SCR-54-mobile-returned (83.2): waive only after UI-2-1, with UI-2-4 named.** The rest is:
  - the full sentence instead of the shorter quote (Conflicts 10);
  - the consequence above the pinned button;
  - the title (Conflicts 9).
- **SCR-54-mobile-verified (85.1): waivable as written, once the UI-2-6 wording is corrected.** The rest is:
  - the title instead of "Verified" (Conflicts 9);
  - the extra "Verification scope" row and Next panel (Conflicts 10);
  - Export held (Conflicts 5).

## Verified
- None in this lens. This is the first UI review, and round 2's `## Fixes` lists no UI finding.

## Notes
- The shared `AgentCard` derives "step 4 of 4" from the steps sent (first step not done). The board says "step 3 of 4" with three steps ticked. This is covered by exception Conflicts 15; it is worth the design engineer's eye when signing.
- The figure tag uses the shared `Tag` (mono). The board draws "2 · CHIDI CHECKING" as one sans tag. The split follows the spec's fixture, so this is a matter of taste.
- I made no writes. `W-2702` was undecided (state `action_needed`, revision 1) at the end of my session, so I did not reset the mock. My screenshots are in the session scratchpad and were not copied into the feature folder, because no fidelity run was made this round (the round-1 run stands, as instructed).
