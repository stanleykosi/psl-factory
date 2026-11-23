DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-92 is now the generic `request_schema` form engine, the project, source and organisation pickers, per-action uploads, and a first batch of 6 PMO lines. That is one reviewable frontend PR.
- Build order: F-86 (built, not merged) must merge first. It owns the per-line registry `src/features/start-work/lines/index.ts` and the chooser, project picker and source picker that F-92 extends. This is a dependency, not a blocker.
- Invoice intake `pmo-finance/v1` is F-94, received bids are F-88, and later lines get their own features. The payments surface is dropped from F-92.
- Auth is not rated. The server decides who may start a line: `GET /lines` returns only the lines the viewer may start, and `POST /work` enforces it. The client adds no permission logic.
- Not run for this verdict: `design.py check`, and live `GET /lines` for `can_submit_via_api` and `project_options_url`. The spec writer confirms both first.

## Scope
Binding for the spec writer. Frontend only, against contract 1.24.0 (`/Users/Hunchoo/psl-factory/contracts/psl-factory.openapi.json`) and answers A-23 to A-26.

In scope:
- A generic form renderer driven by `request_schema` from `GET /lines`. It honours `content_type` (JSON or multipart) and `submit_url`. It maps the typed 422 `fields[]` onto the form's fields. It sends `POST /work` with an idempotency key and handles replay per A-24. It retries once after `csrf_failed`.
- The project picker (`GET /lines/projects`), the source picker (`GET /projects/{case_id}/intake-sources`, with `parent_id` and `before`) and an organisation picker. F-86 builds the first two as components. F-92 wires them to the schema. The organisation picker uses whatever options endpoint `request_schema` names, and nothing else.
- Per-action uploads through `POST /cases/{case_id}/files` (one file per upload, up to 5 MiB, multipart). The start body cites the returned `upload_id`. It reuses F-85's `EvidencePicker`, so there is no second upload control.
- Lines with `can_submit_via_api:false` keep F-86's "not available here" row and its link.
- Batch 1 of 6 PMO lines, simplest first, by the size of their `POST /work` body in 1.24.0:
  1. `pmo-issues/v1`: `intake.issue_id` only, picked from the source picker.
  2. `pmo-escalation/v1`
  3. `pmo-minutes/v1`: the minutes upload path in 1.24.0 is the spec writer's to confirm; do not assume it.
  4. `pmo-emergency/v1`
  5. `pmo-leadership-report/v1`: same body shape as the weekly report (`template_id`, `content_id`, `start_at`, `end_at`).
  6. `pmo-change/v1`: the largest body of the six; it drops to batch 2 if the spec writer finds more than a schema-driven form can carry.
- The spec writer reads each line's `request_schema` from the live `GET /lines` and names the exact fields. If a line is `can_submit_via_api:false` or has no `project_options_url`, it swaps out for the next simplest line (`engagement/v1`, `rfp-response/v1`) and says so.
- Labels and help text come from `request_schema` and the boards. Never invent fields, labels or rules.

Out of scope:
- `pmo-weekly-report/v1`, which stays with F-86.
- `pmo-finance/v1` (invoice, completion and preparation modes), which is F-94.
- The received-bid form (`POST /received-bids`), which is F-88.
- All `finance-*`, `delivery-*`, `planning`, `commercial` and other lines, in later batches.
- Any workspace screen after the start.

## Risk
Medium. The engine is a shared cross-layer contract (`request_schema`, content type, idempotency, uploads, 422 mapping) that every later line uses. A schema-driven form can silently drop or invent fields, so the 422 `fields[]` mapping and the idempotency replay need real tests. No money, identity or data migration is in this batch, because invoice moved to F-94. `pmo-emergency` and `pmo-change` are the most sensitive lines. The server holds their rules, and the client only passes values and shows the server's refusals.

Design: the SCR-04 boards are approved under the recorded exception in `design/review.json`, which covers the 13 Nov client approval. The generic form states (line chosen, needs fixing, upload, submitted, unavailable) must be confirmed against the boards before the build. Any state with no board goes back to the design engineer. It is not invented.
