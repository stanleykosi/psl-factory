DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-33 project retrospective (2 boards, well under the 8-board limit) is one outcome: hold and record the retrospective live through the project meetings.
- Backend answers D-8 and D-9 settle the open data questions; D-185 says to follow them. Architecture (v9) and the 13 Nov design approval (D-173/D-181 exceptions) cover the screen.
- Build starts only after F-85 (lane C, PR #101) is on main. That wait delays the build and does not block readiness. Write the spec against F-85's spec and keep the adapter mapping in this feature folder.
- The three-box layout (went well / did not / lessons) has to be packed into the single live `summary`. That is a visible change from the boards, so the client must see the result.
- Nothing here moves money, touches payroll, sends client messages or changes auth.

## Scope
Outcome: a person records the project retrospective as a recorded meeting version and sees its place in the closure checklist.

Task ID: FE-DELIVERY-CLOSURE. Board: SCR-33.

In scope, using live API 1.24.0:
- Reads:
  - `GET /projects/{case_id}` for the project header.
  - `GET /projects/{case_id}/delivery/{dossier_id}/closure-checklist`, for the `retrospective` check and the strip.
  - `GET /projects/{case_id}/meetings?kind=retrospective`, for saved retrospectives and versions.
  - `GET .../meetings/{meeting_id}`, for `summary`, `participants`, `decisions` and `actions`.
  - `GET .../meetings/options`, for participants, owners and proofs.
- Save: `POST /projects/{case}/meetings` with `kind:"retrospective"`, `revision`, `reference`, `occurred_at`, `purpose`, `summary`, `participant_ids[]`, `decisions[{text, evidence_id, change_evidence_id?}]` and `evidence_id`. Pass `meeting_id` to append a new version. Every save is a recorded version.
- Follow-up action from a lesson: `POST /projects/{case}/actions/create`, then `POST .../meetings/{id}/actions`.
- Use `case_revision` or `revision` as DC-1 describes. Send the exact evidence (the notes file) and a reference on every save, and follow DC-4 for the proof path.

Binding rules:
- D-8: "went well", "did not go well" and "lessons" go inside `summary`, as three headed sections by a fixed convention. Decisions and actions stay separate records. The meeting command saves a record. The minutes-preparation flow is the separate draft path, so this screen has no draft.
- D-9: the closure checklist returns the retrospective link with its exact selected `version_id`. Show that version as the one the checklist used. Do not filter by "latest".
- Hide the "Save draft" control (D-182 rule) and the separate "Cites" per box. Say so in the spec and build notes. Per-decision proof stays, because decisions need `evidence_id`.
- Parse the headed sections back out of `summary` on read. If a saved summary has no recognisable headings, show it whole.
- Do not invent approvers, counts or values. Unknown stays unknown.

Out of scope:
- The closure screen itself (F-118).
- Archive and handover.
- Minutes-preparation drafting.
- Any change to the shared workspace frame (lane C, F-85).

## Risk
Medium. The screen has several behaviours (versioned save, action creation, checklist link) and a cross-layer contract: revisions, evidence ids, and a `summary` convention that decides what the screen shows. It writes internal meeting records only. No money, payroll, external messaging, auth or migrations are involved, and nothing is hard to undo because saves append versions. Surfaces are ui, api and contract-change (the three-box to one-summary packing). Product acceptance is required for the changed form layout and the hidden draft.
