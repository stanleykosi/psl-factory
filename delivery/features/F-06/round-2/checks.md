GATE: FAIL
COMMIT: c4d0b05e5e25272eb9a66bf37cc0c390ba487c01
ATTEMPT: 1

## Summary
- checks.sh passed
- Protected paths: M delivery/config.json
- Commit c4d0b05e5e25, round 2, attempt 1

## checks.sh (last 80 lines of checks.log)

```
== backend: django system check
System check identified no issues (0 silenced).
== frontend: install, lint, typecheck, test, build

added 449 packages in 2m

> psl-factory-frontend@0.1.0 lint
> eslint . --max-warnings 0


> psl-factory-frontend@0.1.0 typecheck
> tsc --noEmit


> psl-factory-frontend@0.1.0 test
> vitest run


 RUN  v5.1.0 /Users/Hunchoo/psl-factory-worktrees/f-06/frontend


 Test Files  15 passed (15)
      Tests  363 passed (363)
   Start at  06:06:20
   Duration  58.82s (tests 50%, environment 29%, transform 9%, import 6%, setup 5%, worker 1%)

    Isolate  15 workers spawned · ~8.24s startup each (spawn + environment, per file)
             at least ~9.42s faster with isolate: false — reuses workers across files instead of one per file


> psl-factory-frontend@0.1.0 build
> next build

▲ Next.js 16.4.6 (Turbopack)
✓ Running next.config.ts took 7.5s

  Creating an optimized production build ...
✓ Compiled successfully in 3.9s
  Running TypeScript ...
  Finished TypeScript in 61s ...
  Collecting page data using 7 workers ...
  Generating static pages using 7 workers (0/9) ...
  Generating static pages using 7 workers (2/9) 
  Generating static pages using 7 workers (4/9) 
  Generating static pages using 7 workers (6/9) 
✓ Generating static pages using 7 workers (9/9) in 2.1s
  Finalizing page optimization ...

Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /assistant
├ ○ /exceptions
├ ○ /my-work
├ ○ /overview
├ ○ /projects
├ ○ /setup
├ ƒ /work/[id]
├ ƒ /work/[id]/decide
└ ƒ /work/[id]/history


○  (Static)   prerendered as static content
ƒ  (Dynamic)  server-rendered on demand

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
```
