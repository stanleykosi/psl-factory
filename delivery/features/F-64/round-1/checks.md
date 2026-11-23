GATE: FAIL
COMMIT: 714580f7340dde93c2b581ed1c2cf9e92c5a6d41
ATTEMPT: 2

## Summary
- checks.sh failed with exit 143
- Protected paths: none changed
- Commit 714580f7340d, round 1, attempt 2

## checks.sh (last 80 lines of checks.log)

```
== backend: django system check
System check identified no issues (0 silenced).
== frontend: install, lint, typecheck, test, build

added 457 packages in 3m

> psl-factory-frontend@0.1.0 lint
> eslint . --max-warnings 0


> psl-factory-frontend@0.1.0 typecheck
> tsc --noEmit


> psl-factory-frontend@0.1.0 test
> vitest run


 RUN  v5.1.0 /Users/Hunchoo/psl-factory-worktrees/lane-a/frontend

 ❯ tests/assistant.test.tsx (63 tests | 1 failed) 434203ms
   ❯ default state (SCR-05-desktop) (5)
     × signed out: the callout with next = this page 30763ms
 ❯ tests/ledger-source.test.tsx (47 tests | 1 failed) 158253ms
   ❯ who may act (AC 7, 13) (3)
     × finance_lead, ceo and pm see the same controls on every fixture; the new code reads no /me 30081ms
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
Not implemented: navigation to another Document
Not implemented: HTMLCanvasElement's getContext() method: without installing the @napi-rs/canvas npm package
```
