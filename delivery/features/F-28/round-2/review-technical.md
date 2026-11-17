VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: cc694876c715f0c927f3879491eb9ede706c4f31

# Round 2 technical review (diff 521bbf18..cc694876, 5 files)

- Links.tsx: `project_tab` links now render as `<Link className="psl-btn psl-btn--secondary">`. Still real links; the `assistant` branch is unchanged. No regression.
- Sections.tsx: `ws-table--stack` is added only when the table has a `tag` column, and every cell gets `data-label`. Tables without a tag column keep their existing look.
- workspace.css: the new rules apply only inside the phone media query and only to `.ws-table--stack`. They exclude the `:has(.ws-table__steps)` layout through `:not(:has(.ws-table__steps))`, so the F-23 step-column tables keep their own rules. A table with both a tag column and a step column gets the stack class but not the row-block rule; that combination is unlikely and `tr` keeps its existing layout, so it is not raised.
- Residual risk (non-blocking): any other table with a tag column, including F-23 tables, will now stack on phones. This is intended (no sideways scroll, each cell labelled). I did not check the F-23 boards at 390px in a browser. The e2e check covers only the F-28 actions table.
- Tests: `tests/minutes-end.test.tsx` passes (42/42), including the new asserts for the `psl-btn--secondary` class, the `ws-table--stack` class and the `data-label` values. The e2e spec adds checks for no sideways scroll in the table frame and for the Action, Owner, Due and State labels. I did not run the e2e spec.
- TECH-1-1 and TECH-1-2: left non-blocking, as the round-2 build notes explain. Accepted.

No blocking findings.
