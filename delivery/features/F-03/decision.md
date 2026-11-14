RECOMMENDATION: AUTO_MERGE
COMMIT: 3f684410f771cf53c1103d40aaa7977b09c084b3
APPROVER: approver

## Summary
- F-03 adds a read-only work item page (`/work/[id]`) and a history page (`/work/[id]/history`). Both run against the contract mock. The change also adds per-id mock fixtures and a small extra handler in `frontend/mock/server.mjs`.
- Round 3 on head 3f68441 passed every check: the gate (142 unit tests, lint, typecheck, build), the technical, UX, UI and QA reviews, and PMO acceptance. Every blocking finding (UI-1-1, UI-1-2, UI-2-1) is verified closed.
- All 21 changed files are in the F-03 lane. Nothing touches openapi, `src/api`, `src/shell`, styles, architecture, migrations, lockfiles, CI or the protected delivery files. No always-human path or surface is involved.
- My own spot-check: I re-ran `tests/work-item.test.tsx` and `tests/mock-contract.test.ts` on this head and all 101 tests passed. I also read the restricted-row code (`WorkItemHistory.tsx:71-83`). A restricted row never shows its event, detail or version.
- Note on policy: readiness rated this medium risk, and 21 files is more than the 15-file cap. `merge-decision.py` will probably lower this recommendation to ESCALATE. My recommendation is about the change's merits.

## Why
The change is read-only UI against a mock. It keeps the business rules visible as required: facts stay separate, unknown values read "Unknown" and never 0, the agent card cannot approve, send or pay, and restricted history rows stay hidden. It invents none of the values the contract lacks; those are listed as contract gaps for architecture. The spec's assumptions come from the approved SCR-02 boards (tag wording and colours, route shape, mock design). The station layout follows the design engineer's recorded 14 Nov 2026 decision. None of them is a pricing, policy, free-versus-paid or new public-copy decision, so a person has nothing to decide here. Known follow-ups do not block the merge:
- F-02 will conflict in `server.mjs`. The pre-merge sync and re-check handles that.
- QA-3-1 and QA-3-2 are mock limits.
- `feature.json` is out of date: `operation_ids` is empty, and its copy of AC 4 is stale (PMO-3-1, PMO-3-2).

## Acceptance criteria
1. W-1004 shows six separate facts with the exact texts: met. Unit test, plus QA's page check (Earned 10:58/16:12/16:40, Sent "Not yet", Receipt recorded "Unknown", Verified "Not yet", Paid note shown).
2. Unknown or missing facts read "Unknown": met. Unit tests, which I re-ran and which pass.
3. State tag wording and class for all 11 states: met. Table-driven unit test.
4. Station track (list below 1080px, row from 1080px, no sideways scroll, one `aria-current`): met. e2e at 390/760/900/1079/1080/1440, and measured independently by the QA, UI and UX reviewers. The spec's 1080px wording is the authoritative one. The `feature.json` copy of AC 4 is stale (PMO-3-2).
5. Agent card never offers a decision (W-1003 WORKING, step 3 of 4; W-1002 "No agent work"): met. Unit tests and QA.
6. Reduced motion stops the pulse: met. QA measured animation `[]` with reduce and `psl-pulse` without.
7. Decision link only when `you_can_act` is true: met. W-1001 has the link to `/work/W-1001/decide?task=T-2001`; W-1002 has no control. Unit tests and QA.
8. Effect-uncertain next step is a warning callout with no buttons: met. W-1005 shows 0 buttons (QA).
9. SAMPLE DATA shows even when the mode is live: met. Unit test.
10. 403/404 permission view leaks no id or title: met. Unit tests and QA (W-1099, forced 403).
11. 401 shows signed-out with `next=/work/W-1001`: met. Unit test and QA.
12. Error card and Try again recover: met. Unit test, and QA saw a 500 then a 200 over 2 fetches.
13. History in returned order, WAT times ("12 Nov 16:40"), includes a return and an approval: met. Unit test and QA.
14. Restricted rows hide event, detail and version: met. Unit test and my own code read.
15. History is read-only (only filter, rows select, Show more, Try again): met. Unit test and QA.
16. Filter and paging request parameters, and Show more: met. Unit test, and QA saw 10, then 12 rows, then no Show more.
17. Mock per-id selection, fallback, kind, limit, cursor, and `_kind` stripped: met. mock-contract tests (re-ran, pass) and QA curl.
18. Every work fixture is schema-valid: met. The mock-contract directory test passes (re-ran).
19. Polling rules (D-UPDATES r2): met. Unit tests with fake timers. QA saw 5 s polling for W-1003, none for W-1001, and the failed-poll warning. Hidden-tab polling and the revision-triggered history reload are proved by unit tests only.
20. Accessibility: met. Axe e2e at 390 and 1440 on the listed pages (47 e2e tests pass per build.md).
21. Gate: met. checks.md GATE: PASS on 3f68441.

## For the human
Not applicable (AUTO_MERGE).

## Human decision (14 Nov 2026)
Merge route HUMAN_APPROVAL (medium risk; 21 changed files). Under the design engineer's standing delegation (13 Nov 2026) the coordinator judged that no product, security, money or business-rule decision was involved (the design choices were the design engineer's own, 14 Nov 2026), recorded approval, and squash-merged PR #4 as 2c3a09b8745640ae0d22a8270b99a501b00ac630.
