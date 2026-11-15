VERDICT: PASS
COMMIT: 28c13dbcca5af9b6db6f276e2878c43a487a8958
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- The builder's claim on TECH-1-2 holds: the outcome form uses the card layout, which shows the file picker only while no file is attached, and E-RFP-OUTCOME takes one `evidence_id`. A second file cannot be added, so nothing is silently dropped.
- Round 2 changed only frontend presentation and the follow-up guards. Send is off for a blank edit box, "Use the draft" returns to the draft text, and focus moves to the status line. Contract, request bodies and the click-only send are unchanged.
- Fidelity (round-1 TECH-1-1) is not re-blocked. It waits on the design engineer as UI-1-7; AC1 and AC2 stay unchecked in build.md, which is honest.
- The gate passes per checks.md. I read the diff and did not re-run anything.

## Findings
- TECH-2-1 | non-blocking | low | frontend | The new TECH-1-2 test does not fail on the old code (the builder says so). It guards the one-file rule and is still worth keeping. The contract question (should the outcome take several proof files?) is already in build.md for the backend developer. `frontend/tests/rfp.test.tsx`.
- TECH-2-2 | non-blocking | low | frontend | The spec colour table (lost red, unknown neutral) was changed to lost grey, unknown amber, following the boards. Disclosed in build.md. Update the spec or the design engineer's decision record so the two agree. `frontend/src/features/rfp/labels.ts`.

## Verified
- TECH-1-1 | reopen | Still open as UI-1-7 (4 of 18 boards at 90 or more). It waits on the design engineer; not re-blocked here.
- TECH-1-2 | verified | `ProofField.tsx` card layout renders the picker only when `empty`. `OutcomeForm.tsx:211` uses `layout="card"`. `outcomeBody` takes one `evidenceId`. No dropped files are reachable. No code change was needed.
- TECH-1-3 | carried | Typed zero is still sent as a value. Not in this round's fixes; low and non-blocking, unchanged.
- TECH-1-4 | carried | The stale-409 reload failure still sets no notice. Unchanged; low. The stale note is now only shown on a draft (UX-1-2), which is a small improvement.
- TECH-1-5 | carried | `sending` followed by a failed reload still has no "Check again". Unchanged; low.
- TECH-1-6 | carried | Outcome 409/403 followed by a failed reload still shows the error card; entries are kept. Unchanged; low.
- TECH-1-7 | carried | `T-2101/T-2102` versus the spec's `T-2001/T-2002`. Unchanged; the spec still needs the correction.
- TECH-1-8 | verified | No finding in round 1; nothing in round 2 reintroduces hard-coded option text.

## Notes
- Blank-box guard: `blank = editing && text.trim() === ''` is checked inside `send`, so a keyboard or double activation cannot bypass the disabled button. After "Use the draft", `edited` is undefined (it needs `editing`), so the sent body is the drafted text and no `body` key is sent, as the spec requires.
- The shared status element for Sending… and Sent keeps focus through the change. No new send path was added.
