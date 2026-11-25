STATUS: READY
COMMIT: 7087a95dfd0f4127015dde32fe85bf5b1092c34f
BUILDER: builder
LANE: full

## Summary
- A form engine (`frontend/src/features/start-work/engine/`) turns each line's served `request_schema` into the drawer's controls, body and 422 map. It plugs into F-86's registry, chooser, project picker and start state machine.
- Five lines work: pmo-issues, pmo-escalation, pmo-emergency, pmo-change (JSON to POST /work) and pmo-minutes (multipart to POST /projects/{case_id}/minutes/intake with the notes file).
- Record choices come only from intake-sources (parent_id, before) and, for escalation, the project's escalation register. No id is typed.
- A line whose schema the engine cannot fully draw is "Not available here yet" (pmo-leadership-report in the mock; any line with an array/object leaf, or a leaf the config has no source or words for). pmo-weekly-report is unchanged apart from added optional args, plus a schema guard test.

## Changes
- engine/schema.ts, plan.ts, config.ts, body.ts, controls.tsx, engine.tsx, escalations.ts, minutes.ts: schema walk, plan, body, 422 target, controls, minutes send.
- lines/pmoIssues, pmoEscalation, pmoEmergency, pmoChange, pmoMinutes: one config each; lines/index.ts: registry entries, additive `LineFormProps` (line, project, onRevision), `Prepared`, optional `send`, `available`, optional `line` arg on missing/buildBody/target.
- useStart.ts: optional 4th arg `line`; uses `form.send` when present; the revision a source read returns replaces the project's (reset on project change or 409 reread). LineForm.tsx, StartWorkDrawer.tsx pass `line`; LineChooser.tsx `isStartable` also asks `form.available`. intake.ts: `FieldValue` adds `File`.
- mock/start-live.mjs: served schemas for all lines, source rows with parent_id/before paging, escalation register, minutes multipart route with log; server.mjs routes it. Also maps the server's P-nnnn path ids back to UUIDs. Both pass `node --check`.
- Tests: tests/start-work-engine.test.ts (48), start-work-engine-ui.test.tsx (22), updated start-work-live, next-config (allow-list line), rfp-intake-mock (engine file control has an empty accept on purpose), e2e/start-work-lines.spec.ts, e2e/start-work.spec.ts chooser counts.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] fieldsOf per line, leadership unsupported: engine tests and chooser e2e.
2. [x] buildBody validates with ajv against each served schema, extra key fails, no background, nulls for empty optionals: engine tests.
3. [x] Weekly guard: "the weekly guard" test in start-work-engine.test.ts.
4. [x] Issues: e2e (both viewports) checks body keys and /work/4102.
5. [x] Escalation: UI test (labels from served direction/target, null template, reference, empty text).
6. [x] Dependent pickers: UI test (parent_id query, "Choose emergency record first.", clears on parent and project change).
7. [x] Minutes: e2e and UI test list the six parts, no background, no /files call; grep shows `FormData` only in engine/minutes.ts and no uploadCaseFile in engine/lines.
8. [x] Required empty: no request, each named (e2e, UI tests).
9. [x] 422 mapping table: engine tests; unknown name gets its own box (UI test).
10. [x] Replay/uncertain: e2e minutes (same file and key), UI tests for a JSON line (409, 503).
11. [x] Latest revision sent: UI test.
12. [x] 401/403/404/csrf_failed handled by F-86's machine for one JSON line and minutes (UI tests).
13. [x] Failed source read shows retry, Start stays enabled (UI test). The "mock stopped mid-start" case is covered by the uncertain tests, not a separate e2e.
14. [x] Chooser shows the unsupported line with the link (e2e, live test).
15. [x] Greps in the registry test.
16. [x] No "8 days" text; fields and values read from the schema.
17. [ ] Fidelity tool NOT run. It needs a page URL with the drawer already open and the SCR-04 artboards; the drawer opens only by clicks. Open for the design engineer/coordinator.
18. [ ] Live check against Django 8020 not done (no login access allowed). Labels (Emergency record, Authorisation, Change version, Escalation request) and titles/start labels are mine from field names.

## Validation
- `tsc --noEmit` clean; `eslint . --max-warnings 0` clean; `node --check` on both mock files.
- Full vitest: 4377 tests, all pass after the final fix (one failing guard in rfp-intake-mock fixed; the rerun of that file passed, 18/18). Named files (next-config, demo-mock, mock-contract, start-work-live, start-work, line-adapter) pass.
- Playwright on 4980/4981: start-work-lines 8/8 and start-work 10/10 at 1440 and 390; axe clean on the issues form. Servers were stopped by Playwright; no listeners remain.

## Blocked
Not blocked.
