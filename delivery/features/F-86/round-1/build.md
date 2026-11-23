STATUS: READY
COMMIT: 7d7d6cc313cb158e9d765a2593d154f06e430d16
BUILDER: builder
LANE: full

## Summary
- Start work now reads live `GET /lines` on every opening: no groups, no "Next:", title plus description; lines the screen cannot start (and `invoice`, hidden) follow the spec's unavailable rule with an "Open in the full form" link to `django_url`.
- The weekly report starts end to end on `POST /work` (`pmo-weekly-report/v1`): project picker on `GET /lines/projects`, Week, Reference, one idempotency key, 200 opens `/work/{id}`; 401/403/404/409/413/415/422/429/5xx follow the spec table.
- `lines/index.ts` is the per-line registry (`lineFormFor`, `LineForm`); F-88 adds `lines/<line>.tsx` plus one entry in `FORMS` and does not touch `LineChooser.tsx`. `fetchSources` and `SourcePicker` (intake-sources) and `StartUpload` (F-85 `EvidencePicker`) are built and tested but not rendered by the weekly form.
- Not done here: AC18 live run against Django (no permitted test login, no projects) and the fidelity tool (see Validation).

## Changes
Paths relative to `frontend/`.
- `src/features/start-work/types.ts`: live types (`Lines`, `Line`, `ProjectOptions`, `Project`, `IntakeSources`, `StartBody`, `WeeklyBody`, `StartResult`); v7 `Field`, `LineOption` kept, v7 line/body renamed `LegacyLine`, `LegacyStartBody` for `intake.ts`.
- `useStartWork.ts`: live `fetchLines`, `useLines`, `fetchProjects(line, q, page?)`, `fetchSources(caseId, line, {field, parentId, before})`; `fetchOptions` and `ProofState` kept for v7 pieces.
- `useStart.ts` (new): the start state machine (sync double-press guard, key reuse, uncertain lock and "Check again", 409 re-read of the revision, 422 mapping via the line's `target`).
- `lines/index.ts`, `lines/weeklyReport.tsx` (new): registry and the weekly line (fields, `missing`, `buildBody`, 422 name table).
- `LineChooser.tsx`: live rows, runs of startable lines as radio cards with unavailable cards between, in returned order; `StartWorkDrawer.tsx`: no `default_line`, every entry opens the chooser, prefill only for a startable live line; `LineForm.tsx` is now the `LineDrawer` shell.
- `ProjectPicker.tsx`, `SourcePicker.tsx`, `StartUpload.tsx` (new); `RecordPicker.tsx`: additive optional `source` and `emptyText` props (data source swap only).
- `labels.ts`: unavailable, 409 and 404 words as constants; unused v7 start labels removed. `start-work.css`: two small rules.
- `mock/start-live.mjs` (new) and `mock/server.mjs`: live `GET /lines`, `/lines/projects`, `/projects/{id}/intake-sources`, weekly `POST /work` with the cookie scenarios `start_stale`, `start_uncertain`, `start_denied`, `csrf_failed`, `start_missing`; `GET /__mock/start-live-log`. Served only when the mock runs with `liveStart` (`node mock/server.mjs` sets it); `startMockServer()` without it keeps the v7 start so the v7 contract tests stay valid.
- Tests: new `tests/start-work-live.test.tsx` (48 tests). Removed because they test the replaced v7 drawer: `tests/start-work.test.tsx`, `start-work-proof.test.tsx`, `start-work-ppe-forecast.test.tsx`, `start-work-prefill.test.tsx`, `rfp-intake.test.tsx`, and e2e `start-work-proof`, `start-work-ppe-forecast`, `rfp-intake`; `e2e/start-work.spec.ts` rewritten. Edited: `assistant.test.tsx` and `issue-detail.test.tsx` (draft and "Raise an escalation" now expect "You can't start this here."), `start-work-intake.test.ts` (type rename), `next-config.test.ts` (allow-list gains `LineChooser.tsx`, `start-live.mjs`, `start-work-live.test.tsx` for `django_url`).
- `src/api`: no change.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Chooser shows live lines by title and description, no group heading, no "Next:": `tests/start-work-live.test.tsx` (chooser) and a 1440/390 look at the dev build on 4980/4981. `e2e/start-work.spec.ts` asserts it too (written, not run: it needs its own production build and ports).
2. [x] Unavailable rows (cannot submit, or no registered form) link to `django_url`, are not radios, Next stays disabled, `invoice` never shown: unit test with `pmo-minutes`, `finance-payroll` (can submit, no form), `pmo-issues` and an injected `invoice`.
3. [x] `fetchProjects` sends `line`, `q` only when non-empty (trimmed, capped at 120), `page` only when asked; 25 + 3 items, `next_page` 2 then null: unit test. "Show more" is RecordPicker's scroll-to-append (D-157), not a button: it requests `next_page` while it is set. Deviation from the spec's wording, kept because the spec says reuse `RecordPicker`.
4. [x] Empty press makes no `POST /work` and lists "Project/Week/Reference is required.": unit test and browser look.
5. [x] Body is exactly the weekly branch, with `template_id` and `content_id` null and no `background`; CSRF header sent: `buildBody` test, hook test, and a real browser start against the mock (request log showed the body, then URL `/work/4102`).
6. [x] Double press sends one request; "Check again" after 503 resends the same body and key: hook tests with the mock log (one started work).
7. [x] 409 keeps values, re-reads the revision by title search, next press has a new key and revision 5: hook test.
8. [x] 422 table, one test per row plus "none dropped" and "no fields" cases.
9. [x] 401 signed-out, 403 `csrf_failed` refreshes the session once and does not say "can't start", 404 says exactly "This record is unavailable.": hook tests.
10. [x] Hand-edited `case_id`: the mock answers 404 and the form shows the 404 wording; another project can still be started. Other-team projects are never listed because the list is the server's.
11. [x] Network failure (fetch throws) locks the form as uncertain and starts nothing: hook test. The mock-paused e2e was not run.
12. [x] `StartUpload` wraps `EvidencePicker`, disabled with "Choose a project first." before a project, keyed by case so it empties on a project change, returns the `upload_id`: component tests. `grep uploadCaseFile` finds it in the file's comment only (the call is inside `EvidencePicker`, as the spec asks); no second multipart helper under `start-work` (test greps).
13. [x] `fetchSources` sends `field`, `parent_id`, `before` only when set, returns `nextBefore` and `caseRevision`: unit test.
14. [x] `onStarted` receives `String(work_id)` (hook test); prefill for a line not in the startable list shows "You can’t start this here." (drawer test, plus updated assistant and issue-detail tests).
15. [x] No `default_line` in `src/features/start-work`; `LineChooser.tsx` imports only `lineFormFor` (a registry lookup), no per-line form: test greps.
16. [x] No "8 days" text under `src/features/start-work`: test grep.
17. [ ] Fidelity: not run, see Validation.
18. [ ] Live run: not done. The test accounts have no projects and no permitted login here. `GET /lines` live shape matches `live-schema.d.ts`; `start_at`/`end_at` as `YYYY-MM-DD` is still unverified against Django (assumption in the spec).

## Validation
- `npm run lint` and `npm run typecheck`: pass.
- `npm test`: 158 files; the run showed 3768 passed and 1 failed (`tests/setup-delegation.test.tsx`, a timing assertion on an announcement, unrelated to this branch). Re-run alone: 35 of 35 pass.
- `npm run build`: pass. (`checks.sh` itself was not run, because it runs `npm ci`, which the builder rules forbid.)
- Dev servers on 4980 (Next) and 4981 (mock): a Playwright script opened the drawer at 1440 and 390, checked the chooser, the empty-press summary and the project list, then made one valid start (typed dates `16 Nov 2026`, `22 Nov 2026`; body had `start_at: 2026-11-16`, `end_at: 2026-11-22`) and landed on `/work/4102`. Both servers stopped by PID; ports free.
- Design-fidelity tool: NOT run. It takes only a `--page` URL and cannot open the drawer (a click is needed), so it cannot capture any of the four boards. The 1440 and 390 screenshots I took look right against the layout of the old boards; the board differences are the spec's own (no groups, no "Next:", an added Reference field, no Template line, no help line, an unavailable card the board does not draw). A UI reviewer or the design engineer needs to compare by hand or give the tool a way to open the drawer.
- Broken outside this branch's tests (not changed, for the coordinator): e2e `demo.spec.ts` (starts a v7 line through the drawer), `hr.spec.ts` (HR "Month" form) and the Start work parts of `frame.spec.ts` and `alerts-bell.spec.ts` open the new drawer; they were not run. The demo's v7 start also has no live form. Not part of the gate (`checks.sh` runs vitest, not Playwright).

## Blocked
Not blocked.

## Notes for the coordinator
- Shared code to fix once: `makeCommand` body spread order (TECH-1-1) untouched, as instructed. `ValidationSummary` links focus a non-focusable wrapper unless the target has `tabIndex`; I gave the project box `id="sw-field-project"` and `tabIndex={-1}`, but the Week and Reference links only scroll, because `IntakeField` ids are internal. A shared fix would let `IntakeField` take an id.
- `start-work-intake.test.ts`, `intake.ts`, `IntakeField.tsx`, `StartProof.tsx` still carry v7 types for `StepForm`; they can shrink when StepForm moves.
- Board conflicts follow LC-Q3, LC-Q10, LC-Q11 as accepted. The 409 and "Not available here yet" wording are constants in `labels.ts`/`useStart.ts`.

## Browser tests (coordinator request)
Run on 4980/4981 from the lane worktree (production build, the project's Playwright config): `start-work.spec.ts` (10 tests, 1440 and 390, with axe), `hr.spec.ts`, `frame.spec.ts`, `alerts-bell.spec.ts`, `demo.spec.ts`. First run: 89 passed, 3 failed, 3 skipped. Fixed: the validation test found an axe target-size problem on the summary links (drawer CSS now gives them 24px targets); `hr.spec.ts` opened the old HR form, and now asserts the chooser shows the unavailable Payroll line with its full-form link and a disabled Next. Re-run: `start-work.spec.ts` and `hr.spec.ts` all pass. `frame.spec.ts` and `alerts-bell.spec.ts` passed on the first run unchanged. `demo.spec.ts` (3 tests) is skipped by the config (demo off in e2e); its first test starts a v7 invoice through the drawer and cannot pass while the drawer is live-only, so it needs a follow-up when the demo moves. The servers the run started were stopped by PID; ports 4980 and 4981 are free.

## Deleted v7 tests: what they covered
- `tests/start-work.test.tsx` and the v7 line table in the old e2e: chooser grouping and "Next:" summary (gone, LC-Q3/D-182); `default_line` main button (gone, no default line); invoice and other v7 line forms (gone until each line moves, now shown as unavailable); generic 422, 409 and uncertain start behaviour (now covered for the weekly line by `start-work-live.test.tsx`); axe (covered by e2e `start-work.spec.ts`).
- `tests/start-work-proof.test.tsx`, `e2e/start-work-proof.spec.ts`: base64 proof upload to `POST /cases/{id}/evidence` inside the drawer (gone: the weekly form takes no file, LC-Q11; `StartUpload` on F-85's multipart upload replaces it and is tested).
- `tests/start-work-ppe-forecast.test.tsx`, `e2e/start-work-ppe-forecast.spec.ts`: PPE and forecast line forms (gone until those lines get live forms; unavailable now).
- `tests/start-work-prefill.test.tsx`: the assistant's prefilled draft form (gone for v7 keys: a draft for a line with no live form shows "You can't start this here.", tested; prefilling weekly values is not built because the spec asks for none).
- `tests/rfp-intake.test.tsx`, `e2e/rfp-intake.spec.ts`: "Log a received RFP" start from the drawer (gone until F-88 registers its form; `rfp-intake-mock.test.ts` still runs).

## Coordinator note (lane C, 23 Nov)
Head moved from the builder's 540892b4 to da0d7b69 only by the coordinator merging F-85's head cdea4f98 (F-85 round 2 plus main e6c24e70, API 1.26.0). One conflict, in the `tests/next-config.test.ts` allow-list: main's entries were kept and F-86's three added. typecheck: 0 errors. Start work and weekly tests: 192 passed. The recorded base moved to cdea4f98, so the review diff is F-86 only.

Head then moved to 7d7d6cc3 by the coordinator merging origin/main e2f44656 (F-85's squash merge). The tree is byte-identical to the gated da0d7b69: `git diff da0d7b69 7d7d6cc3` is empty, and the two conflicts were resolved to F-86's side, which already held F-85's content. Base is now main e2f44656.
