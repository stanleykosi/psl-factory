VERDICT: PASS
REVIEWER: reviewer-security
COMMIT: 438c350fe7fe79233604f2293b6812d10df6c1ee
AUTHORITY: delivery security review

## Summary
- No blocking security problems in 29fff6e5..438c350f. The upload is chained into the start correctly, and the browser applies no limits of its own.
- Evidence ids can't be swapped between cases. The front end keys each uploader by case and clears confirmed ids when the project changes. The mock accepts only ids it issued on the same persona and case, with the field's evidence_kind.
- The CSRF header is on both writes, through the shared client middleware. There is one idempotency key per drawer, and uploads never change it. A double press, or "Check again" after an uncertain start, resends the stored body under the same key.
- File names and backend messages render as React text. No new `href` or HTML sink was added. 403 and 404 read the same, and the mock's 404 body names no case or file.
- The `server.mjs` branch uses the same scenario-then-CSRF order as the M1 path. The `cookies` pass-through only reads the mock-only `psl_mock_start_work`, which allows two named values once per reset, on a mock bound to 127.0.0.1.

## Findings
None.

## Notes
- Non-blocking, mock routing (owner: frontend). `ownsUpload` (`frontend/mock/start-work.mjs`, `ownsUpload`) routes on `kind` only. Spec section E-EVIDENCE-UPLOAD also asks it to check that the `case_id` is one the line can start on. Today no F-09 work-item fixture uses `meeting_notes`, `client_request`, `schedule_source` or `ledger_source`, so nothing is misrouted. The effect is to narrow access, not widen it: a colliding upload would get a 404 from start-work. It is still worth adding the case check so a later F-09 fixture isn't misrouted without notice.
- What was checked:
  - **Limits.** The browser sets no `accept` attribute and runs no size or type check. Spec AC 14 runs this grep over the diff; the diff adds no such pattern.
  - **Plain text.** `ProofField` renders `{file.name}` as text. The tests at `frontend/tests/start-work-proof.test.tsx:420` and `:608` cover the `<b>` message and the `<img onerror>` file name.
  - **Empty evidence_id.** The `evidence_id` guard in `useEvidenceUpload.ts` marks a 200 without an id as failed, so no empty id is sent.
  - **Start gating.** While a file is uploading or failed, Start is off (`proofHeld`). This is bypassed only for the stored uncertain body.
  - **Project lock.** The Project control is locked while an upload runs.
  - **Finance lines.** They come only from `lines.finance_lead.json`. Start-work reads neither `/me` nor roles. `me.finance_lead.json` only mirrors E-LINES.
- Pre-existing, not introduced here: the mock answers `X-Mock-Scenario` before its CSRF check, on the M1 path and now on this branch too. This is test tooling only.
