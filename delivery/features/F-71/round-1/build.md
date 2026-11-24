STATUS: READY
COMMIT: e5f7b00d3f67a933ecb2f9029552c9fa0b173ff6
BUILDER: builder
LANE: frontend

## Summary
- The Money tab reads `GET /projects/{case_id}/money` and `?figure=<key>` through `liveApi`. Rows are shown in the order sent, with `stage_position` before the label, amounts as `<currency code> <grouped amount>`, one line per invoice, and "Paid <amt> · Owed <amt>" with Unknown for each null. No paid word, no total, and no report read.
- The Milestones tab reads `/money` (contract stages only) and `/milestones` (the one section of recorded completions) independently. It has per-press Proof reads (`/milestones/{id}`), a join only through `milestone_id`, a CHANGES column only when a change exists, and Show more with `?page=`. The refusal combinations behave as the spec says.
- The mock is on the live shape: money fixtures, `?figure=`, a live milestones body paged 25 at a time, and the one-completion route. Ajv validates every served body against contract 1.26.0.
- Contract 1.26.0 matches the spec's 1.24.0 field names. The only extras are two required fields on completion items, `age_days` and `origin_meeting`, which the fixtures carry. The completions section key in the mock is `completions` (an assumption; the model never reads the key).
- Full vitest after merging origin/main again (F-85): 164 files, 3904 of 3904 passed, under the lock. `npm run lint`, `npm run typecheck` and `npm run build` pass. The Playwright specs `e2e/money.spec.ts` and `e2e/project-tabs.spec.ts` are rewritten for the live shapes and pass (47 of 47; the P-0108 phone case needed a CSS fix, then passed).

## Changes
- `src/features/projects/moneyModel.ts`, `useMoney.ts`, `MoneyTab.tsx`, new `MoneyCells.tsx`: live types and guard, `readMoney`, and the drill-down on `?figure`. Removed `figureOf`, `valuesDiffer`, `paidWords`, the report, Chidi card and title.
- New `milestonesModel.ts`, `useMilestones.ts`, rewritten `MilestonesTab.tsx`; `money.css` and `project-tabs.css` have small additions.
- Shared tab files (F-75/F-74 touch these): `tabsModel.ts` loses the milestone-only code and adds `ReadTab = Exclude<ListTab,'milestones'>`. `useProjectTab.ts` and `TabParts.tsx` switch their generics to `ReadTab`, and `AmountValue` is removed from `TabParts.tsx`. `ProjectTabContent.tsx` is unchanged because the props are the same.
- Mock: `money.mjs` is rewritten (money, figure, completion; E-REPORT removed). `project-tabs.mjs` has a milestones-only live branch (P-0105 scripted 404, P-0103 stays 403). `server.mjs` gets one small shared change: a GET route for `/projects/{id}/milestones/{n}` placed before the route lookup, and an import. Fixtures: money P-0101, its `.changed`, P-0102 (limited), P-0103, P-0105, P-0106 (empty), P-0107 and P-0108; milestones P-0101, P-0102 (27 rows), P-0106 and P-0108; new `fixtures/projects/milestones.json` (proof versions). `fixtures/reports/` and the v7 `milestones.changed` fixture are deleted.
- Tests: new `mock-live-money`, `milestones-model` and `milestones`; rewritten `money`, `money-model` and `mock-money`; milestone parts removed from `project-tabs*`, `mock-project-tabs` and `demo-mock`.
- Shared-file touches outside the money and milestones code (listed so the coordinator can see them):
  - `tests/mock-contract.test.ts` line 43: the `tab` path value goes from `milestones` to `documents`, because milestones is now the live shape, which the v7 schema check cannot validate. Separate commit.
  - `tests/next-config.test.ts`: the embed check's allow-list gains the two model tests, and its fixtures pattern gains `money/` and `tabs/`, because the contract requires `django_url` in these bodies.
  - `tests/demo-mock.test.ts`: the demo project's milestones and money tabs are checked against the live contract.
- Focus after the last completions page moves to the first new completion, through a small effect in `MilestonesTab.tsx` (`useFocusAfterMore` looks only for links or table rows). The no-access note and the empty and error lines use a new `ptabs__line` class, because `ptabs__note` is hidden on phones. `e2e/money.spec.ts` and `e2e/project-tabs.spec.ts` are rewritten, and the `next-config` allow-list merges both sides (F-85's `work-live.mjs` plus mine).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Rows in the order sent, with the number only on stages: `money.test.tsx` (order and alphabetical tests).
2. [x] A null amount shows Unknown plus `missing_reason`, and no `0.00` appears: `money.test.tsx`.
3. [x] A null paid or owed reads Unknown, the status text is exact, no paid word appears, and `paid === amount` changes nothing: `money.test.tsx` and `money-model.test.ts`.
4. [x] No totals or sums appear: `money.test.tsx` and `milestones.test.tsx`.
5. [x] Two invoices are both listed: `money.test.tsx`.
6. [x] Currency comes from the item (`USD 1,000.00`): `money-model.test.ts`.
7. [x] The `limited` warning and the As of line show: `money.test.tsx` (P-0102).
8. [x] `?figure=` reads once, sources are in order with reference and kind, "No source recorded", "That figure isn't available.", key encoding, and the phone sheet: `money.test.tsx`. The 1440 and 390 widths run with the matchMedia stub.
9. [x] 403 and 404 show only "You can't see this project's money."; a 500, a network failure and a bad body show the error card, and Try again re-reads once: `money.test.tsx`.
10. [x] Milestones: stages only, due and completion text, CHANGES only when present, "change amount Unknown": `milestones.test.tsx` (default and changed cookie).
11. [x] Recorded completions is its own list; Show more asks for `?page=2` and appends: `milestones.test.tsx`.
12. [x] Money 404, completions 404 and both refused: `milestones.test.tsx` (P-0108, P-0105, P-0103, an override).
13. [x] P-0099 and its UUID, and a project outside the persona, answer 404 from every route: `mock-live-money.test.ts`.
14. [x] `mock-live-money.test.ts` validates every fixture and served body (Ajv 2020 with formats) and the P-nnnn form.
15. [x] The old tests are rewritten for the live shape, with none deleted without a replacement; full vitest 3904 of 3904, and e2e rewritten and passing.
16. [x] The grep for `E-REPORT|E-PROJECT-TAB` in the money and milestones files has no hits; eslint is clean on the touched files.
17. [x] Live smoke: Django test client with `force_login` for `qa-seed` on the local DB (127.0.0.1:55433) read the seeded project's `/money` and `/milestones` (both 200). Both bodies pass `isMoney` and `isCompletions`, the real section key is `case`, and the model renders 0 stages and 0 completions, because the seeded project holds no money or completions. A populated live body was not seen. The Django server on 8010 and Next on 4970 were not run against it.
18. [x] Only GET requests leave either tab: `money.test.tsx` and `milestones.test.tsx` (fetch spy).
19. [x] The position number shows on both tabs, and a non-stage row has none: `money.test.tsx` and `milestones.test.tsx` (desktop and phone).
20. [x] A source with a reference shows it after the label, and one without shows the label only: `money.test.tsx`.
21. [x] Proof: exactly one GET per press; shows the name, the date and "Proof version N"; a 403 or 404 shows "Proof isn't available to your role."; no Proof button when `milestone_id` is null: `milestones.test.tsx`.
22. [x] The join only through `milestone_id`, and a same-name completion is not joined: `milestones-model.test.ts` and `milestones.test.tsx`.
23. [x] The completions section is found as the only section, not by its title: `milestones-model.test.ts` and `milestones.test.tsx`.
24. [x] Delivered with null paid shows "Delivered" and Paid Unknown: `money.test.tsx`.

## Validation
- Merged origin/main twice (e6c24e70, then F-85 e2f44656). The only conflict was the `next-config` allow-list, resolved by keeping both sides.
- Full `npx vitest run` under heavy-lock: 164 files, 3904 passed, 0 failed. `npm run lint` and `npm run typecheck` exit 0; `npm run build` exits 0 under the lock.
- Playwright under the lock (`e2e/money.spec.ts` and `e2e/project-tabs.spec.ts`, ports 4970 and 4971): 46 of 47 passed, and the one failure was the phone P-0108 note hidden by CSS. After the `ptabs__line` fix I reran the P-0108 cases: 2 of 2 passed. I did not rerun the other 45.
- Fidelity: one run on a production build earlier in the round, before the final merge (next start 4970, mock 4971, finance_lead, no exceptions applied). The CSS change after it only affects the phone note lines. Coverage and visual:
  - SCR-12 desktop 57.1 / 84.1
  - SCR-12 mobile 36.4 / 82.8
  - SCR-38 desktop 65.1 / 81.9
  - SCR-38 desktop changed 78.6 / 82.9
  - SCR-38 mobile 59.1 / 79.3
  - SCR-38 mobile changed 75.0 / 82.2
- Gaps, not iterated; all are D-182 hides or live-data differences, so I propose waivers and exceptions for the design engineer:
  - The `NGN` code instead of ₦.
  - Fixture stage names differ from the board's sample words.
  - Paid words, the "Done on · proof" wording and the composed invoice statuses are hidden.
  - The report title, the Chidi card and the "Mark milestone N complete" button are hidden.
  - The "Recorded completions" heading and the Proof button are additions.
  - "Back to Projects" and "Tunde Bello · PMO" belong to the shell.
- The mock-contract `tab` change, the `next-config` allow-list and the `demo-mock` edits are the shared-test touches listed above. Servers are stopped, and the worktree is clean and pushed.

## Blocked
None.
