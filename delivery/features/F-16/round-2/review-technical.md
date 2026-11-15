VERDICT: PASS
COMMIT: df180ca0716d9a70e19bc82f5df57cce37e99aeb

# F-16 round 2 technical review

Scope: diff 713e628..df180ca, six files, all layout and accessibility. Scope was confirmed in review-security.md. `useDecision.ts`, the claim/decide calls, `expected_revision`, 409/stale handling and the `src/shell` and `src/features/work-item` code have no diff, so the F-14 seam is unchanged.

## Checks
- Focus (done): `DecideHeader` focuses the h1 in an effect keyed on `focusHeading`. The prop is true only in `DoneView`, so focus moves once on arrival. Other callers pass no prop, so the h1 gets no `tabIndex` and there is no extra tab stop. A new test asserts `activeElement` is the h1.
- Focus (stale): `StaleView` focuses its h2 from an effect with an empty dependency list, so it fires once on mount. The `role="alert"` on the same element also announces. Focus plus alert may read twice, which is acceptable and not blocking.
- Polite live region: the `role="status"` line is static text inside `DoneView`, mounted once and never re-rendered with new text, so it fires once. It mounts together with its content, which some screen readers skip. That is a best-effort limit, not a defect.
- Agent on phone stale: `phone && agent` and `!phone && agent` are mutually exclusive, so the agent renders in exactly one place and there is no double render. `useIsPhone` uses `useSyncExternalStore` with a server snapshot of `false` and a matchMedia subscription, so it follows viewport changes and there is no hydration mismatch. The agent note moves between slots on a breakpoint change, but its state is not lost because it is presentational.
- Paid line: on desktop it is hidden only when the reloaded `next_step` contains the sentence, and it shows on phones or when the reload is missing. A reload failure (`reloaded` undefined) still shows the line, so the information is never dropped. The test counts exactly one on desktop.
- h1 on the 5xx and 401 views: a `decide-sr` h1 is added, and nothing else changes. The new test covers 5xx. 401 uses the same wrapper pattern.
- `chidi-done.png` is a static asset. Non-Chidi agents fall back to `agentImage`. The name match is case-insensitive, and an undefined name is handled by `?.`.
- CSS: the `.psl-callout.decide-next` override does not touch other callouts. `psl-callout--success` is kept for the existing assertion. Phone-only rules sit inside the phone media block.
- Tests: none weakened. `decide.test.tsx` and `e2e/decide.spec.ts` have no diff. One assertion changed from a presence check to an exact count of 1, which is stricter. `checks.md` shows all project checks passed on this head.

## Round 1 impact
Round-1 findings are fixed per build.md (UI-1-1, UI-1-2, UX-1-1, UX-1-2) and match the code above. Everything else in round 1 is unaffected by this diff.

No TECH findings.
