VERDICT: CHANGES
COMMIT: 3b782e399d96666f02e5efbaf52ff86a8f590e0a
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- Contract use is sound. Bodies match the 1.25.0 live types, ids go through one `idOf` helper, nothing is sent as 0 or NaN, and null reads as "Not recorded", "No owner" or "No deadline set". The summary round trip and the carried decisions with `change_evidence_id` are correct.
- Sending: the retrospective's two writes use `liveApi.POST` with `csrfHeader` and `call`, the shared client path, as the spec says for a non-work-line screen. There is no own fetch or sender, no revision or idempotency token inside any `inputs`, and no `makeCommand`. No adapter or `src/features/workspace` change.
- Proof rule: the notes file and every proof come from `options.proofs`, with nothing preselected. Save is off when the list is empty. No upload and no invented evidence id.
- One blocking gap: a 422 that the page cannot place on a field is invisible in the follow-up action form and shows a misleading line in the retrospective form.
- Shared edits (`mock/server.mjs`, `types.ts`) are small and within the lane.

## Findings
- TECH-1-1 | blocking | medium | frontend | A 422 with no mappable field is not shown. Spec: "422 shows `fields[].message` under the named field, else the `message` in a `Callout`." `failureOf` (`useRetrospective.ts:33-38`) puts any field name outside `FIELD_OF` into `fields.other`, and the message becomes "Check the highlighted fields." only when some field exists. Two results. (a) `ActionForm.tsx:62` draws the Callout only when `failure.kind !== 'invalid'`, and no control reads `fields.other` or `ownerId`, so a 422 with `fields: []` (a plain `message`) or with an `owner_id` field draws nothing, and the person sees Create re-enable with no explanation. (b) `RetroForm.tsx:166-177` shows "Check the highlighted fields." when the only field was `other`, `ownerId` or `dueAt`-like and nothing is highlighted. Expected: show the API `message`, or the unplaced field messages, in the Callout whenever no control carries them; add an Owner error too. Add a test: 422 with empty `fields` on action create, and a 422 naming an unmapped field on save.
- TECH-1-2 | non-blocking | low | frontend | `save` in `useRetrospective.ts:193-196`: if the POST succeeds and the re-read inside `confirmSaved` fails with a non-network error (for example 429), the catch maps it to "Try again shortly" and Save is enabled again. Nothing says the version was recorded, and a repeat press gets a 409 for the stale revision. Safe (no duplicate), but the message is wrong. Treat any failure after a 201 as unconfirmed, or keep the saved version number and say it was saved.
- TECH-1-3 | non-blocking | low | frontend | `createAction` on an unconfirmed failure (503 or network) does not re-read the actions list. It only tells the person to check, and the form stays open, so a retry hits the duplicate-reference 422. Re-read the detail on `unconfirmed` so the result is shown, as the retrospective save does.
- TECH-1-4 | non-blocking | low | frontend | A `signed_out` failure on either write (401 after the page loaded) draws nothing: the Callout is excluded for `signed_out` in `RetroForm.tsx:166` and for `invalid` only in `ActionForm`, and the Save press ends silently. Show the sign-in link.
- TECH-1-5 | non-blocking | low | frontend | The strip says "The checklist used version n (saved <date>)" using `detail.occurred_at`, which is when the meeting was held. This follows the spec wording; consider "held" so the date is not read as a save time.
- TECH-1-6 | non-blocking | low | frontend | The builder says the e2e was not re-run after the toast change (3b782e39). Run `e2e/retrospective.spec.ts` once before merge. The toast does not carry a "saved" claim before the re-read, since `savedNote` is set only after it. Criterion 21 (live Django) is still unchecked; acceptable for a read and save screen if QA covers it on 55433.

## Verified
Round 1: no earlier findings.
Checked and fine: one POST per press (`inFlight` ref plus the disabled button); stale 409 keeps the typed values and re-reads the revision; csrf failure is not retried; no `/meetings/{id}/actions` call; no `retrospective_id` or "latest" filter; empty deadline sends `due_at: null`; unknown timing reads "Timing unknown"; the checklist's two extra checks are not drawn; unconfirmed save keeps Save off until the re-read. I read the code and the build notes. I did not run the full gate, which passed per the brief.
