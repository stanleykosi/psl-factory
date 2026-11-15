VERDICT: CHANGES
COMMIT: 352893425c8d197b3de15ab04eac6c68d1d05782
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- The code matches the contract: request bodies, error handling and the person-only follow-up send are correct, and the change stays in lane. `server.mjs`, the shell, the API and `package.json` are untouched. Only the `RESPONSE_OPERATIONS` assertion changed. The builder's deviations (T-2101/T-2102, the sidecar location) hold up.
- The follow-up send has exactly one caller, a click handler (`useFollowup.send`). It has a ref guard, a key kept per (version, text), no resend after a network error or a 409, and no Send on `effect_uncertain`.
- Outcome and team-input writes follow the spec's order: 409 reloads and keeps entries, 403 reloads and removes the form, network/5xx reloads once without resending. `amountValue` never sends a missing amount as zero.
- One blocking gap: AC1/AC2 (visual >= 90 on all 18 boards) is not met. 14 boards are under 90 (builder's own checklist leaves both unchecked). One real defect: extra proof files on the outcome form are uploaded but not sent.
- The 8 non-blocking points are below. I read the code and did not re-run anything; checks.md shows the gate passed.

## Findings
- TECH-1-1 | blocking | high | frontend | Spec AC1 and AC2 require visual >= 90 on all 18 boards. Only 4 reach it (desktop team-input, rfp-outcome, -lost, -pending). Desktop rfp-won 73.5 and rfp-pending 74.6, and phone rfp-won 74.4, rfp-lost 78.5 and rfp-pending 77.3, are far below. `round-1/build.md` Fidelity table and `round-1/fidelity/scores.txt`. Most of the gap comes from exceptions D-60 approved (omitted copy, the 40px title), but the spec does not accept "under 90 with a cause" as a pass. The fix is more layout work. If the gap is a design call, the design engineer must change the criterion (or approve more exceptions) before this passes. The UI review judges the layout causes.
- TECH-1-2 | non-blocking | medium | frontend | Several proof files can be attached on the outcome form, but the write sends only `ids[0]`. E-RFP-OUTCOME has no `evidence_ids`, so the later files are uploaded and silently dropped, and the person believes both are recorded. `frontend/src/features/rfp/useOutcome.ts` (`outcomeBody(..., ids[0], ...)`) with `frontend/src/features/response/ProofField.tsx:96-98`, which lets a person keep adding files. Expected: allow one file on the outcome form (hide the picker once one is uploaded), or tell the person only the first counts. Ask the backend developer whether the outcome should take several (add to the contract questions).
- TECH-1-3 | non-blocking | low | frontend | `amountValue` accepts "0" and "0.00" and sends `amount: "0.00"` as a real value. Typed zero is explicit, but the product rule is that unknown is not zero. Consider refusing zero (or showing a "did you mean not known?" hint). `frontend/src/features/rfp/labels.ts` (`amountValue`).
- TECH-1-4 | non-blocking | low | frontend | Follow-up 409: if the reload also fails (5xx), no notice is set and the old draft stays with Send on. A repeat press would just 409 again, so nothing unsafe happens, but the person is not told. `frontend/src/features/rfp/useFollowup.ts`, stale branch (`if (!(next instanceof ApiError)) setNotice(...)`). Also, after the reload "Current draft (vN)" shows only while the edit box is open and `can_edit` is true. If the new draft is not editable, the person's text disappears.
- TECH-1-5 | non-blocking | low | frontend | A reply of `sending` followed by a failed reload leaves "Sending…" with no way to refresh. There is no "Check again" for `sending`, only for `effect_uncertain`. `frontend/src/features/rfp/FollowupCard.tsx` and `useFollowup.ts` (`replied`).
- TECH-1-6 | non-blocking | low | frontend | Outcome 409 or 403 whose reload fails with a 5xx replaces the page with the error card (`setPage({kind:'error'})`). Entries stay in hook state, but the error card shows no form until Try again (a reload, which keeps entries). Spec says keep entries; this holds, but the form disappears meanwhile. `useOutcome.ts`, `record` (`if (refusal) return setPage({ kind: 'error', error: next })`).
- TECH-1-7 | non-blocking | low | integration | The spec fixes `T-2001`/`T-2002`; the build uses `T-2101`/`T-2102` because `mock/fixtures/E-WORK-ITEM.json` and `work/W-1002.json` already hold `T-2001`, and `server.mjs` finds the default first. I confirmed the collision (`grep` finds `T-2001` in those fixtures). It is the right call, and it is already listed in build.md. The fidelity URL differs from the spec's command (`task=T-2101`). Update the spec or the coordinator's board table to match.
- TECH-1-8 | non-blocking | low | frontend | `RecordedView` and `RfpFrame` are drawn from the returned fields, and nothing hard-codes option text (the `Engineering` grep finds only a pre-existing comment in `features/exceptions/types.ts`). No finding. One note: `RfpFrame` leads the eyebrow with `item.line`, which the spec does not list. build.md names it, and the board draws it.

## Verified
None (round 1).

## Notes
- Contract: E-RFP-OUTCOME body keys, E-RFP-FOLLOWUP keys (`expected_revision`, `version`, `idempotency_key`, `body` only when edited), `learned_at` and `remind_at` in WAT (`watIso`), and `lessons_items` not sent all match the spec table. The mock checks run in the documented order and every reply is validated against v7.
- D-60 items (a), (b), (c) are implemented as decided: the frame is desktop only, unknown keeps proof required, and the omitted copy is a listed exception.
- Security lens (CSRF, tenant, agent send) is for the security reviewer. I saw nothing in the code that sends without a click.
