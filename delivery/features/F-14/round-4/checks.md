GATE: PASS
COMMIT: c26c9f34deee37f0078dbc4f852fec363bf35f6c
ATTEMPT: 1

## Summary
- checks.sh passed
- Protected paths: none changed
- Commit c26c9f34deee, round 4, attempt 1

## checks.sh (last 80 lines of checks.log)

```
> psl-factory-frontend@0.1.0 test
> vitest run


 RUN  v5.1.0 /Users/Hunchoo/psl-factory-worktrees/f-14/frontend


 Test Files  35 passed (35)
      Tests  856 passed (856)
   Start at  16:55:47
   Duration  36.86s (tests 57%, environment 25%, import 8%, transform 5%, setup 5%)

    Isolate  35 workers spawned · ~2.40s startup each (spawn + environment, per file)
             at least ~9.60s faster with isolate: false — reuses workers across files instead of one per file


> psl-factory-frontend@0.1.0 build
> next build

▲ Next.js 16.4.6 (Turbopack)
✓ Running next.config.ts took 1822ms

  Creating an optimized production build ...
✓ Compiled successfully in 856ms
  Running TypeScript ...
  Finished TypeScript in 3.8s ...
  Collecting page data using 7 workers ...
  Generating static pages using 7 workers (0/21) ...
  Generating static pages using 7 workers (5/21) 
  Generating static pages using 7 workers (10/21) 
  Generating static pages using 7 workers (15/21) 
✓ Generating static pages using 7 workers (21/21) in 617ms
  Finalizing page optimization ...

Route (app)
┌ ○ /
├ ○ /_not-found
├ ○ /assistant
├ ○ /exceptions
├ ƒ /finance/month-end
├ ƒ /frame-fixtures/phone-back
├ ○ /my-work
├ ○ /notifications
├ ○ /overview
├ ○ /projects
├ ○ /settings/alerts
├ ○ /setup
├ ○ /setup/costing-rule
├ ○ /setup/delegation
├ ○ /setup/payroll-visibility
├ ○ /setup/roles
├ ○ /setup/rules
├ ○ /setup/rules/delivery
├ ○ /setup/rules/finance
├ ○ /setup/staff
├ ○ /setup/templates
├ ƒ /work/[id]
├ ƒ /work/[id]/decide
├ ƒ /work/[id]/history
└ ƒ /work/[id]/respond


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
Not implemented: navigation to another Document
Not implemented: navigation to another Document
Not implemented: navigation to another Document
```
