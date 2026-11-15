DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: not-required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-19 is FE-CLIENTS only: the clients list and the client detail with the billing contact (SCR-35 default and detail, desktop and mobile). That is 4 boards, inside the D-64 cap of about 8. It is one reviewable PR.
- Gates are met. FE-CLIENTS is in architecture v7 with "Unresolved gates: none" (architecture/packages/v7/delivery.md:2450-2480). Dependencies FE-M3-PROJECTS (F-07) and FE-CONTRACT-V7 (F-13) are merged, and `frontend/src/api/schema.d.ts` already types `/api/v1/clients`, `/api/v1/clients/{client_id}` and `/api/v1/clients/{client_id}/billing-contact` (lines 967-1029, operations from line 6590).
- Design is client-approved. SCR-35 is in design/review.json (approved 13 Nov 2026, canvas 1794581312-b166, "good to go"), design/screens.md:80 lists the four artboards, and the four .dc.html boards exist under design/canvas/project/. `design.py check` was not run (my role has no shell). The spec writer or builder runs it first and stops if it fails.
- One soft gate: D-CLIENTS-VIEW (architecture/model.json:1607) is revision 1, `proposed`, with no approval recorded. It counts only under the recorded exception (architecture/sources/decisions-2026-11-15.md items (g) and (i)), the same basis as F-09 and F-17: contract mock only, the backend developer may change or refuse any field, nothing released. The spec must state these limits and the PR must not claim a real backend.
- No clients code exists in `frontend/src` beyond a mention in `features/projects/ProjectsList.tsx` and start-work. T-CLIENTS (the API) is `planned`, so the endpoints are `unimplemented` and the builder adds fixtures and mock handlers.

## Scope
**Outcome (one):** a signed-in person with case.read on at least one of a client's cases sees the client register and can open a client to see the billing contact, its projects and its money, and can set the billing contact, on the contract mock.

**In (binding):**
1. Clients list (SCR-35 default, desktop and mobile) from E-CLIENTS (`GET /api/v1/clients`): name, projects count, owed, "billing contact set", sample label when `sample: true`, `as_of` shown, paging by `next_cursor`. A new route and a link from the existing shell/navigation only where the boards place it.
2. Client detail (SCR-35 detail, desktop and mobile) from E-CLIENT (`GET /api/v1/clients/{client_id}`): `revision`, `billing_contact` (name, email, `set`), `projects` (linking to the existing project journey from F-07), and `money` (invoiced, received, owed).
3. Set the billing contact with E-CLIENT-CONTACT (`PUT .../billing-contact`) with the CSRF header and `expected_revision` taken from the detail `revision` (never guessed). No automatic retry. 409: keep what is shown, reload, show the newer version. 422: map `fields[].name` to the right input. 401, 403 and 404 use the existing ApiError mapping (404 hides records the person may not see).
4. Rules to keep: unknown money shows "Unknown", never 0 or blank (INV-UNKNOWN); the board's "billing contact needed before invoices start" message is shown as copy and nothing is derived or enforced in the frontend; the frontend decides no eligibility and does not derive it from `/me` roles; tokens only, no hard-coded colour.
5. Mock and tests: fixtures including billing contact not set, set, unknown owed, empty list, sample, 409, 422 and a restricted/404 client; mock handlers for the three operations that validate against the schema; unit tests; Playwright with axe at 390 and 1440. Existing projects, work item and shell tests stay green. The design-fidelity gate applies to all four boards (100% of elements after approved exceptions, visual >= 90 at 1440 and 390).

**Spec writer must list up front (board versus contract), for the design engineer before the build:** any board element with no field in the typed schema, for example the board's "readiness" column and "what is blocked" on the detail (design/screens.md:131 names both), versus the schema's `billing_contact_set` and `money`. Do not extend the contract locally: record each gap as a contract proposal in build.md, as F-14 did, or name a fidelity exception for the design engineer to sign.

**Out:**
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, T-CLIENTS, REC-CLIENT.
- Any invoice, receipt, allocation or payment behaviour. The billing contact is a client record field only. Invoice release logic stays with Finance and the backend.
- Project tabs and the project report (FE-M3-PROJECT-TABS, FE-M3-REPORT), and the rest of the project journey beyond linking to it.
- Real sends or any real contact notification. Nothing leaves the mock.

**Size:** one PR (two screens, one write, 4 boards). If the spec exceeds it, split as (a) list and (b) detail with the contact write, in that order.

**Task ID:** FE-CLIENTS (R-PROJECT). **Endpoints:** E-CLIENTS, E-CLIENT, E-CLIENT-CONTACT, all on the contract mock. **Acceptance:** A-CLIENTS (frontend half). **Decision consumed:** D-CLIENTS-VIEW (proposal, under the recorded exception).

**Backend items to record (not blocking):** E-CLIENTS, E-CLIENT and E-CLIENT-CONTACT are `unimplemented`; where client records live (REC-CLIENT) and who holds "client contact authority" (the schema says "as the backend allows") are for the backend developer. Revision conflict handling is verified only on the mock.

## Risk
Medium. It is a cross-layer contract the backend developer has not yet confirmed (D-CLIENTS-VIEW proposed, architecture/model.json:1607) and it includes one write (the billing contact, which gates later invoicing) plus a money display where unknown must never read as zero. It is not high because it is mock-only, the write is a single contained field with revision control, no invoice, payment or migration logic runs, and nothing is released. SURFACES: `ui`, `api` (new endpoints consumed) and `contract-change` (a still-proposed v7 contract). `payments` is not listed because only displayed money is in scope. PRODUCT-ACCEPTANCE is not-required: it conforms to client-approved boards and adds no new business rule, with the board-versus-contract gaps handled as above.

## Questions
None.
