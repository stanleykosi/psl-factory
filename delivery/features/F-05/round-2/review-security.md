VERDICT: PASS
COMMIT: cc3e185dd1ead6fc3079f9e15ef4f969b8b97fc8
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- The round-2 rebuild changed layout only. It did not touch `src/api/client.ts` or the write path in `useStartWork.ts`. CSRF on writes, the sync double-press guard, keys made when the drawer opens, "Check again" resending the same body and key, and a new key only after a definitive 409/422 are all as they were in round 1.
- Nothing in the browser decides authority. The always-shown "change line" opens a chooser that lists only the lines E-LINES returned. Back/Cancel, titles and the 480px width come from static maps of line keys. Server text (`decided_by`, 422 `name`/`message`) renders only as React text.
- The new optional Proof field is display only. It has no control, and `buildIntake` skips it, so evidence is never sent (`intake.ts:130-137`). A required evidence field still blocks starting from the drawer.
- My round-1 `journey_url` note is mostly fixed. `safePath` refuses `//`, `/\` and absolute URLs. It can still be beaten by a tab or newline character, which browsers strip (SEC-2-1). This is non-blocking because the value comes only from our own server.
- No new dependencies. The only fixture changes are copy and two optional `proof` fields, with no secrets or personal data. The mock rejects a POST /api/v1/work sent without CSRF (it returns 403).

## Findings
- SEC-2-1 | non-blocking | low | frontend | `safePath` (frontend/src/features/start-work/LineForm.tsx:120-122) lets through a path whose second character is a tab, CR or LF. Example: `"/\t/evil.example"` or `"/\n\\evil.example"`. Browsers strip those characters while parsing the URL, so the link resolves off-site. `node -e 'new URL("/\t/evil.example","http://localhost:3511/").href'` prints `http://evil.example/`. Expected: link only when `new URL(url, window.location.origin).origin === window.location.origin`, or accept only `^/(?![/\\])` with no ASCII control characters or whitespace anywhere. Add that case to the "not a same-origin path" test at tests/start-work.test.tsx:646. This can only be reached through a bad or compromised E-LINES value, so it is low risk.

## Verified
- Round-1 note (journey_url) | verified with residual | `safePath` now gates the `<Link>`. `//x`, `/\x` and `https://…` are not linked, and the 3-case test at tests/start-work.test.tsx:646 passes per build.md. The tab/newline bypass is still open and is SEC-2-1. Live mock pm E-LINES returns only `"/projects"`.
- CSRF kept | verified | `git diff 760ba3c cc3e185 --name-only` shows no change to `src/api/client.ts`. Submit still goes through `api.POST`. A throw from a missing token still maps to signed-out, not uncertain (`useStartWork.ts`, submit catch). A raw POST to the mock without a token returned 403.
- Idempotency kept | verified | The `writing` ref guard, `sent.current` replay while uncertain, and `setKey(newIdempotencyKey())` only on 422/409 are unchanged. The new `awaitingChange` flag is set only on 422 and cleared on any change, so it cannot block "Check again" after an uncertain result.
- No client-side authority | verified | The case and revision still come only from `caseRef` (the line or the server option). The `labels.ts` maps are presentation only. The chooser lists only returned lines.
- Safe error and uncertain handling | verified | A 5xx, a non-4xx answer or a network error still locks the form and shows the uncertain notice. A 401 shows signed out, and a 403/404 shows "You can't start this here." plus the server message. A 422 field that matches nothing is drawn as `ProblemBox` (the name with underscores replaced, and the message as text), with no HTML sink.

## Notes
- Still open from round 1, by design (PMO-0-2): if the user leaves after an uncertain result, the key is thrown away. Only server-side duplicate detection per case and line closes that gap. This is for backend/product.
- `ProblemBox` uses `problem.name` as its React key. Duplicate names from the server would only log a React warning. This is not a security issue.
- Out of scope for a frontend-only round against the contract mock: real session and CSRF validation, per-record grants, and server-side option filtering.
