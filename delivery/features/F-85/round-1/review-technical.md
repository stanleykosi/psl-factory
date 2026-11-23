VERDICT: PASS
COMMIT: 35189b4503a76ae516ba153f77434a9a562bdc0d
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead), lighter panel (D-180)

## Summary
- Adapter (`adapter.ts`) and `CommandDescriptor` match the spec shape exactly: null tokens stay null in `body()`, a keyless line has `idempotency.field === null` and no key in the body, and `commands()` only describes commands (nothing is sent).
- v7 W-id path is intact: `isLiveWorkId` (`/^\d+$/`) switches the layout and both pages, and any other id falls through to the old frame and panes. The mock routes numeric ids only.
- Null `revision` and `case_revision` pass through the live item, `LineContext` and the weekly-report tokens untouched. No `?? 0` or `|| 0` appears in the new code.
- The only `liveApi.POST` calls are the upload and the unused-by-design `fileToEvidence` proposal. The picker takes `caseId` as a prop only, and `UploadId` and `EvidenceId` are distinct brands.
- Live-only criteria 2, 19 and the live half of 22 were not checked, because of the known environment limits.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `makeCommand` body spreads `...inputs` last (`adapter.ts` body()), so a caller's inputs could override `action`, the revision tokens or the key. Lane A and B should not pass those names, or the spread should come first. No current caller does.
- TECH-1-2 | non-blocking | low | frontend | The history `evidence_id` is drawn as the text "Evidence N" with no link (`LiveWorkItemView.tsx`, History). The spec says "evidence link"; no evidence page route exists yet, so this is acceptable until one does.
- TECH-1-3 | non-blocking | low | frontend | In `ErrorState`, a 403 `csrf_failed` on a read shows "Refresh your session and try again." without calling `refreshSession()` itself. `call()` does refresh on csrf (`client.ts:64`) when `refreshOnCsrf` is set, so the behaviour is covered. Confirm the page's read uses that default.

## Verified
None.
