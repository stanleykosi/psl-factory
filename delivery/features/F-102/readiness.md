DECISION: READY
RISK: medium
SURFACES: ui, api, auth
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none

REVIEWER: readiness

## Summary
- Part 1 only (reads) of the fixed asset (PPE) schedule, SCR-55. Part 2 (reviews, uploads, corrections) is F-102B and depends on this feature merging.
- Part 1 is 6 of F-42's 14 boards, so it fits one reviewable PR. The earlier "about 7" estimate is now an exact list (see Scope).
- Wait: the shared line adapter F-85 (lane C, PR #101) is not yet on main. This delays the build start only, and the coordinator holds the builder. It is not a blocker. Write the spec against `/Users/Hunchoo/psl-factory-main/delivery/features/F-85/spec.md`.
- Data is settled: API 1.24.0 supplies every read. E-23 and E-24 are answered. No client decision is open.
- Risk is medium: it is a cross-layer contract reshape with record-level access on the accounting-note link. It moves no money and posts nothing (`ledger_posted` is read-only).

## Scope
Outcome: a person with access opens `/work/{id}` on line `fixed_assets` (W-3901..W-3912, task FE-CONNECT-1) and sees the live register, the unclear dates and proof, and the depreciation schedule, or a plain held state. They can also start a case. The line adapter mapping lives in this feature's folder. The shared frame in `frontend/src/features/workspace` is not changed. A needed frame change is named as a dependency on lane C.

Boards in part 1 (F-42's 14 boards are 7 states in desktop and phone pairs):
- `SCR-55-desktop-investigating` and `SCR-55-mobile-investigating`
- `SCR-55-desktop-calculating` and `SCR-55-mobile-calculating`
- `SCR-55-desktop-verified` and `SCR-55-mobile-verified`

Boards in part 2 (F-102B, 8 boards): `register-review`, `date-review`, `schedule-review` and `returned`, each in desktop and phone.

Boundary: the register, unclear dates, proof and schedule read panels are built here as read-only components. The part 1 boards show them in their stage context. F-102B adds the review controls on top of the same components and must not rebuild them. Where a part 1 state needs a review state to read correctly (a returned case, say), show the stage and finding text from `assets` as plain read-only text. Draw no controls.

Reads and endpoints:
- `GET /work/{work_id}/assets`: `stage`, `finding`, and the register (entity, provider, currency, period, assets, events, closing controls).
- `schedule` (ready or held, with rows, totals and scope). Held shows its reason. Missing balances show Unknown, never 0.
- Unclear dates and proof states: `date_attachment_ids`, `has_opening_attachment`, `opening_return`, and the date-proof PDF (`GET /work/{work_id}/assets/date-proofs/{fact_id}`) as a view or download.
- `review_options` and `schedule_review_id`: read only. Show who may review what as text, with no actions.
- The accounting-note link (E-24): shown only when the person can read the exact Finance mapping.
- Show `completeness` and `native_source_verified`, which are live data the design does not draw. Place them with the existing register header pattern and flag this for product acceptance.
- Start a case: `POST /work` (`finance-ppe/v1`) from the existing Start work drawer, with the adapter's line definition.

Out of scope for part 1 (F-102B): `POST /projects/{case_id}/asset-registers`, `POST .../dates` (multipart), `POST /work/{id}/assets/opening-proof`, `POST /work/{id}/reviews` (register, basis, schedule), and the basis review (E-23).

Hidden per D-182 and reported as not supplied by the API:
- "Chidi never reads asset values" (no API guarantee).
- The accounting-note text (the API gives only a link).
- The phone short money form.

Rules:
- Unknown money stays unknown, never 0.
- Do not invent approvers, business rules or amounts.
- Per-record access applies. Show no value the API did not return to this person.

## Risk
Medium. The reads are reshaped from the v7 mock sections into `assets`, and the accounting-note link depends on per-record access (auth). Both are contract-sensitive but contained. Part 1 has no review decisions, uploads, money movement, ledger posting or restricted payroll data, so it can merge under D-180/D-184. The one write, `POST /work`, starts an internal case. The higher-scrutiny work (review decisions) sits in F-102B. Product acceptance is required because live-only fields are added and some drawn parts are hidden.
