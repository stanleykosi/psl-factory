VERDICT: PASS
COMMIT: af3b958cfa5807108e940017aefdc04e60375b1b
REVIEWER: reviewer-ui
AUTHORITY: UI design reviewer (design-fidelity gate)

## Summary
Lean confirm (D-64, D-66 extra round) from `git diff f91bc63..af3b958 -- frontend/src`; no fidelity run, build or boards comparison needed.
- Scope: both CSS additions are inside the existing `@media (max-width: 720px)` block, so desktop is untouched. The flow modifier `ws-decide--flow` is added only when `flow.allLocked && hasReconcile`; in every other state the pinned bar rules (D-63: fixed, borderless, full-width, 2px top rule, consequence sentence beside the buttons, `padding-bottom: var(--ws-bar-h)`) apply unchanged.
- Flow state: `.ws-decide.ws-decide--flow { position: static }` keeps the remaining bar styling (surface, top rule, padding) and `.ws:has(...) { padding-bottom: 0 }` removes the now-unneeded bar clearance. The reconcile pinned button is no longer covered (QA-5-1).
- Wrapping: `white-space: normal` is added to `.ws-decide .psl-btn` alongside the existing `min-height: 44px`. Wrapping only increases height, so the 44px target floor holds; widths are governed by the unchanged `flex: 1 1 120px` wrapper.
- Note: the `white-space: normal` rule applies in the pinned state too, so a long label may now grow the bar; `--ws-bar-h` is measured from the element, so clearance follows.

## Findings

## Verified
- UI-3-1 | verified | in round-4/fidelity/unknown-money-1440/side-by-side.png the money cells are now left-aligned in the body sans, as on SCR-56, and the amber note shows the warning icon. unknown-money 72.3 -> 75.6, coverage 100%.

## Notes
- Non-blocking follow-up: the checklist "UNKNOWN - Unknown" double label.
