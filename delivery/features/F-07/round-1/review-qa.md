VERDICT: PASS
COMMIT: 195926d6854956a6918ef6199c0a5f57ce3a32ad
REVIEWER: reviewer-qa
AUTHORITY: integrated QA (UI against the contract mock only)

## Summary
- Reran `e2e/projects.spec.ts` on this head (`E2E_PORT=3701 MOCK_PORT=3702`): 24 of 24 passed. This is independent evidence for the axe, 390 no-scroll, focus, touch-target and reduced-motion checks (criterion 15). `test-results` deleted afterwards.
- Drove the shared production build (app 3711, mock 3712) with my own Playwright script as finance_lead, pm and none, at 1440x900 and 390x844 (Africa/Lagos). Every page I opened had axe (wcag2a, 2aa, 21a, 21aa, 22aa) "clean" and document width equal to viewport width. Pages: list, journey P-0101, empty P-0105, no access P-0099 and P-0102 as pm, and persona none.
- Journey Projects -> Lagoon Health · patient app -> `/projects/P-0101` (12 lines in order) -> line 6 "Prepare an invoice / Ready to continue" -> `/work/W-1004` -> browser Back to `/projects/P-0101`. All worked.
- Nothing was exercised against the real backend. `apps/` is untouched, T-PROJECTS does not exist yet, and grants, tenant isolation and real paging are unproved. These results show the UI honours the contract on the mock only. Fixtures stand in for data. The 401, 5xx and network paths were not driven by me; they rest on the e2e run above (page.route) and the builder's component tests.
- No blocking findings. One non-blocking note below.

## Findings
- QA-1-1 | non-blocking | low | frontend | An opaque `case_id` containing reserved characters is encoded twice. `/projects/P%2F..%3Cb%3E` sent `GET /api/v1/projects/P%252F..%253Cb%253E`, because Next hands the route param already encoded and openapi-fetch encodes it again. Expected: one level of encoding, so the backend sees the same id the URL carried. Actual: the id the server decodes is `P%2F..%3Cb%3E`. Real ids are uuids (REC-CASE), so there is no impact today, and the mock falls back to the default journey for unknown ids. The fix is to decodeURIComponent the segment before the client call, in `frontend/src/features/projects/useProject.ts` or the route page. Check this when FE-CONNECT-1 meets the real API.

## Verified
None (round 1, no fixes to retest).

## Evidence
All requests below are the browser's calls to `/api/v1/projects...`; the stack was app 3711 and mock 3712.

| Check | Command or page | Result |
|---|---|---|
| e2e | `cd frontend && E2E_PORT=3701 MOCK_PORT=3702 npx playwright test e2e/projects.spec.ts` | 24 passed (1.0 min) |
| List, finance_lead (AC1, 4) | `/projects` | h1 "Projects", one request `?limit=20`, 20 rows (phone: 20 cards), "Show more", rows-per-page 10/20/50, closing note "You see projects your roles cover." |
| Show more | click | `?limit=20&cursor=o20`, 24 rows, "All 24 showing" |
| Rows per page | click 10 | `?limit=10`, URL `/projects?limit=10`, 10 rows |
| Search (AC3) | type "lagoon" | URL `/projects?q=lagoon`, request `?limit=20&q=lagoon`, 1 row |
| No results | type "zzz" | "0 shown", "No projects match", "No project you can see matches your search." with Clear search; Clear search restored 20 rows, URL `/projects`. No request had an empty `q`. |
| pm (AC9) | `/projects` | 4 rows. `/projects/P-0102` shows "You can't open this project" with no "Harbour Bank" in the page. |
| finance_lead | `/projects/P-0102` | h1 "Harbour Bank · mobile onboarding" |
| Journey (AC5, 6) | `/projects/P-0101`, finance_lead and pm | 12 `li`s in order. All 11 tag texts appear, including "Stopped: invoice follow-up needed", plus "Verified" twice. |
| Empty journey (AC7) | `/projects/P-0105` | title, Journey tab, "What is next", "The whole journey", "No work on this project yet." Phone has a "← Projects" link. |
| No access (AC8) | `/projects/P-0099` (finance_lead) | tab title "Project · PSL Factory"; the page text has no "P-0099"; "NO ACCESS / You can't open this project / ... not even its name." / "Back to projects"; no tab bar or breadcrumb. |
| Persona none (AC9) | cookie `psl_mock_persona=none`, `/projects` and `/projects/P-0101` | the frame's "No sections are open to your role yet." / "Ask a Lead or Admin to check your roles.", no h1, no projects request, at 1440 and 390. This matches spec line 229 as corrected. |
| Unknown id | `/projects/X-1` | the fallback journey (Lagoon Health), as the spec's Assumptions say |
| Keyboard | Tab from page load on `/projects` | skip link, My work, Projects, Overview, Assistant, Setup, search field, first project link, in a logical order. Focus rings, rows-per-page arrow keys and the failed Show more are covered by the e2e run (tests 23, 24, 16, 17). |
| Errors, 401, 403 (AC10, 11) | e2e tests 2, 7, 21, 22, 17 | passed: list error with Try again, 403 NotOpenState, 401 callout for list and journey, journey 500 then Try again recovers, failed Show more keeps rows. |

## Unproved
- Real backend, grants, tenant isolation, real paging and cursor behaviour. Search matching is a mock title substring only.
- Screen reader behaviour. UX-1-1 (identical link names for lines with the same name) is a UX finding; I did not retest it. I saw that P-0101 has two "Prepare an invoice" lines whose link text differs only by the tag.
- Real-device phone rendering. 390 was a Chromium viewport emulation only.
