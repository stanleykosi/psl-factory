# A Lead sees every exception they may see on one read-only list at /exceptions

> Tasks: FE-M2B (R-EXCEPTION part only; R-RESPONSE, A-RESPONSE and A-RECONCILE stay open for the later responses feature). Architecture: package v5, manifest digest `a91bc3ce41f97d59afd80bf918b8462d2a5d3eaf3ff7bace23cde79b751e8606` (`architecture/packages/v5/manifest.sha256`). E-EXCEPTIONS is identical in v4 and v5, so the mock and `schema.d.ts` stay on v4 and nothing is regenerated. Design: approved canvas version 1794581312-b166 (`design/review.json`); screens: SCR-10 (default, empty). Artboards: `design/canvas/project/SCR-10-desktop.dc.html` and `SCR-10-mobile.dc.html`. Shared loading, empty and error patterns come from `STATES-desktop.dc.html` and `STATES-mobile.dc.html`.

## Summary
- A new route, `/exceptions`, shows E-EXCEPTIONS rows in the order the API returns them. Each row has a kind tag, "since <time>", the work title linked to `/work/<work_id>`, what is being done and who acts. It has a 10/20/50 rows-per-page choice, a "Show more" control (only when `next_cursor` is present), an "N shown" count (rows loaded, never a total) and an "As of <time>" line in Africa/Lagos time.
- The list is read-only. There are no action buttons; any action happens on the work item. A 401 shows `SignedOutState`. A 403 or 404 shows a "This list is for Leads" view with no row data. A network error or 5xx shows the shared error card with Try again.
- `src/features/exceptions/index.ts` exports `ExceptionsList` (with optional `limit`, `compact`, `maxRows` and `seeAllHref`) and `useExceptions`, so F-08 can embed the list later without editing it.
- The mock handler lives in its own `frontend/mock/exceptions.mjs`. It serves 25 rows across all five kinds, pages them by `limit` and cursor, answers the PM persona 403, and offers an empty scenario. `server.mjs` gains one entry in `M1_OPERATIONS` and one dispatch line.
- The work item's `NextStep` gains one "See all exceptions" link for five exception states.

## Context
- **App frame (F-01):**
  - `frontend/src/app/layout.tsx` wraps every page in `AppShell` (`frontend/src/shell/AppShell.tsx`). `/exceptions` is not one of the `DESTINATIONS` in `frontend/src/shell/destinations.ts`, so no top-bar item is highlighted there. That is the same as `/work/[id]` today, and it stays that way (no shell change).
  - `frontend/src/shell/FrameStates.tsx` exports `LoadingState` and `SignedOutState({pathname})`.
  - `frontend/src/api/errors.ts` maps 401→`unauthenticated`, 403→`forbidden` and 404→`not_found`. Anything else is `server`, and a failed fetch is `network`.
  - `frontend/src/api/client.ts` exports `api` and `call()`.
  - E-EXCEPTIONS is already typed as `operations['E-EXCEPTIONS']` in `frontend/src/api/schema.d.ts` (lines 222 and 1735).
- **Work item (F-03):**
  - `frontend/src/features/work-item/WorkItemStates.tsx` exports `WorkErrorCard({message, error, onRetry})`.
  - `frontend/src/features/work-item/labels.ts` exports `formatWat()`, which gives "12 Nov 16:40" in Africa/Lagos time.
  - `frontend/src/features/work-item/useWorkHistory.ts` is the paging pattern to follow: a request counter drops stale answers, Show more appends, and a Show more failure keeps the loaded rows.
  - `frontend/src/features/work-item/WorkItemHistory.tsx` shows the "Rows per page" select, `psl-showmore` and the "As of" line.
  - `NextStep` is at `frontend/src/features/work-item/WorkItemOverview.tsx:164`.
  - F-03/spec.md:250 names "See all exceptions" as this feature's link target.
- **Mock (`frontend/mock/server.mjs`):**
  - `M1_OPERATIONS` is at line 24. At startup the server reads `fixtures/<operationId>.json` for every M1 operation except E-ME (`createMockServer`), so an M1 operation needs a top-level fixture file.
  - Scenarios (`X-Mock-Scenario` or the `psl_mock_scenario` cookie) are applied before dispatch, for declared statuses only. E-EXCEPTIONS declares 401, 403 and 404.
  - E-WORK-LIST is served by the separate module `frontend/mock/work-list.mjs` through one dispatch line. That is the pattern to copy.
  - Per-id work items are served from `frontend/mock/fixtures/work/W-*.json`. W-1005 ("Kora Logistics · Milestone 1 invoice", INV-0405, `effect_uncertain`) already exists.
- **Tests:**
  - `frontend/tests/mock-contract.test.ts:69-76` expects every M1 operation to answer 200 for every persona, and it validates every `fixtures/work/W-<digits>.json` against E-WORK-ITEM, with `sample: true`.
  - `frontend/tests/mock-row-item-match.test.ts` is the row-versus-item title check to follow.
  - `frontend/e2e/work-item.spec.ts` holds the axe helpers (`expectNoAxeViolations`, the TAGS list and the viewports).
- **Design tokens:** the board's tag colours are exactly `--waiting-tint`/`--waiting-ink` (amber) and `--signal-tint`/`--signal-ink` (red), which are `psl-tag--waiting` and `psl-tag--person` in `frontend/src/styles/psl-bundle.css:209-210`. The page also uses `psl-table`, `psl-tablewrap`, `psl-showmore`, `psl-empty`, `psl-callout` and `psl-btn--text`. `tokens.css` and `psl-bundle.css` are not edited.
- **No route** exists today under `frontend/src/app/exceptions/`.

## Contract

### GET /api/v1/exceptions (E-EXCEPTIONS, read)
- **Request:** `call(api.GET('/api/v1/exceptions', { params: { query: cursor ? { limit, cursor } : { limit } } }))`.
  - `limit` is always one of 10, 20 or 50. The default is 20 (D-PAGING).
  - `cursor` is sent only for Show more, and is always the last `next_cursor` received.
- **200:** `{ items: [{ work_id, what, title, doing, who_acts, since }], next_cursor?, as_of }`.
  - `what` is one of `effect_uncertain | owner_needed | setup_needed | blocked | followup_needed`.
- **Errors:**

  | Response | What the person sees |
  |---|---|
  | 401 (`unauthenticated`) | `SignedOutState`, with `pathname` from `usePathname()` (on the page: `/exceptions`) |
  | 403 (`forbidden`) or 404 (`not_found`) | The no-access view (below). It shows no rows and no counts. |
  | `server` or `network` | `WorkErrorCard`, with "We couldn’t load the exceptions. Your work is safe; nothing was changed." and Try again, which reloads the first page |

- **Show more failure** (any error on a page after the first): the loaded rows stay. A warning callout says "We couldn’t load more exceptions. Choose Show more to try again." A 401 on Show more shows `SignedOutState` instead.
- **Permission and tenant rule:** "Leads; filtered by grants" (handoff.md:4284). The backend filters. The frontend never reads `useMe().roles` or `destinations` to decide whether to fetch or what to show. It shows exactly the rows it is sent, and shows the no-access view on 403 or 404.
- **Idempotency/versioning:** read-only, so safe to retry. Answers to an earlier request (a superseded limit, or Try again) are dropped by a request counter, as in `useWorkHistory`. Changing the limit reloads page 1 and discards the loaded rows.
- **Types:** `frontend/src/features/exceptions/types.ts` derives them, with no edit to `src/api/**`:
  - `ExceptionsPage = operations['E-EXCEPTIONS']['responses'][200]['content']['application/json']`
  - `ExceptionRow = ExceptionsPage['items'][number]`
  - `ExceptionKind = ExceptionRow['what']`
  - `ExceptionsLimit = NonNullable<NonNullable<operations['E-EXCEPTIONS']['parameters']['query']>['limit']>`

### Hook: `useExceptions({ limit?: ExceptionsLimit })`
- Returns `{ state, limit, setLimit, retry, showMore }`. `state` is one of:
  - `{status:'loading'}`
  - `{status:'error', error: ApiError}`
  - `{status:'ready', items, nextCursor?, asOf, more:'idle'|'loading'|'failed'}`
- Show more appends the next page in the order received. It does not de-duplicate, sort or filter.

### Component: `ExceptionsList`
- **Props:**

  | Prop | Type | Default | What it does |
  |---|---|---|---|
  | `limit` | `ExceptionsLimit` | 20 | The page size to request |
  | `compact` | `boolean` | false | Embedded mode, with no page chrome (see below) |
  | `maxRows` | `number` | none | Compact mode only: render only the first n rows received. This truncates the display and does not reorder. |
  | `seeAllHref` | `string` | `'/exceptions'` | Target of the "See all exceptions" link in compact mode |

- It imports nothing from `src/app/exceptions/**`.
- **Full mode** (the `/exceptions` page):
  - A toolbar row with "N shown" (`items.length`, mono) and a "Rows per page" select (10/20/50), styled as in `WorkItemHistory`.
  - The rows.
  - Show more, as a `psl-showmore` bar holding "Showing N" and a "Show more" `psl-btn--text` button, rendered only when `nextCursor` is present. While loading it has `aria-disabled` and `is-busy`.
  - "As of <formatWat(as_of)>".
  - The footer sentence, exactly as on the board: "The factory never resends after an unknown outcome until it has checked for a receipt. Nothing here is lost; each item resumes where it stopped."
- **Compact mode:**
  - The rows, then one link "See all exceptions" to `seeAllHref`.
  - It has no h1, intro, rows-per-page select, Show more, footer sentence or "N shown".
  - The "As of" line is kept as small text.
  - Loading, empty, error, 401 and no-access states render the same as in full mode, inside the component.
- **Rows at 720px and wider:** a `psl-table` inside `psl-tablewrap`, with the visually hidden caption "Exceptions, in the order the factory reports them". The columns are:

  | Column header | Cell content |
  |---|---|
  | WHAT HAPPENED | The kind tag, then "since <t>" in `<time dateTime={since}>` |
  | WORK | A Next.js `Link` with `title` to `/work/${encodeURIComponent(work_id)}` |
  | WHAT’S BEING DONE | `doing` |
  | WHO ACTS | `who_acts` |

- **Rows below 720px:** a `<ul>` of cards, each showing the tag and "since <t>", the title link, `doing`, and "Who acts: <who_acts>".
- **Kind tags:** the text is upper case, as on the boards.

  | `what` | Tag text | Class |
  |---|---|---|
  | `effect_uncertain` | SEND UNCERTAIN | `psl-tag psl-tag--waiting` (amber) |
  | `owner_needed` | OWNER NEEDED | `psl-tag psl-tag--person` (red) |
  | `setup_needed` | SETUP NEEDED | `psl-tag psl-tag--person` |
  | `blocked` | BLOCKED | `psl-tag psl-tag--person` |
  | `followup_needed` | FOLLOW-UP NEEDED | `psl-tag psl-tag--person` |

  The mapping is a `Record<ExceptionKind, …>` in `features/exceptions/labels.ts`, so a new enum value fails the typecheck.
- **"since <t>":** both times are taken in Africa/Lagos.
  - If `since` falls on the same calendar day as `as_of`, show "since HH:mm" (24-hour).
  - Otherwise show "since D Mon" (for example "since 10 Nov").
  - The `time` element's `title` attribute holds `formatWat(since)`.
- **No controls on rows** other than the title link. No reconcile, resume, cancel, record-response, resend or "Ask" buttons appear anywhere.
- **No SAMPLE DATA tag** is drawn per row (the rows have no `sample` field). The frame's existing `NEXT_PUBLIC_SHOW_SAMPLE_LABEL` rule is untouched.

### Page: `frontend/src/app/exceptions/page.tsx`
- `metadata.title` is "All exceptions · PSL Factory". The page renders a client component from `features/exceptions`.
- The header is h1 "All exceptions", with the sub-line: "Everyone’s work that can’t move on by itself, across every line you can see: an outcome we couldn’t confirm, a missing owner or rule, or a check that failed."
- Below the header is `<ExceptionsList />` in full mode.
- The search box, the Filter button, the "4 OPEN" total and the per-row reference from the boards are not drawn (readiness PMO-0-1).

### Screen states (SCR-10)
1. **Loading:** `LoadingState`.
2. **Default:** the rows as above.
3. **Empty** (`items: []`): `psl-empty`, with h2 "No exceptions." (h3 in compact mode) and "Everything is moving or verified." (STATES board, "EMPTY · EXCEPTIONS"). In full mode, "As of" is still shown. There is no Show more and no footer sentence.
4. **Error:** `WorkErrorCard` with the message above and Try again.
5. **Signed out:** `SignedOutState`.
6. **No access (403/404):**
   - `psl-empty`, with h2 "This list is for Leads".
   - The text "Your own exceptions appear in My work, under Needs me."
   - A link "Go to My work" to `/my-work`.
   - The page h1 stays, and no row data, count or `as_of` is shown.

### Work item link (shared touch in F-03's file)
- In `NextStep` (`WorkItemOverview.tsx:164`), after the next-step text, add a Next.js `Link` "See all exceptions" to `/exceptions`. It is rendered only when `item.state` is one of `effect_uncertain`, `awaiting_reconciliation`, `owner_needed`, `setup_needed` or `followup_needed`.
- The change is one import (`Link` is already imported, so possibly none), one constant set and one conditional element. Nothing else in F-03 changes.

### Mock
- **`frontend/mock/exceptions.mjs`** exports `exceptionsList({ url, persona, cookies })` and returns `{ status, body }`. It reads `frontend/mock/fixtures/E-EXCEPTIONS.json` once.

  | Request | Answer |
  |---|---|
  | Persona `pm` (not a Lead) | 403 `{code:'forbidden', message:'Only Leads can see all exceptions.'}` |
  | Persona `none` | 200 `{items: [], as_of}` (the C8 precedent in `work-list.mjs`) |
  | Cookie `psl_mock_exceptions=empty` | 200 `{items: [], as_of}` for any persona allowed to see the list |
  | Otherwise | A page of the fixture's `items` in file order |

  - **`limit`:** 10, 20 or 50. Any other value or no value counts as 20, as for history.
  - **Cursor:** `o:<offset>`. A malformed or out-of-range cursor counts as offset 0.
  - `next_cursor` is `o:<offset+limit>` only while rows remain.
  - Every answer is schema-valid against the 200 or 403 schema.
- **`frontend/mock/fixtures/E-EXCEPTIONS.json`** is the single row source, and it is also the file the server loader requires. It holds `{ as_of, items: [...] }` and is valid as a 200 body.
  - It has 25 rows, newest `since` first, covering all five kinds. At least two rows are `effect_uncertain`, and every other kind has at least one row.
  - Row 1 is `{work_id:'W-1005', what:'effect_uncertain', title:'Kora Logistics · Milestone 1 invoice', …}`, with `doing` that says nothing was resent.
  - The other 24 rows use `W-1501` to `W-1524`, one each.
  - At least one row's `since` is on an earlier Lagos day than `as_of`, to exercise "since D Mon".
  - `fixtures/exceptions/` is not created, because one file is enough.
- **`frontend/mock/fixtures/work/W-1501.json` to `W-1524.json`:**
  - Each is valid against E-WORK-ITEM, with `sample: true`, and has the same `title` as its row.
  - The `state` matches the kind:

    | Row kind | Work item `state` |
    |---|---|
    | `owner_needed` | `owner_needed` |
    | `setup_needed` | `setup_needed` |
    | `followup_needed` | `followup_needed` |
    | `effect_uncertain` | `effect_uncertain` or `awaiting_reconciliation` |
    | `blocked` | `action_needed` |

  - `next_step` is plain business language. They have no tasks you can act on.
- **`frontend/mock/server.mjs`** changes in three places only:
  - one import (`import { exceptionsList } from './exceptions.mjs';`);
  - `'E-EXCEPTIONS'` appended to `M1_OPERATIONS`;
  - one dispatch line after the E-WORK-LIST line: `if (route.operationId === 'E-EXCEPTIONS') { const r = exceptionsList({ url, persona, cookies }); return send(res, r.status, r.body); }`.

  Rebase on whichever of F-05, F-07 or F-08 merges first.
- **`frontend/tests/mock-contract.test.ts`** changes minimally so the generic loop accepts a declared per-persona status. Add `const PERSONA_STATUS: Record<string, Record<string, number>> = { 'E-EXCEPTIONS': { pm: 403 } };`. The loop then expects `PERSONA_STATUS[id]?.[persona] ?? 200` and validates the body against that status's schema. This replaces the literal `200` at lines 72-74. Nothing else in the file changes.

### Fixture examples
```json
{ "as_of": "2026-11-14T10:05:00Z",
  "items": [
    { "work_id": "W-1005", "what": "effect_uncertain", "title": "Kora Logistics · Milestone 1 invoice",
      "doing": "Chidi is checking for a delivery receipt by reference. Nothing resent.", "who_acts": "Chidi · then Finance if not found",
      "since": "2026-11-14T10:02:00Z" },
    { "work_id": "W-1503", "what": "owner_needed", "title": "Lagoon Health · Milestone 4 invoice",
      "doing": "Held at Finance review: no Finance Lead is set up for this project.", "who_acts": "Admin or Finance Lead · Setup",
      "since": "2026-11-10T08:30:00Z" } ] }
```
The first row renders as "SEND UNCERTAIN · since 11:02", because 10:02Z is 11:02 WAT. The second renders as "OWNER NEEDED · since 10 Nov".

## Lanes
- **Frontend lane (owns):**
  - `frontend/src/app/exceptions/**`
  - `frontend/src/features/exceptions/**`: `index.ts`, `ExceptionsList.tsx`, `ExceptionsPage.tsx`, `useExceptions.ts`, `labels.ts`, `types.ts` and `exceptions.css`
  - `frontend/tests/exceptions*.test.ts(x)`
  - `frontend/e2e/exceptions.spec.ts`
- **Mock (frontend lane, owns):**
  - `frontend/mock/exceptions.mjs`
  - `frontend/mock/fixtures/E-EXCEPTIONS.json`
  - `frontend/mock/fixtures/work/W-1501.json` to `W-1524.json`
- **Shared files.** These are additive. Each one is listed in build.md, and the integration owner resolves merge order with F-05, F-07 and F-08.
  - `frontend/mock/server.mjs`: the import, the M1 entry and one dispatch line.
  - `frontend/tests/mock-contract.test.ts`: the `PERSONA_STATUS` map and its use in the generic loop.
  - `frontend/src/features/work-item/WorkItemOverview.tsx`: the `NextStep` link only. F-03's code is otherwise owned by the work-item lane.
- **Backend lane:** nothing. T-EXCEPTIONS (the real endpoint, grant filtering and A-RESUME) is a separate backend task. build.md lists the missing fields (PMO-0-1) for it.
- **Not touched:**
  - `src/api/**`, `src/shell/**`, `src/styles/tokens.css`, `src/styles/psl-bundle.css`
  - `architecture/**`, `openapi.json`
  - `decide/**`, `my-work/**`
  - F-05's, F-07's and F-08's files, and `src/app/overview/**`
  - `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`

## Acceptance criteria
1. **Default list.** As `finance_lead` at 1440x900, `/exceptions` shows:
   - h1 "All exceptions" and the sub-line;
   - a table with the headers WHAT HAPPENED, WORK, WHAT’S BEING DONE and WHO ACTS;
   - 20 rows in fixture order, with the first row tagged "SEND UNCERTAIN" and linked to `/work/W-1005`;
   - "20 shown", "As of …" and the footer sentence.

   — verify: `cd frontend && E2E_PORT=3601 MOCK_PORT=3602 npx playwright test e2e/exceptions.spec.ts`, which asserts these.
2. **Order kept.** The rendered titles equal the fixture `items[].title` order exactly, with no sorting. — verify: the `tests/exceptions.test.tsx` case "keeps the order returned", using a fetch stub that returns rows out of `since` order.
3. **Kind mapping.** Each of the five `what` values renders its tag text and class from the table above. `effect_uncertain` is the only one with `psl-tag--waiting`. — verify: `tests/exceptions.test.tsx` "maps every kind".
4. **Times.** `since` on the same Lagos day as `as_of` reads "since HH:mm" in WAT, and an earlier day reads "since D Mon". "As of" uses `formatWat`. — verify: unit tests with `2026-11-14T10:02:00Z` → "since 11:02" and `2026-11-10T08:30:00Z` → "since 10 Nov".
5. **Paging.**
   - The first request carries `limit=20` and no `cursor`.
   - Choosing 50 in "Rows per page" requests `limit=50` with no cursor and replaces the rows.
   - Show more requests `limit=<current>&cursor=<next_cursor>` and appends.
   - Show more is absent when `next_cursor` is absent.

   — verify: `tests/exceptions.test.tsx` "paging" asserts the request URLs. In e2e, 20 rows plus Show more gives 25 rows, then no Show more.
6. **Show more failure keeps rows.** A 500 on the second page leaves the 20 rows and shows "We couldn’t load more exceptions. Choose Show more to try again." — verify: `tests/exceptions.test.tsx`.
7. **Empty.** `items: []` shows "No exceptions." and "Everything is moving or verified.", with no table, no Show more and no footer sentence. — verify: the unit test, and e2e with cookie `psl_mock_exceptions=empty` at 390 and 1440.
8. **Signed out.** A 401 shows "You’re signed out." with a Sign in link whose `next` is `/exceptions`. — verify: `tests/exceptions.test.tsx`, and e2e with cookie `psl_mock_scenario=401`.
9. **Wrong user.** As persona `pm`, `/exceptions` shows "This list is for Leads" and a "Go to My work" link, with no row titles, no "shown" count and no "As of". — verify: e2e with cookie `psl_mock_persona=pm`, and a unit test with a 403 stub.
10. **Wrong tenant / not visible.** A 404 renders the same no-access view as a 403 and shows no item data. — verify: `tests/exceptions.test.tsx` with a 404 stub, and e2e with `psl_mock_scenario=404`.
11. **Provider failure.** A network error or 503 on the first page shows "ERROR · COULDN’T LOAD", "We couldn’t load the exceptions. Your work is safe; nothing was changed.", "Reference <code> for support." and Try again. Try again issues one new first-page request. — verify: `tests/exceptions.test.tsx`.
12. **No actions.** In every state, the list renders no `button` other than Show more and Try again, and no link other than the title links, "Go to My work", "Sign in" and (in compact mode) "See all exceptions". — verify: a unit test that queries all buttons and links in the default state and asserts the allowed set.
13. **Compact embed.** `<ExceptionsList compact limit={10} maxRows={3} />`:
    - requests `limit=10`;
    - renders exactly 3 rows;
    - has no h1, no rows-per-page select, no Show more and no footer sentence;
    - renders one "See all exceptions" link with `href="/exceptions"`, or with `seeAllHref` when given.

    The 403 and empty states also render inside it. — verify: `tests/exceptions.test.tsx` "compact".
14. **Reusable exports.** `src/features/exceptions/index.ts` exports `ExceptionsList` and `useExceptions`, and nothing in `src/features/exceptions/**` imports from `src/app/**`. — verify: the file content, and `grep -r "@/app\|src/app" frontend/src/features/exceptions` returns nothing.
15. **Phone layout.** At 390x844, `/exceptions` shows the rows as cards (tag, since, title link, doing, "Who acts: …"), with no horizontal scroll (`document.documentElement.scrollWidth <= 390`). The Show more and Try again targets are at least 44px tall. — verify: e2e.
16. **Accessibility (A-ACCESSIBILITY).** axe reports no violations (wcag2a, wcag2aa, wcag21a, wcag21aa and wcag22aa) for:
    - the default, empty and no-access states at 1440x900 and 390x844;
    - the title link and Show more, which show a visible focus outline when tabbed to.

    — verify: `e2e/exceptions.spec.ts`, using the `work-item.spec.ts` helpers.
17. **Mock contract.**
    - E-EXCEPTIONS answers 200 and a schema-valid body for `finance_lead` and `none`, 403 for `pm`, and every declared error through `X-Mock-Scenario`.
    - `limit=10` gives 10 rows and `next_cursor`. Following the cursors gives all 25 rows, once each, in file order, and the last page has no `next_cursor`.
    - `limit=7` counts as 20. `cursor=nonsense` returns the first page.
    - The `psl_mock_exceptions=empty` cookie returns `items: []`.

    — verify: `cd frontend && npx vitest run tests/exceptions-mock.test.ts tests/mock-contract.test.ts`.
18. **Rows match items.** For every row in `E-EXCEPTIONS.json`:
    - `fixtures/work/<work_id>.json` exists;
    - its `title` equals the row's `title`;
    - its `state` matches the kind per the Mock section.

    W-1501 to W-1524 pass the existing schema and `sample: true` check. — verify: the `tests/exceptions-mock.test.ts` "rows match their work items" case, and `mock-contract.test.ts` "every fixture in fixtures/work is schema-valid".
19. **Rows open their item.** Clicking the first row's title on `/exceptions` opens `/work/W-1005`, which shows "Kora Logistics · Milestone 1 invoice". Clicking a W-15xx row opens its own item, not the default fixture. — verify: e2e.
20. **Work item link.**
    - `/work/W-1005` (`effect_uncertain`) shows a "See all exceptions" link to `/exceptions`.
    - `/work/W-1003` (`processing`) and `/work/W-1006` (`verified`) do not.

    — verify: a new case in `tests/exceptions.test.tsx` rendering `NextStep` for each of the 11 states, so that exactly the five listed show the link. In e2e, `/work/W-1005` shows it.
21. **Shared edits stay small.**
    - `git diff <base> -- frontend/mock/server.mjs` shows only the import, the `M1_OPERATIONS` entry and one dispatch line.
    - The `WorkItemOverview.tsx` diff touches only `NextStep` and a constant.
    - The `mock-contract.test.ts` diff is limited to `PERSONA_STATUS` and its use.
    - No file under `src/api/**`, `src/shell/**`, `architecture/**` or `delivery/` (other than this feature folder) changes.

    — verify: `git diff --stat <base>` and the per-file diffs.

## Out of scope
- Recording a response (SCR-16), reconcile, resume and cancel (E-WORK-ACTION), E-RESPONSE and E-EVIDENCE-UPLOAD. Any button for these, on the list or on the work item. These are the later feature, after v6.
- Search, the Filter button and chips (CMP-22), the "N OPEN" total and the per-row reference, which E-EXCEPTIONS does not supply (PMO-0-1). Do not compute a total from loaded rows, and do not show `work_id` as a reference.
- Client-side sorting, grouping or filtering by kind. De-duplicating rows across pages.
- Polling or auto-refresh of the list.
- The Overview page and the placement or mount of the embedded list (F-08 and its follow-up).
- Top-bar highlighting for `/exceptions`, a phone back link ("← Queue" on the board), or any other shell change.
- A SAMPLE DATA tag, or any change to `NEXT_PUBLIC_SHOW_SAMPLE_LABEL`.
- New npm dependencies. Editing `openapi.json`, `schema.d.ts`, `src/api/**`, `src/shell/**`, tokens, bundle CSS or `architecture/**`. Repointing the mock to v5.
- Backend T-EXCEPTIONS, Django or real-API wiring.
- Hiding the work item's "See all exceptions" link by role. The backend answers 403 and the page shows the no-access view.

## Assumptions
- The mock answers PM 403 and `none` an empty 200, because the permission is "Leads" and `work-list.mjs` already gives `none` empty lists (C8). The generic loop in `mock-contract.test.ts` gets a small per-persona status map, because otherwise it cannot accept a Lead-only operation. F-08's E-OVERVIEW can reuse that map.
- The rows go in the top-level `fixtures/E-EXCEPTIONS.json` and not under `fixtures/exceptions/`, because the server loader already requires that file for every M1 operation. One file avoids a duplicate row set.
- The empty scenario uses a `psl_mock_exceptions=empty` cookie, because the existing scenario mechanism carries only error statuses, and persona `none` is blocked by the shell's `NoSectionsState`.
- 403 and 404 share one no-access view with the copy "This list is for Leads". SCR-10 draws no permission state, and INV-ACCESS says not to distinguish them. The copy is the spec writer's.
- The BLOCKED and FOLLOW-UP NEEDED tags use the red family, as readiness item 4 says. The boards draw only SEND UNCERTAIN, OWNER NEEDED and SETUP NEEDED.
- "since" uses one rule: HH:mm on the same Lagos day, otherwise D Mon. The board mixes "since 11:02", "since Mon" and "since 3d" as examples, with no rule given.
- On phones, cards also show since and who acts, though the phone board omits them. Readiness lists every field per row, and these are small text lines.
- `blocked` rows point to work items in `action_needed`, because there is no `blocked` work state. `effect_uncertain` rows may point to `awaiting_reconciliation` items, as both states mean the same exception.
- The `maxRows` prop is added so F-08's planned 3-row preview fits without editing this component. The API's `limit` cannot be 3.
- The table uses a 720px breakpoint, to match the facts-strip breakpoint used in F-03 and F-04.
- `WorkErrorCard` and `formatWat` are imported from `features/work-item` (read-only reuse) and not copied.
