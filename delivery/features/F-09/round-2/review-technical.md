VERDICT: PASS
COMMIT: 14d6953dd4a39c4ceed7f77dba5a77fb2ecf65cb
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- TECH-1-1 is fixed. `settle` now calls `proof.sync(item.case_revision)` every time it keeps the form (after a stale, 403 or uncertain-open reload). So the next press sends the reloaded revision, and already-uploaded evidence ids stay attached. The new test fails on the old code: the upload returns 5, the reload gives 7, and the old hook would have sent 5 again.
- TECH-1-2 and TECH-1-3 are fixed. The reopened-task heading (D-38) is an inference, and build.md labels it as one. It is right for the forward flow in every fixture. It can name the wrong station after rework or a further move. That is a non-blocking finding for the backend, below.
- The merge c08f47d is clean. Its only frontend changes are PR #19's shell files (`AppShell.tsx`, `PhoneBar.tsx`, `shell.css`, `shell.test.tsx`), and at head they match e09827a byte for byte. No feature file was touched by the merge.
- The other round-2 changes are small and stay in the lane: the hint/alert `touched` state, the phone reconcile ask-first press, the bar `note` and the 36px success h1. No existing test was weakened. The two changed assertions now check the new bar-note location and the pristine hint, which is stronger than before.

## Findings
- TECH-2-1 | non-blocking | low | backend | `recordedStation` (`frontend/src/features/response/useResponse.ts:82-86`) treats the done station just before the current one as the station where the response was recorded. This holds when the item moves forward by one station. It does not hold when (a) a "changes requested" or "rejected" answer sends the item back for rework: then there is either no done station before the current one, so the heading falls back to the current station (for example "Prepare UAT pack"), or there is an unrelated one; or (b) the item has moved past the next station before someone reopens the task: then the heading names the later station. In both cases the heading is plausible but wrong. Round 1 had the same weakness, since it always used the current station, so this is no regression. The fix is the `recorded.station` (or similar) field that D-38 already says to raise. Until then, the inferred heading should not be taken as a fact about where the response was recorded.

## Verified
- TECH-1-1 | verified | `useEvidenceUpload.ts:154-157` adds a stable `sync`. `useResponse.ts:146` calls it in `settle` before `setView({kind:'form'})`, and the done path needs no sync. The `revision` ref now follows the reloaded item, and `caseRevision()` falls back to the prop when the reload has no `case_revision`. Upload-409 and retry still reload on their own (`:91`, `:110`). New test `response.test.tsx:588-601`: item revision 4, the upload returns 5, the first POST carries 5 and gets 409, the reload gives 7, and the second POST carries `case_revision: 7` with `EV-C-1601-1`. On 4efaee8, `revision.current` (5) would have overridden 7, so the test fails there, as build.md says.
- TECH-1-2 | verified | `WorkItemOverview.tsx:1-3` now names ResponseEntryLink and ReconcilePanel's E-WORK-ACTION as the only write.
- TECH-1-3 | verified | `load` sets `responderId` only when the task names exactly one responder, and sets `station` from `recordedStation`. `SuccessView` prefers `station`. Tests cover W-1601 reopened ("REL-0077 · LAGOON HEALTH", h1 "Client UAT response"), W-1605 (two responders, no organisation) and W-1602 ("SOW signature", "SOW-0207 · TAMARIND LOANS"). On the inference itself, see TECH-2-1.

## Notes
- The phone reconcile ask-first button (`ReconcilePanel.tsx:80,192-197`) only switches the handler when `outcome === null && !locked`, so `submit`'s `writing` lock and `ready` guard are unchanged. The test shows that nothing is sent before a choice and exactly one action is sent after it.
- `.resp-title--done` (36px) comes before the phone media rule `.resp-title { font-size: 24px }` (`response.css:120,127`). Both have the same specificity, so the phone keeps 24px as build.md states.
- `touched` stays true after a 409 clears a choice. That is the right result: the person has already interacted, so the missing line should be an alert.
