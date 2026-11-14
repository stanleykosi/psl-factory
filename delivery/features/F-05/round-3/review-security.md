VERDICT: CHANGES
COMMIT: 230edd60f366ea64a1a138dc66f2084bd447ebd1
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- The new `safePath` refuses the four named cases: control characters (tab, newline), backslashes, protocol-relative `//` and absolute URLs from another origin. But it now returns the URL parser's cleaned-up path, and that path can begin with `//`. So `"/.//evil.example"` (and `/..//`, `/a/..//`, `/%2e//`) passes the origin check and is linked as `//evil.example`, which takes the user to another site. Round 2 passed the raw string through, so it did not have this hole. It is new in this round (SEC-3-1).
- CSRF is unchanged. Round 3 does not touch `src/api/client.ts`, the mock or `package.json`, and the merge a257dfa brings into `frontend/` only three PNGs under `public/agents/`.
- Idempotency is unchanged. The `writing` guard, the uncertain replay of `sent.current` with the same key, and a new key only on 422/409 are all as before. The only change on the write path is a narrower set of names that are matched inline (`fillable`), and that cannot send or replay anything.
- Nothing in the browser decides authority. The case still comes only from `caseRef`. The moved help text and the problem boxes render server text only as React text. The Tola mascot is a static local image with `alt=""`.
- No new dependencies (`next/image` is part of Next) and no secrets in the diff.

## Findings
- SEC-3-1 | blocking | medium | frontend | The same-origin check can still be beaten, now through dot segments. `safePath` (`frontend/src/features/start-work/LineForm.tsx:121-130`) checks `resolved.origin === origin` and then returns `resolved.pathname + resolved.search + resolved.hash`. The parser collapses `.` and `..` segments, so `new URL("/.//evil.example", origin).pathname` is `"//evil.example"`. The origin matches, so that string goes to `<Link href>` at `LineForm.tsx:146`, and the browser reads it as protocol-relative: `http://evil.example/`. I ran an exact copy of the function in node: `safePath("/.//evil.example","http://localhost:3511")` returned `//evil.example`. `/..//evil.example`, `/a/..//evil.example`, `/%2e//evil.example` and `/%2e%2e//evil.example` do the same. Round 2's raw-string check passed `/.//evil.example` through unchanged, and a browser resolves that as a same-origin path, so this bypass is new in this round. Expected: return `resolved.href`, which is an absolute same-origin URL (Next's `Link` treats a same-origin absolute URL as local). Or refuse when `resolved.pathname.startsWith('//')`. Then add `'/.//evil.example'`, `'/..//evil.example'` and `'/%2e//evil.example'` to the refused `it.each` at `frontend/tests/start-work.test.tsx:680` and to the component `it.each` at `:700`. The risk is the same as TECH-2-1: only a bad or compromised E-LINES value can reach it, and the mock sends only `"/projects"`. It is blocking because this round claims and tests this exact rule and leaves a working bypass.

## Verified
- SEC-2-1 / TECH-2-1 | reopen | Tab, CR, LF, other C0 controls, DEL, backslash, `//x`, `https://other`, `javascript:` and empty are now refused. I checked this in the code and the tests at `tests/start-work.test.tsx:678-686` and `:700-711`. A leading space (`" //evil"`) is also safe: the parser strips it and the origin then differs. But the dot-segment bypass in SEC-3-1 still links off-site, so the same-origin rule does not hold yet.
- CSRF kept | verified | `git diff cc3e185 230edd6 --name-only -- frontend/src/api frontend/mock frontend/package.json frontend/package-lock.json` is empty. The merge a257dfa adds only `frontend/public/agents/{chidi,tola,zainab}.png` under `frontend/`.
- Idempotency kept | verified | `useStartWork.ts:185-219`: 201 goes to the work item, a 5xx or non-4xx is uncertain (the form locks and the key is kept), a 422 gets a new key plus `awaitingChange`, and a 409 gets a new key and a reload. `fillable` changes only which 422 problems are drawn inline and which are drawn as their own boxes.
- Authority and output handling | verified | `movedHelp` text comes from the line's own `field.help` and renders as a text node. The `ProblemBox` key change (`name-index`) is display only. There is no `dangerouslySetInnerHTML` and no new URL sink besides `journey`.

## Notes
- Still open from round 1, by design (PMO-0-2): if the user leaves after an uncertain result, the key is thrown away. Only server-side duplicate detection closes that gap. This is for backend/product.
- The merge also brings in delivery and architecture files from origin/dlv-00-delivery-setup. They contain secret-boundary text only, not secret values.
