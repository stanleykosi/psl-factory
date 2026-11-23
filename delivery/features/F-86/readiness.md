DECISION: READY
RISK: medium
SURFACES: ui, api
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- This is the small F-86a slice of the first pass: the chooser, the pickers, upload, the unavailable-line state and one line (weekly report) end to end. It is one reviewable PR.
- Build-order dependency, not a blocker: F-86 builds in the lane C worktree only after F-85 (adapter and evidence picker) has merged.
- The weekly report starts through `POST /work` with `line:"pmo-weekly-report/v1"`. That is the contract's weekly report branch in the `POST /work` request schema (about line 12119 of `contracts/psl-factory.openapi.json`). `POST /projects/{case_id}/weekly-report-intake` is a different operation. It saves drafts with `action:"save_draft"` and also starts work with `action:"start"`, and it belongs to SCR-25, not to Start work.
- I did not check architecture approval, decision status or `design.py check` for SCR-04. `baseline.approval_evidence_refs` is empty in `feature.json`. The coordinator must confirm these before the spec is accepted.

## Scope
Outcome: Start work reads the live chooser, picks a project and a source record, uploads files to the case, starts the weekly report through `POST /work`, then opens the new work item. Task ID: FE-CONNECT-1, SCR-04 only.

In:
- `GET /lines`. It has no `group` and no `next` summary, so show neither.
- `GET /lines/projects?line=&q=&page=`, giving `case_id` and `case_revision`.
- `GET /projects/{case_id}/intake-sources`.
- Upload through F-85's evidence picker, which uses `POST /cases/{case_id}/files` and returns `upload_id`.
- Lines with `can_submit_via_api:false` are shown as unavailable, with a link to `django_url` (LC-Q3, A-25). No form is built for them.
- One line end to end, weekly report. The body is `{line:"pmo-weekly-report/v1", case_id, case_revision, idempotency_key, background?, intake:{inputs:{template_id, content_id, start_at, end_at}}, reference}`. Every field is required except `background`, and no extra keys are allowed. `template_id` and `content_id` may be null. `start_at` and `end_at` are strings of at most 64 characters.
- On success, take `work_id` and open `/work/[id]`. A 200 is the expected first-start answer (A-24).

Out:
- Every other line's form, which later lane C features cover.
- The Finance invoice start. `invoice` is not among the `POST /work` lines (A-26), so show nothing for it.
- The weekly report content: parts, cites, save draft, correct. That is SCR-25 and `weekly-report-intake`.
- Minutes, received bids and the DC-1..DC-5 lines.
- Any field not in the OpenAPI schema.
- Business rules.

Open items the spec must not guess:
- Backend question 8: there is no per-line field list. Use only the schema fields above, and take their labels from the SCR-04 board and the design. Where the board shows a field the schema lacks, record it as a gap.
- Backend question 1: file to evidence id. Upload gives `upload_id` only. Use whatever F-85 defines.
- A-24: the replay result for the same `idempotency_key` is unconfirmed. Send one key per submit and do not build replay handling beyond showing the server's error.
- Map 422 `fields[]` names to the typed body keys and flag any mismatch. Do not rename.

## Risk
Medium. The feature creates a work record and uploads files, and it shares F-85's adapter, which is a cross-layer contract. A wrong mapping fails with 422 or starts the wrong work. The effect is contained, easy to check for one line, and has no money, identity or migration. Surfaces are ui and api. The weekly report sends nothing outside the factory. PRODUCT-ACCEPTANCE is required because the client sees a changed start flow and its copy.
