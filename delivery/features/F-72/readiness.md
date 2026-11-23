DECISION: READY
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-08 Document review is already built and approved on the v7 mock (F-29). F-72 only changes the data source to live API 1.22.0 `documents_preview` and `documents_decide`.
- The coordinator answers (coordinator-answers.md, D-180, delivery/connect/LANES.md) settle the earlier questions as recorded defaults with limits. READY holds only inside those limits.
- The decision write needs no proof file, and the work is one screen and one write call, so it fits one reviewable PR.
- Product acceptance is required. The client confirms or changes the defaults below (batched B7, B8) before the screen counts as accepted.
- Not re-checked in this pass: `design.py check` and the architecture package, which the coordinator covers as for F-56/F-57. The spec writer must confirm FE-CONNECT-1 and the design gates before the build starts.

## Scope
Outcome: a reviewer opens a document version, reads title, version, audience, sections and whether it is current, then records approve or return through the live decision call.

Task: FE-CONNECT-1 (the task id LANES.md prescribes for connecting built screens in this push). Operations: `GET` and `POST /api/v1/projects/{case_id}/document-reviews/{version_id}`.

Decision body, all required: `expected_revision` (from the GET), `verdict`, `delegated`, `note` (1 to 4000 characters). Response: `{review_id, verdict}`.

In:
- Rewire reads to `title`, `version` (integer), `revision`, `audience`, `current`, `decisions[]` and `preview[]` (`{field, text}`).
- Offer only verdicts listed in `decisions[]`; the screen draws approve and return only.
- Note required for every verdict, as the contract requires. This is the B8 default and must be named in the spec and the PR.
- Send `delegated: false` for an ordinary reviewer. This is the best reading of B-11, flagged in the spec and the PR. The builder must not set it any other way.
- Handle 409 stale revision (reload and keep the note), 422 `action_unavailable` and 403.
- Remove the claim step, which does not exist live.
- Drop the parts with no live source (B7 default): agent section notes, "changed since" marks, Compare, the per-check list, the person, time and note on the returned banner (show `review_status` text only), the reference in the crumb (case title only) and the TEST TEMPLATE tag. Do not invent replacements.
- Entry path (B-7): use the best defensible reading of `version_id`. The Documents tab items give only an evidence `record_id`. If no defensible link exists, the spec must say how the page is entered (for example from the work item carrying the document version), flag it, and hold only that entry path, shown disabled with its reason and listed in the PR.

Out:
- `.../publication` operations (revise, request review, publish, retry, cancel), a separate feature.
- A `reject` verdict UI (B8 default: not yet).
- The `django_url` field.

## Risk
Medium. It is a cross-layer contract change from v7 `/tasks/{id}/decision` to the live document-review contract (integer version id, required `delegated`, `reject` verdict in the API), and the write records a review decision that affects the document's publication state. It is not high: no money, identity or migration, one write call, and `expected_revision` guards against races. Surfaces are ui and api, plus contract-change and product-decision, because the dropped parts, the note rule and the `delegated` default are choices the client must accept.
