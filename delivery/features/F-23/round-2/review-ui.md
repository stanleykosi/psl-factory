VERDICT: CHANGES
COMMIT: 0d6dabf7e5d6f6d97e9283ca5da8e22e23016772
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- UI-1-1 to UI-1-4 are fixed. The default no longer has the tab bar. The decision ticks sit beside the words. The review has no second task card. The drafted and review panels match the boards, and IN is neutral.
- One new blocking finding comes from the UI-1-5 change. The unknown due date is now the plain string "Unknown" in a text column. The board draws it in amber, and the spec's `due {unknown: true}` contract is gone (UI-2-1). A gap remains that F-23 can fix, so D-104's condition for accepting SCR-28-desktop at 69.2 is not met yet.
- The new rule (no task card when a workspace step links the task) changes no F-17, F-21 or F-22 board page. It does remove the card from two behaviour fixtures, W-2009 (F-17) and W-2208 (F-21). Neither is a board page, and their suites pass.
- Scores: desktop 69.2, 81.3, 85.4, 78.7; phone 74.2, 82, 82.5, 78.7. Coverage after exceptions is 100 on all eight boards.

## Findings
- UI-2-1 | blocking | low | frontend | SCR-28-desktop, SCR-28-mobile (and W-2306..W-2308) | Several things went wrong in fixing UI-1-5:
  - **What changed:** the Due column changed from `date` to `text`, and A-3's due became the literal `"text": "Unknown"` (`mock/fixtures/work/W-2301.json`, and the same in W-2306..W-2308 and the sidecars).
  - **On screen:** the page now draws "Unknown" as ordinary ink text. The board draws it bold amber, as an unknown value, on desktop and phone alike ("No owner yet · due Unknown" is amber on the phone board). The design system and D-94 make an unknown amber, so the restyle shows here.
  - **Contract:** it also drops the spec's contract (spec.md, `table` "due `date`… due `{unknown: true}` reads 'Unknown'"). The unknown is now a string the frame cannot tell from a real value (INV-UNKNOWN in `Sections.tsx:5`).
  - **Fix:** restore the `date` column with `{unknown: true}` on A-3. If "13 Nov" without the year still matters, the place for it is the frame's date formatter or a backend `label`, not text cells.
  - **Simplest:** revert to round 1's date cells and keep UI-1-5 as the frame-backlog item it was (non-blocking). The round-1 Unknown pill was already amber.
  - **Re-check:** one single-board run of SCR-28-desktop afterwards is enough to confirm it stays at about 69 for D-104.
- UI-2-2 | non-blocking | low | frontend | SCR-28-desktop-drafted, -review (both widths) | The board draws the DRAFTED row tag and the drafted status tag in blue. The page draws them in neutral grey (`status.tone: neutral`, row tag neutral). Taste-level; leave as is unless the design engineer wants the board's tone.
- UI-2-3 | non-blocking | low | frontend | SCR-28-mobile | The stacked phone rows (UX-1-4) are readable and keep Edit and Remove on screen. Each cell sits on its own line about 40px apart, though, where the board's phone rows are compact ("owner · due" on one line). This is frame, covered by Conflicts 10.

## Verified
- UI-1-1 | verified | round-2 SCR-28-desktop side-by-side: no project tab bar; the subtitle sits under the h1 at y 202, as on the board; the panels start at y 340 (the agent band is the remaining offset, a frame item). W-2301/W-2306..W-2308 have no `context.project`; W-2302..W-2305 keep it.
- UI-1-2 | verified | `workspace.css` grid rule for `.ws-side .ws-row:has(> .ws-checkwrap)`: the tick is level with the words at 1440 (decisions panel) and at 390 (SCR-28-mobile side-by-side).
- UI-1-3 | verified | SCR-28-desktop-review: the Minutes panel starts at y 258, level with Decide, and the empty band is gone. SCR-28-mobile-review: no task card; the minutes panel is first. `WorkItemOverview.tsx:719-733` filters out only the tasks a step's `task_id` names.
- UI-1-4 | verified | drafted: one "MINUTES" panel whose first row is "Minutes v1 · client version · DRAFTED"; review: "MINUTES V1 · FOR LAGOON HEALTH" panel with the same first row; no extra h2 or version line; IN tags neutral.
- UI-1-5 | reopen | the year is gone, but the change made the unknown a plain string (UI-2-1).
- UI-1-6 | open | carried as before: the design engineer decides whether the third Tola sentence stays blue or becomes an amber note.

## Task-card rule and the other features' boards
- I checked every fixture for a step `task_id` that matches an item task. The rule hides the card only on W-2009 (F-17, T-2009), W-2208 (F-21, T-2208), W-2303.next, W-2304 and W-2305 (+ .approve).
- No F-17, F-21 or F-22 fidelity run scores W-2009 or W-2208. Their boards are scored on other fixtures, none of which has such a pair. So no board in those features can move.
- On W-2009 and W-2208 the decision is still reached from the step's own link, and the F-17 and F-21 tests for that link pass, as the build reports.
- The build's sentence "F-17/F-21/F-22 line boards have no such pair" is correct for board fixtures. It should add that the two behaviour fixtures lose their task card.

## Waivers (one line per board)
- SCR-28-desktop 1440 (69.2): D-104 accepts it as a one-board exception to the 70 floor, provided no fixable gap remains. UI-2-1 is still open, so the waiver stands only after that fix. Everything else is the approved frame: agent band, column swap, Decide panel plus open form, button rows, fallback status tag.
- SCR-28-desktop-suggesting 1440 (81.3): waiver OK (D-83). The rest is the frame's agent checklist and note tone.
- SCR-28-desktop-drafted 1440 (85.4): waiver OK (text carries 85.4).
- SCR-28-desktop-review 1440 (78.7): waiver OK.
- SCR-28-mobile 390 (74.2): waiver OK once UI-2-1 is fixed.
- SCR-28-mobile-suggesting 390 (82): waiver OK.
- SCR-28-mobile-drafted 390 (82.5): waiver OK.
- SCR-28-mobile-review 390 (78.7): waiver OK (text carries 78.7).

## Notes
- Code lens for round 2:
  - The CSS additions use tokens only, with no hex, rgb or hsl.
  - The `initial` prefill and `itemValues` proposal reader add no UI of their own.
  - Phone table stacking applies only to tables with step buttons.
- Carried forward without re-review: the round-1 Notes and frame-backlog items (agent checklist through `AgentChecklist`, a section note always drawn as a warning, crumb links, the side-column Edit as a button). Round 2 does not touch them.
- I started no servers this round. The evidence is the builder's round-2 side-by-sides in `round-2/fidelity/<board>-<width>/` and the code at the head.
