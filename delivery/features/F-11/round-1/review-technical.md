VERDICT: PASS
COMMIT: 06b4c0e93bbc3083cea431c2f022c1e267486f24
REVIEWER: reviewer-technical
AUTHORITY: technical review (lead)

## Summary
- The request shapes match the spec and v7. GET sends `area`/`cursor`. PUT sends `expected_revision` exactly as read (0 included), `value.roles` filtered to `editor.options` in option order, `starts`, a trimmed `reason` only when non-empty, `evidence_id` only after an upload, and CSRF through the client. POST evidence sends the four v4 fields. The overlay is checked equal to v7 apart from `proof_case`.
- Authority rules hold. Editing is gated per row by `isEditable` (`can_change`, `role_set`, options, no `link`). `/me` roles are never read. Ticks start only from `editor.selected`. Not set comes only from `set:false`, and counts come only from the count fields. Phones get no editor.
- Save outcomes follow the spec. A synchronous ref guard allows one write. 409 re-reads and clears the edits. 422 keeps the edits and marks fields. 403/404 re-read. An uncertain result re-reads once, never resends, and locks Save if the re-read fails. Focus moves to the callout.
- The mock follows the specified check order. Overrides are keyed per persona, scenario and component. The case-revision counter is shared with the evidence mock and served back in `proof_case`. Shared-file edits are additive. The three root fixtures are a disclosed, needed side effect of the loader.
- Only non-blocking edge cases were found: paging plus save, overlapping uploads, a stray date, an ungrouped label fallback.

## Findings
- TECH-1-1 | non-blocking | low | frontend | After any write, `refresh` re-reads only the first page (`useSetupRules.ts:40-44`). If the person loads a second page with Show more and saves an editable row from it, the reloaded page no longer holds that row. On 200 the panel says "Saved as version N." but `row` falls back to `rows[0]` (`SetRulePanel.tsx:41`), so a different rule is now selected. On an uncertain result `fresh` is undefined, so the panel shows "This rule changed. Check the version shown…" (`SetRulePanel.tsx:152-158`) even though nothing is known. No unsafe write follows, because the next save carries the read revision and the backend answers 409. Expected: keep the selected row in view after the re-read, for example by re-reading up to the loaded depth or treating "row not found" as "couldn't check". Or record that editable rows always arrive on the first page.
- TECH-1-2 | non-blocking | low | frontend | Two overlapping uploads in one edit can leave the wrong file showing. The file input stays enabled while an upload is in flight (`ProofField.tsx:37-44`). `pickProof` reads `current.caseRevision` from the render closure (`SetRulePanel.tsx:88`), so both uploads send the same `case_revision`. Whichever answer arrives last wins: either a 409 "The record changed" that wipes a good upload, or the earlier file's `evidence_id`. Expected: ignore or disable a new choice while `proof.status === 'uploading'`, or apply only the latest pick's result, for example with a per-pick token like `generation`.
- TECH-1-3 | non-blocking | low | frontend | `versionText` calls `Intl.DateTimeFormat#formatToParts` on `new Date(row.effective_from)` (`format.ts:22`). An unparsable `effective_from` throws a RangeError while rendering and takes down the whole Setup view. The contract says `format: date-time`, but the field is a proposal and the screen should tolerate bad data. Expected: fall back to "v{revision}" when the date is invalid.
- TECH-1-4 | non-blocking | low | frontend | A Finance row with `group` but no `group_label` shows the raw `group` key as the panel heading and button label (`FinanceRulesView.tsx:28`). That puts a technical identifier on screen, contrary to the AGENTS.md guidance. Expected: put such rows under "Other Finance rules" or use a neutral heading.

## Verified
None (round 1).

## Notes
- AC 25 (phone fidelity: visual scores 66 / 78.9 / 83.7 against a bar of 90) is open, per build.md. It depends on the D-08 shell back-link slot. That falls under the UI review and the design engineer's exception decision, not this lens.
- `setup.mjs`/`evidence.mjs` and `server.mjs` import each other in a cycle. It is safe today because every cross-module binding is used lazily inside functions. Keep it that way, or move `SCENARIO_BODIES`/`OPENAPI_PATH` into a small shared module when a proof lane takes over `evidence.mjs`.
- If the person clears the Starts date, the panel sends `starts: ""`, which the overlay rejects (`minLength 1`). The backend's 422 then marks Starts, which is acceptable. Omitting the key would also be valid.
- Process: build.md records that the builder's fidelity runs reset F-12's mock and wrote into the F-12 worktree. They were cleaned up. This feature's code is not affected.
