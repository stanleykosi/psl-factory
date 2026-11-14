VERDICT: PASS
COMMIT: 0758d3e3f8568c084ed88b1c37a05f0641d62510
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- SEC-3-1 is closed. `safePath` now refuses any same-origin result whose path starts with `//`. I ran it in node against 47 hand-picked bypass forms and 300,000 random strings. Every value it returned was a single-slash path on the same site.
- The six new refused cases in the tests fail on the old function: with the round-3 `LineForm.tsx` swapped in, 6 failed and 8 passed. With the head version, all 61 tests in `tests/start-work.test.tsx` pass. I restored the file afterwards and the worktree is clean.
- The merge of the v7 base brings no security regression into F-05's files. `src/api/client.ts`, `package.json` and the lock file are the same as the base, so the X-CSRFToken middleware is the base's own. Since round 3, the only change in the start-work code is the `safePath` line.
- Idempotency, authority and output handling are as verified in round 3. The new `ceo` mock persona is local mock data only. There are no new dependencies and no secrets.

## Findings
None.

## Verified
- SEC-3-1 / TECH-3-1 | verified | `frontend/src/features/start-work/LineForm.tsx:123-132` now has `if (resolved.origin !== origin || resolved.pathname.startsWith('//')) return undefined;`. I tested an exact copy in node with origin `http://localhost:4611`. These are all refused: dot segments (`/.//`, `/..//`, `/a/..//`, `/a/b/../..//`, `/././/`), encoded dots (`/%2e//`, `/%2e%2e//`, `/%2E%2E//`, `/.%2e//`), absolute same-origin forms (`<origin>//evil`, `<origin>/.//e`, `http://LOCALHOST:4611//evil`), `//`, `///` and `////`, backslash forms, tab and newline, a leading ASCII space, `http:/.//evil`, `http://localhost:4611@evil`, other origins, and `javascript:` and `data:`. Some odd forms are passed through, but each one stays on this site. Leading NBSP, U+3000, BOM and U+2028 come back percent-encoded (`/%C2%A0//evil.example`). `http:evil.example` becomes `/evil.example`. Encoded `%2f` and `%5c` stay encoded. `?//x` becomes `/?//x`. A 300,000-case random fuzz over `/ . .. %2e // \ space tab %2f %5c ; ? # @ : http: host` found 0 results that start with `//`, do not start with `/`, or resolve to another origin. On the test side, the six added cases at `tests/start-work.test.tsx:688-693` fail on the 230edd6 function and pass at head.
- SEC-2-1 / TECH-2-1 | verified | This was reopened in round 3 only because of the dot-segment bypass, which is now closed. The same-origin rule holds.
- CSRF kept | verified | `git diff origin/dlv-00-delivery-setup 0758d3e --name-only -- frontend/src/api frontend/package.json frontend/package-lock.json` is empty. `useStartWork.ts` still writes through `api`/`call` from `@/api/client`, and `client.ts:18-35` sets X-CSRFToken on every write.
- Idempotency kept | verified | `git diff 230edd6 0758d3e -- frontend/src/features/start-work frontend/mock/start-work.mjs` changes only `safePath`. The key handling in `useStartWork.ts` (lines 92, 198 and 211) is as checked in round 3.
- Merge impact | verified | Compared with the base, F-05 touches four shared files.
  - `mock/server.mjs` adds the start-work route and the `ceo` persona. The mock's refusal to start under NODE_ENV=production is from the base and is still tested.
  - `PhoneBar.tsx` and `TopNav.tsx` show "+ Start" only when `me.startable_lines` is not empty. This is display only; the server decides on every start.
  - `mock-contract.test.ts` adds the persona and swaps the unmocked-operation example.
  - There is no `dangerouslySetInnerHTML`, `innerHTML`, `window.open` or location assignment in the start-work files or the shell bars.

## Notes
- Non-blocking: the component-level `it.each` at `tests/start-work.test.tsx:714` still covers only the round-2 forms. Adding one dot-segment case there would also prove the link is never drawn. The unit test already covers the function.
- Still open from round 1, by design (PMO-0-2): if the user leaves after an uncertain result, the idempotency key is thrown away. Only server-side duplicate detection closes that gap. This is for backend/product.
