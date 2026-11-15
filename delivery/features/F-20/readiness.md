DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- FE-SETUP-TEMPLATES (F-11D) is one outcome: the Templates tab on Setup lists the document templates and uploads a new version of one. It covers two boards, SCR-34-desktop and SCR-34-mobile, so it fits one PR.
- Both dependencies are merged: FE-M3-SETUP (F-11, the Setup frame and `ReservedTab` placeholder at `frontend/src/app/setup/templates/page.tsx`) and FE-CONTRACT-V7 (F-13). SCR-34 is in the client-approved screen list (design/review.json:69).
- D-TEMPLATES-VIEW is still `proposed` at revision 1 and is owned by the backend developer. It is the only open decision. It is not a blocker. Decision (g) in architecture/sources/decisions-2026-11-14-v2.md lets the frontend build against a proposal on the contract mock only. F-11 passed on the same basis, using the early-start exception, whose limits are mock only, nothing released and PSL approval still needed. Those limits carry over.
- `src/api/schema.d.ts` already types E-TEMPLATES and E-TEMPLATE-VERSION with the proposed fields, so no contract overlay is needed. Nothing here needs a client answer.
- Per the 13 Nov product decision, every template is a test template until PSL supplies its own. The frontend shows what the backend returns in `test_template` and never sets it.

## Scope
**Binding for the spec writer.**

**Outcome (one, observable):** A person opens Setup, then Templates. They see each document template by line, with its name, current version, kind, who last changed it and when, how many versions it has, and a badge saying whether it is a test template or PSL's own. A person whose `can_upload` is true can upload a new version (file, optional note). They see the new version as current, and the badge as the backend returns it. This works at 390px and 1440px on the contract mock.

**Boards in scope (every element, design-fidelity gate), 2 of the 8-board cap:**
- design/canvas/project/SCR-34-desktop.dc.html
- design/canvas/project/SCR-34-mobile.dc.html

**In:**
1. Route `/setup/templates`. Replace the `ReservedTab` render in `frontend/src/app/setup/templates/page.tsx` with the real view inside the existing `SetupFrame`. The Templates tab in the frame becomes live.
2. List from E-TEMPLATES (GET `/api/v1/setup/templates`). Fields: `line`, `name`, `version`, `test_template`, and optionally `template_id`, `kind`, `updated_at`, `updated_by`, `versions`, `revision`, `can_upload`. Show "as of" from `as_of`. Rows appear in the order returned. Page with `cursor` and "Show more" only when `next_cursor` is present. Show Africa/Lagos dates as the F-11 `format.ts` already does.
3. Test-template badge. It comes from `test_template` and uses the board's copy ("test template. When PSL supplies its real template, upload it here; documents already sent ke..."). Read the full copy from the board. Do not infer "PSL's own" from a missing field.
4. Upload action ("Upload PSL's version" as drawn), shown only for rows with `can_upload === true`. It sends E-TEMPLATE-VERSION (POST `/api/v1/setup/templates/{template_id}/versions`) with `expected_revision` exactly as read, `filename`, `content_base64`, and an optional `note` of up to 2000 characters. It carries the CSRF header, like the F-11 save.
   - On 200, reload the list and show the new version and `test_template` as returned.
   - On 409, show the API message, reload, and clear the person's selection. Never re-apply it to a newer version.
   - On 422, mark the named fields and put the message in a `role="alert"` callout.
   - 401 goes to SignedOutState. 403 and 404 show the no-access view.
   - Block double submit while a request is in flight. Do not retry after a network error without reloading first, because the upload may have landed.
5. A row without `template_id` or without `can_upload` is read-only. Show no upload control and no placeholder.
6. Mock: add the handlers in a new `frontend/mock/templates.mjs`, with fixtures in `frontend/mock/fixtures/templates/`. Include one scenario per board, plus a read-only persona, an empty list, a 409 and a 422. The upload bumps `versions` and `revision` in memory, and `/__mock/reset` clears it. Append the E-TEMPLATES and E-TEMPLATE-VERSION entries to `M1_OPERATIONS` and the dispatch lines in `server.mjs`, additively, and list them in build.md. No fixture value is presented as PSL's own template.
7. Tests: component tests for each state in item 4 and for the `can_upload` and `test_template` gating, and the request body including revision 0. Playwright, axe and the fidelity check for both boards at 390px and 1440px.
8. If the generated types and the boards disagree, the types in `src/api/schema.d.ts` win. List any mismatch in build.md for the backend developer, because D-TEMPLATES-VIEW is theirs to confirm.

**Out:**
- Template download, preview, delete, or rollback to an older version. None are drawn and no endpoint exists. The `versions` count is shown as a number only unless the board draws a history.
- Any change to `architecture/**`, `src/api/**`, `openapi.json` or `src/shell/**`.
- Other Setup tabs (F-11B, C, E, F). New npm dependencies.
- Document generation that uses a template (SCR-08 and the invoice preview). Real PSL templates and real file storage (FE-CONNECT).
- Virus scanning or file-type policy. The backend owns it. The UI shows the 422 it returns.

**Ownership (disjoint from the other lanes):**
- Owns: `frontend/src/app/setup/templates/**`, new files `frontend/src/features/setup/Templates*.tsx` and `useTemplates*.ts`, `frontend/mock/templates.mjs`, `frontend/mock/fixtures/templates/**`, `frontend/tests/setup-templates*.test.tsx`, `frontend/e2e/setup-templates*.spec.ts`.
- Shared, additive only: `SetupFrame.tsx` and `ReservedTab.tsx` (only to let Templates stop being reserved), `M1_OPERATIONS`, the `server.mjs` dispatch lines. List each in build.md.

**Task IDs:** FE-SETUP-TEMPLATES (R-SETUP). **Endpoints:** E-TEMPLATES (GET), E-TEMPLATE-VERSION (POST). **Acceptance:** A-TEMPLATE-VERSION and A-ACCESSIBILITY.

## Risk
Medium. The feature adds one write, a CSRF file upload that supplies the documents later sent to clients, and it depends on a still-proposed backend contract (D-TEMPLATES-VIEW r1 in architecture/model.json:1435). There is no money, identity, migration or authority change, and the 409 and `expected_revision` pattern from F-11 contains the concurrency risk. The `test_template` flag is a business fact the client cares about. The UI must not set it or imply that a test template is PSL's own. Surfaces are `ui`, `api`, `contract-change` (the proposed fields, which gate FE-CONNECT) and `product-decision` (the test-template wording). Product acceptance is required because the flow and copy are new and the client must see them.

## Notes
- I could not run `design.py check` (I have no shell). The coordinator should confirm it passes for canvas 1794581312-b166 before the spec is written.
- The READY decision rests on the recorded early-start exception and decision (g) with their limits: mock only, no release, and D-TEMPLATES-VIEW must be approved before FE-CONNECT. If the coordinator reads that exception more narrowly than F-11 did, this becomes NOT-READY on D-TEMPLATES-VIEW.
- No earlier readiness file exists for F-20.
