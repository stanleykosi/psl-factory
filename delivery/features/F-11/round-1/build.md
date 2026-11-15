STATUS: READY
COMMIT: 06b4c0e93bbc3083cea431c2f022c1e267486f24
BUILDER: builder
LANE: full

## Summary
- `/setup` now redirects to `/setup/rules`. That page shows the Setup frame (SETUP eyebrow, title, seven route tabs with Roles and Rules badges), the "N rules aren’t set yet" banner, the RULE / AREA / CURRENT VALUE / VERSION table and the "Set a rule" panel. `/setup/rules/finance` (7 grouped panels with "Set … rules" disclosures) and `/setup/rules/delivery` are built too, along with read-only phone layouts for all three and six reserved tab routes.
- Every value comes from E-SETUP-RULES. "Not set" means only `set:false`, and counts come only from `not_set_count` / `roles_missing_count`. The editor appears only on rows with `can_change`, a `role_set` editor with options, and no `link`. `/me` roles are never read.
- Save sends E-SETUP-RULE-SAVE with `expected_revision` as read (0 for Not set), `value.roles` in option order, `starts`, an optional trimmed `reason`, an optional `evidence_id` and the CSRF header. A ref guard allows one write at a time. Outcomes: 200 re-reads; 409 re-reads and clears every edit; 422 marks the fields; 403/404 show the message and re-read; a network or server error re-reads once and never resends. Focus moves to the callout. Proof uploads through E-EVIDENCE-UPLOAD using the proposed `proof_case`.
- Mock: `setup.mjs` and `evidence.mjs`, one fixture per board, an `admin` persona, scenarios (desktop, mobile, readonly, empty, forbidden, many), save cookies (stale, invalid) and a proposal overlay. Tests prove the overlay equals v7 apart from `proof_case`, and that the v4 core still validates.
- Fidelity: the three desktop boards PASS. The three phone boards reach 100% coverage after the requested exceptions, but their visual scores are 66 / 78.9 / 83.7, below 90. Almost all of that gap is the D-08 frame offset (see Validation).

## Changes
- `frontend/src/app/setup/page.tsx`: now `redirect('/setup/rules')`.
- `frontend/src/app/setup/rules/{page,finance/page,delivery/page}.tsx`: the three views with their metadata titles.
- `frontend/src/app/setup/{roles,costing-rule,delegation,payroll-visibility,staff,templates}/page.tsx`: the reserved tabs.
- `frontend/src/features/setup/`:
  - `contract-proposal.ts`: v4 types plus the v7 proposal types and `proof_case`.
  - `api.ts`: `readRules`, `saveRule` and `uploadEvidence`. This is the only place that casts, for the `cursor` query and the proposal save body.
  - `format.ts`: version text and today in Africa/Lagos, `valueText`, `isEditable`, link and area routes, `formatSize`, `fieldsFromMessage`, `groupButtonLabel`.
  - `useSetupRules.ts`: first page and Show more; `refresh` re-reads after a write.
  - `useRuleSave.ts`: the single-write guard and save outcomes.
  - `SetupFrame.tsx`: frame and tabs, the setup destination gate, read states, the phone back link, empty state, Show more.
  - `RulesView.tsx`, `FinanceRulesView.tsx`, `DeliveryRulesView.tsx`, `SetRulePanel.tsx`, `ProofField.tsx`, `ReservedTab.tsx`, `icons.tsx` (info, paperclip and tick icons) and `setup.css` (token variables only).
- Mock:
  - `frontend/mock/setup.mjs`, `frontend/mock/evidence.mjs` and `frontend/mock/proposals/setup.json` (overlay: `rules_response`, `save_body`, `evidence_response`).
  - Fixtures: `frontend/mock/fixtures/setup/{rules,finance,delivery}.{desktop,mobile}.json` and `frontend/mock/fixtures/me.admin.json`.
- Tests: `frontend/tests/setup-rules.test.tsx` (37), `frontend/tests/setup-mock.test.ts` (13), `frontend/tests/setup-proposal.test.ts` (5) and `frontend/e2e/setup.spec.ts` (15).
- Shared files (integration owner, additive):
  - `frontend/mock/server.mjs`:
    - two imports;
    - `E-SETUP-RULES`, `E-SETUP-RULE-SAVE` and `E-EVIDENCE-UPLOAD` appended to `M1_OPERATIONS`;
    - `'admin'` appended to `PERSONAS`;
    - two dispatch lines;
    - `resetSetup()` in `/__mock/reset`.
  - `frontend/tests/mock-contract.test.ts`:
    - `PATH_VALUES.component` and `PATH_VALUES.case_id`;
    - two `BODY` entries;
    - new `PERSONA_STATUS` (pm/none → 403 on all three) and `CONTRACT_BODY` (`contractRules`, `contractEvidence`), in F-06's shape. That includes F-06's three-line change to the persona loop, plus one `expectValid` line that applies `CONTRACT_BODY` to 200 bodies only;
    - the admin row in "E-ME carries each persona fixture".
  - New root fixtures `frontend/mock/fixtures/E-SETUP-RULES.json`, `E-SETUP-RULE-SAVE.json` and `E-EVIDENCE-UPLOAD.json`. These are minimal v4-valid bodies, needed only because `createMockServer` reads `fixtures/<id>.json` for every `M1_OPERATIONS` entry. Changing that loader line instead would not be additive. The dispatch never serves them.
- `git diff 3c0e57e -- frontend/src/shell frontend/src/api architecture frontend/package.json frontend/package-lock.json delivery/checks.sh delivery/config.json delivery/merge-policy.json` is empty.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] `/setup` lands on `/setup/rules` with the frame, the seven tabs and both badges: e2e "/setup lands on rules…" checks the URL, title, tab texts and hrefs, `aria-current`, "Roles2"/"Rules8" and axe.
2. [x] The 10 rows appear in order with values, versions, HOLDS WORK, the costing link and the banner: unit "shows the board rows in order…" plus the e2e.
3. [x] Counts come only from the count fields: unit tests with the fields absent (no badge, no banner, phone h1 "Rules"), with 0 (badge "0", no banner) and with 1 (singular banner). The paging test also proves the count stays at the first page's value.
4. [x] Unknown values are never shown as values: unit "never shows an unknown as a value" (a stray `display_value`/`value` with `set:false` shows Not set, `set:true` without text shows "Set", no `value` contents rendered).
5. [x] Read-only Lead: unit (no panel, no inputs); e2e with `psl_mock_setup=readonly` (0 Save buttons, a forced PUT gets 403); `setup-mock.test.ts` (readonly/pm/none PUT → 403).
6. [x] Editor gating is per row: unit `isEditable` cases, picker contents, no panel when no row qualifies, identical markup for finance_lead and admin.
7. [x] Checkboxes come from `editor.options` and start from `editor.selected`: unit (3 options, none ticked for the RFP rule, PMO Lead for client documents) and e2e (exactly one "PMO Lead").
8. [x] First save: unit checks the exact body, the CSRF header, the reload, "v1 · since 14 Nov", Rules7 and the banner at 7, the status message and focus. The e2e against the mock checks the same, including a real upload.
9. [x] A blank Why sends no `reason`, no upload sends no `evidence_id`, and a double click sends one PUT: unit.
10. [x] Stale save: unit and e2e (message focused in the alert, the other person's version shown, edits cleared, "Save as version 2", one PUT).
11. [x] Invalid save: unit and e2e (alert text, `aria-invalid` on Why and Starts, edits kept). `fieldsFromMessage` table test.
12. [x] Mock validation: `setup-mock.test.ts` covers out-of-option roles → 422 `value.roles`, −1 or a string revision → 422, a mismatch → 409 with nothing changed, an unknown component → 404, and a missing or foreign CSRF token → 403 `csrf_failed`.
13. [x] Uncertain effect: three unit tests (revision unchanged keeps the edits, revision changed clears them, failed re-read locks Save until another rule is picked). One PUT in each.
14. [x] 401, 403/404, pm and server error: unit (401 read and save → sign-in `next=%2Fsetup%2Frules`, 403/404 → no access with no rule names, pm → no rules call, Try again re-reads). e2e with the forbidden cookie, the pm persona (no setup request) and a 401.
15. [x] Proof upload: unit (POST to C-SETUP-1 with kind, filename, base64 content and `case_revision` 1, then 2; "Uploaded · 2 KB"; disabled drop on a row without `proof_case`; a 422 marks Proof and Save still works; 409 asks again and re-reads). `setup-mock.test.ts` checks the real sha256.
16. [x] Finance view: unit and e2e as finance_lead (crumb, lead text, "All 25 values are Not set…", 7 groups, 25 NOT SET tags, button labels including "Set BU totals rules", `aria-expanded`, picker limited to the group, one panel at a time, none when read-only).
17. [x] Delivery view: unit and e2e (columns, 5 rows, "Keep, never purge", info callout, Next panel, no controls).
18. [x] Phone at 390 with `mobile`: e2e (back link to `/setup/roles`, "Rules · 6 not set", 6 cards, no tabs or Save; finance "25 values Not set.", 3 groups, "+ 4 MORE LINES · OPEN ON DESKTOP"; delivery 4 rows; `scrollWidth <= 390` on each).
19. [x] Paging: unit (50 rows, a failed page keeps the rows and warns, Show more appends 5 and disappears) and e2e with `many` plus a routed 503.
20. [x] Reserved tabs: e2e loops over all six (URL, that tab current, "{Label} comes next.", title, no setup request, pm → no access). Unit test for `ReservedTab`.
21. [x] Empty: e2e with `empty` on all three views.
22. [x] Contract overlay: `setup-proposal.test.ts` checks that overlay equals v7 apart from `proof_case`, and that every fixture and mock answer in every scenario, area and page is overlay-valid and v4-valid once stripped. Every save body built in `setup-rules.test.tsx` is checked inside the fetch stub against the overlay and, as its v4 core, against v4.
23. [x] `npx vitest run tests/mock-contract.test.ts`: 87 passed (200 for finance_lead and admin, 403 for pm and none, every declared error scenario).
24. [x] Accessibility: e2e runs axe with no violations on rules at 1440 and 390, finance and delivery at 1440 and 390, a reserved route at 1440 and 390, the panel after a 422, and readonly at 1440 and 390. The keyboard test reaches the tabs, the panel controls in order and Save with a solid 2px ring. The fieldset/legend group, labelled checkboxes, date, Why and Proof, and one h1 per view are all checked.
25. [ ] Design fidelity: the desktop boards PASS. The phone boards reach 100% coverage after the requests, but their visual scores are 66 / 78.9 / 83.7, below 90 (see Validation). Reports are in `round-1/fidelity/`, requests in `round-1/fidelity/exception-requests.json`.
26. [x] Shared edits stay additive: the protected-path diff is empty. `server.mjs` adds 7 lines and changes 2 (the `M1_OPERATIONS` and `PERSONAS` lists). `mock-contract.test.ts` changes are listed under Changes.

## Validation
- `cd /Users/Hunchoo/psl-factory-worktrees/f-11 && bash /Users/Hunchoo/psl-factory/delivery/checks.sh` exited 0: Django check clean, lint 0 warnings, typecheck clean, 16 files / 405 tests passed, build OK.
- `cd frontend && E2E_PORT=4101 MOCK_PORT=4102 npm run test:e2e`: 98 passed, including the 15 in `setup.spec.ts`.
- Fidelity (`fidelity.mjs --exceptions round-1/fidelity/exception-requests.json`, `next start` on 4101, mock on 4102):

  | Board | Coverage (after requests) | Visual | Result |
  |---|---|---|---|
  | SCR-13-desktop-rules 1440 | 77.6% (100%) | 93.4 | PASS |
  | SCR-13-desktop-finance-rules 1440 | 93.1% (100%) | 96.2 | PASS |
  | SCR-13-desktop-delivery-rules 1440 | 93.9% (100%) | 97.9 | PASS |
  | SCR-13-mobile-rules 390 | 14.3% (100%) | 66.0 | FAIL (visual) |
  | SCR-13-mobile-finance-rules 390 | 100% | 78.9 | FAIL (visual) |
  | SCR-13-mobile-delivery-rules 390 | 100% | 83.7 | FAIL (visual) |

  - **Why the phone scores are low.** The phone boards draw "← Setup" inside the dark top bar. The app's phone bar belongs to `src/shell` (not touched here), so the back link sits just under it (D-08, A-14). That pushes all content down about 42px, which is about half a card or row step, so nearly every row square misses. The side-by-sides show the content otherwise matches card for card. Pulling the link up into the main padding made the scores worse (63 / 74 / 81). The fix is the planned frame back-link slot (D-08 / D-13 follow-up).
  - **Tool limitation 1: cookies.** `fidelity.mjs` sets `--cookies` with `url: <page>`, and Playwright then scopes them to the page's folder (`/setup/rules/`), so they never reach `/api/v1`. For the desktop boards the mock's defaults are the same data: the persona is finance_lead (only the top bar's role text differs) and the scenario is desktop. For the phone boards I started the mock with `MOCK_SETUP_SCENARIO=mobile`, a small env default added to `setup.mjs` for this purpose. To re-run: `MOCK_PORT=4102 MOCK_SETUP_SCENARIO=mobile node mock/server.mjs`.
  - **Tool limitation 2: card text.** On SCR-13-mobile-rules the tool reads the page's cards (`ul > li`) as repeated data rows and hides their words, while the board's cards are separate blocks. That accounts for 11 of the 12 coverage requests on that board.
- **Exception requests** (none approved yet; all in `exception-requests.json`):
  - Start work and More ways to start (F-05 not at base);
  - the persona text;
  - the Setup tab bar as a nav of links (A-7);
  - the Rule, Starts and Why labels and their values (real labels, a native select, a native date input; A-11, A-14);
  - the duplicate PMO Lead (PMO-0-4);
  - the Proof sample file (A-14);
  - the phone card texts (tool limitation 2 above).
  - Requests that do not show as tool misses are listed in the file's `$comment`: A-1, A-6, A-8, A-12, A-13 and D-08.
- **For the backend developer (T-SETUP), all proposals:**
  - D-SETUP-RULES-VIEW row fields and the two counts;
  - `expected_revision` minimum 0 (PMO-0-1; the v4 minimum of 1 blocks a first save);
  - `starts`, `reason` and `evidence_id` on the save;
  - a `cursor` query parameter on E-SETUP-RULES (it returns `next_cursor` but declares none);
  - the row field `proof_case {case_id, case_revision, evidence_kind}`, which goes beyond v7 (A-3);
  - the value shape `value: {roles: [...]}` (A-5).
- **Ownership.** `frontend/mock/evidence.mjs` and `ProofField` are setup-local, held until FE-M2A-PROOF or FE-M2B-RESPONSE takes them over (PMO-0-5).
- **Sample data and fixture choices.** All fixture values are sample data, not PSL policy. In `finance.desktop.json`, "Group reviewer" is also a `role_set` row alongside the "who …", preparer and executor rows.
- **Incident.** The session scratchpad is shared with another builder (F-12). My helper script name collided with theirs, and three of my fidelity runs used their script. Those runs:
  - sent a `POST /__mock/reset` to their mock on 4202;
  - opened pages on their 4201 server;
  - wrote two output folders into `/Users/Hunchoo/psl-factory-worktrees/f-12/frontend/` (`psl_mock_persona=admin/`, `psl_mock_persona=finance_lead/`). I deleted both; none of their tracked or untracked files were touched.

  If F-12's mock state looked reset around 07:57, this was the cause. My later scripts live in `scratchpad/f11/`.
- Servers I started on 4101 and 4102 are stopped. `frontend/test-results` is deleted.

## Blocked
Not blocked. AC 25's phone visual bar (≥ 90) cannot be met without a frame back-link slot in `src/shell` (the D-08 follow-up, frame owner). The design engineer can accept the phone scores as a provisional exception, as D-08 and D-16 did for earlier features.
