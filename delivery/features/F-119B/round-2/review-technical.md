VERDICT: PASS
COMMIT: 48221d25fe73354c183109e18cfaaa5c621ae4d1
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-1-1 is fixed: the phone test now Tabs from the first box to Save on an empty form and on case 2002 with a carried decision, and asserts for each stop that it ends above the bar and that `elementFromPoint` returns it. Save is last in the phone DOM order (`{decisions}{saveBar}`), so the walk covers every form control before Save.
- TECH-1-2 is fixed: the rAF id is kept in `frame`, cancelled on each new focus and in an unmount cleanup. The cleanup reads the ref at unmount, which is correct here.
- TECH-1-3 is fixed: the recorded red run at 53c24b19 (step 1, "Lessons for next projects", bottom 775 against bar top 762) matches the mechanism the test is meant to catch.
- Two non-blocking gaps remain: the follow-up action controls are not in the walk (they never share the screen with the bar, so no occlusion is possible), and the first box is not hit-tested.
- Not re-run by me: no servers were started, per the round rules. Evidence is the builder's 27/27 e2e run, 49 unit tests, tsc and eslint, and the GitHub gate on this head (PASS).

## Findings
- TECH-2-1 | non-blocking | low | product | AC 24's parenthetical names "the decisions and follow-up controls" as reached by Tab from the first box to Save. The walk covers the decisions. The follow-up controls are `ActionForm` in `RetrospectiveView.tsx` (~L177), rendered only when the form is not shown (`!(form && editing)`), so they never coexist with `.retro__savebar` and cannot be drawn under it. The criterion text and the test scope disagree. Expected: product or the spec owner confirms that follow-up controls are out of the bar check (or the criterion is reworded), and the spec records it. Actual: no test on `ActionForm` controls; no occlusion path exists today. Path: `frontend/e2e/retrospective.spec.ts` (walk, ~L413-462), `frontend/src/features/retrospective/RetrospectiveView.tsx:168-185`, `delivery/features/F-119B/spec.md` AC 24.
- TECH-2-2 | non-blocking | low | frontend | The walk starts by focusing "What went well" with `preventScroll` at scroll 0 and then presses Tab, so the starting box itself is never hit-tested. At scroll 0 it is almost certainly clear of the bar, but AC 24 says "from the first box". Expected: run the same poll and `elementFromPoint` assertion on the starting box before the first Tab. Actual: the first assertion is on the second stop. Path: `frontend/e2e/retrospective.spec.ts` (`walk` start, `field(page, 'What went well').evaluate(...focus...)`).

## Verified
- TECH-1-1 | verified | Read the new walk: it loops Tab until focus leaves the form (fail) or reaches the bar (pass, 80-step cap), polls each stop until its bottom is at or above the bar top +1 (Save in the bar is exempt), and asserts `elementFromPoint` hit for every in-form stop. Two forms are walked: empty (7 stops, asserted > 6) and 2002 with a carried decision (asserted more stops than the first). Decision text, supporting-file select and Remove are inside the form before Save on phone, so they are walked. Builder's 27/27 e2e run on this head is the evidence; not re-run by me.
- TECH-1-2 | verified | `RetroForm.tsx`: `frame` ref; `cancelAnimationFrame(frame.current)` before each new `requestAnimationFrame` in `clearOfBar`; `useEffect(() => () => cancelAnimationFrame(frame.current), [])` on unmount. Phone-only guard and the `el.contains(target)` early return are unchanged.
- TECH-1-3 | verified | Read the recorded discrimination run in `round-2/build.md`: the new test fails at 53c24b19 at "empty form step 1" with the poll timing out (bottom 775.25 against bar top 762), which is the expected failure for code without the focus handler and with fixed 110px padding. Not re-run by me (copy and servers are out of scope for this round).
- Old test weakening | verified | The removed test checked four controls. Every control it checked (What didn't is now the walk's first stop after the start box, Lessons, Tunde Bello, Ada Obi, Add a decision) is still covered by the walk. No `.only`, `.skip`, `fixme` or `waitForTimeout` in the spec.
- TECH-5-3 (remount at 720px) | carried | Accepted trade-off in the builder's `## Left`. Unchanged by this diff.
