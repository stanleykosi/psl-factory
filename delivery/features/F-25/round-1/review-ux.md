VERDICT: PASS
COMMIT: 4686abdab3e88ab0d1a4a6c8f093f7b389dbae2c
REVIEWER: reviewer-ux
AUTHORITY: delivery UX review

## Summary
- Walked Milestones, Registers (Issues) and Actions as PM on the contract mock at 1440 and 390 (production build, ports 4794/4795): values, order, Unknown, separate facts, links and states match the spec and D-104; no sideways scroll at either width.
- Changed state (psl_mock_milestones=changed) works: CHANGES column added, INVOICE and PAID kept, "₦4,250,000.00 + the change · change amount Unknown", phone "CHANGED · CR-0031" link to the work item. No sum anywhere.
- Paging (P-0102 Issues, Show more) appends; empty tabs (P-0106), no-match with Clear search, no access to a tab (P-0103) and no access to a project (P-0099) all say something useful, with no earlier row text shown.
- Rows link to /work/<id> only when they carry one (invoice refs, change refs, issue and action titles).
- Visual-fidelity waivers (7 of 8 boards under 90) are a design-engineer decision for the UI review, not a UX finding. I did not run axe or keyboard walks myself; I rely on the builder's e2e for those.

## Findings
- UX-1-1 | non-blocking | P-0106 and empty registers, desktop and phone | An empty tab shows a heading ("No actions yet") and then the sentence ("No actions on this project yet."), which says the same thing twice. | Keep one of the two, or make the heading a short title that adds something.
- UX-1-2 | non-blocking | Actions DUE column, desktop and phone | Dates read "04 Nov" with a leading zero; the board draws "4 Nov". | Drop the leading zero in the shared day format for this tab (or confirm it is the app's convention).
- UX-1-3 | non-blocking | Registers, ISS-0221 AGE | A closed issue shows "Unknown" under AGE where the board draws "—". This is the approved Conflicts 11 exception, but a PM may read it as a data fault. | Resolve with the backend "age does not apply" signal when it exists.

## Verified
None (round 1).
