DECISION: READY
RISK: medium
SURFACES: ui, api, product-decision
PRODUCT-ACCEPTANCE: required
BLOCKING-DECISIONS: none
REVIEWER: readiness

## Summary
- SCR-47 archive (6 boards: default, working, uncertain) connects to live API 1.24.0. It is one outcome and fits one PR.
- The backend has settled the open questions. D-20: files carry a stable group and the exact source kind and ID, so grouping needs no guessing. D-21: an authorised person reserves the archive from the current source IDs, and `required_source_ids` can preselect the list. A go-live alone does not record a completed archive. The design said "no approval step", and the live product now has a person reserve.
- Uncertain delivery (section 10): a person records delivered, not delivered or unknown through `POST /work/{id}/delivery-observations`, with proof and a reason. The `reconcile` action then resolves the original receipt. The archive's own file-level recovery is lookup, then retry only when the lookup says missing.
- D-1: file proofs go through the operation that owns the evidence. The archive recovery call takes no `evidence_id`, so D-1 does not block this screen.
- The build waits on F-85 (lane C, PR #101) merging. This is not a readiness blocker. Write the spec against F-85's spec. The adapter mapping lives in this feature folder, and the shared frame stays untouched.

## Scope
Outcome: the project archive runs live, showing work in progress and an uncertain archive result with its recovery.

Task: FE-DELIVERY-HYPERCARE-ARCHIVE. Screen: SCR-47.

In:
- Reads: `GET /work/{id}/archive-files` (`files[] {id, name, status, group, source kind and ID, job{id, revision, state}, actions[], receipt}`, `verified`, `finding`, `plan_id`, `store`, `sources[]`, `required_source_ids[]`, `can_reserve`, `limited`) and `GET /work/{id}/history` for times.
- Index grouped by the group the API supplies (D-20). Counts come from `files[].job.state`: copying, confirmed, not confirmed (unknown), missing, held. Draw "42 files, each matched" only from `verified`.
- Start the archive: `POST /work/{id}/archive-files` `{expected_revision, case_revision, source_ids[]}` (202). The source list is preselected from `required_source_ids` and shown for the person's review (D-21).
- Uncertain state: per-file `POST .../archive-files/{job_id}/recovery` `{revision, action:"lookup"|"retry"}`. Show retry only when the API lists it in `actions[]`. Add the `reconcile` action (`POST /work/{id}/actions`, 202, no outcome or evidence). Add `POST /work/{id}/delivery-observations` where the work read exposes it and the person has recovery authority.
- Shared handling stays: lock, stale-reload, uncertain state, unknown is not zero, restricted rows.
- Adapter: `delivery-archive/v1` line mapping. Tokens: `expected_revision` plus `case_revision` (DC-1), `revision` on recovery. Allowed actions come from the line read (DC-5).

Out (hide the part and say so in the spec, D-182 rule):
- Tola's step card and notes (DC-3). Show only a one-line status and times.
- The manual "mark each file found or not found" check. The system looks up, and retry follows a missing result.
- The "keep, never purge" storage rule text: the API gives only `store`. Show `store` and `limited`.
- Draft store rules (`POST .../archive-files/rules`) and `POST /work` start. These are Setup, not this screen.
- `POST /work/{id}/corrections` is not part of the three boards unless a board draws it.

## Risk
Medium. The screen reserves an archive and can retry file copies. That is a cross-layer contract with revision tokens and an uncertain-effect recovery path, but it moves no money, identity or client messages. Retry is gated by a prior lookup and by the API's `actions[]`. Surfaces: ui, api, and product-decision (the design's "no approval step" and "mark found or not found" change to a person reserving and a system lookup, which is PSL's decision per D-185). Product acceptance is required because the flow and copy differ from the board. Retries must reconcile before repeating. Never invent attempt counts, file counts or limits.
