VERDICT: PASS
COMMIT: 81a9bb9f021d125b3c0f55234434deb93977ec7e
REVIEWER: reviewer-ux
AUTHORITY: reviewer-ux (lighter panel, D-180)

## Summary
- D-188 sync-only re-check of 3b7df6cc (F-86, PR #103) merged into the branch, giving 81a9bb9f. Delta 7c649b84..81a9bb9f is 32 files, all Start work (src/features/start-work, mock/start-live.mjs, a start-live hook in mock/server.mjs gated on liveStart and on Start paths, start-work/rfp/assistant/hr tests and e2e) plus one next-config allow-list line (union of both sides). No file under src/features/documents, the Documents tab, mock/documents.mjs or the document-review tests changed; nothing from F-86 touches SCR-08 or its states, so my earlier walk and findings stand. No servers, no browser run in this re-check.
- Walked SCR-08 on the running mock (Next 4970, mock 4971) at 1440 and 390 as the PM persona: approve with note, return with note, blocked, older version (2900), returned, empty sections, stale, unavailable, forbidden, server error, no access (2999, `abc`).
- Behaviour matches the spec: controls follow `decisions[]`; blank note shows "Add a note to record your decision." and focuses the field; after a write the page re-reads and shows APPROVED / RETURNED TO PM with "No decision is open to you on this version."
- Phone Approve opens the "Approve with a note" sheet (button "Approve v2"), blank note is refused inside the sheet with focus on the field; no horizontal overflow at 390.
- Stale keeps the typed note and shows the spec callout; 403, 422 and 5xx wording match the spec; 403/404/invalid id all show the same "You can't open this document" with nothing about the document.
- Removed parts (section notes, Compare, per-check list, returned person/time, TEST TEMPLATE) are gone as accepted in D-182 (B7, B8, B12); not findings. Only the browser walk was run; no full test run (heavy lock was occupied; D-192 lifted it for walks).

## Findings
- UX-1-1 | non-blocking | low | frontend | The aside shows a panel headed "Audience" containing a row labelled "Audience" and a tag with the value, so the word appears twice (`src/features/documents/DocumentParts.tsx` AudiencePanel). Drop the inner label or the panel head.
- UX-1-2 | non-blocking | low | frontend | Not exercised in the walk: the success toast text and the disabled state of the buttons while the uncertain notice shows (only seen in the page text; covered by unit tests per build.md). A person should glance at both on the next visual pass.

## Verified
- None. Round 1; no earlier findings to verify.
