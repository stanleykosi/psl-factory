VERDICT: PASS
COMMIT: 07aca01552f49d7d12a62a81baa077e2b2394cc7
REVIEWER: ux-reviewer
AUTHORITY: UX reviewer

## Summary
- Walked SCR-19 on the shared dev server (Next 4970, mock 4971) at 1440 and 390 as PMO Lead, PM, CEO, Finance Lead and a no-section user, across every mock scenario (ok, baseline, proofreq, inuse, norole, paged, conflict, uncertain, uncertain-saved, reread-fail, forbidden, notfound).
- Journey matches the approved boards apart from the accepted changes (B32 option 1, D-195/D-202): name before recording, "Completed <date time>" only after the re-read, proof radio plus tick gating "Mark complete", D-187 wording present, hold lines in plain words.
- One press (even a double click) sent one POST; 409 kept the choices and asked to check the proof again; 503 showed "Check again" that only re-reads; "Milestone recorded" appeared only after the re-read, and a failed re-read said "saved but couldn't confirm".
- F-71 carry-over verified: the Proof button on the Milestones tab opens on the first press (aria-expanded true) and closes on the second (false). Phone width works; the bottom bar does not hide content.
- Two non-blocking issues on the hold states (below). Screenshots are in the scratchpad ux folder (…/scratchpad/ux/).

## Findings
- UX-1-1 | non-blocking | medium | frontend | When a hold says the milestone can't be completed (norole, name_in_use), the proof radios and the live "Drop a file here or choose a file" upload zone still show with no control to use them, so a person can pick or upload a private file that leads nowhere. Expected: show the hold line only, or read-only proofs and no upload. Actual: seen at 1440 for `norole` and `inuse`. Spec literal for proof_required, but it is a dead-end look. frontend/src/features/projects/MilestoneComplete.tsx
- UX-1-2 | non-blocking | low | frontend | The norole hold reads only "You can’t mark this milestone complete." with no reason or next step. Suggest naming who can ("Ask the PMO Lead"), once LB-2 settles who that is. MilestoneComplete.tsx / milestonesModel.ts HOLD_WORDS

## Notes
- Mock returns can_complete true for every persona (PM, CEO, Finance Lead), so the per-role path cannot be tested here; this is LB-2, which is open and not a UI fault.
- On the Milestones tab the entry links ("Mark complete for Go-live", "for Hypercare") appear only on uncompleted rows; the tab's own hold line was not reachable on the default scenario.
- Keyboard order on the page is natural: breadcrumbs, proof radio, file input, confirmation checkbox. "Mark complete" is a real button, disabled until proof and tick, with a hint line.
- While uncertain, the form shows "Uploads are closed / The completion is being recorded." This is accurate but slightly odd in the uncertain state.

## Verified
- None. Round 1.
