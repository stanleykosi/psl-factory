# Setup > Delegation: list the delegations the backend shows and add one from its own lists (contract mock only)

> Tasks: FE-SETUP-DELEGATION (R-SETUP; acceptance A-DELEGATIONS frontend half, with the F-11 Setup and F-20 Templates tests kept green). Architecture: package `architecture/packages/v7`, manifest digest `f6231d20b4fdeabbdca9bde5986a0a7883536f1a5cafc883848ef62dd6d4b624`; FE-SETUP-DELEGATION at `architecture/packages/v7/delivery.md:2835`, `gate_ids: []`, no unresolved gates; E-DELEGATIONS and E-DELEGATION typed in `frontend/src/api/schema.d.ts:799`, `:474`, `:3937`, `:5590` (this feature changes no generated type). Decision consumed: D-DELEGATION-VIEW (`proposed`, under the recorded exception `architecture/sources/decisions-2026-11-15.md` items (g), (i)). Held: guide D05 (`guide/04-DECISIONS.md:49`, open) and D-ADMIN-AUTHORITY (open; gates FE-SETUP-ROLES, not this task). Design: client-approved canvas version 1794581312-b166 (13 Nov 2026); `design.py check --project .` run for this spec on 16 Nov: `EXCEPTION`, `passes: true` (design sha `2859ab21…d82`, D-89 frame-only change). Screens: SCR-13 delegation, 2 artboards: `SCR-13-desktop-delegation`, `SCR-13-mobile-delegation` (`design/canvas/project/`). Model: `delivery/features/F-20/spec.md` (Setup tab, list plus panel), `delivery/features/F-21/spec.md` (shape).

## Conflicts with the boards (for the design engineer, before the build)

"Recommend" is what this spec builds if no answer comes. Items 1 to 4 change what a person sees or can do and need an answer; items 5 to 12 are exceptions to sign.

### Need an answer

1. **The phone board draws "Add delegation" but no form.** `SCR-13-mobile-delegation` ends with a full-width "Add delegation" button; nothing shows what it opens. **Recommend:** the button opens the shared `Drawer` (`frontend/src/components/Drawer.tsx`, a full-height sheet below 720px) titled "Add a delegation", with exactly the desktop panel's fields, hint, note, messages and "Add delegation" button, plus "Cancel"; open on press, as D-98 (2) settled for minutes. Every element in the sheet is a listed difference (category `undrawn phone form`), scored on no board. **Alternative:** the design engineer draws the phone form first (the four-concepts route for undrawn designs); then the phone half of this feature waits and the desktop half builds alone. **Pending the design engineer.**
2. **From is drawn as a dropdown ("Kemi Adebayo · PMO Lead ▾"); v7 has no From.** In v7 E-DELEGATION delegates from the caller only (no `from_person_id`; `additionalProperties: false`), and E-DELEGATIONS returns no From choices. Binding rule 3 forbids a From dropdown the backend has not offered. **Recommend:** From follows `from_options[]` (proposal G-SCR13A-1, mock overlay only): absent → a read-only value "You" (no control); one option → that option as read-only text; two or more → a `Select` with exactly those options and no pre-selection. The default mock sends two options (Kemi Adebayo, Ada Okafor) so the desktop board's dropdown renders; the fidelity driver chooses Kemi. Whether an Admin may delegate on someone else's behalf is a D05/D-ADMIN-AUTHORITY question for PSL, not the frontend's.
3. **To "narrows to people who already hold the same role"; v7 has one unpaired list.** **Recommend:** To shows `delegate_options[]` as returned. When the overlay's `delegate_options[].for_person_id` (G-SCR13A-2) is present, To lists only the options whose `for_person_id` equals the chosen From's `person_id` (an exact match on a backend key, no role logic), is disabled with the reason "Choose who is delegating first." until From is chosen, and clears when From changes. When `for_person_id` is absent, the whole list shows. The frontend never filters by `role`. The hint "Only people who already hold the same role are listed" is the board's text; it states a backend rule the frontend does not check (see item 4).
4. **Two board sentences state authority rules the screen cannot guarantee.** The hint under To and the panel note "Delegating can't give anyone authority they don't already have. Decisions made by the delegate are recorded under their own name." are true only if the backend enforces G-SCR13A-5 and D05's runtime rules, neither of which is built or decided. **Recommend:** show both exactly as drawn (readiness carries them as the board's text), enforce nothing they say, and make their wording a product acceptance check (below). Option B: the backend sends them (`delegate_hint`, `note` on E-DELEGATIONS, a contract proposal) and the screen shows them only when sent. The design engineer or PSL picks; until then Option A.

### Exceptions to sign

5. **Dates is one field on the board ("18 Nov – 25 Nov 2026"); the library has no range picker.** **Recommend:** a fieldset with legend "Dates" holding two `DateField`s, "Starts" and "Ends" (E-DELEGATION sends `starts` and `ends` separately). The single range text is a difference (category `component`).
6. **Authority is not drawn.** v7 E-DELEGATION has optional `authority`, "one of E-DELEGATIONS `authorities[]`". **Recommend:** absent or empty `authorities[]` → no field, `authority` not sent; exactly one → a read-only line "Authority: <label>" and that value sent (the only one the backend offered; nothing chosen by the frontend); two or more → a `Select` labelled "Authority", no pre-selection, required to choose. The default board fixture sends no `authorities[]`, so the board's form is unchanged; the `authority` scenario proves the field. A row's `authority`, when returned, shows as "Authority: <label>" (label from `authorities[]`, else the raw value) under the reason (desktop) and in the card line (phone): extra text, category `no column` (A-DELEGATIONS needs authority shown as returned).
7. **ACTIVE is not drawn.** `status` `scheduled`/`active`/`ended` read "Upcoming"/"Active"/"Ended" in a neutral `Tag` (the boards draw UPCOMING and ENDED in the same neutral grey); the tag's uppercase is the bundle's. Status is never worked out from dates.
8. **Tab badges "Roles 2" and "Rules 8".** Not shown (no read on this page carries them; G-SCR13A-6), as F-20 Templates. Category `frame`.
9. **Frame items.** "Admin · sample", top nav, "+ Start", the phone bar "← Setup" (to `/setup/rules`, `useSetupPhoneBack`) are the shell's and F-11's; exceptions as `delivery/features/F-20/fidelity-exceptions.json`.
10. **View-only person.** With list-level `can_add` false or absent, the desktop panel and the phone button are not drawn (the boards always draw them). Shown only in the `readonly` scenario; not scored.
11. **Outcome text.** After a write, a polite notice ("Delegation added: Kemi Adebayo to Femi Ade, 18–25 Nov 2026.") or a warning (Contract, write outcomes). Not drawn; appears only after a press.
12. **No edit or end controls.** The board draws none; none are built even on rows with `can_change: true` (G-SCR13A-3 has no endpoint). Matches the board.

## Held items (binding; carried from readiness)
- **D05 is open; D-ADMIN-AUTHORITY is open; D-DELEGATION-VIEW is a proposal.** PSL has not named which roles may delegate, who holds Admin, or what absence evidence is needed. The frontend decides none of it.
- **No client-side list of delegable authorities or eligible delegates.** The only sources are the backend's `authorities[]`, `delegate_options[]` and (overlay) `from_options[]`. The frontend ships no list, no default, no free text, no pre-selection, and sends only values from those lists.
- **No effect claimed beyond what the backend returns.** The screen records and lists. It never says or implies that a delegate "can now approve", that tasks moved, or that a delegation is in force, beyond the row's returned `status`. Whether a delegation takes real effect (acting on the delegator's tasks under the delegate's own name, claimed tasks on end, expiry, revocation) is the backend's and D05's.
- **Contract mock only; nothing released.** The backend developer may change or refuse any field. The PR and build.md must not claim a working delegation, enforcement of the authority ceiling, or the self-approval rule.

## Summary
- A person the backend marks able to add (`can_add`) opens Setup > Delegation (`/setup/delegation`) and sees the delegations E-DELEGATIONS returns: from → to, dates, reason, state; desktop table plus "Add a delegation" panel, phone cards plus "Add delegation".
- They add one: From, To and Authority come only from the backend's lists; Dates and Reason are typed; one CSRF-guarded PUT with `expected_revision` as read; the list is re-read and the new row shown.
- 422 messages show beside their field; 409 re-reads and keeps the entries; an unconfirmed write never shows "added" and never allows a blind second add.
- Nothing is derived from `/me` roles or persona; 403 and 404 look the same; view-only people see no add control.
- Mock only, with contract proposals G-SCR13A-1, -2, -4 and list-level `can_add` (plus `expected_revision` 0 and 422 `fields[]`) recorded for the backend developer.

## Context
- Route: `frontend/src/app/setup/delegation/page.tsx` renders `ReservedTab tab="delegation"` today; replace it for this tab only (`ReservedTab.tsx` stays for Roles, Costing rule, Payroll visibility, Staff accounts).
- Frame and shared pieces: `frontend/src/features/setup/SetupFrame.tsx` (`SetupFrame`, `SetupGate`, `RulesReadState` with `what`, `ShowMore` with `noun`, `useSetupPhoneBack`). Pattern to copy: F-20 `TemplatesView.tsx` (desktop `.setup-desktop` and phone `.setup-phone` halves, live region, focus after re-read), `useTemplates.ts` (first page, Show more, refresh), `useTemplateUpload.ts` (one write at a time, outcome kinds, re-read after uncertain), `api.ts` (`uploadTemplateVersion`: keeps 422 `fields[]` as `UploadError`), `SetRulePanel.tsx` (`OutcomeNotice`), `format.ts` (`boardDay`, `lagosToday`), `contract-proposal.ts` (proposal types beside the v7 types).
- Components (D-91, import from `@/components`): `Select`, `DateField`, `TextField`, `Panel`, `Button`, `Callout`, `Tag`, `EmptyState`, `Drawer`, `ValidationSummary`, `VisuallyHidden`, `Unknown`, `PageTitle`. No new local copies of any of them.
- Mock: no delegation handler exists; E-DELEGATIONS and E-DELEGATION answer 501 today (not in `M1_OPERATIONS`, `frontend/mock/server.mjs:42`). Setup mocks to copy: `frontend/mock/templates.mjs` (scenario cookie plus `MOCK_*_SCENARIO` env, because the fidelity tool scopes cookies to the page folder), `frontend/mock/setup.mjs` (`SETUP_DENIED` = `pm`, `none`), overlay schemas in `frontend/mock/proposals/setup.json`. Persona `admin` (`frontend/mock/fixtures/me.admin.json`, "Ada Okafor", destinations include `setup`).
- Tests to copy: `frontend/tests/setup-templates.test.tsx`, `setup-templates-mock.test.ts`, `mock-contract.test.ts`, `frontend/e2e/setup-templates.spec.ts`.
- Backend: none built for delegation. `delivery/backend-handoff/gaps-a-project-setup.md:186-203` lists the SCR-13 delegation gaps.

## Contract

### E-DELEGATIONS `GET /api/v1/setup/delegations` (v7, plus overlay)
Query: `cursor` (from `next_cursor`), `limit` not sent (default 20; the board draws no rows-per-page). Response (v7): `items[]` {`delegation_id`, `from` {name, role?, is_you?}, `delegate` {name, role?, is_you?}, `authority?`, `starts`, `ends?`, `reason?`, `status` scheduled|active|ended, `can_change?`, `revision?`}, `next_cursor?`, `as_of`, `authorities?[]` {value, label}, `delegate_options?[]` {person_id, name, role?}, `revision?` (min 0).

Overlay (proposals, mock only, all optional; the page works without each):
| Field | Proposal | Page use |
|---|---|---|
| `can_add: boolean` (list level) | new from readiness | add panel/button only when `true`; absent = no add control |
| `from_options[]` {person_id, name, role?} | G-SCR13A-1 | Conflicts 2 |
| `delegate_options[].for_person_id` | G-SCR13A-2 | Conflicts 3 |
| `items[].from.person_id`, `items[].delegate.person_id` | G-SCR13A-1 | none (fixtures may carry them) |

Display rules: from → to always (desktop FROM and TO cells "Name · Role"; phone "Name → Name", then a line of `from.role`, dates, reason joined with " · "); a missing `role` or `reason` draws nothing; a missing `ends` draws "Unknown" (amber `Unknown`), never blank, 0 or an open-ended claim; dates in Africa/Lagos as the board writes them ("18–25 Nov 2026" same month, "28 Nov – 03 Dec 2026" across months, "28 Dec 2026 – 03 Jan 2027" across years); status word per Conflicts 7. No count, status or eligibility is computed.

### E-DELEGATION `PUT /api/v1/setup/delegation`
Request (v7): `{expected_revision, delegate, starts, ends, authority?, reason?}`, CSRF header as the other Setup writes. Overlay adds `from_person_id?` (G-SCR13A-1), sent only when From came from `from_options[]` with two or more choices. Values:
- `expected_revision`: the list `revision` from the latest successful read, as read (0 included; v7 says minimum 1, so 0 is a contract proposal and the mock accepts it). No `revision` in the read → no add control.
- `delegate`: a chosen `delegate_options[].person_id`; `authority`: per Conflicts 6; `starts`/`ends`: `YYYY-MM-DD`; `reason`: trimmed, left out when blank (v7 optional; the frontend sets no length cap and no "required").
- No `idempotency_key` (v7 has none and the body is closed).

Client-side checks (format only, before any request): To chosen; Starts and Ends valid dates; Ends on or after Starts ("Ends can't be before Starts."); Authority chosen when the field is a `Select`; From chosen when it is a `Select`. Nothing else (no past-date rule, no role rule, no overlap rule: backend).

Responses and what the page does:
| Status | Page |
|---|---|
| 200 `{revision}` (overlay adds `delegation_id`, G-SCR13A-4) | re-read the first page; notice "Delegation added: <from> to <to>, <dates>." in the polite live region; focus the new row when `delegation_id` is returned and listed, else the table heading; form cleared. Nothing is drawn from the 200 body itself |
| 422 `{code, message, fields?[{name,message}]}` (`fields[]` is a proposal, as F-20) | `message` in a `Callout` at the top of the form; each `fields[].name` in `from_person_id`, `delegate`, `starts`, `ends`, `authority`, `reason` under its control (`aria-invalid`, `aria-describedby`), focus to the first; entries kept; no re-read |
| 409 | re-read; the shared stale sentence "This changed while you were working. The list has been reloaded; check it and add again."; entries kept, `expected_revision` re-based on the new read; no automatic resend |
| 401 | the page becomes `SignedOutState` with `next` = `/setup/delegation` |
| 403, 404 | the backend `message` in a problem notice, list re-read; nothing about a hidden record is shown |
| network, timeout, 5xx (uncertain) | never "added". Warning "We couldn't confirm the delegation. Checking the list…", then re-read once: (a) re-read `revision` equals the one sent → "It was not added. You can add it again." entries kept, Add enabled; (b) `revision` moved → "The list changed while we were checking. Look for your delegation before adding it again." entries kept, Add disabled with that reason, plus "Start again" which clears the form; (c) re-read fails → locked, "Try again" re-reads only (F-20 `unchecked`) |
| Permission, tenant | the backend decides per record and action; the mock refuses `pm` and `none` (403) and a delegate/authority/from not in its lists (422). A wrong-tenant read is 403/404 and shows `NotOpenState` with no names |
| Concurrency | one write at a time (a ref checked synchronously; a double click sends one PUT); the button is busy while sending |

### Screen states
- **Loading:** `RulesReadState` loading. **Error:** `WorkErrorCard` "We couldn’t load the delegations. Your work is safe; nothing was changed." with retry. **401:** signed-out. **403/404:** `NotOpenState` with a visually hidden h1 "Setup" (F-20 pattern).
- **Empty:** `EmptyState` "No delegations to show." / "Delegations you may see will appear here."; the add panel still shows when `can_add`.
- **Default:** both boards. **View-only:** no panel, no button. **Many:** Show more appends; a failed page keeps loaded rows.
- **Add:** the states of the table above. No animation beyond the busy button; respects `prefers-reduced-motion`.

### Mock (`frontend/mock/delegations.mjs`, new)
- Scenario cookie `psl_mock_delegations` (env `MOCK_DELEGATIONS_SCENARIO` sets the run default) = `default` | `empty` | `readonly` | `forbidden` | `many` | `authority` | `single`. Save cookie `psl_mock_delegations_save` = `stale` (409) | `invalid` (422 naming `delegate` and `ends`) | `uncertain` (500, nothing written) | `uncertain_written` (writes, then 500).
- Fixtures `frontend/mock/fixtures/delegations/<scenario>.json`, sample names only:
  - `default`: admin view; Kemi Adebayo · PMO Lead → Femi Ade · PMO Lead, 2026-11-18 to 2026-11-25, "Annual leave", `scheduled`; Ada Okafor · Finance Lead → Chika Obi · Finance Lead, 2026-11-02 to 2026-11-04, "Conference", `ended`; `can_add: true`; `from_options` Kemi and Ada; `delegate_options` Femi (`for_person_id` Kemi) and Chika (`for_person_id` Ada); no `authorities`; `revision: 2`.
  - `empty`: no items, `can_add: true`, `revision: 0`, options as default. `readonly`: default rows, no `can_add`, no options. `many`: 45 rows, `next_cursor` paging at 20, one row without `ends`, one `active`. `authority`: one `from_options` entry, two `authorities`, rows with `authority`. `single`: no `from_options` (From reads "You"), `delegate_options` without `for_person_id`, one `authorities` value.
- Check order (as `templates.mjs`): scenario; CSRF (missing header → 403); persona `pm`/`none` → 403; overlay body schema 422 (unknown property, bad date, empty value); `ends` before `starts` 422; `from_person_id` not in `from_options` 422; `delegate` not in the (paired) `delegate_options` 422; `authority` not in `authorities` (or sent when none offered) 422; `expected_revision` ≠ list revision 409; no `can_add` 403; success appends a row (status from the mock clock 2026-11-16, the only place status is worked out), bumps `revision`, returns `{revision, delegation_id}`. In-memory per persona:scenario; `/__mock/reset` clears it.
- `frontend/mock/server.mjs`: add both operation ids to `M1_OPERATIONS`, route them to `delegations.mjs`, call its reset from `/__mock/reset`. `frontend/mock/proposals/setup.json`: add `delegations_response` and `delegation_body` keys (v7 schema plus the overlay fields; `expected_revision` minimum 0). Existing keys unchanged.

## Lanes
- **Frontend lane (builder)** owns: `frontend/src/features/setup/DelegationView.tsx`, `DelegationForm.tsx` (one form used by the desktop panel and the phone Drawer), `useDelegations.ts`, `useDelegationAdd.ts`; additive edits to `features/setup/api.ts` (`readDelegations`, `addDelegation` keeping 422 `fields[]`), `contract-proposal.ts` (delegation overlay types), `format.ts` (date range text), `setup.css` (additive `setup-deleg*` rules, tokens only); `frontend/src/app/setup/delegation/page.tsx`; the mock files above; tests `frontend/tests/setup-delegation.test.tsx`, `setup-delegation-mock.test.ts`, `mock-contract.test.ts` (new fixtures only), `frontend/e2e/setup-delegation.spec.ts`; factory files `delivery/features/F-27/fidelity-exceptions.json`, `round-<N>/build.md`, `round-<N>/fidelity/**`.
- **Shared, read only:** `SetupFrame.tsx`, `ReservedTab.tsx`, `TemplatesView.tsx`, `RulesView.tsx`, `SetRulePanel.tsx` (import `OutcomeNotice` only), `frontend/src/components/**`, `src/shell/**`, `src/api/**` (including `schema.d.ts`), `src/styles/**`, `frontend/package.json`, the lock file, `playwright.config.ts`, `vitest.config.ts`, existing fixtures, `architecture/**`, `design/**`, `apps/**`, and the protected `delivery/checks.sh`, `delivery/config.json`, `delivery/merge-policy.json`.
- **Backend lane:** none. For build.md, not blocking: E-DELEGATIONS and E-DELEGATION are unimplemented; proposals G-SCR13A-1, -2, -4, list-level `can_add`, `expected_revision` 0 on a first delegation, 422 `fields[]`, optional `delegate_hint`/`note` (Conflicts 4 option B); backend rules to confirm G-SCR13A-5 (authority ceiling, no approving one's own prepared item); open questions (project-scoped delegation; claimed tasks on end); G-SCR13A-3 and -6 not built.
- **Integration owner:** the coordinator. `mock/server.mjs`, `mock/proposals/setup.json` and `features/setup/api.ts` may also be touched by F-25/F-26 running in parallel (D-102): whichever merges second merges the current base and reruns `delivery/checks.sh` and the e2e.
- **Ports:** app 4801, mock 4802 (no other spec uses 48xx). `cd frontend && E2E_PORT=4801 MOCK_PORT=4802 npx playwright test e2e/setup-delegation.spec.ts e2e/setup.spec.ts e2e/setup-templates.spec.ts`, `timezoneId: 'Africa/Lagos'`. Fidelity on a production build (`next build`, `next start -p 4801`, mock on 4802 with `MOCK_DELEGATIONS_SCENARIO=default`). `df` first (stop under 3 GB); delete `frontend/test-results` after. e2e is not in `checks.sh`: paste its output in build.md.
- **Review routing (high risk):** technical (opus), security (opus: authority and identity, CSRF write), UI (opus first review, fidelity gate on 2 boards), UX (sonnet), QA (opus); product acceptance required; first build on Opus (D-64). Not merged without the design engineer's "merge" (D-06).
- **Size:** about 900 to 1,400 lines (two thirds tests and fixtures). One PR.

## Acceptance criteria
Fidelity command (swap `--board`, `--width`, `--out`):
```
node /Users/Hunchoo/software-factory/packages/design/fidelity/fidelity.mjs \
  --playwright <worktree>/frontend/node_modules/playwright/index.mjs \
  --board /Users/Hunchoo/psl-factory/design/canvas/project/SCR-13-desktop-delegation.dc.html \
  --page "http://localhost:4801/setup/delegation" --width 1440 \
  --cookies psl_mock_persona=admin \
  --exceptions /Users/Hunchoo/psl-factory/delivery/features/F-27/fidelity-exceptions.json \
  --wait-ms 500 --out /Users/Hunchoo/psl-factory/delivery/features/F-27/round-<N>/fidelity/SCR-13-desktop-delegation-1440
```
Desktop is reached by a driver (`round-<N>/fidelity/drive-states.mjs`) that resets the mock and, with the real controls, chooses From Kemi Adebayo, To Femi Ade, Dates 2026-11-18 to 2026-11-25, Reason "Annual leave", then freezes (no hand-edited DOM beyond freezing). Phone is the live URL at 390.

### Fidelity
1. **Both boards pass.** `SCR-13-desktop-delegation` at 1440 and `SCR-13-mobile-delegation` at 390: `pass: true`, coverage after exceptions 100, visual ≥ 90 (a D-83-style waiver only if the design engineer signs one). — verify: the commands; `round-<N>/fidelity/scores.txt`.
2. **Exceptions limited.** Each entry in `fidelity-exceptions.json` has `role`, `name`, `category`, `reason`, `approved_by` (`"builder proposal, pending design engineer"` until signed) and maps to a Conflicts number; none covers a value the data supplies (name, role, date, reason, status). One fidelity run per round. — verify: file content; build.md.

### Page behaviour
3. **List from data.** With `default`, desktop shows FROM, TO, DATES, REASON, STATE with "Kemi Adebayo · PMO Lead", "Femi Ade · PMO Lead", "18–25 Nov 2026", "Annual leave", "Upcoming", and the ended row; phone shows "Kemi Adebayo → Femi Ade", "PMO Lead · 18–25 Nov 2026 · Annual leave" and the tag. A row without `ends` shows "Unknown"; a row without `reason` or `role` draws nothing there; status comes only from `status` (a test with a past-dated `scheduled` row still shows "Upcoming"). — verify: `tests/setup-delegation.test.tsx`; page at 1440 and 390.
4. **Add control only on `can_add: true`.** `readonly` (no `can_add`) and a fixture with `can_add: false` show no panel, no button and no disabled placeholder; `default` shows them. The same fixture gives the same controls for personas `admin`, `finance_lead` and `ceo`; nothing reads `me.roles`. — verify: component tests; `grep -n "roles" frontend/src/features/setup/Delegation*.tsx frontend/src/features/setup/useDelegation*.ts` finds no read of `/me` roles.
5. **No list of its own.** From, To and Authority offer exactly the backend's options in its order, none pre-selected; there is no free-text input for a person or authority; a test that edits the DOM to add an option or dispatches a change to an unlisted value results in no PUT (the submit takes values only from the lists). No string naming a role, authority or person appears in `src/features/setup/Delegation*` or `useDelegation*`. — verify: component tests with a recording `fetch`; `grep -nE "PMO Lead|Finance Lead|Admin|Kemi|Femi|Ada|Chika" frontend/src/features/setup/Delegation*.tsx frontend/src/features/setup/useDelegation*.ts` returns nothing.
6. **From follows `from_options`.** `single` shows From as read-only "You" and sends no `from_person_id`; `authority` (one option) shows it as text; `default` (two) shows a `Select` and sends `from_person_id` of the chosen one. — verify: component tests.
7. **To pairing.** In `default`, To is disabled with "Choose who is delegating first." until From is chosen; choosing Kemi lists only Femi, choosing Ada only Chika; changing From clears To. In `single` (no `for_person_id`) To lists every returned option. — verify: component tests.
8. **Authority.** No field and no `authority` in the body for `default`; read-only line and the single value sent for `single`; a required `Select` with no default for `authority`. Rows with `authority` show "Authority: <label>". — verify: component tests.
9. **Write request.** A valid add sends exactly one PUT `/api/v1/setup/delegation` with the CSRF header and a body that validates against the overlay `delegation_body`: `expected_revision` = the read's `revision`, `delegate` = the option's `person_id`, `starts`/`ends` as `YYYY-MM-DD`, `reason` trimmed or absent, no `idempotency_key`, no extra keys. A double click sends one. — verify: component tests; `setup-delegation-mock.test.ts`.
10. **Format checks only.** Missing To, an invalid date, or Ends before Starts shows the message under the field and sends nothing; a past Starts date or any other rule is sent as is. — verify: component tests.
11. **Success re-reads.** On 200 the first page is re-read, the new row appears from the re-read (not from the 200 body), the polite notice reads "Delegation added: …", focus moves to the new row (or the table heading when no `delegation_id`), the form clears. — verify: component test and e2e.
12. **422.** With `psl_mock_delegations_save=invalid`, the top message and the messages under To and Ends show, focus goes to To, entries stay. — verify: component test and e2e.
13. **409.** With `stale`, the list is re-read, the stale sentence shows, entries stay, the next press sends the new `revision`; no automatic resend (fake timers 60 s: one PUT). — verify: component test.
14. **Uncertain write.** `uncertain`: never "added"; after the re-read, "It was not added. You can add it again." and Add enabled. `uncertain_written`: the new row is listed, the "list changed" warning shows, Add is disabled with its reason and only "Start again" re-enables an empty form. A failed re-read locks the form with "Try again" (read only). — verify: component tests; e2e reads the mock state (one row added in `uncertain_written`, none in `uncertain`).
15. **Access.** 401 on read or write → signed-out with `next=/setup/delegation`; persona `pm`/`none` or `forbidden` → the not-open view, no names, no further call; 403/404 on the PUT → the backend message, list re-read; `/me` without `setup` → no delegation call at all. — verify: component tests with a recording `fetch`.
16. **No claimed effect, no agent.** The page contains no text saying a delegate can act, approve or has gained anything, other than the board's note and hint (Conflicts 4); there is no agent, suggestion or generated text. — verify: `grep -niE "can now|now able|has been given|granted" frontend/src/features/setup/Delegation*.tsx` returns nothing; component test of `document.body.textContent` after a success.
17. **Phone add form.** At 390, "Add delegation" opens the Drawer sheet "Add a delegation" with the same fields, messages and outcomes as desktop; Escape and Cancel close it and return focus to the button; after success the sheet closes and the new card is shown. (Pending Conflicts 1.) — verify: e2e at 390.
18. **Paging.** `many`: 20 rows, Show more appends the next 20 then 5 and the end message; a failed page keeps loaded rows with the problem callout. — verify: component test.

### Quality
19. **Accessibility.** No axe violations (`wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22aa`) at 1440 and 390 on default, the open phone sheet, the 422 state, the uncertain warning, empty, readonly and not-open; no sideways scroll at 390; visible focus; 44px targets on phones (D-92c); every field labelled, the Dates fieldset has a legend; errors announced; status words in text, not colour only; no animation under `reducedMotion: 'reduce'`. — verify: `e2e/setup-delegation.spec.ts`.
20. **Tokens and components only.** `git diff` adds no `#hex`, `rgb(`, `hsl(` in `features/setup/*.css`; no local copy of a component that `@/components` exports. — verify: grep on the diff.
21. **Mock matches the contract.** `setup-delegation-mock.test.ts`: every fixture validates against the generated E-DELEGATIONS 200 schema plus the overlay; the check order; CSRF; persona rule; the 422s for an unlisted delegate, authority and from; 409; success bumps `revision`; reset clears. — verify: `cd frontend && npx vitest run tests/setup-delegation*.test.* tests/mock-contract.test.ts`.
22. **Contract not extended.** `git diff --stat` shows no change in `frontend/src/api/**`, `apps/**`, `architecture/**`, `design/**`, protected paths, or existing fixtures; every overlay field is a contract proposal in build.md. — verify: `git diff --stat`; build.md.
23. **Existing behaviour kept.** `tests/setup*.test.*`, `shell.test.tsx`, `tests/components/**`, `e2e/setup.spec.ts`, `e2e/setup-templates.spec.ts` pass with no assertion removed or loosened; the other reserved tabs still render `ReservedTab`. — verify: `delivery/checks.sh`; the e2e command above.
24. **build.md evidence.** Commands and results, both scores, every exception with its Conflicts number, every contract proposal, the held items and the D-DELEGATION-VIEW limits in the PR description. — verify: file content.

### Product acceptance must check
The coordinator runs these on the branch (contract mock, `localhost`), then the design engineer confirms after a demo (as D-100/D-101); D05 items stay with PSL.
- **PA-1:** no add, From, To or Authority control appears unless the response provides it; switching persona with the same fixture changes nothing (criteria 4 to 8).
- **PA-2:** the board's two authority sentences (Conflicts 4) are acceptable to show while the backend does not yet enforce them, or Option B is chosen.
- **PA-3:** nothing on the page claims a delegation takes effect, moves tasks or grants anything; state is the returned status only (criteria 3, 16).
- **PA-4:** an unconfirmed add cannot produce a second delegation by one more press (criterion 14).
- **PA-5:** the phone add sheet (Conflicts 1) and the From/To/Authority behaviour beyond the boards (Conflicts 2, 3, 6).
- **PA-6:** the PR states contract mock only, D05 and D-ADMIN-AUTHORITY open, nothing released.

## Out of scope
- Editing, ending or cancelling a delegation (G-SCR13A-3); any per-row control even when `can_change` is true.
- Roles, Staff accounts, Payroll visibility, Costing rule tabs (FE-SETUP-ROLES gated by D-ADMIN-AUTHORITY); tab badges (G-SCR13A-6); the SCR-13 validation board's combined role-and-delegation save (G-SCR13B-5); the account menu's "Delegate while away".
- Any rule the backend owns: which roles may delegate, same-role eligibility, authority ceiling, self-approval, overlaps, past dates, absence evidence, real effect on tasks and decisions, expiry, revocation.
- Filtering options by role, deriving anything from `/me`, a hard-coded "Admin", default selections, free-text people.
- Idempotency keys, automatic retries, optimistic rows from the 200 body.
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `design/**`, `src/shell/**`, new npm dependencies.

## Assumptions
- From reads "You" when `from_options` is absent. Reason: v7 delegates from the caller; the frontend must not read the name from `/me` or assume a row's `is_you`.
- `for_person_id` pairing is an exact key match, not role logic. Reason: readiness forbids role filtering; the key is the backend's statement of eligibility.
- Default board fixture sends no `authorities[]`. Reason: the board draws no Authority field; a separate scenario proves A-DELEGATIONS' authority path.
- `expected_revision` is the list-level `revision`, and 0 is sent as read. Reason: E-DELEGATION creates, so only the set's revision applies; v7's minimum 1 conflicts with the list's minimum 0 (proposal).
- An unchanged `revision` after an uncertain write means nothing was written. Reason: a successful write bumps the set's revision; when it moved, the page refuses a one-press re-add.
- `ends` absent shows "Unknown". Reason: INV-UNKNOWN; the backend has not said absent means open-ended.
- "Active" uses the same neutral tag as Upcoming and Ended. Reason: the boards draw both drawn states neutral; green is for verified outputs only (D-92b).
- The phone card's role is `from.role`. Reason: the board shows one role and both people hold it in the sample.
- Reason has no client cap and is optional. Reason: v7 sets neither; the backend's 422 decides.
- Outcome and stale sentences are frontend wording, not business rules. Reason: sources are silent; the approver may escalate wording.
- Ports 4801/4802. Reason: assigned range 4800-4809; no other spec uses 48xx.
