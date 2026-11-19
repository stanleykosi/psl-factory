GATE: FAIL
COMMIT: 0a7196f6eaf9b82b7193ea7139b2e0b72cb9aeb9
ATTEMPT: 1

## Summary
- checks.sh failed with exit 1
- Protected paths: none changed
- Commit 0a7196f6eaf9, round 1, attempt 1

## checks.sh (last 80 lines of checks.log)

```
System check identified no issues (0 silenced).
== frontend: install, lint, typecheck, test, build

added 457 packages in 53s

> psl-factory-frontend@0.1.0 lint
> eslint . --max-warnings 0


> psl-factory-frontend@0.1.0 typecheck
> tsc --noEmit


> psl-factory-frontend@0.1.0 test
> vitest run


 RUN  v5.1.0 /Users/Hunchoo/psl-factory-worktrees/f-48/frontend

 ❯ tests/mock-contract.test.ts (297 tests | 297 skipped) 10104ms

 Test Files  1 failed | 99 passed (100)
      Tests  1974 passed | 297 skipped (2271)
   Start at  11:59:19
   Duration  251.51s (tests 64%, environment 18%, import 8%, transform 6%, setup 4%)

    Isolate  100 workers spawned · ~4.04s startup each (spawn + environment, per file)
             at least ~53.62s faster with isolate: false — reuses workers across files instead of one per file

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
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: navigation to another Document
Not implemented: navigation to another Document
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
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package

⎯⎯⎯⎯⎯⎯ Failed Suites 1 ⎯⎯⎯⎯⎯⎯⎯

 FAIL  tests/mock-contract.test.ts [ tests/mock-contract.test.ts ]
Error: Hook timed out in 10000ms.
If this is a long-running hook, pass a timeout value as the last argument or configure it globally with "hookTimeout".
 ❯ tests/mock-contract.test.ts:160:1
    158| let base: string;
    159|
    160| beforeAll(async () => {
       | ^
    161|   server = await startMockServer({ port: 0 });
    162|   base = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;

⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯[1/1]⎯
```
