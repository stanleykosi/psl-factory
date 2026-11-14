VERDICT: PASS
COMMIT: 06b4c0e93bbc3083cea431c2f022c1e267486f24
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- Who may change a rule comes only from the API. `isEditable` needs `can_change === true`, a `role_set` editor with options and no `link`. `/me` roles are never read, and the mock refuses a PUT on any row without `can_change` (403), whatever the persona.
- Every write (rule save and proof upload) goes through `call(api.PUT|POST)`, so the shared middleware adds `X-CSRFToken`. Unit and e2e tests check the header, and the mock rejects a missing or foreign token with `csrf_failed`.
- Outcomes are safe. 401 shows sign-in. 403/404 on a read shows `NotOpenState` with no rule names. 409 re-reads and clears the edits. 422 keeps the edits. 5xx or a network error re-reads once, never resends, and locks Save when the re-read fails too. `expected_revision` stops a duplicate version.
- All API text is shown as plain React text, with no raw HTML anywhere. Rule and area links only go to fixed, known routes, so an unknown `link` slug cannot become a link to some other address. No new packages, no real secrets (only the mock `mock-csrf-admin` token).
- Three low, non-blocking points: Save stays enabled while a proof upload is still running, and two things for the backend proposal about `proof_case` and `evidence_id`.

## Findings
- SEC-1-1 | non-blocking | low | frontend | Save stays enabled while a proof upload is still in flight. Expected: Save waits (or is disabled) while Proof shows "Uploading…", so a rule is never saved without the proof the person is attaching. Actual: `onSave` runs during an upload. The body has no `evidence_id`, and the success path bumps `generation`, so the upload's result is thrown away. The file still lands on the setup case, though, with no link to any rule version, and the person sees "Saved as version N." A second file chosen during an upload also isn't guarded (both use the same `case_revision`; one gets 409). Path: frontend/src/features/setup/SetRulePanel.tsx:245 (button `disabled={busy \|\| locked}` ignores `current.proof.status === 'uploading'`), frontend/src/features/setup/SetRulePanel.tsx:77-96.
- SEC-1-2 | non-blocking | low | backend | Backend proposal: `evidence_id` on E-SETUP-RULE-SAVE must be tied to the rule. Expected (T-SETUP): the backend accepts `evidence_id` only if that evidence belongs to this rule's `proof_case`, was uploaded by the same person and hasn't been used by another version. Otherwise it returns 422. Actual: the mock never checks `evidence_id` (frontend/mock/setup.mjs:131-158), and the A-3 proposal in build.md doesn't state this rule. Without it, any evidence id the person can name could be filed as proof for a rule change (INV-AUDIT). Record it with the A-3 proposal.
- SEC-1-3 | non-blocking | low | backend | Backend proposal: send `proof_case` only on rows the person may change, and authorise uploads to that case by the rule's change right. Expected: `proof_case` (a case id and revision) is omitted when `can_change` is false. E-EVIDENCE-UPLOAD to the setup case is allowed only for someone who may change the matching rule. Actual: the readonly mock scenario still serves `proof_case` on rows with `can_change:false` (frontend/mock/setup.mjs:69-70; frontend/mock/fixtures/setup/rules.desktop.json). The frontend never uses it there, because the panel only shows editable rows, but the proposal should say this.

## Verified
None (round 1).

## Notes
- Things checked that are fine:
  - Path parameters (`component`, `case_id`) are URL-encoded by openapi-fetch.
  - `ApiError.message` only ever carries a `{code,message}` body or a fixed text. A 5xx in the panel shows fixed text, and the read error card shows only `error.code` as a support reference.
  - The `restricted` flag is typed but never shown. The frontend never reads the `value` object, and a test proves a stray `value` with `set:false` is not rendered. Hiding a restricted value remains the backend's job (INV-RESTRICTED).
  - The paging cursor is a value the server hands back, not something the person types.
- `restricted` (pre-existing contract gap, not introduced here): v7 doesn't say what a restricted row must leave out. When F-11E (payroll visibility) shows restricted rows, it should decide how they render (for example "Restricted" rather than `display_value`/"Set") and test it.
- Process note for the coordinator, not a code issue: the builder reports that a scratchpad script-name clash sent a `POST /__mock/reset` to F-12's mock on 4202, opened pages on F-12's 4201 server, and wrote (then deleted) two folders in the F-12 worktree. No secrets or tracked files were involved. Giving each builder its own scratchpad subfolder would prevent this.
- The `MOCK_SETUP_SCENARIO` environment default is mock-only and accepts only the listed scenario names.
