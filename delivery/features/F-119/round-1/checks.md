GATE: FAIL
COMMIT: de279c08b01dca4c09872c4a4eb68a25c71e6ad4
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit de279c08b01d, round 1, attempt 1

## checks.sh (last 80 lines of checks.log)

```
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 2 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  tests/cash-forecast.test.tsx > amounts as returned (AC 2 to 4) > no changed file under src adds parseFloat, Number(, reduce(, compactAmount or toFixed (AC 3) and none reads /me (AC 8)
AssertionError: expected [ …(6) ] to deeply equal []

- Expected
+ Received

- []
+ [
+   "+  return match ? Number(match[1]) : null;",
+   "+  return value && /^[1-9]\\d{0,9}$/.test(value) ? Number(value) : null;",
+   "+      const base = { text: row.text, evidence_id: Number(row.evidenceId) };",
+   "+    evidence_id: Number(draft.evidenceId),",
+   "+    owner_id: draft.ownerId === '' ? null : Number(draft.ownerId),",
+   "+    evidence_id: Number(draft.evidenceId),",
+ ]

 ❯ tests/cash-forecast.test.tsx:339:97
    337|     }
    338|     const added = diff.split('\n').filter((l) => l.startsWith('+') && …
    339|     expect(added.filter((l) => /parseFloat|Number\(|\.reduce\(|compact…
       |                                                                                                 ^
    340|     expect(added.filter((l) => /\buseMe\b|\/api\/v1\/me(?!\/onboarding…
    341|   });

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/2]⎯

 FAIL  tests/no-success-callouts.test.ts > no success callouts for an action result > renders a success callout only in the allowlisted files
AssertionError: expected [ Array(1) ] to deeply equal []

- Expected
+ Received

- []
+ [
+   "src/features/retrospective/RetrospectiveView.tsx",
+ ]

 ❯ tests/no-success-callouts.test.ts:26:56
     24|
     25|   it('renders a success callout only in the allowlisted files', () => {
     26|     expect(found.filter((file) => !(file in ALLOWED))).toEqual([]);
       |                                                        ^
     27|   });
     28|

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[2/2]⎯
```
