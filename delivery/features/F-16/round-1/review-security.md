VERDICT: PASS
COMMIT: 713e628b94ce0babdd045dbb45f17ac85cafb507
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Layout-only change: `useDecision.ts`, `format.ts`, `src/api/**`, `src/shell/**`, `src/features/work-item/**`, `tests/decide.test.tsx`, `e2e/decide.spec.ts`, mock server code and `package*.json` have no diff against base 6282bb2 (`git diff --stat 6282bb2..713e628` checked for each)
- Claim/decide calls, CSRF, `expected_revision`, 409 stale handling (no retry), uncertain-effect reload, error mapping and note rules all still live only in the untouched `useDecision.ts`/`DecidePanel.tsx`; the only DecidePanel edit is a CSS class
- `you_can_act` gating is equivalent: the new `layout` map sends `forbidden || !task.you_can_act || !claim` to the read-only view as before; `decide_presentation` is never consulted for gating
- The PROPOSAL `decide_presentation` block renders only as React text nodes; `queue.next.href` goes through the existing `isAppPath` (leading single `/`, no whitespace or backslash), so external, protocol-relative and `javascript:` links are refused; the comment box is `disabled`, has no handler and sends nothing (component test records fetches)
- `drive-states.mjs` and `serve-frozen.mjs` exist only under `delivery/features/F-16/round-1/fidelity/` on the delivery branch, not on the task branch or under `frontend/`, so they do not ship

## Findings
None.

## Notes
- Non-blocking, low: `decidePresentationOf` (frontend/src/features/decide/presentation.ts:43-46) casts the block without checking it at runtime. Only `queue.position/total` (integers) and `next.href` (string, app path) are checked. If a non-string `label`, `subject`, `waiting` or agent field arrived, React would throw on render and the page would fail closed (no markup injection, no authority). This is acceptable for a mock-only proposal. When the contract takes these fields, generate them from the schema, or guard each one as a string.
- Non-blocking: `view.client` and `deco.subject` set the done heading and the page title. They are display only, but a person reads them during a money decision. When this moves to the contract, take them from server-derived record fields rather than free text.
- Test-only helper (pre-existing pattern, not shipped): `serve-frozen.mjs` calls `listen(port)` with no host, so it binds to all interfaces and proxies to the app on 4601. Its frozen-path check is a `startsWith(join(root,'frozen'))` prefix test. It is local tooling, but binding to `127.0.0.1` would be tidier.
- Frozen pages and W-19xx fixtures hold only `.example` addresses and the mock persona name. No tokens, CSRF values, cookies or secrets were found.
- On no-access, loading and error, the phone bar note is `undefined`, so no id or reference leaks there. The reference shows only on the read-only view, which already showed it in the Breadcrumb.
- No new dependencies. `next/image` is used with `unoptimized` and fixed `/agents/*.png` sources from the existing allow-lists.
