DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-49 is part 2 of FE-RFP-INTAKE: **a person logs a received RFP from the Start work drawer** (SCR-23). Part 1 (F-36, SCR-24) is merged (#70) and F-47 is merged (#66), so the RFP document can now be an `evidence` intake field. That is 2 boards (desktop drawer and phone full screen), within D-64.
- Gates are met. FE-RFP-INTAKE has `gate_ids: []` and "Unresolved gates: none" (architecture/packages/v7/delivery.md:1843-1875). SCR-23 is in the 13 Nov client approval (design/review.json:36). D-RFP-INTAKE r1 and D-START-INTAKE r1 are `proposed`, so this runs under the same recorded exception as F-05 and F-36: contract mock only, nothing released.
- The real write is held by two backend answers: G-23-1 (creating a new client) and G-23-5 (the shared fixed intake case, and 409 contention on its revision). Neither is a PSL decision. The page is built on the mock; both are recorded for the backend developer in build.md.
- I did not run `design.py check` (no shell in this role). The spec writer runs it first.

## Scope
**Outcome (one):** a PM or PMO person opens Start work, chooses "Log a received RFP" (Pre-sale), fills in the client, RFP reference, RFP document, received time, submission method and target, deadline state and note, and presses "Log RFP". The document uploads when chosen. The person lands on `/work/<work_id>`, where the RFP shows as Unassigned for F-36's assign panel. Contract mock, 390 and 1440.

**Boards (2):** `design/canvas/project/SCR-23-{desktop,mobile}.dc.html`.

**Task and endpoints:** FE-RFP-INTAKE (R-START), A-START-INTAKE (the logged RFP appears in Unassigned). E-LINES, E-LINE-OPTIONS (client picker), E-EVIDENCE-UPLOAD, E-WORK-START (201 `{work_id, state}`), E-ME `startable_lines`. All are typed in frontend/src/api/schema.d.ts.

**In:**
1. A new `rfp_intake` line (group Pre-sale, `case_scope: fixed`, `start_via: work_start`) in the mock lines, with its record options under `options/`. It is offered only through `startable_lines`.
2. Reuse F-47's `evidence` kind, upload chaining and revision handling in `features/start-work/**`. Do not fork them. Extend the intake only where SCR-23 needs a kind or behaviour F-47 does not have.
3. Deadline: "Unknown", "Stated" and "Not stated" are three separate values (INV-UNKNOWN). Neither Unknown nor Not stated ever becomes a date.
4. Mock-only overlays, each listed in build.md: `show_when` (G-23-2) for "Deadline" and "Submit to", with the fallback of all fields shown and a returned 422 when a stated deadline has no date; the deadline state (G-23-3).

**Held, not drawn as a working control:**
- "New client · they'll be added to the client register" (G-23-1). The picker lists existing clients only. The new-client row appears only if the line returns an `allow_new` overlay, and then only on the mock.
- Any claim that the RFP "has its own case" (G-23-5).

**Out:**
- SCR-24 (F-36, done), the RFP response workspace (F-37), the submission pack (F-38).
- `rfp.submission_plan` (G-23-4, for SCR-40) and the upload size limit (G-23-6).
- Agent work: Tola reading the RFP (G-24-4).
- Backend, OpenAPI, `schema.d.ts` regeneration, `architecture/**`, `src/shell/**`.
- Fixed assets, forecast, payroll drawers (F-51 and later).

**Binding for the spec:**
1. Authority comes from `startable_lines` and the returned line. Nothing is derived from roles. 403 and 404 look the same.
2. Writes send CSRF, the case revision and the start's `idempotency_key`. A 409 re-reads the revision and keeps what was typed. After an uncertain failure the page re-reads first and never resends. A double press starts one work item.
3. The page never checks duplicates (same reference, client or file). Only a backend 409 or 422 is shown, as returned.
4. "Received" is not validated in the browser (backend: not in the future). WAT is sent as the backend specifies. The page invents no time zone rule.
5. The "next" text is shown as returned. It never says an agent has already read the RFP.
6. Tokens and components only, every field labelled, errors announced, 44px targets on the phone (D-92c). One fidelity run per round over the 2 boards, at least 90 or a signed D-83 waiver. Axe at 390 and 1440. Fixture ids W-33xx (reserved for F-36), T-33xx.

## Risk
Medium. It creates a client-bid work item and uploads append-only evidence to a shared fixed intake case, so a wrong revision hits other loggers (G-23-5). But it is a single drawer on F-47's merged upload path, with no money, migration, client sending or release. SURFACES: ui (2 boards), api (E-LINES, E-WORK-START, E-EVIDENCE-UPLOAD), contract-change (the `rfp_intake` line, `show_when`, deadline state and `allow_new` as mock overlays). `security` is not ticked, because F-47's case-scoped upload grant is reused unchanged. PRODUCT-ACCEPTANCE is required, because logging an RFP is a new client flow with new wording.

## Questions
None for PSL. For the backend developer (they hold the real write, not this build):
1. G-23-1: does Start work create a new client in the same transaction, or is there a separate clients write?
2. G-23-5: does E-WORK-START create the RFP's own case, or keep one fixed intake case? If it is fixed, how is the shared revision conflict avoided?
3. Is the RFP reference unique per client, and what does a second logging return (409 or 422)?
