VERDICT: PASS
REVIEWER: reviewer-ui
COMMIT: ee8fe64afa47a84ad9599e9f70820ec5fdacaae6
AUTHORITY: delivery UI review

## Summary
- UI-1-1, UI-1-2 and UI-1-3 are fixed. I checked the live build on :4895 (persona finance_lead) at 1440 and 390, and the builder's round-2 fidelity run. I did not re-run the tool.
- The verified boards dropped to 55.6 (desktop) and 51.9 (phone). This is mostly an offset caused by the frame, not a wrong drawing. The strip now matches the board: same cells, same order, same dark and green colours, and the caption under it. It sits lower on the page because of frame items the spec already lists:
  - Desktop: the shared StationTrack is 103px tall against the board's roughly 62px, because of the "Done" status lines (Conflicts 11).
  - Phone: the two-line item title, the status tag and the History row (Conflicts 9 and 11) put the strip about 75px lower. The board's "12 Nov" is at y168; the page's is at y243.
  - A dark block that is moved down scores worse, pixel by pixel, than the old white list did. The one-board floor exceptions describe this accurately. They are still pending the design engineer's signature, which does not block this review.
- One small part of the drop is a real difference, on the phone strip only. I raise it as non-blocking UI-2-1 below.
- Note on the worktree: while I was reviewing (04:26), the f-43 worktree had the round-1 `src` staged over HEAD. Another agent was running a revert test with vitest. I read the code with `git show HEAD:`. The running build (BUILD_ID 04:25) serves the HEAD strip. Whoever staged it should restore the worktree to HEAD before the next build.

## Findings
- UI-2-1 | non-blocking | low | frontend | **Phone strip cells use the desktop type, not the board's.**
  - Board: SCR-56-mobile-verified draws each cell with 8px padding. The label is IBM Plex Mono at 10px. The value is in the body font (IBM Plex Sans 700, 15px).
  - Page at 390: the label is 11px (`--text-label-size`) and the value is Archivo (`--font-display`) at 14px. The tool reports "font IBM Plex Sans on the board, Archivo on the page" on all six values.
  - Each cell is 58px tall on the page and about 52px on the board, so the strip is 117px against about 104px. This adds a little to the low phone score.
  - No exception lists this.
  - Expected: under 720px, set `.ws-figstrip dd` to the body font family (keep weight 700). Or list it as a `component` exception (the strip keeps one value face across widths) for the design engineer to sign.

## Verified
- **UI-1-1 (fixed).**
  - W-4004 at 1440: a six-column ink strip, 898x69 at y298. Each cell has a mono label over a bold value. VERIFIED is green, and its tone comes from the fixture's tag.
  - Under the strip, "The forecast never moves cash or authorises a payment." is a `p.ws-caption` with no panel.
  - At 390: a 3x2 grid with the same cells, and the caption under it.
  - The 10 tool-limit exceptions are removed. Raw coverage rose from 68.8 to 93.8 (desktop) and from 29.4 to 82.4 (phone).
  - The CSS rules (`workspace.css:291-305` at HEAD) are additive and line-scoped, and use tokens only.
- **UI-1-2 (fixed).**
  - W-4001 Sources: three "ACCEPTED" tags in the done tint, at both widths.
  - W-4003 Delivery: "UNKNOWN" in the uncertain tint, at both widths.
- **UI-1-3 (fixed).**
  - W-4003 at 390 runs in this order: title, status, History, mini stations, "STATION 7 OF 8 · PUBLISH", banner, Delivery, Next, the callout and its choices, then the pinned "Record and continue".
  - There is no gap, and there is exactly one `.resp-reconcile`.
  - At 1440 the panel sits at the top of the side column.
- **UI-1-4.** "Unknown" is now listed as `component` with Conflicts 1 and 14.
- **Shared `Sections.tsx` change, checked on other lines.**
  - W-3907 (F-42) and W-2706 (F-33) "NOT SET" facts now show as the stopped-tone tag, with the same words, matching the other tags on those pages. This is a consistent improvement, not a regression.
  - W-2004, the older line on the same `cash_forecast` key, is unchanged. Its figures are titled, so there is no strip, and no section turns into a caption.
  - `FiguresStrip` and the caption apply only on `cash_forecast` with untitled sections.
- **Fidelity (builder's round-2 run, production build, one run).**

| board | coverage | after exceptions | visual | waiver |
|---|---|---|---|---|
| desktop investigating 1440 | 86.1 | 100 | 84.4 | D-83 |
| desktop review 1440 | 74.6 | 100 | 75.6 | D-83 |
| desktop uncertain 1440 | 84.6 | 100 | 70.9 | D-83 |
| desktop verified 1440 | 93.8 | 100 | 55.6 | D-83 + floor exception (pending) |
| mobile investigating 390 | 77.8 | 100 | 83.1 | D-83 |
| mobile review 390 | 56 | 100 | 78.4 | D-83 |
| mobile uncertain 390 | 57.1 | 100 | 74.5 | D-83 |
| mobile verified 390 | 82.4 | 100 | 51.9 | D-83 + floor exception (pending) |

  - Every report has 0 unexcepted items.
  - Desktop verified differences:
    - The missing items are the crumbs line, SAMPLE DATA and Record actuals (C11, D-92, C5).
    - The moved items are Start work, the menu, the user name and the heading order (frame, C11).
    - The extras are the alerts bell, the crumb list, History and the station list (C11).
    - The station row has no gutters and has status lines (C11).
  - Phone verified differences:
    - "Received" becomes the full title (C9).
    - The back link (C11).
    - CALC becomes CALCULATED and 2/2 becomes 2 of 2 (C9).
    - The extras are the caption and Next (C10).
  - Each of these has an exception or waiver. The only exception is UI-2-1.
- **Overflow and contrast.**
  - `scrollWidth` equals the viewport on W-4001, W-4003 and W-4004 at 390 and at 1440.
  - The strip's white text on ink and on the verified green is readable.
  - The tags use the existing tone tokens.
- **Carried forward (impact assessment).** The round-2 diff touches only the strip, the caption, fact tags, the reconcile placement and ReconcilePanel's internal-line hint. The review and investigating boards (C1, C2, C6, C15 and so on) are unchanged from round 1, and their scores are within 1.3 points of round 1 (the uncertain phone board went up 3.2). Round 1's readings still hold for them.

## Notes
- UI-1-5 (the "Review and decide" landmark on W-4001) is still open, as the builder said. It is non-blocking.
- The phone callout still reads "Confirm what happened before anything is resent." (UX-1-2). This wording is for the design engineer.
