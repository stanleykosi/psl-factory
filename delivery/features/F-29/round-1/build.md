STATUS: READY
COMMIT: 9a6dd8ea67a79b6f699f55bdbe4ed24c873baeeb
BUILDER: builder
LANE: full

## Summary
- New page `/projects/[caseId]/documents/[documentId]?v=<n>` (SCR-08): numbered plain-text sections, changed-section tint with the agent note, Checks panel and Audience, "Your review" with Approve v<n> / Return with note (phone: Return and Approve in a pinned bar, Return opens the Drawer), the returned state, and the "not open to you", read-only and cannot-act states.
- Approve and return reuse `useDecision` (claim once, decide once with `expected_revision`, 409 stale, uncertain effect re-reads and never resends). Approval shows "You approved v2 · name · time. Not sent to the client." only from the re-read chain.
- Documents tab now lists P-0102's documents (`DocumentsTab.tsx`); a row links to the review only with a `work_id`. The `ComingNext` panel is gone (every tab has content).
- Mock only: `mock/documents.mjs` (D-2901 v1/v2, cookie `psl_mock_document` variants), work items W-2901 (+approve/return sidecars) and W-2902, `P-0102.documents.json`, overlay `mock/proposals/document-review.json`. "Ask Tola to draft v3" / "Edit as v3" are disabled with "Not available yet" (no handler).
- "Added during F-29" written in `delivery/BACKEND-HANDOFF.md`.

## Changes
- `frontend/src/features/documents/`: `documentModel.ts` (pure model: check words, note rule, version rule, plain-text paragraphs), `useDocument.ts`, `DocumentReview.tsx` (page, states, review host), `DocumentParts.tsx` (sections, checks, returned banner, agent panel), `ReviewControls.tsx`, `document-review.css`.
- `frontend/src/app/projects/[caseId]/documents/[documentId]/page.tsx`: new route.
- `frontend/src/features/projects/`: `DocumentsTab.tsx` (new), `ProjectTabContent.tsx`, `tabsModel.ts` (documents in `ListTab`, row check), `ProjectJourney.tsx` (ComingNext removed). Narrow edits.
- `frontend/mock/`: `documents.mjs`, `server.mjs` (one dispatch line + import), `project-tabs.mjs` (documents served from fixtures), fixtures and proposal overlay.
- Tests: `document-review-model.test.ts`, `document-review.test.tsx`, `mock-document-review.test.ts`, `e2e/document-review.spec.ts`; updated `project-tabs.test.tsx`, `projects-journey.test.tsx`, `mock-project-tabs.test.ts`, `mock-money.test.ts`, `mock-projects.test.ts` (documents no longer 501).
- `delivery/BACKEND-HANDOFF.md`; `delivery/features/F-29/fidelity-exceptions.json` and `round-1/fidelity/` (main folder).

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Default page: e2e "the default board" (1440) checks crumb "Lagoon Health / Documents / SOW-0198", title, tags, five sections, section 4 tint and Tola note, three checks, audience, both buttons; axe clean.
2. [x] Documents tab: e2e lists 3 rows, only the SOW row links; unit test too.
3. [x] Approve: e2e request log is exactly claim then decision `{expected_revision: 2, verdict: 'approve'}`; green callout text matches from the re-read; no controls; fresh load shows "already been made".
4. [x] Return: empty note shows the announced field error and sends nothing; with note sends `verdict: return` + note and shows the returned state. Note rule unit tested. Caveat: the quote shown after a return in the mock is the fixture's, not the typed text.
5. [x] Returned and returned-hidden variants (e2e, unit).
6. [x] Held buttons disabled, "Not available yet", no POST after a forced click; no `POST /documents` in `frontend/src`.
7. [x] cannot-act (`prepared_by_you`) has no controls (e2e, unit). Controls come only from `you_can_act`.
8. [x] no-review: read-only, no POST, no work read (e2e).
9. [x] amount-unknown reads Unknown (e2e, unit); model test covers all four statuses plus absent.
10. [x] Hostile text shows as characters (unit, e2e).
11. [x] 401/403/404 and persona ceo (e2e); 403/404 identical, no title; another project's document is not shown (unit).
12. [x] 409, 422 and network failure (e2e, unit): no second decision, no "approved", re-read.
13. [x] Failed read shows Try again that re-reads (e2e, unit).
14. [x] v=1 and v=2 own state; missing, "latest", 0, 2x and v=3 are not found (model, unit, e2e).
15. [x] no-sections and empty-sections (e2e, unit).
16. [x] Phone e2e: back link, one amounts tag, flag line, Approve/Return >=44px, drawer note field with error.
17. [x] axe at 1440 (default, returned, cannot-act, approved) and 390 (default, returned, cannot-act): no violations.
18. [ ] Fidelity (see Validation): coverage 100% after exceptions on 3 of 4 boards; one text item in the desktop default had no exception at measure time and an exception for it is now in the file (not re-measured). Visual 69.3 to 73.3, all four below 90: waivers proposed in `fidelity-exceptions.json`, pending the design engineer.
19. [x] checks.sh exit 0; e2e `decide`, `project-tabs`, `minutes` and `document-review` pass (95 + the re-fixed 401 test).

## Validation
- `bash delivery/checks.sh` (under the lock): exit 0 on the pushed head. An earlier run failed on two stale 501 assertions (fixed).
- `E2E_PORT=4851 MOCK_PORT=4850 npx playwright test document-review project-tabs minutes decide`: 95 passed, 1 failed (my 401/403 test applied the scenario cookie to `/me`); fixed to scope the scenario to the document read and the single test re-run: passed.
- Fidelity, production build, 1440 and 390, fonts loaded, one run (cookies persona pm, `psl_mock_document`): SCR-08-desktop 86.4 -> 97.7% coverage with exceptions, visual 73.1; desktop-returned 100%, 73.3; mobile 100%, 69.3; mobile-returned 100%, 73.0. The desktop-default gap was the "Drafted by … Changes since v1 are 2 sections…" sentence (spec Conflicts 5): exception added after the run, not re-run. A last section line-height tweak followed the run and was not re-measured. Reports in `round-1/fidelity/`.
- Judgment calls (not in the spec text): the crumb uses `project_title` "Lagoon Health" although P-0102's own title is "Harmattan Bank · mobile onboarding" (spec says Lagoon Health); "Changes since v1: …" is one sentence from `decision.changes`; `chain.steps[].note` is not read (the mock sends `returned`); a document is shown as not open when its `case_id`, version or id differs from the address; `psl_mock_document=empty-sections` and `hostile` were added.

## Blocked
None.
