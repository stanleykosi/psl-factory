GATE: FAIL
COMMIT: ec939861a647cc4a8e62d795394263c13a08b2e6
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit ec939861a647, round 2, attempt 1

## checks.sh (last 80 lines of checks.log)

```


> psl-factory-frontend@0.1.0 test
> vitest run


 RUN  v5.1.0 /Users/Hunchoo/psl-factory-worktrees/lane-a/frontend

 ❯ tests/api-live-schema-drift.test.ts (2 tests | 1 failed) 39316ms
   × src/api/live-schema.d.ts equals openapi-typescript output for the live contract 39305ms

 Test Files  1 failed | 157 passed (158)
      Tests  1 failed | 3753 passed (3754)
   Start at  10:41:01
   Duration  999.02s (tests 51%, environment 24%, import 14%, setup 8%, transform 3%)

    Isolate  158 workers spawned · ~3.48s startup each (spawn + environment, per file)
             at least ~271.12s faster with isolate: false — reuses workers across files instead of one per file

npm warn EBADENGINE Unsupported engine {
npm warn EBADENGINE   package: 'jsdom@31.0.1',
npm warn EBADENGINE   required: { node: '^22.22.2 || ^24.15.0 || >=26.0.0' },
npm warn EBADENGINE   current: { node: 'v24.12.0', npm: '11.6.2' }
npm warn EBADENGINE }
npm warn EBADENGINE Unsupported engine {
npm warn EBADENGINE   package: 'w3c-xmlserializer@6.0.0',
npm warn EBADENGINE   required: { node: '^22.22.2 || ^24.15.0 || >=26.0.0' },
npm warn EBADENGINE   current: { node: 'v24.12.0', npm: '11.6.2' }
npm warn EBADENGINE }
npm warn deprecated eslint@9.39.5: This version is no longer supported. Please see https://eslint.org/version-support for other options.
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

⎯⎯⎯⎯⎯⎯⎯ Failed Tests 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  tests/api-live-schema-drift.test.ts > src/api/live-schema.d.ts equals openapi-typescript output for the live contract
Error: Test timed out in 30000ms.
If this is a long-running test, pass a timeout value as the last argument or configure it globally with "testTimeout".
 ❯ tests/api-live-schema-drift.test.ts:11:1
      9| const LIVE_SOURCE = join(root, '../contracts/psl-factory.openapi.json'…
     10|
     11| it('src/api/live-schema.d.ts equals openapi-typescript output for the …
       | ^
     12|   const dir = mkdtempSync(join(tmpdir(), 'psl-live-schema-'));
     13|   try {

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
