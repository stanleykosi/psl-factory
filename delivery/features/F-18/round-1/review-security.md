VERDICT: PASS
COMMIT: 352893425c8d197b3de15ab04eac6c68d1d05782
REVIEWER: reviewer-security
AUTHORITY: security reviewer

## Summary
- This change touches only the frontend and the contract mock (45 files, no new packages, no backend). Both writes and the send go through the shared client, so they carry the CSRF header and return typed errors. Nothing retries automatically.
- The follow-up goes only when a person clicks Send. Loading the page, reloads, timers and effects never call E-RFP-FOLLOWUP, and a test advances the clock 10 minutes to prove it. A ref guard means a double click makes one request. The idempotency key is made once per (version, text) and reused for a repeat press. A draft in effect_uncertain shows no Send or Edit, and "Check again" only reloads. A 409 reloads the item and keeps the person's text.
- A won or lost outcome cannot be recorded again once it is recorded. Only pending and unknown offer "Record the outcome" again, and only while the backend still returns `results`. Every outcome needs proof, and team input needs proof plus the confirmation checkbox before Record turns on.
- What a person can do comes only from the backend's flags (`you_can_act`, `can_send`, `can_edit`, `results`, `record_as`, `rfp_outcome` present). Response text, the draft, `note`, `next[]` and the agent's checks are shown as plain text and grant nothing. No `dangerouslySetInnerHTML` was added. Links built from data use `/work/${encodeURIComponent(id)}`.
- A 403 or 404 on a read shows NoAccessState. The new route's tab title is fixed text and does not name the item. No secrets were added in code or fixtures, and all fixture emails use the `.example` domain.

## Findings
None.

## Verified
- Round 1: nothing to verify.

## Notes
- Non-blocking, for the backend (T-RESPONSE / D-RFP-OUTCOME). The mock returns the stored reply for a repeated `idempotency_key` before it checks anything else, even when the `body` or `version` differs (`frontend/mock/response.mjs` sendFollowup). The real endpoint should refuse a reused key whose payload differs (422 or 409), not replay it.
- Non-blocking, for the backend. The frontend keeps a key only for the last (version, text) pair, and only while the follow-up card stays mounted (`frontend/src/features/rfp/useFollowup.ts` keyFor). Two cases can produce a new key for a draft whose earlier send was uncertain. (a) After a network error, the reload still shows `drafted` with `can_send`, and the person edits the text, or edits it and changes it back. (b) The card unmounts, for example after "Record the outcome" is reopened. This matches the spec: the key changes when the text changes. Even so, protection against a second email depends on the server putting the draft into `sending` or `effect_uncertain` once a send has been attempted, not on the key alone. INV-RESEND should say so.
- Non-blocking. If a person opens Edit, clears the text and presses Send, the agent's original draft goes, because blank text is never sent as `body` (as specified). This is safe, since nothing blank goes out, but the person may be surprised. UX may want Send turned off while the edit box is blank.
- Not checked here, for the backend. Who may record an outcome or send a follow-up is enforced only by the mock's flags (persona `none`, `can_send`). The real permission and tenant checks belong to the unbuilt backend and must be reviewed when it is built.
