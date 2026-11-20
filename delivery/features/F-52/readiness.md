DECISION: READY
RISK: medium
SURFACES: ui, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: coordinator (D-123, follow-up batch; the user said "yeah lets run the followups too", 20 Nov)

## Summary
- F-52 is follow-up batch A: small fixes found while delivering F-33, F-35, F-39, F-43, F-37 and F-49, all on screens already merged and client-approved. Each item was recorded as a follow-up in a review, PMO acceptance or the night log, and needs no PSL decision.
- None of it touches the Start work form, which F-51 is building now (the F-49 empty-submit check is batch B, after F-51).

## Scope
1. F-33 income schedule: "approved" or "verified" wording appears only after the re-read confirms it (the same rule F-45 applied on the ledger line). Source: F-43 and F-45 build notes, F-45 decision.
2. F-33 income schedule: a real two-reviewer stale-409 test (the shared fix from F-35/F-39 is in dlv-00). Source: F-39 PMO follow-up.
3. F-35 leadership report stale notice: add a next-step sentence and move focus to the notice (UX-3-1, UX-3-3). "Survives reload" (UX-3-2) is out: the notice is page state, and the backend has no record of a refused decide.
4. F-39 escalation mock: add the W-3602 send-for-review fixture so that path completes on the mock (QA-4-1).
5. Shared response mock: a T-3401 `team_input` response handler, so F-37's "Record team input" completes on the mock (QA-3-1).
6. Shared header History link: at least 44px tall on phones (F-35 UI-2-1 / F-40 notes).
7. Test reliability: rfp-intake-mock beforeEach ECONNRESET (retry the reset, or send `Connection: close`).

## Risk
Medium. Items 1–3 change what a person reads on merged screens (wording timing, notice text and focus). The rest are mock data, a tap-target size and a test fix. No write, authority, money or send path changes.
