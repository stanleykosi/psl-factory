DECISION: NEEDS-INFO
RISK: medium
SURFACES: ui, api, contract-change, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-08 (Document review) is already built on the v7 mock (F-29). F-72 rewires it to live API 1.22.0 `documents_preview` and `documents_decide` on `/projects/{case_id}/document-reviews/{version_id}`.
- The decision write needs no proof file, so the evidence question (short list 1) does not block this screen. That is a good sign for a small PR.
- Two things cannot be built without guessing. First, nothing live tells the page which `version_id` to open from the Documents tab (B-7). Second, `delegated` is a required boolean and nothing says what sets it (B-11).
- Several drawn parts have no live source: agent section notes, "changed since" marks, compare, the per-check list, the returned banner, project title and reference, and the template and test-template tag. These need a keep-or-drop answer from the design engineer.
- I did not run `design.py check` and did not read the architecture package or `design/review.json`. This readiness covers only the connection map, the live contract and the file list. The gates must be confirmed before a spec starts.

## Scope
Outcome: a reviewer opens a document version and reads its title, version number, audience, sections and whether it is the current version. The reviewer then records approve, return or reject through the live decision call. The screen uses the F-56/F-57 live client pattern.

Task: FE-CONNECT-1. Operations in scope: `GET` and `POST /api/v1/projects/{case_id}/document-reviews/{version_id}` (`documents_preview`, `documents_decide`).

Request body for the decision: `expected_revision` (the case revision from the GET), `verdict`, `delegated`, `note`. All four are required, and `note` is 1 to 4000 characters. The response is `{review_id, verdict}`.

In:
- Rewire the reads to `title`, `version` (integer), `revision`, `audience`, `current`, `decisions[]` and `preview[]` (`{field, text}`).
- Show only the verdicts listed in `decisions[]`.
- Handle the 409 stale-revision, 422 `action_unavailable` and 403 states.
- Drop the claim step. It does not exist live.
- Show the integer ids in the route.

Out, unless the owner answers below:
- The `.../publication` operations (revise, request review, publish, retry, cancel). These are new live behaviour that the design does not draw. They are a separate feature.
- A new verdict UI for `reject`, unless `decisions[]` offers it and the design owner approves how it looks.

Held: the drawn parts above that have no live source stay hidden or removed only as the design engineer decides. The builder must not invent replacements. The `django_url` field is not to be used.

Binding rules:
- Keep the note required for every verdict, because the contract requires it. The design may show it as optional for approve, so the owner must confirm.
- Never set `delegated` by guess.

## Risk
Medium. The change is cross-layer: it moves from v7 `/tasks/{id}/decision` to a different live contract, which brings a new verdict (`reject`), a new required field (`delegated`) and an integer version id. It also records a review decision, which affects the document's publication state. It is not high: there is no money, identity or migration, the write is one call, and the case revision protects it against races. The surfaces are ui and api. It is also a contract-change and a product-decision, because the design is dropped or changed in places and `reject` and `delegated` are new rules.

## Questions
1. (B-7, blocks the entry path) How does a person reach `version_id` from the Documents tab? `GET /projects/{case_id}/documents` items give only an evidence `record_id` ("Version 2"). Is that `record_id` the version id, or which field or link is? Backend question.
2. (B-11, blocks the write) What sets `delegated`, and is it `false` for an ordinary reviewer? Backend question. If it is never true for a normal reviewer, say so and we send `false`.
3. (Product owner or design engineer) Approve the live gaps: drop agent section notes, "changed since" marks and Compare, and the per-check Done/Held/Blocked list (live gives only blocking `findings[]` through `publication`). Show the returned banner only as `review_status` text with no person, time or note. Show the crumb from the case title alone, with no reference. Hide the TEST TEMPLATE tag. Is each of these acceptable for this release? (B-8, B-9, B-10)
4. (Product owner) Should the screen offer `reject`, and what should the person see for it? Should approve require a note, as the contract does?
