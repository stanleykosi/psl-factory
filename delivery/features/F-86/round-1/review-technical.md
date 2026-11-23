VERDICT: PASS
COMMIT: 7d7d6cc313cb158e9d765a2593d154f06e430d16
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel D-180

## Summary
- Live shapes match contract 1.26.0 in the worktree: GET /lines, GET /lines/projects, GET /projects/{case_id}/intake-sources, and the POST /work weekly branch (exact required keys, `reference` 1..160, 200 with integer `work_id`). Types come from `live-schema.d.ts`, so the compiler checks them.
- Start state machine is sound: synchronous double-press guard, one key reused on "Check again", new key after definitive 409/422/429, 5xx/network/missing id treated as uncertain.
- Deleted v7 tests cover behaviour that is gone from the drawer (grouping, `default_line`, v7 forms, base64 proof). The weekly line is covered by 48 new tests. The assistant tests lost start-result coverage; see TECH-1-2.
- Three non-blocking items: the mock drifts from 1.26.0, the assistant start-result path lost coverage, and 1.26.0 serves more than the spec hand-built.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `mock/start-live.mjs:27-36` and the project fixtures (`PROJECTS`) omit fields that 1.26.0 requires. `/lines` items lack `request_schema` and `content_type`; project items lack `django_url`, `source_options_url` and `workflow_intake_url`. The mock is not validated against the contract, so the tests pass on shapes the live server never sends. Add the fields so the mock matches 1.26.0.
- TECH-1-2 | non-blocking | low | frontend | `tests/assistant.test.tsx` lost the whole post-start behaviour for the assistant's "Start this invoice" (the "Started INV-0415." line, the thread re-read, focus, the "Open INV-0415" footer, uncertain and 409 through the drawer). The invoice has no live form, so it is unreachable today and the removal is defensible. But `onStarted` still exists for the assistant. A test that starts the weekly line through the assistant drawer would keep it covered. F-92 or F-88 can add it.
- TECH-1-3 | non-blocking | low | frontend | `LineChooser.tsx:4,47-48` filters `invoice`, but 1.26.0's `key` enum has no `invoice`, so the filter is dead code. Harmless. Remove it, or keep it to protect against a restored line.

## Verified
- Contract 1.26.0 check: /lines items now also carry `request_schema` and `content_type` (`application/json` or `multipart/form-data`), plus `submit_url` and `project_options_url`. The spec hand-built, per line, whether a line takes an upload (`takesUpload`), the field list, the project and source-picker choice, and the body. F-92's schema-driven engine can read all of these from `request_schema` and `content_type`. The line keys now include `received-bid`, which is not in the `/lines/projects` or `intake-sources` line enum, so F-88 must handle its project options differently. Project items also serve `source_options_url` and `workflow_intake_url`, which the picker ignores. None of this breaks F-86.
- `GET /lines/projects`: `q` maxLength 120 and `page` 1..10000 match `fetchProjects` (q trimmed and capped at 120, sent only when non-empty; page only when asked). `next_page` is an integer or null and is used as the cursor.
- `intake-sources`: `before`, `parent_id` and `field` are optional integers/strings and sent only when set. `items[].id` is an integer, `next_before` an integer or null, `case_revision` is read. This matches `fetchSources` and `SourcePicker`. Not rendered by the weekly form, as the spec says.
- POST /work weekly body from `buildBody`: `line`, `case_id`, `case_revision`, `idempotency_key`, `intake.inputs{template_id:null, content_id:null, start_at, end_at}`, `reference`, with no extra keys (additionalProperties false). `background` is omitted (optional). Status 200 is handled, and a 2xx without a valid `work_id` is treated as uncertain. The `X-CSRFToken` header comes from `csrfHeader`.
- Weakened tests: none found. The eight deleted v7 files and the edited `assistant`, `issue-detail` and `hr.spec` assertions follow build.md. They changed because the behaviour was removed (D-182/D-183, LC-Q3, LC-Q11), not because the behaviour still exists and was relaxed. The `next-config` allow-list gained three F-86 files and nothing was removed.
- `start_at` and `end_at` as `YYYY-MM-DD` is still unverified against Django (maxLength 64 only), as build.md AC18 says. AC18 (live run) and AC17 (fidelity) are not done and need the coordinator to confirm them.
- Not re-run: the full gate (passed on this head per checks.md). I read the diff only.
