VERDICT: PASS
REVIEWER: reviewer-technical
COMMIT: 8d72b263470b8c40dfd1e6223d8ce5c486712092

## Verified
- TECH-1-1 | verified | `isLinkUrl` (documentModel.ts) gates the Download link in NoText: http(s) or a relative path pass; javascript:, data:, vbscript:, file:, ftp:, `//host`, `/\host`, backslash and empty values do not. Model test covers these cases.
- TECH-1-2 | verified | After a return, ReviewHost sets `reread` once the refresh settles. If the document still isn't `returned`, ReviewNotice shows a warning ("We couldn't confirm the return was recorded…") with Try again, instead of "Recording the return…" forever.
- TECH-1-3 | verified | The dead register view is gone from the DocumentsTab call. `VIEW = { register: 'issues' }` stays only because useProjectTab needs a view, and a comment now says so.
- Fixture move | verified | P-0102.documents.json became P-0101.documents.json (6 rows). All 176 tests pass in a targeted run of document-review*, mock-project-tabs, project-tabs and projects-journey (6 files). projects-journey already expects "Documents 6". The e2e spec URLs now use P-0101. The other P-0102 hits (money, start-work and so on) are not document fixtures.

## Findings
- TECH-2-1 | minor, non-blocking | `isLinkUrl` treats `java\tscript:x` (a tab or newline inside the scheme) as relative, because the scheme regex fails on the tab. Browsers strip tabs and newlines before parsing, so this is a gap in the check. React 19.3.1 also sanitizes javascript: hrefs, so it is not exploitable today. Suggest stripping `/[\u0000- ]/g` before the scheme test and rendering the stripped value.

## Update for head 8d72b263 (diff 48752f43..8d72b263)
- The merge only brings F-28 (minutes end states): workspace frame files (Links.tsx project_tab link, Sections.tsx, labels.ts RECORD_ID export, proposals.ts, workspace.css stacked-table rules), mock/workspace.mjs (audience-specific `.next` sidecar), new W-2309 to W-2314 fixtures, F-28 tests, and additive notes in delivery/BACKEND-HANDOFF.md (+11 lines).
- No file F-29 changed was touched: documents feature, DocumentsTab, project-tabs mock, documents.mjs, server.mjs (E-DOCUMENT handling) and F-29 tests are identical to the reviewed head. mock-contract.test.ts was not changed by F-29.
- Coordinator checks on this head: delivery/checks.sh exit 0 (2226 tests), e2e document-review, minutes-end, minutes and project-tabs 93 of 93 passed.
- Verdict unchanged.
