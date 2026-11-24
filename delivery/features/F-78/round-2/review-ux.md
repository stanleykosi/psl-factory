VERDICT: CHANGES
COMMIT: ca4abee2fb0b22e6aca06c61e643eba2ae8fb02f
REVIEWER: ux-reviewer
AUTHORITY: UX reviewer

## Summary
- Walked SCR-19 on the shared dev server (Next 4970, mock 4971) at 1440 and 390 as PMO Lead on the mock cases ok, norole, inuse, baseline, proofreq, forbidden, conflict, uncertain, uncertain-saved and reread-fail. Screenshots: /private/tmp/claude-501/-Users-Hunchoo-psl-factory/4e9455a7-949a-43f4-9a55-a544c0864821/scratchpad/ux2/.
- UX-1-1 is fixed: under norole, inuse, baseline and proofreq there are no radios, no upload zone and no Mark complete at either width; only the hold line (and "Open the Milestones tab" for inuse).
- The journey holds: a double click sent one POST; the tick for a file clears on replace; a PNG is refused with no request; 409 keeps the form and the retry records; 503 shows "Check again", which only re-reads; "Milestone recorded" shows only after the re-read; a failed re-read says "saved but couldn't confirm" and Check again then records.
- One new blocking accessibility fault: the "What happens next" panel head is dark navy on blue at 1440 (about 1.7:1).
- LB-2 (live hides the button for every staff role) is recorded, not a finding. The 409 and re-read-fail cases at 390 could not be re-run because the mock's one-shot flags were used at 1440 (not reset, as the shared server is not to be reset); both are the same code as at 1440.

## Findings
- UX-2-1 | blocking | medium | frontend | The "What happens next" panel head is unreadable: the text is rgb(22,56,143) on the rgb(36,89,214) head, a contrast of about 1.7:1 (WCAG needs 4.5:1 for text; the build says it uses the board's white on-strong). Cause: the shared rule `.cmp-panelbox.psl-panel--agent > .psl-panel__head { color: var(--action-ink) }` (components.css:90, three classes) beats `.mscomplete__next > .psl-panel__head { color: var(--on-strong) }` (milestone-complete.css:9, two classes). Expected: white heading text on the blue head, as the board shows. Seen at 1440 on the allowed record (png-1440.png). frontend/src/features/projects/milestone-complete.css:9
- UX-2-2 | non-blocking | low | frontend | A PNG picked for upload shows "PNG files can't be used as proof" with a "Try again" link. The spec wording ("Only a PDF can be attached as proof.") appears only on a server 415, and the client-side refusal uses the picker's own words. Suggest the spec wording for both. frontend/src/features/workspace/EvidencePicker.tsx
- UX-1-2 (carried, non-blocking, LB-2): the norole hold still reads only "You can't mark this milestone complete." The wording waits on LB-2.

## Notes
- Phone layout is flat as the board shows: the milestone name as the heading, the project line, no breadcrumb, a short next line, and the bar clear of the content.
- Mock `proofreq` has no PDF zone because its options set can_attach_pdf false; the spec's PDF-only-under-proof_required case could not be seen in the mock.
- In the uncertain states the form still says "Uploads are closed / The completion is being recorded." (carried from round 1; accurate, slightly odd).

## Verified
- UX-1-1 | verified | norole, inuse, baseline and proofreq at 1440 and 390: radios=0, file input=0, Mark complete=0; only the hold line shows.
- UX-1-2 | reopen | still not changed (waits on LB-2, recorded as non-blocking).
