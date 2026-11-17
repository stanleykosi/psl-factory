VERDICT: PASS
REVIEWER: reviewer-ui
COMMIT: cc694876c715f0c927f3879491eb9ede706c4f31

## Summary
- Round-2 builder fidelity scores accepted (not re-run): desktop-internal 76.9, phone-internal 89.0, desktop-published 81.5, phone-published 92.1. Coverage is 100% after exceptions on all four. Phone-published passes the tool. The other three are under 90 and above D-83's 70 floor.
- I took screenshots of W-2312 at 1440 and 390 against :4794 (`scratchpad/r2-1440.png`, `scratchpad/r2-390.png`). They confirm both round-1 fixes.
- The remaining gaps are all forced by D-111. They go to the design engineer as D-83 visual waivers (`approved_by` in `fidelity-exceptions.json` is still "builder proposal, pending design engineer"):
  - C1: "Sent to" section.
  - C3: 4-column actions table instead of rows of title and tag.
  - C4/C5: phone shows desktop wording and every section.
  - C6: "Open actions" in the links row.
  - C7: returned sentence in a white panel with a tag instead of the green band.
  - C8: Next in the side column, after main.
  - C11: frame tab bar with no counts and no current tab, and frame nav.
- No new CSS colours or one-off components. The new stack rules use existing tokens (`--space-*`, `--ink-muted`, `--rule-*`).

## Verified
- UI-1-1 | verified | "Open actions" now renders as `psl-link psl-btn psl-btn--secondary`, weight 600, an outlined button beside "Open the minutes". It is still a link and the assistant link is unchanged. Unit test asserts the class.
- UI-1-2 | verified | At 390 the actions table stacks each row, with ACTION, OWNER, DUE and STATE labels on every cell. The frame `scrollWidth` equals `clientWidth` (322), so there is no sideways scroll. OWNER NEEDED and Unknown are visible with their labels. Unit and e2e tests assert the labels and the no-scroll condition.
- UI-1-3 | verified | `fidelity-exceptions.json` now carries entries for the frame items and layout gaps, each citing its Conflicts number. The waiver is still pending the design engineer.

## Notes
- "Open actions" keeps the link underline (`psl-link`) while "Open the minutes" has none. This is taste, not blocking.
- The "Sent to" and actions panels still have a large empty area left of the "Confirm what happened" panel at 1440. This predates F-28 (same as F-21 W-2212) and I have not raised it against F-28.

## F-23 regression check (coordinator request)
- I loaded W-2301 to W-2308 at 390 on :4794. None of their tables carries `ws-table--stack` (W-2301, W-2306, W-2307 and W-2308 have one 5-column table each, with no state tag column; W-2302 to W-2305 have no table). The merged F-23 minutes tables are unchanged, so there is no regression against the F-23 boards.
- Only the F-28 pages (W-2310, W-2311, W-2313, W-2314) stack. The rule would apply to any future tag-column table, which is a note for the next feature, not a finding.
