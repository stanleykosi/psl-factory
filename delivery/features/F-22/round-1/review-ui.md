VERDICT: CHANGES
COMMIT: 6d857c318ffb4d772126d9e236e9dba90f0625ba
REVIEWER: reviewer-ui
AUTHORITY: delivery UI review

## Summary
- All four SCR-25 boards reach 100% coverage after exceptions, and every visual score is at least 70 (76, 78.5, 80.5, 85.8). The amber return note, the received sentence with a green "Verified" tag, the DELIVERED tags and the "12 Nov 15:10" times all match D-97.
- The new "Next" panel on desktop reuses the red Decide head and border. The boards draw a plain panel, and the builder's own phone version is already plain. This is fixable in the feature's own CSS.
- "Edit your update" is filled green, the Decide panel's verified colour. The boards draw it blue, and the design system's colour rules say buttons are blue and green means a verified output. Also fixable in the lane.
- Because both gaps are fixable, the D-83 visual waivers are not justified yet for SCR-25-desktop-returned, SCR-25-desktop-received or SCR-25-mobile-returned. The SCR-25-mobile-received waiver is justified.
- No full fidelity re-run, as D-64 says. This review reads the builder's report.json and side-by-side.png in `round-1/fidelity/` (in the worktree). No server was started.

## Findings
- UI-1-1 | blocking | medium | frontend | SCR-25-desktop-returned, SCR-25-desktop-received | The "Next" panel is restyled. The page draws it with the Decide panel's red head fill and red border. Both boards draw a plain panel: a black-ruled box with a plain "NEXT" head and an ink rule under it. On received the red is also wrong in meaning, because nothing there needs a decision. The phone version is already plain (`.ws-decide--info` in the 390 media block, workspace.css:171-173), so the two widths disagree. Cause: Workspace.tsx always adds `psl-panel--decide` and `psl-panel__head--decide`, even when the title is "Next". | When `hasNext`, leave out the `--decide` modifiers, or add a `ws-decide--next` modifier at every width. Then draw the panel as a plain `psl-panel` with an ink border and a plain head, as the boards do. Keep "Decide" unchanged when `next` is absent, so F-17 and F-21 render as before.
- UI-1-2 | blocking | medium | frontend | SCR-25-desktop-returned, SCR-25-mobile-returned | "Edit your update" is restyled. Both boards fill it with blue `action`. The page fills it with green `verified`, because the Decide panel's rule `.ws-decide .psl-btn:not(.psl-btn--secondary):not(.psl-btn--reject) { background: var(--verified) }` (workspace.css:33-34) applies to it. Under design/system/project/README.md:20-21 (D-92b), buttons are blue `action` and green is kept for verified outputs. Editing a returned draft is not a verified output. | Scope the green fill so it does not apply inside the Next panel: use the same modifier as UI-1-1, e.g. `.ws-decide:not(.ws-decide--next) .psl-btn...`. The primary button then keeps the default `psl-btn` blue. Add a component or e2e check of the computed background, if one exists for the Decide panel.
- UI-1-3 | non-blocking | low | frontend | SCR-25-desktop-received, SCR-25-mobile-received | The side `<aside>` is still labelled "Review and decide" (Workspace.tsx:314) on a page where it only holds "Next" lines. The visible head and the landmark name disagree for screen-reader users. | When `hasNext` and no steps, label the aside after its heading, e.g. `aria-labelledby` set to the panel head.
- UI-1-4 | non-blocking | low | frontend | SCR-25-mobile-returned | The pinned phone bar draws the consequence line ("Edit your part, then Tola reassembles v2...") above the button, where the board draws only the button. This is the existing Decide bar behaviour from F-21 (consequence above the buttons) and was not added here, so it should not hold this round. | Leave as is, or list it for the design engineer as a frame difference.

## Board waivers (D-83: is the remaining gap unfixable?)
- SCR-25-desktop-returned (visual 76): not justified yet. UI-1-1 (red Next head and border) and UI-1-2 (green button) are fixable in this lane. The rest is justified: the frame's own title, tabs without counts, the subtitle, the History link and the crumb as plain text (D-81, Conflicts 7). The amber return note is the D-97 choice; the board's pink danger callout is superseded by D-97 and D-92b.
- SCR-25-desktop-received (visual 78.5): not justified yet, because of UI-1-1. The rest is justified: the sentence drawn as a ruled row with a green VERIFIED tag instead of a green box (D-97 (1)), DELIVERED tags with "12 Nov 15:10" times (D-97 (2)), the Approved row with no receipt (D-97 (3)), and the frame's own title, tabs and subtitle (D-81).
- SCR-25-mobile-returned (visual 80.5): not justified yet, because of UI-1-2. The rest is justified: the frame's title "Weekly client report · 5–11 Nov" with its subtitle, the "← Queue" back link (frame item), the "Your update" panel the board leaves out, the full return note from the single data set (Conflicts 6), and the consequence line in the pinned bar (UI-1-4, F-21 behaviour).
- SCR-25-mobile-received (visual 85.8): justified, no fixable gap. The Next panel is already plain at 390. The differences come from the frame title, back link and status label from data ("Received by client", not "DONE"), the single backend sentence with its Verified tag (Conflicts 6, D-97), and the "What happened" and "Next" panels the board leaves out.

## Verified
- None (round 1).

## Notes
- Tokens only: the new CSS in workspace.css:171-173 uses only `var(--…)` tokens and no hard-coded colours. The callout comes from the shared `Callout` (warning) and the tags from the shared `Tag`, as D-91 asks.
- Nothing overflows at 390 in the phone side-by-sides. Recipient names wrap beside their tag and time, and the rows stay aligned.
- On the desktop pages the status tag sits slightly higher than on the boards (beside the title instead of on its baseline). This is the existing frame position from F-21, not changed here.
