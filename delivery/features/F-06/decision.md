RECOMMENDATION: ESCALATE
COMMIT: c4d0b05e5e25272eb9a66bf37cc0c390ba487c01
APPROVER: approver

## Summary
- The page itself is solid. F-06A, the read-only All exceptions list (SCR-10), passes at head c4d0b05: the gate (attempt 2), Technical, UX, UI, QA and PMO acceptance all name this head, and the fidelity check passes (desktop 100% / 90.7, phone with the board's rows 100% / 91.6). It writes nothing and shows no amounts.
- Two acceptance criteria are met only as amended by D-04, which the coordinator accepted provisionally. AC12 (no actions) now allows Filter and search. AC15 (phone cards) no longer shows "since" and "Who acts". The design engineer has not approved either change.
- Search, Filter, "N OPEN" and the reference line depend on contract fields (`q`, `what`, `open_count`, row `ref`) that exist only in the unconfirmed v7 proposal. `useExceptions.ts:34-35` always sends `q`/`what`. A real backend that ignores them would show an unfiltered list that looks filtered (TECH-2-1, PMO-2-1). This change is outside the approved contract, and the policy lists `contract-change` as an always-human surface.
- Product acceptance is required (readiness `PRODUCT-ACCEPTANCE: required`), and so far it is only provisional, by the coordinator.
- 46 files changed, against the policy's auto-merge cap of 15 (mostly mock fixtures). The merge-decision script would lower AUTO_MERGE regardless.

## Why
The work is good, and inside scope (no `src/api`, `src/shell`, `architecture/`, lock or migration paths are touched). But it can be called done only if two decisions belong to the designated human: changing two written acceptance criteria (D-04) and building UI behaviour on contract fields the backend developer has not confirmed. The overnight rules keep exactly these things (product approval and backend decisions) in "Waiting for you", so I am asking one question rather than merging.

## Acceptance criteria
1. Default list: met. QA's e2e default-list run on this head passed, and I confirmed `open_count`/`ref` render only when sent (`ExceptionsList.tsx:74, 310, 357`).
2. Order kept: met (unit test).
3. Kind mapping: met (unit test).
4. Times: met (unit test; D-04(e) keeps the spec's own "since" rule).
5. Paging: met. Unit tests cover it, QA reproduced it in the browser (limit 10/20/50, cursor, Show more), and the paging bar now sits below the table (D-04(b)).
6. Show more failure keeps rows: met. QA stubbed a 500 on the cursor page and the rows stayed.
7. Empty: met (unit and e2e at 390 and 1440, axe clean).
8. Signed out: met (unit and e2e for cookie 401 and list-only 401).
9. Wrong user (pm): met. QA got a 403 view with no rows, search or count.
10. 404: met (unit and e2e).
11. Provider failure: met (503, network, Try again).
12. No actions: met only as amended. As written, the only buttons allowed are Show more and Try again. The page adds Filter and search (D-04, provisional). They narrow the list and do not act on work.
13. Compact embed: met (unit tests only; no page mounts it yet).
14. Reusable exports: met. I spot-checked it: grep for `@/app`/`src/app` in `frontend/src/features/exceptions` returns nothing.
15. Phone layout: met only as amended. As written, cards show the tag, since, title, doing and "Who acts". Built cards drop "since" and "Who acts" (D-04(d), provisional). No horizontal scroll and 44px targets were verified.
16. Accessibility: met. axe is clean in all states at both widths. Non-blocking QA-2-1: focus is lost after a rows-per-page change, the same as on /my-work.
17. Mock contract: met, but only after `contractBody` strips the proposal fields. The request query is not checked (TECH-2-2).
18. Rows match items: met (unit test, including `ref` against `reference`).
19. Rows open their item: met (e2e and QA).
20. Work item link: met (unit and e2e).
21. Shared edits stay small: met (`server.mjs` 4 lines, `WorkItemOverview.tsx` 14 lines, `mock-contract.test.ts` 15 lines).

## For the human
Do you accept F-06 as built for merge into `dlv-00-delivery-setup`? That means accepting both of these:
(1) the D-04(a)-(f) design exceptions, which rewrite AC12 (Filter and search allowed) and AC15 (phone cards without "since" and "Who acts").
(2) search, Filter and "N OPEN" shipping against the unconfirmed v7 proposal fields `q`, `what`, `open_count` and `ref`.
If you say no to (2), the alternative is TECH-2-1's fix before merge: show search and Filter only when the backend sends `open_count`.

Files to look at:
- `/Users/Hunchoo/psl-factory/delivery/OVERNIGHT-DECISIONS.md` (D-04, D-05, D-11)
- `/Users/Hunchoo/psl-factory/delivery/features/F-06/round-2/build.md` ("Engineering proposal" and "Exceptions requested")
- `/Users/Hunchoo/psl-factory/delivery/features/F-06/round-2/review-technical.md` (TECH-2-1)
- `/Users/Hunchoo/psl-factory/delivery/features/F-06/round-2/fidelity-review/` (side-by-side images)
- `/Users/Hunchoo/psl-factory-worktrees/f-06/frontend/src/features/exceptions/useExceptions.ts:34-35`, and `ExceptionsList.tsx`
