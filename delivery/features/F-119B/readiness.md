DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- F-119B is the follow-up record for F-119 (same task FE-DELIVERY-CLOSURE, branch fe-delivery-closure-retrospective, worktree lane-d2), per D-208 in delivery/OVERNIGHT-DECISIONS.md.
- Outcome is F-119's closure and retrospective (SCR-33, `/projects/[caseId]/retrospective`) with UX-5-1 fixed.
- It adopts F-119's spec (delivery/features/F-119/spec.md) as binding. No new scope.
- Start head: 9d9b149c0eee33789567d9006229314f1224d6d0 (F-119 round-6/build.md, UX-5-1 fix). D-208 requires the round to start on that head or later.
- F-119's readiness, risk and surfaces carry over unchanged. Nothing in the record has changed the risk.
- F-119's round 1 to 5 reviews, the D-202 fidelity signatures (delivery/features/F-119/fidelity-exceptions.json: 28 exceptions and 2 D-83 waivers) and the round-6 build are evidence for this record and are cited, not re-earned. Nothing merges unreviewed: F-119B runs gate, lenses, QA, PMO and merge as normal.

## Scope
Outcome: a person records the project retrospective as a recorded meeting version and sees its place in the closure checklist, with UX-5-1 (phone focus under the fixed Save bar) fixed.

Task ID: FE-DELIVERY-CLOSURE. Board: SCR-33 (desktop and mobile). Live API 1.24.0. Endpoints and binding rules exactly as F-119's spec.md:
- Reads: `GET /projects/{case_id}`, `GET /projects/{case_id}/delivery/{dossier_id}/closure-checklist`, `GET /projects/{case_id}/meetings?kind=retrospective`, `GET .../meetings/{meeting_id}`, `GET .../meetings/options`.
- Writes: `POST /projects/{case}/meetings` (kind retrospective, append-only versions) and `POST /projects/{case}/actions/create` with `meeting_id` (no separate link call).
- Summary convention D-8 (three headed sections, parse on read, no-heading fallback); D-9 checklist `version_id` shown, never "latest"; no "Save draft"; no per-box "Cites".

Additional fix in scope: UX-5-1, the focused phone control must not sit under the fixed Save bar (F-119 round-6 fix, to be re-verified in this round).

Out of scope: as F-119's spec.md (F-118 closure screen, archive, handover, minutes drafting, F-85 workspace files, DC-4 upload, linking existing actions, change_evidence_id controls).

## Risk
Medium, unchanged from F-119. The screen has several behaviours (versioned save, action creation, checklist link) and a cross-layer contract (revisions, evidence ids, the `summary` convention). It writes internal meeting records only; no money, payroll, external messaging, auth or migrations, and saves append versions. Surfaces are ui (phone layout and focus behaviour, product-visible form change), api (live 1.24.0 operations) and contract-change (three boxes packed into one `summary`). Product acceptance is required for the changed form layout and the hidden draft, as in F-119.

## Questions
None. F-119's spec open questions (decisions rows, "When it was held", notes file source, footnote wording, checklist strip without dossier) were carried into F-119's build and are carried into F-119B under F-119's spec. Any answer recorded in F-119's brief or spec applies here unchanged.
