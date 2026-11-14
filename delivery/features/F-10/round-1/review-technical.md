VERDICT: PASS
COMMIT: 02db3e841a47c4d83ed907c5bba467ef3a05a164
REVIEWER: reviewer-technical
AUTHORITY: technical reviewer (lead)

## Summary
- I reviewed b91ca6a..02db3e8 (19 files, frontend lane plus the integration-owner entries). Every touched path is inside the spec's lanes. `architecture/**`, `src/api/**`, `src/shell/**` and the shared CSS are unchanged.
- The money rules hold. `cashView` uses `cash_received_detail` when it is present and falls back to v4 `cash_received` only when it is absent. An amount counts as known only when `unknown === false` and the decimal pattern matches, and everything else reads "Unknown", never 0 or blank. `compactAmount` uses BigInt, rounds half away from zero and steps up a unit correctly (999950 gives ₦1M, 999950000 gives ₦1B, -1250 gives -₦1.3K). The full value comes from the existing `formatAmount`.
- Counts are shown exactly as returned, and a missing count reads "Unknown". The page fetches only after `parsePeriod`, which takes exactly one valid YYYY-MM string, and sets no default month (no `new Date`). Restricted rows never link, whatever `work_id` says. 403 and 404 render the same no-access view. 401 goes to `SignedOutState` with the correct `next`.
- The proposal fields are typed locally with the exact v7 names and enums, all optional. A pure v4 body renders, and this is tested both in unit tests and with the mock's `contract` scenario. The mock serves bodies that are valid v7 as served and valid v4 after `contractBody`, and `server.mjs` changes by exactly 3 lines.
- The tests are real and include negative cases: a restricted row carrying `work_id: "W-9"`, inconsistent counts, malformed amounts, 403 vs 404 producing the same DOM, and a superseded answer being dropped. No existing test is weakened. The `mock-contract.test.ts` changes only generalise the 200 expectation through `PERSONA_STATUS`.

## Findings
- TECH-1-1 | non-blocking | low | frontend | AC12 asks for a test that "an answer that arrives after a retry has started is ignored". The unit test at `frontend/tests/finance-month-end.test.tsx` ("an answer to a superseded read is ignored") covers only a superseded period. The same request counter guards retries (`useMonthEnd.ts:17-25`), and the UI offers no Try again while a read is pending, so the risk is low. A retry-specific case (first read pending, `retry()` called, first answer resolves late) would cover the criterion literally.
- TECH-1-2 | non-blocking | low | frontend | Out-of-contract values crash the page instead of degrading. `taskTag` reads `STATE_TAGS[task.state].text` (model.ts:111-114), `AgentNote` reads `AGENT_NAMES[note.agent].name` (MonthEndView.tsx:143) and `formatClock` throws a RangeError on an invalid `as_of`. A tone outside the enum yields `psl-tag--undefined`. Both v4 and v7 close these enums and v7 types `as_of` as date-time, so a conforming backend never triggers this. When T-FINANCE lands, a defensive fallback (neutral tag, no note, no as-of) would be cheap.
- TECH-1-3 | non-blocking | low | frontend | The full cash value is exposed only through `aria-describedby` on a plain `<span>` (MonthEndView.tsx:63-68). The spec mandates this, so it is not a build defect. However, screen readers often don't announce descriptions on non-focusable static text, so the "full value for screen readers" goal may not be reached in practice. I am flagging it for the UX/accessibility review to confirm with a screen reader. An alternative is a visually hidden text sibling.

## Notes
- The phone "← Finance" sits at the top right of the h1 line (month-end.css, the `@media` block), not on its own line under the phone bar as the spec's Layout says. The builder disclosed this in build.md with fidelity evidence (79 vs 94.9). It is a design call for UI/PMO and the design engineer, not a technical defect.
- `fidelity-exceptions.json` lists only the two frame items, a subset of the four the spec allows. That is fine.
- The avatar PNGs are the base's PR #12 files (md5 `da53372b…`, `8a35aac4…`, `fc4cfd33…`), not the spec's md5s. The coordinator directed this, and no binaries are added on this branch.
- The `monthend-noaccess` and `monthend-plain` class names have no rules in `month-end.css`. They are harmless hooks.
- `router.back()` when `history.length > 1` can leave the app when the page was opened from an external link in a tab that has history. PMO-0-4 specified this, and the real target is pending with the design engineer.
- I ran no commands beyond reading. The gate's `checks.md` shows checks.sh passing on this head.

## Verified
None (round 1).
