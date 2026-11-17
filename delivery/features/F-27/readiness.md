DECISION: READY
RISK: high
SURFACES: ui, api, auth, security, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-27 is the Setup Delegation tab (SCR-13 delegation): 2 boards (desktop and phone), well inside the D-64 cap of about 8. It lists current, scheduled and ended delegations and adds one. One outcome, one PR.
- Gates are met. FE-SETUP-DELEGATION is in architecture v7 with `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:2835-2865). SCR-13 is in the client approval of 13 Nov 2026 (design/review.json, screens list). Its dependencies FE-M3-SETUP (F-11 rules) and FE-CONTRACT-V7 are built and merged; F-20 Templates (PR #34) is the pattern to copy.
- D-ADMIN-AUTHORITY (open, business owner) does NOT gate this task. It gates FE-SETUP-ROLES only (delivery.md:2867-2900; E-PERSON-ROLES, E-INVITE, E-DEACTIVATE). D-DELEGATION-VIEW is `proposed` (architecture/build_model.py:838), not approved. It counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)), the same terms as F-21: contract mock only, the backend developer may change or refuse any field, nothing released. Guide decision D05 (identity delegation, guide/04-DECISIONS.md:49) is `open`. That holds the real runtime transition, not the screen (see Held).
- No approver, authority or delegation rule is invented. The frontend shows what E-DELEGATIONS returns and lets the backend decide who may delegate what to whom. The risk is high because it is authority, so it gets security and technical review and does not merge without the design engineer (D-06).
- I did not run `design.py check` (no shell in this role). The spec writer or builder runs it first and stops if it fails.

## Scope
**Outcome (one):** a person the backend says may manage delegation opens Setup > Delegation (`/setup/delegation`), sees the delegations they may see as the backend returns them, and adds one. On the contract mock only.

**Boards (2):** SCR-13-desktop-delegation and SCR-13-mobile-delegation (design/canvas/project/).
- Desktop: the Setup frame (SETUP eyebrow, "Roles, rules and delegation", the seven-tab bar with Delegation current). A table FROM (name and role), TO (name and role), DATES ("18–25 Nov 2026"), REASON, STATE tag (UPCOMING, ENDED; ACTIVE for `active`). Beside it the "Add a delegation" panel: From, To (hint "Only people who already hold the same role are listed"), Dates, Reason, "Add delegation", and the note "Delegating can't give anyone authority they don't already have. Decisions made by the delegate are recorded under their own name."
- Phone: "← Setup" back link, title "Delegation", one card per delegation ("Kemi Adebayo → Femi Ade", "PMO Lead · 18–25 Nov 2026 · Annual leave", state tag), and a bottom "Add delegation" button. The board draws no phone form. The add form on a phone is a listed difference to settle at spec time (as in D-98 (2)); it opens the shared Drawer/sheet and uses the same fields and messages as desktop.

**Task ID and endpoints:** FE-SETUP-DELEGATION (R-SETUP); acceptance A-DELEGATIONS (frontend half) plus the existing Setup and accessibility tests staying green. E-DELEGATIONS (GET /api/v1/setup/delegations, with cursor and limit) and E-DELEGATION (PUT /api/v1/setup/delegation: expected_revision, delegate, starts, ends, authority, reason). Both already exist in frontend/src/api/schema.d.ts, so v7 as is covers: the table, the status, the delegate_options, the authorities, the 422s and the revision. Items beyond v7 are the contract proposals below.

**Reuse, not rebuild:** `features/setup/SetupFrame.tsx` (frame, SetupGate, RulesReadState, ShowMore, useSetupPhoneBack), the F-20 TemplatesView/useTemplates and TemplateUploadPanel pattern for list plus side panel, the `frontend/src/components/` library (D-91; use Tabs, Tag, Drawer, Callout, form controls, no new local copies), `frontend/mock/setup.mjs` with an overlay in `frontend/mock/proposals/setup.json`, and `contract-proposal.ts` for the proposal types. Replace the `ReservedTab` use in `app/setup/delegation/page.tsx` for this tab only (keep ReservedTab for the other reserved tabs).

**Buildable now on the mock (everything on the 2 boards):**
- The read states: loading, empty ("No delegations to show"), 401, 403/404 (look the same, nothing about hidden records), error with retry, Show more.
- The table and cards from `items[]`; the state tag from `status`; dates and reason as returned; "Unknown" where a value is absent (INV-UNKNOWN), never blank or 0.
- The add form: From, To, Dates, Reason, and Authority if `authorities[]` offers more than one value. Client-side checks are limited to format (a date range with ends on or after starts, required fields). The backend 422 `fields[]` messages show beside the field. Stale `expected_revision` shows the generic 409 (re-read, nothing re-applied), with no auto-retry.
- The write: a CSRF-guarded PUT with `expected_revision` as read; on success re-read the list and show the new row. A failed write leaves the form values in place.
- A per-record view-only mode: no add panel and no add button unless the backend sends authority to change. Today v7 only has per-row `can_change`, so see the proposal for a list-level flag.
- Mock scenarios: default (one scheduled, one ended), empty, readonly, forbidden, stale 409, invalid 422, many (paging), matching the F-11/F-20 scenario cookies.

**Held (and why):** D05 and D-ADMIN-AUTHORITY mean PSL has not named which roles may delegate, who holds Admin, or what absence evidence is needed. The frontend must therefore not decide any of it.
- Which authority types may be delegated, and which roles can be a delegate: only from `authorities[]` and `delegate_options[]`. The frontend ships no list and no default.
- Whether a delegation takes effect for real (the delegate acting under their own name on the delegator's tasks and decisions, claimed tasks on end, expiry and revocation): backend and D05. The screen only records and lists. The note on the board is displayed as the board's text; the frontend enforces nothing it says.
- Real use of any delegation. Nothing is released; the mock accepts and lists.
- Edit and end-early controls. The board draws none. Do not add them (G-SCR13A-3, nice-to-have).

**Out:** the Roles, Staff accounts, Payroll visibility and Costing rule tabs (FE-SETUP-ROLES is gated by D-ADMIN-AUTHORITY, FE-SETUP-TEMPLATES is done); badges on the tab bar from other reads (Templates draws none; F-27 follows it, or shows counts only if the page already has them from a read it makes). Backend, OpenAPI, schema.d.ts regeneration, `architecture/**`, `src/shell/**`. If the boards need something the contract lacks, record it as a contract proposal in build.md and do not extend the contract locally beyond the mock overlay.

## Binding rules for the spec
1. **No authority is invented.** No role, person, approver or "Admin" is hard-coded or derived from `/me` roles. Every control appears only when the response says so (per-row `can_change`, list-level flag if the backend adds one; the `setup` destination gate only opens the tab). Persona or role names never grant a control (INV-ACCESS).
2. **Delegation cannot grant authority the delegator lacks.** The frontend shows only `delegate_options[]` and `authorities[]` the backend returned for the chosen From. It offers no free-text delegate or authority and sends only values from those lists. It must never widen the lists, pre-select an option, or add one locally. The backend enforces the authority ceiling and the "delegate cannot approve what they prepared" rule (G-SCR13A-5), and the UI repeats no rule of its own. A 422 on `authority` or `delegate` is shown as the backend sent it. Tests prove the screen cannot submit a value outside the lists and that it makes no inference from roles.
3. **From is never assumed to be the caller** once the proposal gives `from_options[]`. Until then the From field shows the single person the response names (the caller, with `is_you`), as a read-only value, not a dropdown. If the list has more than one From option, it shows the backend's list and nothing else.
4. **Access per record and action.** Each row's change control follows its own `can_change`. A row from another person or a forbidden row shows no detail beyond what the response returns. 403 and 404 look the same.
5. **Decisions under their own name.** Display rows as from → to; never show the delegate's decisions as the delegator's. Do not claim an effect ("Femi can now approve") the backend did not return. Show state as `status` says. No agent action or generated text: delegation is a human act.
6. **Uncertain or failed writes:** a failed or timed-out PUT does not show "added". Re-read the list before offering a retry, and send `expected_revision` as read. An idempotency key for the PUT is a backend promise not yet built, so the frame sends no key it cannot rely on. If E-DELEGATION returns no `delegation_id`, the new row appears after the list re-read, not from the response.
7. **Honest words.** The page title and tab labels are the boards'. Mock data is labelled as sample as the F-11/F-20 screens do (team builds keep SAMPLE DATA tags off per the 14 Nov decision (c), so no change here). Do not state a real person or approver as policy. Mock names such as Kemi Adebayo, Femi Ade, Ada Okafor and Chika Obi are fixtures only. The design examples supply no live policy.
8. **Tokens and components only.** No hard-coded colour, 44px targets on phones (D-92c), prefers-reduced-motion respected, labels on every field, errors announced, focus order right.
9. **Fidelity (D-64, item (h)):** UI review passes only on the design-fidelity check of both boards with every element present (after approved exceptions) and a score of at least 90, one run per round. Axe at 390 and 1440. Differences (phone add form, left-out controls) go in the exceptions file for the design engineer to sign.

## Contract proposals (for build.md; mock overlay only, for the backend developer to confirm)
From gaps-a-project-setup.md, SCR-13 delegation section. All additive, none invented by the frontend as policy.
- **G-SCR13A-1 (blocking for the From dropdown):** optional `from_person_id` on E-DELEGATION (defaults to the caller; allowed only if the caller can act for them), and `from_options:[{person_id,name,role}]` on E-DELEGATIONS. Until confirmed, the build uses the single From the response names and a read-only field. It must not show a From dropdown the backend has not offered.
- **G-SCR13A-2 (blocking for the To narrowing):** `delegate_options[].for_person_id` (or `GET /setup/delegations/options?from=`) so To narrows when From changes. Until confirmed, show `delegate_options[]` as returned with the board's hint line; do not filter by role in the frontend.
- **G-SCR13A-3:** end or cancel a delegation early (`POST /setup/delegations/{delegation_id}/end` with expected_revision) or confirm rows are append-only. Not drawn; not built (nice-to-have).
- **G-SCR13A-4:** E-DELEGATION returns `{delegation_id, revision}`.
- **G-SCR13A-5:** the backend enforces authority within the delegator's own and refuses a delegate approving their own prepared item (a backend rule to confirm; no UI work).
- **G-SCR13A-6:** `/me` `setup_tabs` or one summary read for the tab counts (Roles 2, Rules 8). Not required here.
- **New from readiness:** a list-level `can_add` (or `can_change` on the list response) so the add panel and button hide for a view-only person. Today only per-row `can_change` exists, which cannot say whether someone with no rows may add. The spec writer records it; until then the mock sends it and the page hides the panel when it is false or absent (absent means no add control, never assume permission).
- Questions already open for the backend developer (not blocking): whether a role can be delegated scoped to a project or only whole roles; whether tasks a delegate claimed return to the owner when a delegation ends.

## Risk
High. The screen sets who may act for whom (identity and authority), and v7's own D-DELEGATION-VIEW is a proposal, D05 is open and no approver is named, so a wrong default or a derived-from-role control would grant authority. That is why every control follows the backend's response, and why SURFACES include auth and security (INV-ACCESS, no self-approval, authority ceiling). It is contained: only two boards, frontend and mock only (frontend/src/features/setup, frontend/mock), no backend and nothing released, so the damage a mistake can do is limited to the mock until the backend developer enforces the rules. PRODUCT-ACCEPTANCE is required: the add form and the authority wording are a business rule PSL must see, and the phone add form and the From and To narrowing go beyond what the boards draw.

## Questions
None. The open items (D05, D-ADMIN-AUTHORITY, D-DELEGATION-VIEW confirmation, the proposals above) are backend or PSL decisions that hold the real transition, not this build.
