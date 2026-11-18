VERDICT: PASS
REVIEWER: reviewer-ux
COMMIT: 159262446042b5ff19fc5de2a8a089bb654b02fb

# UX review, F-30 round 3

Checked the diff 48ba8f7a..3a2884d4 and walked the running app (4833, mock 4832) as the PM persona with a scripted browser at 1440 and 390 width. I did not start, stop or rebuild anything.

## Round-2 findings

- Empty "Post update" (W-2411), desktop and phone Drawer: the keyboard Enter on the submit button moves focus to the first update-type option (a radio). The top summary reads "2 things to fix" with two links (update type, update). Activating a link moves focus to that field's control.
- Empty "Record a reply" (W-2412), desktop and phone Drawer: focus moves to the Reply textarea. The summary reads "1 thing to fix", and its link focuses the textarea.
- Owner picker (W-2413): the options read "PM · Raised it", "Team · recorded by PM" and "Client · recorded by PM · Outside party". The kind word no longer repeats.

## Changed code

- The summary is on for the issue line only, and the other lines draw none. That is as the spec says.
- The summary reuses the shared ValidationSummary. Field links get ids only when the control has none.
- The 403 and 404 e2e cases now check the not-open view, which shows no name and no ISS id.

## Carried forward

Round-2 content is untouched apart from these files. Impact is low and I found nothing new to raise.

No blocking or non-blocking findings.

## Update for head 15926244 (diff 3a2884d4..15926244)
- server.mjs and workspace.mjs: merge added F-29's E-DOCUMENT read (falls through to F-23's rule) and F-28's `.next.<audience>` lookup (falls back to `.next`); F-30's E-WORK-ASSIGN, E-PROJECT-TAB and step/sidecar handling are unchanged, with no duplicate or shadowed branches.
- Sections.tsx and workspace.css: the `ws-table--stack` phone rules apply only to tables with a tag column. F-30's issue fixtures (W-2411 to W-2414) have none, so their tables and timeline are unaffected. The `data-label` attribute and the Unknown receipt fallback only touch F-28 channel items.
- proposals.ts and mock-contract.test.ts: `project_tab` sits beside F-30's overlay keys and the stripping and link schema agree; project-tabs.test.tsx keeps the F-29 Documents cases and F-30's tab-link cases; BACKEND-HANDOFF.md keeps all sections, with no conflict markers. A targeted vitest run of project-tabs and issue-assign-mock passed (38 of 38); the coordinator's checks (2268 tests) and e2e (115 of 115) cover the rest.
- Verdict unchanged.
