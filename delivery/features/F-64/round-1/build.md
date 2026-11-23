STATUS: READY
COMMIT: ee8100763d192604e2ca46e93b624427891555b9
BUILDER: builder
LANE: full

## Summary
- /work/[id]/decide?task= now reads and writes the live task API (GET work, GET task, claim, decision, comments, history, queue=decisions) through liveApi; every D-182 answer (Q1 to Q12) built as recommended.
- The person must pick one review-evidence item (radio list, nothing pre-selected) before approve, return or reject is enabled; the body is exactly {expected_revision, verdict, evidence_id, note}; no retry of a write; 409 shows the stale board, uncertain writes reload once.
- Who may act comes only from can_decide / can_claim / claimed_by_you. No /me inference, no invented approvers; own board unreachable (Q2/Q12). Payment-exception, ceo-costing and cto-emergency variants not touched.
- Board parts with no live source are hidden (chain, basis, change list, preparer, agent notes, alert line, reasons, facts strip, Chidi next step); fidelity-exceptions.json lists each.
- Mock serves the live shapes for integer ids (mock/live-decide.mjs); v7 W-/T- ids stay on the v7 mock.

## Changes
- src/features/decide/{useLiveDecision.ts,DecideView.tsx,DecidePanel.tsx,LiveStates.tsx,LiveContent.tsx,liveFormat.ts,livePresentation.ts,decide.css}: rewritten for the live reads and writes (evidence picker, stale compare with the unsent note kept, read-only board with generic sentence and comment box, done board with history-based "decided by", pager and next decision from the live list only, uncertain notices).
- src/features/decide/{format,useDecision,DecisionContent,DecideStates,presentation}: one-line re-exports of src/features/decide-v7/*, so the v7 helpers are still importable at their old paths. decide-v7 holds the previous v7 code unchanged. No file outside SCR-03 changed: `git diff 8f562602 -- frontend/src/features/{workspace,documents,finance,projects,work-item}` is empty (the earlier import-path edits were reverted).
- src/api/types.ts: aliases LiveWork, LiveTask, LiveTaskRead, LiveDecisionBody, LiveDecisionResult, LiveHistoryItem.
- mock/live-decide.mjs + mock/server.mjs hook; fixtures: work 17/task 41 deciding, 18/42 not yours, 19/43 no packet; cookie psl_mock_decide=stale | no_evidence.
- tests: decide.test.tsx rewritten (58 live tests), mock-live-decide.test.ts (new, validates mock bodies against the live contract), decide-board.test.tsx removed (v7 boards). e2e/decide-board.spec.ts (default, default with evidence chosen, done, stale, not-yours at 1440 and 390: axe with the same tags, no sideways scroll, 44px phone buttons) and e2e/decide.spec.ts (approve, return with note, reject, stale, not-yours with comment, unknown amount, not-open states, no access, signed out, unconfirmed decision with axe) on the mock's live fixtures. no-success-callouts allowlist key renamed to decide-v7/DecideStates.tsx; next-config.test.ts allowlist adds decide.test.tsx and live-decide.mjs (they carry the contract's required django_url field).
- fidelity-exceptions.json (feature folder): 57 entries, approved_by "design engineer, 23 Nov 2026 — D-182".

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Claim once, shows label/version/amount/recipient: tests "reads the task, claims once ... (also under StrictMode)" (one POST /tasks/41/claim {expected_revision:3}, CSRF sent).
2. [x] No pre-selection; buttons off until a choice, body carries the item id: "pre-selects nothing", "Approve sends exactly ..." (evidence_id 88).
3. [x] Approve body has note key even when empty; return/reject empty note refused with no request: "Return or Reject without a note".
4. [x] Done board with verdict, note, label, work state; "decided by" only from a matching history item: four "done board" tests. Says "approved" only after the re-read confirms (checklist 2).
5. [x] 409 on claim and decision: stale board, replaced beside current, unsent note kept, "Review version n", one decision call; two-reviewer sequence where the task closes.
6. [x] Network and 5xx: one reload, no resend, uncertain notice; reload failing too keeps buttons off and Try again only GETs.
7. [x] Read-only board with generic sentence and no claim; 404 no-access, 401 signed-out, 403 on a write turns read-only; non-integer ids send nothing.
8. [x] 422 shows server message and fields, keeps evidence and note; 400 treated alike.
9. [x] Unknown amount: formatAmount test plus null packet and empty amount tests show Unknown, never 0.
10. [x] Only listed verdicts drawn; "no revoke" test greps decide/*, InlineDecide and `api.GET|POST` (none).
11. [x] Pager only when the live list holds this work; list failing leaves the page working; done board list and next link hidden on failure.
12. [x] Comment box on read-only board: sends {revision, body}, body required, 403 removes box, 409/422 messages, 409 and uncertain failure reload without resending, one send per tap.
13. [x] All calls use liveApi; api-live-schema-drift passes (full suite).
14. [~] Boards: see Fidelity. Layout follows the boards apart from D-182 removals; visual scores are under 90 on every board.

## Validation
- delivery/checks.sh not run as a whole (it runs npm ci, not allowed); its steps run singly: npm run lint clean, tsc --noEmit clean (apart from .next generated files), npm run build (production, API_ORIGIN mock) passed, full vitest on the final head: 158 files, 3825 tests passed. manage.py check not run.
- Authenticated paths are proved on the mock only (live-* accounts have no known password). Live unauthenticated: Django on 8002 answered 401 for GET /api/v1/tasks/41, /work/17 and /work?queue=decisions. Django, mock and next servers stopped; 3000/3001 untouched.
- Playwright: e2e/decide.spec.ts and e2e/decide-board.spec.ts, 19 passed (4964/4965). Full vitest on the final head ee810076: 158 files, 3825 passed. Other e2e specs not run; those that open /work/W-xxxx/decide?task=T-xxxx (delivery-release, minutes, minutes-end, weekly) will now meet the not-open state, because v7 ids are not integers; they follow their screens' own connection.

## Fidelity
One production build (next start 4964, mock 4965), fidelity.mjs with fidelity-exceptions.json, reports in round-1/fidelity/. Done and stale were reached by a throwaway Playwright shim that clicks through (outside the repo). I also did one discovery run without exceptions (in a scratch folder) to get the exact missing names for the exceptions file; the numbers below are the run with exceptions.
| Board | Coverage with exceptions | Visual |
|---|---|---|
| desktop 1440 | 97.8 | 71 |
| mobile 390 | 95.2 | 65 |
| done 1440 | 97.7 | 70.5 |
| done 390 | 100 | 64.3 |
| stale 1440 | 85.7 | 74.1 |
| stale 390 | 84.6 | 77.5 |
| not-yours 1440 | 95.5 | 78.8 |
| not-yours 390 | 94.7 | 85.8 |
Boards where the tool falsely reports the amount as missing (same character U+20A6, value visible on the page), tool key `text: ₦4,250,000.00` unless noted: desktop 1440 (container main), not-yours 1440 (main), stale 1440 (container table), mobile 390 (page), not-yours 390 (page), stale 390 (key `text: Invoice v2 · ₦4,250,000.00`, page). Done boards are not affected.
Open items, none hidden by an exception: the amount "₦4,250,000.00" is on the page but the tool reports it missing on four boards (same character; it matches a different element, so likely a tool limit); done 1440 side panel (complementary) not matched; stale 1440 table and its two column headers (the compare is a grid, not a table, as before D-182); stale 390 "REPLACED" and "To" labels differ. Visual is under 90 on every board mainly because D-182 removes large board parts (strip, agent card, chain), so the pages are much shorter: needs a design-engineer waiver or decision. Own board not checked (unreachable).

## Notes for the coordinator
- Shared code: other pages still on v7 import decide-v7 (see Changes); remove it as they connect.
- Backend questions this builds on (best reading, flagged): A-18 evidence choice, A-19 reasons/preparer, A-20 no revoke, A-21 chain/basis/changes, no can_comment flag (server 403 turns the box off).
- Work title and task label are both drawn (title, then work title as sub-line); in the mock they are the same text.

## Blocked
Not blocked.
