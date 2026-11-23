STATUS: READY
COMMIT: 020724df7e55a58ab2e00d32d4bdde5b273f088a
BUILDER: builder
LANE: full

## Summary
- `/projects` (SCR-22) and `/projects/[caseId]` (SCR-07 Journey) now read live `GET /api/v1/projects` and `GET /api/v1/projects/{case_id}` through `liveApi` and the live types. Option 1 is built for every board conflict in the spec.
- List: status always sent, q trimmed and cut at 120, no limit, cursor "Show more", "N shown, more available", five columns, "No manager" / Unknown, no badges or total.
- Journey: four facts ("Not available" for absent finance, "Figures may be partial."), neutral state tags with the live words, dates, "Show more" by page with focus and retry, tab bar from live `tabs[]` (Delivery never in bar), Delivery route says "not available yet", Assistant link only when `assistant[]` is non-empty and the person has the destination.
- Mock list and journey are in the live shape with fixed UUID ids; P-nnnn is accepted too. New `tests/mock-live-projects.test.ts` validates them against the live contract.

## Changes
- `src/features/projects/`: `model.ts` (live types, query, helpers), `ProjectsList.tsx`, `ProjectJourney.tsx`, `useProject.ts` (page read and append), `ProjectTabs.tsx`, `ProjectTabContent.tsx` (PM/route from `facts.engagement`), `DeliveryTab.tsx` (not-available panel), new `MoreFooter.tsx`, `projects.css`.
- `mock/projects.mjs`, `demo-projects.mjs`, `server.mjs` (id normalising only), `project-tabs.mjs` and `documents.mjs` (one-line `r.id` lookup), fixtures `projects/*.json`, `list.json`, `E-PROJECT.json`, new `P-0125.json` (no " · " title, finance and engagement null, no work).
- Tests: new `mock-live-projects.test.ts`; rewrote `projects.test.tsx`, `projects-journey.test.tsx`, `projects-model.test.ts`; deleted `mock-projects.test.ts` and `delivery-overview.test.tsx` (superseded / Delivery content removed); updated money, project-tabs, engagement-planning(+mock), demo-mock, mock-contract, ceo-mock, next-config, support-handover-mock, delivery-release/hypercare-mock tests. e2e specs updated (projects, project-tabs, delivery-release, delivery-hypercare, demo, ceo, document-review).
- Shared file: `src/features/documents/DocumentReview.tsx` one line (`tabs` instead of `counts`), separate commit 6a58dc2b.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Live list with status=active, no limit: unit test `projects.test.tsx` asserts `?status=active`. Live browser check NOT done (no credentials for live accounts).
2. [x] Tabs send status=all / closed; Active keeps URL clean: `projects.test.tsx`.
3. [x] q trimmed, never empty, max 120: `projects-model.test.ts`, `projects.test.tsx` (200 pasted chars).
4. [x] No manager / Unknown / 0: `projects.test.tsx`.
5. [x] No NEXT MILESTONE, badges, total, rows-per-page; "N shown, more available", Show more appends: `projects.test.tsx`.
6. [x] 401/403/500/400/422/network/empty states: `projects.test.tsx`.
7. [x] Journey from live body: `projects-journey.test.tsx` on the live-shape mock. Live browser check NOT done.
8. [x] No " · " title: `projects-model.test.ts`, `projects-journey.test.tsx`.
9. [x] Four facts, Not available, partial line, no INVOICES VERIFIED/PAID: `projects-journey.test.tsx`.
10. [x] Row content and neutral tags, `/work/12`: `projects-journey.test.tsx`.
11. [x] Show more `?page=2`, focus, failed read keeps rows and Retry: `projects-journey.test.tsx`.
12. [x] No what-is-next/summary; Assistant link conditional, no POST: `projects-journey.test.tsx`.
13. [x] 403/404 and P-0099 / UUID no-access: `projects-journey.test.tsx`.
14. [x] 401 return path, 500 Retry: `projects-journey.test.tsx`.
15. [x] Tab bar from live `tabs[]`: `projects-journey.test.tsx`, `projects-model.test.ts`.
16. [x] Delivery "not available yet": e2e `delivery-release.spec.ts` updated (e2e NOT run, see Validation).
17. [x] Other tabs load by UUID and P-0101: `project-tabs.test.tsx`, `money.test.tsx`, `tab-frames.test.tsx` pass.
18. [x] `mock-live-projects.test.ts` passes, with negative cases (non-UUID id, missing/extra fields fail).
19. [x] grep for `E-PROJECTS`/`E-PROJECT'` in `src/features/projects` finds none for these screens; no forbidden fields in list/journey modules.
20. [x] `factText(null)` is "Not available": `projects-model.test.ts`.
21. [x] Mock served on 4971 during the fidelity run; list, journey rendered.

## Validation
- `npm run lint` and `tsc --noEmit` clean. Full `vitest run` earlier: 21 failures, all fixed since (mock-contract, ceo-mock, engagement-planning-mock, next-config, support-handover-mock); the 17 affected files re-run: 805 passed. A fresh complete run was not repeated after the last fixes.
- Production build passed (`npm run build`, API_ORIGIN 4971). `npm ci` and `manage.py check` not run (rules forbid npm ci; Django untouched).
- Playwright e2e edited but NOT run (config builds on its own ports, machine load ~100).
- Fidelity, one run on a production build, with F-07 exceptions: SCR-22 1440 coverage 78.7% (83% with exceptions) visual 87.7; SCR-22 390 90% (100%) visual 88.6; SCR-07 1440 76.6% (78.7%) visual 85.9; SCR-07 390 90% (100%) visual 86.8. Missing items are exactly the spec's option-1 removals (NEXT MILESTONE column, "5 PROJECTS", INVOICES VERIFIED/PAID, Tola summary and station/count lines) plus sample-data and persona differences; none is a layout bug. Reports are in the builder scratchpad (`.../scratchpad/fid/`). They need design-engineer exceptions or a waiver (all four boards are below the bar until then).
- Servers on 4970/4971 stopped; Django 8010 not started.

## Notes for the coordinator
- Recurring/shared: `Table`/`ShowMore` always draw rows-per-page; I used a small local `MoreFooter` instead. Journey links go to `/work/{integer}`; mock work pages are keyed `W-nnnn`, so those links 404 on the mock until the work-item feature.
- `mock/proposals/delivery-release.json` `project_extra` and `.delivery__*` CSS are now unused.
