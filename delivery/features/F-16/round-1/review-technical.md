VERDICT: PASS
COMMIT: 713e628b94ce0babdd045dbb45f17ac85cafb507
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- The page is a layout change only. `useDecision.ts`, `format.ts` and the claim, decide, 409, uncertain-effect and note logic have no diff. `DecidePanel.tsx` gains one class name (`decide-who`).
- F-14 seam holds: `DecisionRows`, `AmountValue` and `formatClock` keep their single exports and output. There is no diff under `src/shell` or `src/features/work-item`. `tests/decide.test.tsx`, `e2e/decide.spec.ts` and `mock/server.mjs` are untouched. `decide.css` has no hex, rgb or hsl values.
- `decide_presentation` is contained. It is read by a safe cast, hidden when absent and never sent anywhere. `queue.next.href` goes through `isAppPath`. The comment box is `disabled` and tied by `aria-describedby`. Contract fields win: unknown amounts read Unknown, and the title, rows and chain come from the contract.
- Deviations accepted: W-19xx fixtures (W-18xx ids are already work ids, so the move is justified), the frozen-pages proxy on 4603 (same-origin fonts), the no-access title wrapper (the work-item permission card sets 33px, so a scoped override is needed for criterion 6) and the SR-only stale phone title (the board draws none; the h1 stays in the DOM at 26px). The two fidelity waivers in D-56 are outside this review.
- Local run on this head: `decide`, `decide-board`, `mock-decide` and `mock-contract` pass (281 tests, 11s). The vitest `testTimeout` is 30s, so the one earlier timeout was gate load and not a code timing risk. No test waits on real time.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `tests/mock-contract.test.ts`: the crafted-href test ("a crafted next-decision href ... fails the block schema") uses pattern `^/(?!/)`. That is weaker than `isAppPath`, which also rejects whitespace and backslashes, so `/\x.example` passes the schema. The runtime is safe because `nextDecision` uses `isAppPath`, and `decide-board.test.tsx` covers `/\` and a leading space. Optionally align the pattern with `isAppPath`.
- TECH-1-2 | non-blocking | low | frontend | `DecideView.tsx` (layout map): when `layout` is `decide` but `claim` is null, the render falls to the read-only branch while the phone back link says "Decisions". The state is transient and has no behaviour effect. Optionally derive `layout` from the same condition as the render.

## Verified
- Changed assertions in `mock-contract.test.ts`: both are justified and widen coverage. The `decide_presentation` strip mirrors F-14's `presentation` strip, and the widened `boardFixture` condition applies only to W-19xx files that carry `presentation`. Every other file must still have neither block, and the sidecar check enforces this. Nothing is removed or loosened.
- Criterion 18 depends on the recording-fetch tests in `decide-board.test.tsx`, which I read at test level only. I did not re-run the e2e.
