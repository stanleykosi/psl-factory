VERDICT: CHANGES
COMMIT: 9d9b149c0eee33789567d9006229314f1224d6d0
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-5-1 is addressed: the bar's real height is measured on phone into `--retro-bar`, and both scroll padding and page padding derive from it (`RetroForm.tsx` effect, `retrospective.css`). The measurement is removed on phone-off and on unmount.
- TECH-5-2 is addressed: the fixed wait is gone, focus moves by Tab, and the test now reaches controls below the fold (Add a decision).
- The focus handler is phone-only (`if (!phone ...) return`), skips controls inside the bar, and is a no-op on desktop. The TypeScript types for `event.target` on `FocusEvent<HTMLFormElement>` make the `getBoundingClientRect` and `contains` calls valid.
- The e2e test is real (it asserts real focus, real bounding boxes and `elementFromPoint`), but it covers five controls, not the "every control" that criterion 24 requires. This blocks the round (TECH-1-1).
- Not run by me: no servers were started, per the round rules. Evidence is the builder's 27/27 run and the GitHub gate on this head.

## Findings
- TECH-1-1 | blocking | high | frontend | AC 24 (UX-5-1) says "every control in the form that takes keyboard focus (reached by Tab from the first box through to Save and the decisions and follow-up controls)". The phone test (`frontend/e2e/retrospective.spec.ts` ~L416-441) checks only "What didn't" (focus), "Lessons for next projects", Tunde Bello, Ada Obi and "Add a decision". It never checks "What went well", the Reference field, the Notes file select, the decision fields, the follow-up controls, or Save. The criterion's own check is therefore not met as written, and a regression on those controls would pass. Expected: a Tab walk from the first box to the last control (or a loop over all focusable controls in `form` that excludes the bar's own controls), with the same bottom-above-bar and `elementFromPoint` assertions for each. Actual: five sampled controls. Path: `frontend/e2e/retrospective.spec.ts:416-441`.
- TECH-1-2 | non-blocking | low | frontend | `clearOfBar` (`RetroForm.tsx`, the `requestAnimationFrame` in the focus handler) is not cancelled when the form unmounts or the focus moves again. The callback reads `bar.current` and calls `window.scrollBy` after the component may have gone, which is harmless today but can scroll a page the user has left. Expected: keep the frame id and `cancelAnimationFrame` it in an effect cleanup, or accept as a known trade-off. Path: `frontend/src/features/retrospective/RetroForm.tsx` (`clearOfBar`).
- TECH-1-3 | non-blocking | low | frontend | The e2e test's negative case is not recorded. Nothing in `build.md` or `checks.md` shows the test failing at 53c24b19 (before the handler), so the claim that it would catch a hidden control is untested. Expected: a note in the round's `checks.md` of a red run at 53c24b19 (or the reason it is not run), so the test is shown to discriminate. Path: `delivery/features/F-119B/round-1/checks.md`.

## Verified
- TECH-5-1 | verified | The effect measures `el.getBoundingClientRect().height` with `ResizeObserver` on phone only, sets `--retro-bar` on `html`, and removes it in cleanup. `retrospective.css` uses `calc(var(--retro-bar, 110px) + 16px)` for scroll padding and `calc(var(--retro-bar, 110px) + 32px)` for page padding, so a wrapped reason line is covered. Read the code; the 27/27 e2e run is the builder's evidence, not repeated by me.
- TECH-5-2 | verified | Read `e2e/retrospective.spec.ts`: `waitForTimeout` is removed, focus is moved with Tab, and the test covers a control below the fold (Add a decision, asserted above the bar). Coverage is still narrower than AC 24, see TECH-1-1.
- UX-5-1 | verified | Code path read: `onFocus={clearOfBar}` on the form, phone only, skips `el.contains(target)`, and scrolls by `target.bottom - (bar.top - 8)` when positive. The fix is correct for the controls it runs on; the coverage gap is TECH-1-1.
- Phone-only and cleanup | verified | The handler returns early when `!phone`, the effect is keyed on `[phone]`, and cleanup disconnects the observer and removes `--retro-bar`.
- TECH-5-3 (remount at 720px) | carried | Accepted trade-off in the builder's `## Left`. Unchanged by this diff; the values live in `draft`.
