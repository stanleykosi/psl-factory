STATUS: READY
COMMIT: 6c0c9832ffdbeebe93ce33a39210168ca1df8361
BUILDER: builder
LANE: frontend

## Summary
- The Issues register on a project's Registers tab has a "Record an issue" button. It opens a drawer (shared Drawer, same look as Assign PM / Start work).
- Opening it reads GET /projects/{case_id}/issues once. The owner and the evidence are chosen from the served `owners[]` and `proofs[]` (nothing preselected, no ids typed). The form sends `case_revision` from that read.
- Fields: Reference (160), Title (240), Kind (100), Responsible owner, Next action (1000), Evidence, Note (4000), Severity (optional: Critical, High, Medium, Low, or not set = null). Limits are the contract's maxLength.
- One press is one POST, no retry. After a 201 the register is read again; "Recorded: ISS-... It is now Open, severity ..., with <owner>. Next action: ..." is shown only from that read, and the Registers list is reloaded so the new row appears.
- 403/409/422/400 show the server's words (422 field errors go under their fields; 409 re-reads the choices and keeps the entries). A dropped connection or 5xx locks the form with "We couldn't confirm that this happened. Check the page before trying again."; "Check the register" only reads and either shows it as recorded or says it is not there and unlocks.

## Changes
- `frontend/src/features/projects/recordIssue.ts`: contract limits, read check, form checks, POST body (`external_links: []`).
- `frontend/src/features/projects/useRecordIssue.ts`: the read, the one write, re-read and error handling.
- `frontend/src/features/projects/RecordIssueDrawer.tsx`: the drawer.
- `frontend/src/features/projects/RegistersTab.tsx` (+ `project-tabs.css`): the button on the Issues register, opens the drawer, focus returns to the button on close, list reload through the tab's `retry`.
- `frontend/mock/issue-record.mjs` (new), `mock/server.mjs`, `mock/project-tabs.mjs`: GET and POST `/projects/{id}/issues` in the live shape (both UUID and P-nnnn forms), recorded issues added to the top of the Registers issues section. Cookie `psl_mock_record`: ok, forbidden, conflict, invalid, uncertain, uncertain-saved, reread-fail, empty-proofs.
- `frontend/tests/next-config.test.ts`: `issue-record.mjs` added to the allow-list (one line).
- Tests: `tests/record-issue.test.tsx` (11), `tests/mock-issue-record.test.ts` (2), `e2e/record-issue.spec.ts` (1440 and 390).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Action on the Issues register: Playwright, both viewports.
2. [x] Owner and evidence from served lists, none preselected: vitest lists the served owners; body ids are the chosen ones.
3. [x] Contract words and limits only: `LIMITS` and the four severities from the contract; `external_links` sent empty.
4. [x] "Recorded" only from the re-read; new issue in the list: vitest order GET, POST, GET and reread-fail case; Playwright sees ISS-0501 in the list.
5. [x] One request per press, no retry; 409/422/403 in server words; dropped connection locks: vitest.

## Validation
- `tsc --noEmit` clean; `eslint . --max-warnings 0` clean; `node --check` on server, issue-record, project-tabs mocks ok.
- Full vitest: 4556 passed, 1 failed (`rfp-submission.test.tsx` phone AC 20, a load flake: 49/49 pass alone). Targeted files (next-config, demo-mock, mock-contract, project-tabs, project-sections and their models and mocks, record-issue, mock-issue-record) 420 of 420 on first run after the allow-list fix.
- Playwright (ports 4950/4951, config starts and stops its own servers): record-issue 1440 and 390 pass; project-tabs 37 pass (39 total, 0 failed), including axe WCAG 2.2 AA with the drawer open and after recording.
- Design-fidelity tool not run: no board is drawn for this drawer; it reuses the Drawer look.

## Held and why
- Action visibility: nothing in the GET or in the project `actions` says who may record, so the button is shown on the Issues register to everyone who sees it. A person the server refuses sees the server's 403 words in the drawer (no form).
- `external_links` (risk, incident, change links): required by the contract, sent as `[]`; no form for them (not asked).
- GET issues paging (`before`/`next_before`) not used; only the first page is read to find the new issue (newest first).
- F-111B parts (owner updates, replies, assignment, milestone blocks) not built. F-111B's spec does not describe the capture form, so nothing was reused from it.
- Evidence labels: the read serves only `{id, version, kind}`, so options read "kind · version N · no. ID" (kinds repeat, e.g. three policy decisions).
- Possible backend gap: Tunde's Registers tab for Lagoon and Kora serves no `emergencies` section while Kemi's does (demo data, read only).

## Live read (psl_demo5, GET only, Django test client)
- Lagoon (496b3dbd...) and Kora (fb302c5b...) answer 200 for both Tunde Bello and Kemi Adebayo, and each gets the same choices per project.
- Owners (both people, both projects): "PSL demo setup" (id 2) and "Tunde Bello" (id 3). Kemi is not offered as an owner.
- Evidence: Lagoon 38 proofs (e.g. 158 meeting_notes v1, 155 incident v1, 154 completion v2, 153/152/151 policy_decision v6/v5/v4); Kora 25 proofs (e.g. 72 costing v2, 60/59 approval_request, 58 requirements v2, 54/53 approval_contract_review). The cap is 40.
- Lagoon case_revision 138 with one issue (ISS-0233, Open, High, owner 3); Kora revision 89, no issues. The real POST was not sent.
