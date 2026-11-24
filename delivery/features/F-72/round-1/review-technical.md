VERDICT: PASS
COMMIT: 81a9bb9f021d125b3c0f55234434deb93977ec7e
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- D-188 sync-only re-check of 3b7df6cc (F-86, PR #103 merged into the branch). Earlier review passed head 7c649b84. The diff 7c649b84..81a9bb9f is 32 files, all under start-work, its tests, mock/start-live.mjs, mock/server.mjs, e2e and a few shared tests. No file under src/features/documents, the Documents tab, mock/documents.mjs or the document-review tests changed. The only shared hunk is the django_url allow-list in frontend/tests/next-config.test.ts, which now holds both sides' entries (F-86's LineChooser.tsx, start-live.mjs, start-work-live.test.tsx plus F-72's document-review entries). Nothing from F-86 changes what this lens covers on F-72's screens, so the findings below carry forward. I ran no tests.
- One POST per press, guarded by an in-flight ref. The body is exactly the contract's required set: `expected_revision`, `verdict`, `delegated:false` and `note`. It is typed from `live-schema.d.ts`.
- Error handling follows the spec. 409 shows the stale callout, keeps the note and re-reads. 422 on `note` stays on the field. Other 422s (`action_unavailable`) show the message and re-read. 403 refuses and re-reads. A network error or 5xx shows the uncertain notice with buttons off, and Try again only re-reads.
- "Approved" and "returned" appear only after a successful re-read: the toast fires from `onRecorded` after `refresh()` returns true. If the re-read fails, the page shows the unconfirmed notice.
- The Documents-tab link rule is strict. A row links only when `api_url` is exactly this case's `/document-reviews/{n}` path, and 19 refused forms are tested. Only decisions in `decisions[]` (approve, return) get controls, so reject is never drawn.
- Targeted run: 3 files, 71 tests pass (document-review, document-review-model, mock-live-document-review). The gate had already passed.

## Findings
- TECH-1-1 | non-blocking | low | frontend | `useDocument.refresh` returns false when a newer read supersedes it (`mine !== seq.current`), even though that read may succeed. `useReview` would then show "unconfirmed" after a recorded decision. Rare, because the page starts no overlapping reads. Return true or the newer result instead. src/features/documents/useDocument.ts:57
- TECH-1-2 | non-blocking | low | frontend | Any 409 on the POST is treated as `stale` and gets the "changed while you were reading" wording. The contract's 409 is a single generic response, so this matches the spec, but the wording would be wrong for a different 409 cause. src/features/documents/useReview.ts:46
- TECH-1-3 | non-blocking | low | integration | The live end-to-end check (build.md item 19) is HELD. The local database has no document version, and the live Documents tab is not served. The write, the 409/422 paths and whether any real row carries the `api_url` have only been checked against the mock, which is validated against the contract with Ajv. B-7 and B-11 stay open for the backend. Re-run against a seeded status-report version once one exists.

## Notes
- The contract is now API 1.26.0 and the preview requires `django_url`, `template_name`, `template_version` and `sample`. `isDocument` checks only the fields the page uses, so the extra fields do not break it. The page does not show them, which is correct.
- `delegated:false` is flagged in the code comment and the spec as the best reading of B-11. No invented rules found. The note is required for approve as well as return (B8 default). The note is length-checked client-side at 1 to 4000, which matches the contract.

## Verified
None.
