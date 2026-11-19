DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-51 is F-47B, part 2 of FE-M2A-PROOF: **the Start work drawers for fixed assets (`ppe`) and the cash forecast**, 4 boards (`SCR-04-{desktop,mobile}-{ppe,forecast}`). F-47 (#66), F-42 (fixed assets, #68) and F-43 (cash forecast) are merged, so the lines these drawers open exist.
- Gates are met. FE-M2A-PROOF has `gate_ids: []` (architecture/packages/v7/delivery.md:1403-1435). The client approved SCR-04 on 13 Nov. D-START-INTAKE r1 is `proposed`, so this is the same recorded exception as F-47: contract mock only, nothing released.
- The new lines are missing from the mock: `lines.finance_lead.json` has only `invoice`, `schedules` (C-FIN-SCHEDULES) and `ledger_sources` (C-FIN-LEDGER). F-51 adds the two fixed-case lines and their options, and reuses F-47's evidence upload, revision chaining and 409 handling unchanged.
- **Only the fixed-asset drawer has a proof field.** The forecast drawer is Scenario (record), As of (date), Months (integer), Audience (choice) and Sources (a `display` value, "All 3 accepted"). It has no file, so for the forecast the work is the new line and its fields, not an upload. All the kinds it needs are already in `intake.ts` (:12-25).
- Held and out, as already agreed: management accounts and the `money` kind (F-47C, G-SCR04P-1 and -3), and the payroll and business-unit drawers (D-PAYROLL-VISIBILITY, SCR-13 "Who may read inputs", G-SCR04P-5 to -7). I did not run `design.py check` (no shell). The spec writer runs it first.

## Scope
**Outcome (one):** a person with the Finance start right opens Start work, chooses "Fixed assets" and adds the proof file, or chooses "Cash forecast" and sets the scenario, as-of date, number of months and audience. The start lands on `/work/<work_id>`, which is F-42's or F-43's workspace. Contract mock, 390 and 1440.

**Boards (4):** `design/canvas/project/SCR-04-{desktop,mobile}-ppe.dc.html` (Proof; Prior schedule, a record, optional; Accounting note, a choice, optional) and `SCR-04-{desktop,mobile}-forecast.dc.html`.

**Task and endpoints:** FE-M2A-PROOF (R-START), the evidence part of A-START-INTAKE. E-LINES, E-LINE-OPTIONS, E-EVIDENCE-UPLOAD, E-WORK-START and E-ME `startable_lines`. All are typed in frontend/src/api/schema.d.ts.

**Binding for the spec:**
1. Offer only the lines, options and fields the API returns. Derive nothing from roles. The Finance lines go on the Finance persona only (F-47 Conflicts 7).
2. The forecast's "Sources" is `display` text, as returned. The page never counts or sums sources. "All 3 accepted" is not computed.
3. Forecast audience, reviewer and the other forecast rules may be NOT SET in SCR-13 finance rules. Hold the run (`setup_needed`), not the form, and default no value. Check what F-43 shows for a hold and match it.
4. "Months" and "As of" carry no browser rule. The server's 422 is the only error, shown under the field.
5. Proof for fixed assets goes to the line's fixed case, and each upload carries the revision the previous one returned (F-47 spec, items 2 to 4). Evidence is append-only, and removing a chip only stops it being sent.
6. Fixture ids W-44xx (F-47 reserved W-4401 and W-4402), T-44xx. Check for a collision with F-42 and F-43.
7. Reuse F-47's `ProofField`, `useEvidenceUpload` and revision logic. Do not fork. Tokens and components only, 44px targets on the phone, errors announced. One fidelity run per round over the 4 boards, at least 90 or a signed D-83 waiver. Axe at 390 and 1440.

**Out:**
- Management accounts, the `money` kind and E-IMPORT (F-47C).
- The payroll and BU drawers (held).
- The SCR-02 evidence-asked, evidence-supplied and returned states.
- The line workspaces F-42 and F-43.
- Upload size or type rules (backend).
- Backend, OpenAPI, `schema.d.ts`, `architecture/**`, `src/shell/**`.

## Risk
Medium. It reuses F-47's merged upload and start path, and F-47 already got the high-risk review of the proof upload and the revision chain. The new part is two fixed-case lines on that path: the fixed-asset upload is append-only on a shared Finance case, so a stale revision would still hit another logger, and the forecast only starts a run. No money field, payroll or client sending is in this slice. SURFACES: ui, api, contract-change (the two lines and their fields, as the consumer of the proposed D-START-INTAKE). PRODUCT-ACCEPTANCE is required, because both drawers are new to the client.

## Questions
None. The open items belong to later slices: G-SCR04P-1 and -3 (F-47C), and D-PAYROLL-VISIBILITY (PSL, held payroll and BU drawers).
