VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: cc694876c715f0c927f3879491eb9ede706c4f31

## Verified
- UX-1-1 | verified | Checked on the running server (app 4794) at 390 and 1440, W-2312 and W-2313. "Open actions" is an `<a>` with `psl-btn psl-btn--secondary`, href `/projects/C-0211/actions`, 44px high. The outlined button-link now matches the design. This was fixed by UI-1-1.
- Phone actions table (UI-1-2) | verified | At 390 the table frame has scrollWidth equal to clientWidth, so it does not scroll sideways. Each cell is a grid with a visible label: Action, Owner, Due, State. All four values show (ACT-0461 / Tunde Bello / 13 Nov / OPEN). At 1440 the table is unchanged (table-cell, no labels).

## Carried forward
- UX-1-2 | accepted | Frame copy belongs to F-17, which is outside this lane. No impact on F-28.
- UX-1-3 | accepted | Note only. The reconcile order is intended.

## Diff impact
The diff touches only the project_tab link class, the data-label attributes, the ws-table--stack class and its phone-only CSS. Text and roles are unchanged. The stack applies only to tables with a tag column. Stacked tags span the cell width, which is cosmetic and not blocking. I raised no new findings.
