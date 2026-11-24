VERDICT: PASS
COMMIT: cfc3c462382095787d1edf2bbda089f7140d28cc
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel (D-180)

## Summary
- Delta review of 3df5462d..cfc3c462: seven files, frontend only, no contract or data change.
- Unknown is unchanged in meaning. Paid and Owed values still go through the same Value component; the new spans only wrap them. Nothing is summed and no zero is introduced.
- Accessibility semantics are right: aria-expanded on Proof, hidden h2 on each tab, document Escape listener only while the phone sheet is open and removed on cleanup.
- I ran money.test.tsx and milestones.test.tsx (single files, from frontend/): 2 files, 72 tests, all passed on cfc3c462. The gate also passed.
- TECH-1-4 stays open as a non-blocking note.

## Findings
- TECH-1-4 | non-blocking | low | integration | Open from round 1. Live smoke (AC17) saw only an empty seeded project, so a populated live body is unproven. Re-check on the first populated environment, with `reference`, `milestone_id` and `stage_position` set. Stages whose completion is beyond the first 25 rows lose the "Recorded by" line; Proof still works through `milestone_id`. Acceptable and documented.
- TECH-2-1 | non-blocking | low | frontend | MilestonesTab.tsx: aria-expanded is true once a proof has loaded or failed (any state other than loading). It is false while loading. The state says "shown", not "open", which matches the test. A second press re-reads rather than collapsing; consistent with the round 1 design, but the button then reports expanded while pressing it does not collapse. Consider a follow-up if the proof gets a hide action.

## Verified
- UI-1-2 | verified | MoneyCells.tsx wraps each of Paid and Owed in `.money__fig`; money.css sets `white-space: nowrap` on `.money__fig`, `.money__amountlink` and `.money__amount`. The test checks the fig text (`Paid NGN 2,000,000.00 ·`, `Owed NGN 500,000.00`) and the CSS rule. The Unknown row still reads `Paid Unknown · Owed Unknown` with no zero pattern. Layout itself not checked in a browser (builder states this too).
- UI-1-3 | verified | The idle Explanation renders the prompt as the panel body and the head is "Where a figure comes from"; the test asserts both and that the body text is exactly the prompt. No empty box remains.
- UI-1-4 | verified | project-tabs.css restyles `.psl-unknown` inside `.ptabs__ms` and `.ptabs__card` to bold plain text. The test asserts the text is exactly "Unknown", is not inside `.psl-tag`, and the CSS rule exists. The rule only changes style, not content.
- UX-1-1 | verified | MoneyTab.tsx adds a document keydown listener only when `phone && selectedKey !== undefined`, calls `router.replace` to the Money path, and removes the listener on cleanup. The test blurs focus, fires Escape on the body and expects the replace call. Running alongside the sheet's own handler is harmless; both do the same replace.
- UX-1-2 | verified | A visually hidden h2 on Money ("Billing by contract stage", desktop and phone) and on Milestones ("Contract milestones", only when stages exist). The tests find both by level 2 role and name, plus "Recorded completions". Heading order is sound.
- UX-1-3 | verified | `aria-expanded` is false before any press and true on the pressed row only after the proof loads; other rows stay false. The test covers both.
