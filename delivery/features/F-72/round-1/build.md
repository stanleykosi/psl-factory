STATUS: READY
COMMIT: 71e65c9565280619ffa6cccec8a36b0e71a893b4
BUILDER: builder
LANE: full

## Summary
- `/projects/[caseId]/documents/[documentId]` now reads the live `GET .../document-reviews/{version_id}` and `.../publication` (status word, findings; non-fatal) and records Approve/Return through `POST .../document-reviews/{version_id}`. `[documentId]` is the integer live version id; `?v` is retired; the claim step and the work-item decision hook are gone from this page.
- Write body is exactly `{expected_revision, verdict, delegated:false, note}`. **`delegated: false` is the spec's best reading of B-11 (ordinary reviewer); it is never set any other way. PR must name it.** Note is required for Approve and Return (B8 default, 1 to 4000). Only `approve`/`return` present in `decisions[]` are drawn; no Reject.
- Dropped with no replacement (B7 default): section notes, changed-since marks, Compare, per-check list, who/when/note on returned, crumb reference, TEST TEMPLATE. Added per D-182/D-183 defaults: phone Approve opens the note sheet ("Approve with a note"), desktop label "Note for the PM", blockers list ("Not ready to decide yet", only when findings exist) and a neutral "Not the current version" tag.
- Live-shaped mock for this route (version 2901 = v2, 2900 = v1 not current, 2999 = no access) with 13 scenarios, validated against the live contract by Ajv; v7 `E-DOCUMENT` stays because the work-item document link (`src/features/workspace/Links.tsx`) and minutes tests still use it.
- Documents-tab entry (B-7) held: no tab row can name a version id, so rows are plain text unless a row's own `api_url` is exactly this project's document-review path.

## Changes
- `frontend/src/features/documents/documentModel.ts`: rewritten for the live shape (`isDocument`, `publicationOf`, `isVersionId` 1..9223372036854775807, `verdictsOf`, `noteProblem` 4000, `documentHref`, `reviewHrefOf`).
- `useDocument.ts`: rewritten on `liveApi`; preview + publication in parallel, publication failure -> null; `refresh()` returns whether the re-read worked. Ids are passed as strings so a 19-digit id loses no digit.
- `useReview.ts` (new): the one write; 409 stale, 422 note field / `action_unavailable`, 403, csrf, 5xx/network uncertain, unconfirmed re-read, signed-out; one write at a time; Try again only re-reads.
- `DocumentReview.tsx`, `DocumentParts.tsx`, `ReviewControls.tsx`, `document-review.css`: new page, sections from `preview[]`, audience panel, blockers, notices, controls and phone note sheet for both verdicts.
- `mock/documents.mjs`, `mock/server.mjs`, `mock/fixtures/documents/review-2901.json`, `review-2901.publication.json`: live-shaped mock (cookie `psl_mock_docreview`: return-only, with-reject, blocked, returned, empty-sections, hostile, no-publication, stale, unavailable, note-refused, forbidden, server-error). Only a small block in `server.mjs` before route matching plus the reset call.
- Tests: `tests/document-review.test.tsx` (41), `tests/document-review-model.test.ts`, new `tests/mock-live-document-review.test.ts` (22), `e2e/document-review.spec.ts` (11, rewritten). `tests/next-config.test.ts`: three test files and the fixture added to the existing `django_url` allow-list (the live preview schema requires that field; no `src` file uses it).
- Shared-file commit (own commit 46aba65b): `src/features/projects/DocumentsTab.tsx` row link rule and `tests/project-tabs.test.tsx` (rows no longer link; new test for the `api_url` rule). No `src/api`, `src/shell` or `src/features/workspace` change. Protected paths untouched.

## Fixes
None (round 1).

## Acceptance criteria
1. [x] Live preview by integer id, title, v, audience, numbered plain-text sections: `document-review.test.tsx` asserts the path `/api/v1/projects/P-0101/document-reviews/2901`, `<b>`/`<script>` shown literally, `django_url` not shown; e2e checks the board at 1440.
2. [x] Invalid ids send no request: tests for `abc 0 2.5 02 -1`, 20 digits, 2^63, `2901/x`, space, `2901?v=2` assert no document-review request and the "You can't open this document" text; `isVersionId` unit test; the largest id is sent with every digit; e2e `/documents/abc`.
3. [x] 403 and 404 identical, nothing revealed: unit test compares the full body text for both; e2e compares no-version id and no-access project. Live: see 19.
4. [x] Controls follow `decisions[]`: tests for both, return only, none ("No decision is open to you on this version."), and `reject` (no Reject button).
5. [x] Approve body has the four keys, `delegated === false`, `expected_revision` = GET revision (7), CSRF header sent; no `/tasks` or `/work` request.
6. [x] Note required for both verdicts, checked first, focused; 4001 refused, 4000 sent; phone Approve opens the same sheet (unit + e2e).
7. [x] After 200 the page re-reads both reads and toasts "You approved v2. Not sent to the client." / "You returned v2."; controls gone, status tag shows the new `review_status` (unit + e2e). If the re-read fails: "We couldn't reload to confirm it was recorded" + Try again (re-read only; tested).
8. [x] 409: callout, latest loaded, note kept, second press sends the new revision (9 in unit, 8 in e2e).
9. [x] 422 `action_unavailable`: message shown, controls follow new `decisions[]`, findings listed; 422 on the note field shows on the note and keeps it.
10. [x] 403 on write: "You can't record a decision on this document." plus re-read; `csrf_failed`: refresh wording, nothing recorded, buttons enabled.
11. [x] 5xx and network failure: uncertain notice, both buttons off, one POST, Try again reads only (unit and e2e).
12. [x] Double press and press on the other button while one is in flight: one POST.
13. [x] Publication 500: document, sections and controls show, no status tag, no error.
14. [x] Dropped parts absent (test asserts no TEST TEMPLATE, changed since, Compare, Checks, Held/Blocked, Returned by, flagged, Edit as); `matchingSources` finds no `django_url` in `src/features/documents`.
15. [x] Crumb is `Lagoon Health · patient app / Documents` (no reference); project read failure leaves `Documents`; phone back link reads the project title (e2e 390).
16. [x] `current:false` shows "Not the current version"; `review_status` text shown as sent.
17. [x] Documents-tab link rule: `tests/document-review-model.test.ts` (19 refused forms: other case, other path, `//host`, `https://`, `javascript:`, suffix, query, fragment, dot segments, encoded dots, case, leading space, null, number) and `tests/project-tabs.test.tsx` (render). The live tab was probed: see 19.
18. [x] `npx vitest run tests/mock-live-document-review.test.ts` 22 pass; wrong-field cases (`status`, string version, extra on section, extra on publication) fail the same schema.
19. [ ] HELD (no seeded fixture, backend): against live Django (test client, `force_login`, no password files read, no write): the local database has 0 document versions, so there is no real version to read or return. `live-lead` (2 projects) and `live-none` get the same 404 `{"code":"not_found","message":"This record is unavailable."}` on `/projects/{case}/document-reviews/1`. The live `GET /projects/{case}/documents` answers 404 for both `live-lead` projects, so the question "does any live Documents-tab row carry a matching `api_url`" cannot be answered: the tab is not live yet (v7 tab, rows have no `api_url`), so no row links today and direct URL is the only entry (B-7, backend). No Return was recorded (the lane rules also forbid writes). Needs a seeded status-report version.
20. [x] `e2e/document-review.spec.ts`: 11 pass on a production build, 1440 and 390 (read, return with note, approve with note, stale, blocked, hostile text, older version, no access, uncertain, phone sheet, axe WCAG 2.2 AA).

## Validation
- `npm run lint`: clean. `npm run typecheck`: clean.
- Full `npx vitest run`: 158 files, 3803 tests; first run 3802 passed, 1 failed (`next-config.test.ts`, `django_url` allow-list; fixed in 1209ff65, file re-run 7/7 pass). The other 157 files passed in that run.
- `npx playwright test e2e/document-review.spec.ts` (E2E_PORT 4970, MOCK_PORT 4971, production build): 11 passed.
- `delivery/checks.sh` was not run as written because it runs `npm ci`, which the lane rules forbid; its other steps (Django `check` untouched, lint, typecheck, vitest, `next build` via the e2e run) were run individually.
- Fidelity, ONE run, production build, persona pm, existing `F-29/fidelity-exceptions.json` (no new exceptions written): desktop 1440 coverage 72.7% (86.4% with F-29 exceptions) visual 76.8; mobile 390 79.2% (87.5%) visual 77.2; desktop-returned (scenario `returned`) 60.7% (64.3%) visual 76.9; mobile-returned 27.3% (45.5%) visual 78.5. Not at 100% and visual under 90. The missing items on the two default boards are exactly the D-182/D-183 drops: reference in crumb (SOW-0198, crumb link text), "Drafted by Tola ..." sentence, Compare with v1, TEST TEMPLATE, the agent note, the CHECKS panel, "AMOUNTS MATCH COSTING", the phone flag line, the note label "(needed to return)" (now "Note for the PM"), plus the older F-29 persona/frame items. The returned boards drop the returned banner (person, time, quote) and agent panel, hence the low coverage. Reports: `/private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/fid/`. Proposed: design-engineer exceptions or waiver for these removals (visual 76.8 to 78.5, above the 70 floor; not iterated).
- Servers: mock 4971 and Next 4970 started by PID and stopped (no listener left); no Django server was started (test client only). Worktree clean, pushed, `origin/fe-connect-1-document-review` equals HEAD.

## Notes for the coordinator
- B-11 (`delegated: false`) and B-7 (no tab link to a version id; live tab not served) stay open for backend.
- Status tag tone: live gives no tone, so it is "person" while a decision is open to the reader and neutral otherwise.
- Shared-code finding: `mock/server.mjs`' generic scenario cookie `psl_mock_scenario=403` also fails `/me`, so a 403 no-access check in the browser needs the reserved ids instead (used here). Not changed.
- v7 `E-DOCUMENT` fixtures/tests (`mock-document-review.test.ts`, `D-2901.*.json`) remain for the work-item document link; they can go when that link is connected.

## Update after the 1.24.0 / 1.26.0 merges
- 669d6aea: the preview fixture now carries the 1.24.0 required fields `template_name`, `template_version`, `sample`; no code change was needed (the page ignores them). Merged origin/main (API 1.26.0, no conflicts); head 71e65c9565280619ffa6cccec8a36b0e71a893b4. Pushed with the explicit refspec; worktree clean; no server of mine running.
- F-72 files after the merge: `mock-live-document-review`, `document-review`, `document-review-model`, `next-config` tests 78/78 pass against the 1.26.0 contract. Lint clean.
- Typecheck: fails only in `tests/shell-live.test.tsx:95` (missing `positions`): waiting for the lane A hotfix, which is not in origin/main yet. I did not touch it.
- Full `npx vitest run` (log `.../scratchpad/vitest2.log`): 158 files, 3803 tests, 3758 passed, 45 failed in 10 files, none F-72's: `api-live-schema-drift` (1), `mock-live-me` (8), `mock-live-projects` (13), `mock-contract` (16), `asset-schedule`, `assistant`, `cash-forecast` (2), `demo-mock`, `setup-delegation`, `start-work-prefill` (1 each). The first five are main's fixtures and generated types against 1.26.0; the rest are lane A/C files, not re-run singly. Needs main's fix before the gate can be green.

## Follow-up for 1.24.0/1.26.0 (not built; for a small follow-up feature)
- B-7: `GET /projects/{case}/document-versions` lists readable standalone report versions with links to preview and controls. The Documents tab can reach `version_id` from it. Today only direct URL (and a row's own `api_url`) enters the page.
- B-8: the preview now gives `template_name`, `template_version` and `sample`, so the TEST TEMPLATE tag and template line can come back. F-72 ignores them.
- B-9: a compare read exists for two versions of the same report (changed, added, removed, unchanged sections); weekly report review returns draft-only section notes. Compare and "changed since" can return.
- B-10: `/publication` gives findings and `review_status`; the returner's name, time and reason still need a review-history projection (not available).
- B-11: answer confirms `delegated:false` for an ordinary reviewer; the preview's decision token suffix (ordinary vs delegated) may carry a delegated route, so `decisions[]` entries may need parsing. F-72 keeps `delegated:false`.
